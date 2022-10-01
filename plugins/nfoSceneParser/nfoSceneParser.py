import sys
import json
import config
import log
import nfoParser
import reParser
import stashInterface


def parse(scene_id):
    # Get the scene details if needed
    if type(scene_id) is dict:
        stash_scene = scene_id
        scene_id = stash_scene["id"]
    elif type(scene_id) is int:
        stash_scene = stash.getScene(scene_id)
    if stash_scene["organized"] and config.skip_organized:
        log.LogDebug(
            "Skipping already organized scene id: {}".format(stash_scene["id"]))
        return
    # Parse folder nfo (used as default)
    folder_nfo_parser = nfoParser.NfoParser(stash_scene["path"], True)
    folder_data = folder_nfo_parser.parse()
    # Parse scene nfo
    nfo_parser = nfoParser.NfoParser(stash_scene["path"])
    file_data = nfo_parser.parse(folder_data)
    # Fallback to re parser
    if file_data is None:
        re_parser = reParser.RegExParser(stash_scene["path"])
        file_data = re_parser.parse(folder_data)
        if file_data is None:
            log.LogDebug("No matching NFO or RE found: nothing done...")
            return
    # Update scene data from parsed info (and retrieve/create performers, studios, movies,...)
    scene_data = create_lookup_scene_data(file_data, folder_data)
    # [ ] Possible improvement: enrich nfo scene index from regex matched index ?
    if config.dry_mode:
        if scene_data.get("cover_image") is not None:
            scene_data["cover_image"] = "*** Base64 encoded image removed for readability ***"
        log.LogInfo("Dry mode. Would have updated scene based on: {}".format(
            json.dumps(scene_data, indent=3)))
        return
    updated_scene = stash.updateScene(scene_id, scene_data)
    if updated_scene != None and updated_scene["id"] == str(scene_id):
        log.LogInfo("Successfully updated scene id: {} using file '{}'".format(
            scene_id, file_data["file"]))
    else:
        log.LogInfo("Error updating scene id: {} from file. Enable debug log for details.".format(
            scene_id))


def create_lookup_scene_data(file_data, folder_data):
    performer_ids = [] if "performers" in config.blacklist else lookup_create_performers(file_data)
    studio_id = [] if "studio" in config.blacklist else lookup_create_studio(file_data)
    tag_ids = [] if "tags" in config.blacklist else lookup_create_tags(file_data)
    movie_id = [] if "movie" in config.blacklist else lookup_create_movie(file_data, studio_id, folder_data)
    scene_data = {
        "source": file_data["source"],
        "title": file_data["title"] if "title" not in config.blacklist else None,
        "details": file_data["details"] if "details" not in config.blacklist else None,
        "date": file_data["date"] if "date" not in config.blacklist else None,
        "rating": file_data["rating"] if "rating" not in config.blacklist else None,
        "url": file_data["url"] if "url" not in config.blacklist else None,
        "studio_id": studio_id,
        "performer_ids": performer_ids,
        "tag_ids": tag_ids,
        "movie_id": movie_id,
        "scene_index": file_data["scene_index"],
        "cover_image": file_data["cover_image"] if "image" not in config.blacklist else None,
    }
    return scene_data


def is_matching(text1, text2):
    # [ ] Possible improvement: levenshtein distance instead of exact match?
    return text1 == text2


def lookup_create_performers(file_data):
    performer_ids = []
    for actor in file_data["actors"]:
        performers = stash.findPerformers(actor)
        match_direct = False
        match_alias = False
        matching_id = None
        match_count = 0
        # 1st pass for direct name matches
        for performer in performers["performers"]:
            if is_matching(actor, performer["name"]):
                if matching_id is None:
                    matching_id = performer["id"]
                    match_direct = True
                match_count += 1
        # 2nd pass for alias matches
        if matching_id is None and config.search_performer_aliases and (config.ignore_single_name_performer_aliases is False or " " in actor):
            for performer in performers["performers"]:
                if performer["aliases"]:
                    for alias in performer["aliases"].split(", "):
                        if is_matching(actor, alias):
                            if matching_id is None:
                                matching_id = performer["id"]
                                match_alias = True
                            match_count += 1
        # Create a new performer when it does not exist
        if matching_id is None:
            if not config.create_missing_performers or config.dry_mode:
                log.LogInfo(f"'{actor}' performer creation prevented by config (dry_mode or create_missing_xxx)")
            else:
                new_performer = stash.performerCreate(actor)
                performer_ids.append(new_performer["id"])
                log.LogInfo("Created missing performer '{}' with id {}".format(
                    actor, new_performer["id"]))
        else:
            performer_ids.append(matching_id)
            log.LogDebug("Matched existing performer '{}' with id {} (direct: {}, alias: {}, match_count: {})".format(
                actor, matching_id, match_direct, match_alias, match_count))
            if match_count > 1:
                log.LogInfo("Linked scene with title '{}' to existing performer '{}' (id {}). Attention: {} matches were found. Check to de-duplicate...".format(
                    file_data["title"], actor, matching_id, match_count))
    return performer_ids


def lookup_create_studio(file_data):
    if file_data["studio"] is None:
        return
    studio_id = None
    studios = stash.findStudios(file_data["studio"])
    match_direct = False
    match_alias = False
    matching_id = None
    match_count = 0
    # 1st pass for direct name matches
    for studio in studios["studios"]:
        if is_matching(file_data["studio"], studio["name"]):
            if matching_id is None:
                matching_id = studio["id"]
                match_direct = True
            match_count += 1
    # 2nd pass for alias matches
    if matching_id is None and config.search_studio_aliases:
        for studio in studios["studios"]:
            if studio["aliases"]:
                for alias in studio["aliases"].split(", "):
                    if is_matching(file_data["studio"], alias):
                        if matching_id is None:
                            matching_id = studio["id"]
                            match_alias = True
                        match_count += 1
    # Create a new studio when it does not exist
    if matching_id is None:
        if not config.create_missing_studio or config.dry_mode:
            log.LogInfo(f"'{file_data['studio']}' studio creation prevented by config (dry_mode or create_missing_xxx)")
        else:
            new_studio = stash.studioCreate(file_data["studio"])
            studio_id = new_studio["id"]
            log.LogInfo("Created missing studio '{}' with id {}".format(
                file_data["studio"], new_studio["id"]))
    else:
        studio_id = matching_id
        log.LogDebug("Matched existing studio '{}' with id {} (direct: {}, alias: {}, match_count: {})".format(
            file_data["studio"], matching_id, match_direct, match_alias, match_count))
        if match_count > 1:
            log.LogInfo("Linked scene with title '{}' to existing studio '{}' (id {}). Attention: {} matches were found. Check to de-duplicate...".format(
                file_data["title"], file_data["studio"], matching_id, match_count))
    return studio_id


def lookup_create_tags(file_data):
    tag_ids = []
    blacklisted_tags = [tag.lower() for tag in config.blacklisted_tags]
    for file_tag in file_data["tags"]:
        # skip blacklisted tags
        if file_tag.lower() in blacklisted_tags:
            continue
        # find stash tags
        tags = stash.findTags(file_tag)
        matching_id = None
        # Ensure direct name match
        for tag in tags["tags"]:
            if is_matching(file_tag, tag["name"]):
                if matching_id is None:
                    matching_id = tag["id"]
        # Create a new tag when it does not exist
        if matching_id is None:
            if not config.create_missing_tags or config.dry_mode:
                log.LogInfo(f"'{file_tag}' tag creation prevented by config (dry_mode or create_missing_xxx)")
            else:
                new_tag = stash.tagCreate(file_tag)
                tag_ids.append(new_tag["id"])
                log.LogInfo("Created missing tag '{}' with id {}".format(
                    file_tag, new_tag["id"]))
        else:
            tag_ids.append(matching_id)
            log.LogDebug("Matched existing tag '{}' with id {}".format(
                file_tag, matching_id))
    return tag_ids


def lookup_create_movie(file_data, studio_id, folder_data):
    if file_data["movie"] is None:
        return
    movie_id = None
    movies = stash.findMovies(file_data["movie"])
    matching_id = None
    # Ensure direct name match
    for movie in movies["movies"]:
        if is_matching(file_data["movie"], movie["name"]):
            if matching_id is None:
                matching_id = movie["id"]
    # Create a new movie when it does not exist
    if matching_id is None:
        if not config.create_missing_movie or config.dry_mode:
            log.LogInfo(f"'{file_data['movie']}' movie creation prevented by config (dry_mode or create_missing_xxx)")
        else:
            new_movie = stash.movieCreate(
                file_data, studio_id, folder_data)
            movie_id = new_movie["id"]
            log.LogInfo("Created missing movie '{}' with id {}".format(
                file_data["movie"], new_movie["id"]))
    else:
        # [ ] Possible improvement: update existing movie with nfo data
        movie_id = matching_id
        log.LogDebug("Matched existing movie '{}' with id {}".format(
            file_data["movie"], matching_id))
    return movie_id

if len(sys.argv) > 1:
    # Loads from argv for CLI testing...
    fragment = json.loads(sys.argv[1])
else:
    fragment = json.loads(sys.stdin.read())

stash = stashInterface.StashInterface(fragment)
parse(stash.get_scene_id())
stash.exit_plugin("Successful!")
