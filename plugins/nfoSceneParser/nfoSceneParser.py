import sys
import json
import config
import log
import nfoParser
import reParser
import stashInterface


class NfoSceneParser:
    '''stash plugin'''

    def __init__(self, stash):
        self._stash = stash
        self._scene_id = stash.get_scene_id()
        self._folder_data = {}
        self._file_data = {}
        # Get the scene details if needed
        if type(self._scene_id) is dict:
            self._scene = self._scene_id
            self._scene_id = self._scene["id"]
        elif type(self._scene_id) is int:
            self._scene = stash.getScene(self._scene_id)

    def __parse(self):
        ''' Parse data from files, from nfo or regex pattern matching on the filename itself '''
        if self._scene["organized"] and config.skip_organized:
            log.LogInfo(
                f"Skipping already organized scene id: {self._scene['id']}")
            return
        # Parse folder nfo (used as default)
        folder_nfo_parser = nfoParser.NfoParser(
            self._scene["path"], None, True)
        self._folder_data = folder_nfo_parser.parse()
        # Parse scene nfo (nfo & regex).
        re_parser = reParser.RegExParser(self._scene["path"], [
            self._folder_data or reParser.RegExParser.empty_defaults
        ])
        re_file_data = re_parser.parse()
        nfo_parser = nfoParser.NfoParser(self._scene["path"], [
            self._folder_data or nfoParser.NfoParser.empty_defaults,
            re_file_data or nfoParser.NfoParser.empty_defaults
        ])
        nfo_file_data = nfo_parser.parse()
        # nfo as preferred input. re as fallback
        self._file_data = nfo_file_data or re_file_data
        return self._file_data

    def __strip_b64(self, data):
        if data.get("cover_image"):
            data["cover_image"] = "*** Base64 encoded image removed for readability ***"
        return json.dumps(data)

    def __update(self):
        ''' Update the parsed data into stash db (or create them if missing) '''
        # Must have found at least a "title" in the nfo or regex...
        if not self._file_data:
            log.LogDebug(
                "Skipped or no matching NFO or RE found: nothing done...")
            return
        # Retrieve/create performers, studios, movies,...
        scene_data = self.__find_create_scene_data()
        # [ ] Possible improvement: enrich nfo scene index from regex matched index ?
        if config.dry_mode:
            log.LogInfo(
                f"Dry mode. Would have updated scene based on: {self.__strip_b64(scene_data)}")
            return
        # Update scene data from parsed info
        updated_scene = self._stash.updateScene(self._scene_id, scene_data)
        if updated_scene is not None and updated_scene["id"] == str(self._scene_id):
            log.LogInfo(
                f"Successfully updated scene: {self._scene_id} using '{self._file_data['file']}'")
        else:
            log.LogError(
                f"Error updating scene: {self._scene_id} based on: {self.__strip_b64(scene_data)}.")
        return scene_data

    def __find_create_scene_data(self):
        # Lookup and/or create satellite objects in stash database
        file_performer_ids = [] if "performers" in config.blacklist else self.__find_create_performers()
        file_tag_ids = [] if "tags" in config.blacklist else self.__find_create_tags()
        file_studio_id = None if "studio" in config.blacklist else self.__find_create_studio()
        file_movie_id = None if "movie" in config.blacklist else self.__find_create_movie(
            file_studio_id)
        # Existing scene data
        scene_performer_ids = list(
            map(lambda p: p.get("id"), self._scene["performers"]))
        scene_tag_ids = list(map(lambda t: t.get("id"), self._scene["tags"]))
        # Build data for scene update:
        #  - Either new values or None (current data not modified).
        #  - performers and tags are combined (new + existing)
        scene_data = {
            "source": self._file_data["source"],
            "title": (self._file_data["title"] or None) if "title" not in config.blacklist else None,
            "details": (self._file_data["details"] or None) if "details" not in config.blacklist else None,
            "date": (self._file_data["date"] or None) if "date" not in config.blacklist else None,
            "rating": (self._file_data["rating"] or None) if "rating" not in config.blacklist else None,
            "url": (self._file_data["url"] or None) if "url" not in config.blacklist else None,
            "studio_id": file_studio_id or None,
            "performer_ids": list(set(file_performer_ids + scene_performer_ids)),
            "tag_ids": list(set(file_tag_ids + scene_tag_ids)),
            "movie_id": file_movie_id or None,
            "scene_index": self._file_data["scene_index"] or None,
            "cover_image": (self._file_data["cover_image"] or None) if "image" not in config.blacklist else None,
        }
        return scene_data

    def __is_matching(self, text1, text2):
        # [ ] Possible improvement: levenshtein distance instead of exact match?
        text1 = text1.lower() if text1 else text1
        text2 = text2.lower() if text2 else text2
        return text1 == text2

    def __find_create_performers(self):
        performer_ids = []
        created_performers = []
        for actor in self._file_data["actors"]:
            if not actor:
                continue
            performers = self._stash.findPerformers(actor)
            match_direct = False
            match_alias = False
            matching_id = None
            match_count = 0
            # 1st pass for direct name matches
            for performer in performers["performers"]:
                if self.__is_matching(actor, performer["name"]):
                    if not matching_id:
                        matching_id = performer["id"]
                        match_direct = True
                    match_count += 1
            # 2nd pass for alias matches
            if not matching_id and config.search_performer_aliases \
                    and (config.ignore_single_name_performer_aliases is False or " " in actor):
                for performer in performers["performers"]:
                    if performer["aliases"]:
                        for alias in performer["aliases"].split(", "):
                            if self.__is_matching(actor, alias):
                                if not matching_id:
                                    matching_id = performer["id"]
                                    match_alias = True
                                match_count += 1
            # Create a new performer when it does not exist
            if not matching_id:
                if not config.create_missing_performers or config.dry_mode:
                    log.LogInfo(
                        f"'{actor}' performer creation prevented by config (dry_mode or create_missing_xxx)")
                else:
                    new_performer = self._stash.performerCreate(actor)
                    created_performers.append(actor)
                    performer_ids.append(new_performer["id"])
            else:
                performer_ids.append(matching_id)
                log.LogDebug(f"Matched existing performer '{actor}' with id {matching_id} \
                    (direct: {match_direct}, alias: {match_alias}, match_count: {match_count})")
                if match_count > 1:
                    log.LogInfo(f"Linked scene with title '{self._file_data['title']}' to existing \
                        performer '{actor}' (id {matching_id}). Attention: {match_count} matches \
                        were found. Check to de-duplicate your performers and their aliases...")
        if created_performers:
            log.LogInfo(f"Created missing performers '{created_performers}'")
        return performer_ids

    def __find_create_studio(self) -> str:
        if not self._file_data["studio"]:
            return ""
        studio_id = None
        studios = self._stash.findStudios(self._file_data["studio"])
        match_direct = False
        match_alias = False
        matching_id = None
        match_count = 0
        # 1st pass for direct name matches
        for studio in studios["studios"]:
            if self.__is_matching(self._file_data["studio"], studio["name"]):
                if not matching_id:
                    matching_id = studio["id"]
                    match_direct = True
                match_count += 1
        # 2nd pass for alias matches
        if not matching_id and config.search_studio_aliases:
            for studio in studios["studios"]:
                if studio["aliases"]:
                    for alias in studio["aliases"].split(", "):
                        if self.__is_matching(self._file_data["studio"], alias):
                            if not matching_id:
                                matching_id = studio["id"]
                                match_alias = True
                            match_count += 1
        # Create a new studio when it does not exist
        if not matching_id:
            if not config.create_missing_studio or config.dry_mode:
                log.LogInfo(
                    f"'{self._file_data['studio']}' studio creation prevented by config (dry_mode or create_missing_xxx)")
            else:
                new_studio = self._stash.studioCreate(
                    self._file_data["studio"])
                studio_id = new_studio["id"]
                log.LogInfo(
                    f"Created missing studio '{self._file_data['studio']}' with id {new_studio['id']}")
        else:
            studio_id = matching_id
            log.LogDebug(f"Matched existing studio '{self._file_data['studio']}' with id \
                {matching_id} (direct: {match_direct}, alias: {match_alias}, match_count: {match_count})")
            if match_count > 1:
                log.LogInfo("Linked scene with title '{}' to existing studio '{}' (id {}). Attention: {} matches were found. Check to de-duplicate...".format(
                    self._file_data["title"], self._file_data["studio"], matching_id, match_count))
        return studio_id

    def __find_create_tags(self):
        tag_ids = []
        created_tags = []
        blacklisted_tags = [tag.lower() for tag in config.blacklisted_tags]
        for file_tag in self._file_data["tags"]:
            # skip empty or blacklisted tags
            if not file_tag or file_tag.lower() in blacklisted_tags:
                continue
            # find stash tags
            tags = self._stash.findTags(file_tag)
            matching_id = None
            # Ensure direct name match
            for tag in tags["tags"]:
                if self.__is_matching(file_tag, tag["name"]):
                    if not matching_id:
                        matching_id = tag["id"]
            # Create a new tag when it does not exist
            if not matching_id:
                if not config.create_missing_tags or config.dry_mode:
                    log.LogDebug(
                        f"'{file_tag}' tag creation prevented by config (dry_mode or create_missing_xxx)")
                else:
                    new_tag = self._stash.tagCreate(file_tag)
                    created_tags.append(file_tag)
                    tag_ids.append(new_tag["id"])
            else:
                tag_ids.append(matching_id)
                log.LogDebug("Matched existing tag '{}' with id {}".format(
                    file_tag, matching_id))
        if created_tags:
            log.LogInfo("Created missing tags '{}'".format(created_tags))
        return tag_ids

    def __find_create_movie(self, studio_id):
        if not self._file_data["movie"]:
            return
        movie_id = None
        movies = self._stash.findMovies(self._file_data["movie"])
        matching_id = None
        # Ensure direct name match
        for movie in movies["movies"]:
            if self.__is_matching(self._file_data["movie"], movie["name"]):
                if not matching_id:
                    matching_id = movie["id"]
        # Create a new movie when it does not exist
        if not matching_id:
            if not config.create_missing_movie or config.dry_mode:
                log.LogInfo(
                    f"'{self._file_data['movie']}' movie creation prevented by config (dry_mode or create_missing_xxx)")
            else:
                new_movie = self._stash.movieCreate(
                    self._file_data, studio_id, self._folder_data)
                movie_id = new_movie["id"]
                log.LogInfo("Created missing movie '{}' with id {}".format(
                    self._file_data["movie"], new_movie["id"]))
        else:
            # [ ] Possible improvement: update existing movie with nfo data
            movie_id = matching_id
            log.LogDebug("Matched existing movie '{}' with id {}".format(
                self._file_data["movie"], matching_id))
        return movie_id

    def process(self):
        file_data = self.__parse()
        try:
            scene_data = self.__update()
        except Exception as e:
            log.LogError(f"Error updating stash: {e}")
        return [file_data, scene_data]


if __name__ == '__main__':
    # Init
    if len(sys.argv) > 1:
        # Loads from argv for CLI testing...
        fragment = json.loads(sys.argv[1])
    else:
        fragment = json.loads(sys.stdin.read())
    stash_interface = stashInterface.StashInterface(fragment)
    # Parse file data and update scene (+ create missing performer, tag, movie,...)
    nfoSceneParser = NfoSceneParser(stash_interface)
    nfoSceneParser.process()
    stash_interface.exit_plugin("Successful!")
