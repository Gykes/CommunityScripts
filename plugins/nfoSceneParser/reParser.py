import os
import re
import json
import log


class RegExParser:

    def __init__(self, scene_path):
        self._scene_path = scene_path
        self._re_config_file = self.__find_re_config(os.path.dirname(scene_path))

    def __find_re_config(self, dir):
        parent_dir = os.path.dirname(dir)
        re_config_file = os.path.join(dir, "nfoSceneParser.json")
        if os.path.exists(re_config_file):
            # Found => load yaml config
            try:
                with open(re_config_file, 'r') as f:
                    config = json.load(f)
                self._regex = config["regex"]
                self._performers_splitter = config.get("performers_splitter")
                self._tags_splitter = config.get("tags_splitter")
                return re_config_file
            except Exception as e:
                log.LogInfo("Could not load regex config file '{}': {}".format(re_config_file, e))
                return
        elif dir != parent_dir:
            # Not found => look in parent
            return self.__find_re_config(parent_dir)
        log.LogDebug("No re config found for {}".format(self._scene_path))

    def parse(self, defaults = {}):
        if self._re_config_file is None:
            return
        if defaults is None:
            defaults = {}
        match = re.match(self._regex, self._scene_path).groupdict()
        file_actors = []
        if match.get("performers"):
            if self._performers_splitter is not None:
                file_actors = match.get("performers").split(self._performers_splitter)
            else:
                file_actors = [match.get("performers")]
        file_tags = []
        if match.get("tags"):
            if self._performers_splitter is not None:
                file_actors = match.get("tags").split(self._tags_splitter)
            else:
                file_actors = [match.get("tags")]
        file_data = {
            "file": self._re_config_file,
            "source": "re",
            "title": match.get("title"),
            "director": match.get("director") or defaults.get("director"),
            "details": defaults.get("details"),
            "studio": match.get("studio") or defaults.get("studio"),
            "movie": match.get("movie") or defaults.get("title"),
            "scene_index": match.get("index") or defaults.get("scene_index"),
            "date": match.get("date") or defaults.get("date"),
            "actors": file_actors or defaults.get("tags"),
            # tags are merged with defaults
            "tags": list(set(file_tags + (defaults.get("tags") or []))), 
            "rating": match.get("rating") or defaults.get("rating"),
            "cover_image": None,
            "other_image": None,
            "url": None,
        }
        return file_data
