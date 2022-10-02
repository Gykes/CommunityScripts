import sys
import json
import config
import log
import nfoParser
import reParser
import stashInterface


class NfoSceneParser:
    '''stash plugin'''

    def __init__(self, scene_id):
        self._scene_id = scene_id
        self._folder_data = {}
        self._file_data = {}
        # Get the scene details if needed
        if type(scene_id) is dict:
            self._stash_scene = scene_id
            self._scene_id = self._stash_scene["id"]
        elif type(scene_id) is int:
            self._stash_scene = stash.getScene(scene_id)

    def parse(self):
        ''' Parse data from files, from nfo or regex pattern matching on the filename itself '''
        if self._stash_scene["organized"] and config.skip_organized:
            log.LogDebug(
                f"Skipping already organized scene id: {self._stash_scene['id']}")
            return
        # Parse folder nfo (used as default)
        folder_nfo_parser = nfoParser.NfoParser(
            self._stash_scene["path"], True)
        self._folder_data = folder_nfo_parser.parse()
        # Parse scene nfo
        nfo_parser = nfoParser.NfoParser(self._stash_scene["path"])
        self._file_data = nfo_parser.parse(self._folder_data)
        # Fallback to re parser
        if self._file_data is None:
            re_parser = reParser.RegExParser(self._stash_scene["path"])
            self._file_data = re_parser.parse(self._folder_data)
        if self._file_data is None:
            log.LogDebug("No matching NFO or RE found: nothing done...")
            return

    def update(self):
        ''' Update the parsed data into stash db (or create them if missing) '''
        # Update scene data from parsed info (and retrieve/create performers, studios, movies,...)
        scene_data = self.__find_create_scene_data()
        # [ ] Possible improvement: enrich nfo scene index from regex matched index ?
        if config.dry_mode:
            if scene_data.get("cover_image") is not None:
                scene_data["cover_image"] = "*** Base64 encoded image removed for readability ***"
            log.LogInfo(
                f"Dry mode. Would have updated scene based on: {json.dumps(scene_data)}")
            return
        updated_scene = stash.updateScene(self._scene_id, scene_data)
        if updated_scene is not None and updated_scene["id"] == str(self._scene_id):
            log.LogInfo(
                f"Successfully updated scene: {self._scene_id} using '{self._file_data['file']}'")
        else:
            log.LogInfo(
                f"Error updating scene: {self._scene_id} from file. Enable debug log for details.")

    def __find_create_scene_data(self):
        performer_ids = [] if "performers" in config.blacklist else self.__find_create_performers()
        studio_id = [] if "studio" in config.blacklist else self.__find_create_studio()
        tag_ids = [] if "tags" in config.blacklist else self.__find_create_tags()
        movie_id = [] if "movie" in config.blacklist else self.__find_create_movie(
            studio_id)
        scene_data = {
            "source": self._file_data["source"],
            "title": self._file_data["title"] if "title" not in config.blacklist else None,
            "details": self._file_data["details"] if "details" not in config.blacklist else None,
            "date": self._file_data["date"] if "date" not in config.blacklist else None,
            "rating": self._file_data["rating"] if "rating" not in config.blacklist else None,
            "url": self._file_data["url"] if "url" not in config.blacklist else None,
            "studio_id": studio_id,
            "performer_ids": performer_ids,
            "tag_ids": tag_ids,
            "movie_id": movie_id,
            "scene_index": self._file_data["scene_index"],
            "cover_image": self._file_data["cover_image"] if "image" not in config.blacklist else None,
        }
        return scene_data

    def __is_matching(self, text1, text2):
        # [ ] Possible improvement: levenshtein distance instead of exact match?
        return text1 == text2

    def __find_create_performers(self):
        performer_ids = []
        created_performers = []
        for actor in self._file_data["actors"]:
            performers = stash.findPerformers(actor)
            match_direct = False
            match_alias = False
            matching_id = None
            match_count = 0
            # 1st pass for direct name matches
            for performer in performers["performers"]:
                if self.__is_matching(actor, performer["name"]):
                    if matching_id is None:
                        matching_id = performer["id"]
                        match_direct = True
                    match_count += 1
            # 2nd pass for alias matches
            if matching_id is None and config.search_performer_aliases \
                and (config.ignore_single_name_performer_aliases is False or " " in actor):
                for performer in performers["performers"]:
                    if performer["aliases"]:
                        for alias in performer["aliases"].split(", "):
                            if self.__is_matching(actor, alias):
                                if matching_id is None:
                                    matching_id = performer["id"]
                                    match_alias = True
                                match_count += 1
            # Create a new performer when it does not exist
            if matching_id is None:
                if not config.create_missing_performers or config.dry_mode:
                    log.LogInfo(
                        f"'{actor}' performer creation prevented by config (dry_mode or create_missing_xxx)")
                else:
                    new_performer = stash.performerCreate(actor)
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
        if self._file_data["studio"] is None:
            return ""
        studio_id = None
        studios = stash.findStudios(self._file_data["studio"])
        match_direct = False
        match_alias = False
        matching_id = None
        match_count = 0
        # 1st pass for direct name matches
        for studio in studios["studios"]:
            if self.__is_matching(self._file_data["studio"], studio["name"]):
                if matching_id is None:
                    matching_id = studio["id"]
                    match_direct = True
                match_count += 1
        # 2nd pass for alias matches
        if matching_id is None and config.search_studio_aliases:
            for studio in studios["studios"]:
                if studio["aliases"]:
                    for alias in studio["aliases"].split(", "):
                        if self.__is_matching(self._file_data["studio"], alias):
                            if matching_id is None:
                                matching_id = studio["id"]
                                match_alias = True
                            match_count += 1
        # Create a new studio when it does not exist
        if matching_id is None:
            if not config.create_missing_studio or config.dry_mode:
                log.LogInfo(
                    f"'{self._file_data['studio']}' studio creation prevented by config (dry_mode or create_missing_xxx)")
            else:
                new_studio = stash.studioCreate(self._file_data["studio"])
                studio_id = new_studio["id"]
                log.LogInfo(f"Created missing studio '{self._file_data['studio']}' with id {new_studio['id']}")
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
            # skip blacklisted tags
            if file_tag.lower() in blacklisted_tags:
                continue
            # find stash tags
            tags = stash.findTags(file_tag)
            matching_id = None
            # Ensure direct name match
            for tag in tags["tags"]:
                if self.__is_matching(file_tag, tag["name"]):
                    if matching_id is None:
                        matching_id = tag["id"]
            # Create a new tag when it does not exist
            if matching_id is None:
                if not config.create_missing_tags or config.dry_mode:
                    log.LogDebug(
                        f"'{file_tag}' tag creation prevented by config (dry_mode or create_missing_xxx)")
                else:
                    new_tag = stash.tagCreate(file_tag)
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
        if self._file_data["movie"] is None:
            return
        movie_id = None
        movies = stash.findMovies(self._file_data["movie"])
        matching_id = None
        # Ensure direct name match
        for movie in movies["movies"]:
            if self.__is_matching(self._file_data["movie"], movie["name"]):
                if matching_id is None:
                    matching_id = movie["id"]
        # Create a new movie when it does not exist
        if matching_id is None:
            if not config.create_missing_movie or config.dry_mode:
                log.LogInfo(
                    f"'{self._file_data['movie']}' movie creation prevented by config (dry_mode or create_missing_xxx)")
            else:
                new_movie = stash.movieCreate(
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


# Init
if len(sys.argv) > 1:
    # Loads from argv for CLI testing...
    fragment = json.loads(sys.argv[1])
else:
    fragment = json.loads(sys.stdin.read())
stash = stashInterface.StashInterface(fragment)
# Parse file data and update scene (+ create missing performer, tag, movie,...)
nfoSceneParser = NfoSceneParser(stash.get_scene_id())
nfoSceneParser.parse()
nfoSceneParser.update()
stash.exit_plugin("Successful!")
