import os
import re
import json
from datetime import datetime
import log


class RegExParser:
    ''' Parse filenames (with regex) '''

    def __init__(self, scene_path):
        self._scene_path = scene_path
        self._re_config_file = self.__find_re_config(
            os.path.dirname(scene_path))
        self._groups = {}

    def __find_re_config(self, path):
        parent_dir = os.path.dirname(path)
        re_config_file = os.path.join(path, "nfoSceneParser.json")
        if os.path.exists(re_config_file):
            # Found => load yaml config
            try:
                with open(re_config_file, 'r') as f:
                    config = json.load(f)
                self._regex = config["regex"]
                self._splitter = config.get("splitter")
                self._scope = config.get("scope")
                # Scope defaults to the full path. Change to filename if so configured
                if self._scope is not None and self._scope.lower() == "filename":
                    self._name = os.path.split(self._scene_path)[1]
                else:
                    self._name = self._scene_path
                log.LogDebug(
                    "Using regex config file {}".format(re_config_file))
                return re_config_file
            except Exception as e:
                log.LogInfo("Could not load regex config file '{}': {}".format(
                    re_config_file, e))
                return
        elif path != parent_dir:
            # Not found => look in parent
            return self.__find_re_config(parent_dir)
        log.LogDebug("No re config found for {}".format(self._scene_path))

    def __format_date(self, re_findall, date_format):
        date_text = "-".join(re_findall[0] if re_findall else ())
        date = datetime.strptime(date_text, date_format) if date_text else None
        return date.isoformat()[:10] if date else None

    def __find_date(self, text):
        if not text:
            return
        # For proper boundary detection in regex, switch _ to -
        safe_text = text.replace("_", "-")
        # Finds dates in various formats
        re_yyyymmdd = re.findall(
            r"(\b(?:19|20)\d\d)[- /.](\b1[012]|0[1-9])[- /.](\b3[01]|[12]\d|0[1-9])", safe_text)
        re_ddmmyyyy = re.findall(
            r"(\b3[01]|[12]\d|0[1-9])[- /.](\b1[012]|0[1-9])[- /.](\b(?:19|20)\d\d)", safe_text)
        re_yymmdd = re.findall(
            r"(\b\d\d)[- /.](\b1[012]|0[1-9])[- /.](\b3[01]|[12]\d|0[1-9])", safe_text)
        re_ddmmyy = re.findall(
            r"(\b3[01]|[12]\d|0[1-9])[- /.](\b1[012]|0[1-9])[- /.](\b\d\d)", safe_text)
        re_yyyymm = re.findall(
            r"\b((?:19|20)\d\d)[- /.](\b1[012]|0[1-9])", safe_text)
        re_mmyyyy = re.findall(
            r"(\b1[012]|0[1-9])[- /.](\b(?:19|20)\d\d)", safe_text)
        re_yyyy = re.findall(r"(\b(?:19|20)\d\d)", safe_text)
        # Builds iso formatted dates
        yyyymmdd = self.__format_date(re_yyyymmdd, "%Y-%m-%d")
        ddmmyyyy = self.__format_date(re_ddmmyyyy, "%d-%m-%Y")
        yymmdd = self.__format_date(re_yymmdd, "%y-%m-%d")
        ddmmyy = self.__format_date(re_ddmmyy, "%d-%m-%y")
        yyyymm = self.__format_date(re_yyyymm, "%Y-%m")
        mmyyyy = self.__format_date(re_mmyyyy, "%m-%Y")
        yyyy = datetime.strptime(re_yyyy[0], "%Y").isoformat()[
            :10] if re_yyyy else None
        # return in order of preference
        return yyyymmdd or ddmmyyyy or yymmdd or ddmmyy or yyyymm or mmyyyy or yyyy

    def __extract_re_date(self):
        date_raw = self._groups.get("date") or self._name
        file_date = self.__find_date(date_raw)
        return file_date

    def __extract_re_actors(self):
        file_actors = []
        if self._groups.get("performers"):
            if self._splitter is not None:
                file_actors = self._groups.get(
                    "performers").split(self._splitter)
            else:
                file_actors = [self._groups.get("performers")]
        return file_actors

    def __extract_re_tags(self):
        file_tags = []
        if self._groups.get("tags"):
            if self._splitter is not None:
                file_tags = self._groups.get("tags").split(self._splitter)
            else:
                file_tags = [self._groups.get("tags")]
        return file_tags

    def parse(self, defaults={"actors": [], "tags": []}):
        if self._re_config_file is None:
            return
        if defaults is None:
            defaults = {"actors": [], "tags": []}
        # Match the regex against the file name
        matches = re.match(self._regex, self._name)
        self._groups = matches.groupdict() if matches else {}
        if not self._groups:
            log.LogInfo("Regex found in {}, is NOT matching '{}'".format(
                self._re_config_file, self._name))
        file_data = {
            "file": self._re_config_file,
            "source": "re",
            "title": self._groups.get("title"),
            "director": self._groups.get("director") or defaults.get("director"),
            "details": defaults.get("details"),
            "studio": self._groups.get("studio") or defaults.get("studio"),
            "movie": self._groups.get("movie") or defaults.get("title"),
            "scene_index": self._groups.get("index") or defaults.get("scene_index"),
            "date": self.__extract_re_date() or defaults.get("date"),
            "actors": self.__extract_re_actors() or (defaults.get("actors") or []),
            # tags are merged with defaults
            "tags": list(set(self.__extract_re_tags() + (defaults.get("tags") or []))),
            "rating": self._groups.get("rating") or defaults.get("rating"),
            "cover_image": None,
            "other_image": None,
            "url": None,
        }
        return file_data
