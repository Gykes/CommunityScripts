import json
import sys
import time
import config
import log
import nfoParser
import reParser


def parse(scene_id):
    # Get the scene details if needed
    if type(scene_id) is dict:
        stash_scene = scene_id
        scene_id = stash_scene["id"]
    elif type(scene_id) is int:
        stash_scene = graphql_getScene(scene_id)
    # Parsing: NFO has priority, with fallback to re
    if stash_scene["organized"] and config.skip_organized:
        log.LogDebug(
            "Skipping already organized scene id: {}".format(stash_scene["id"]))
        return
    nfo_parser = nfoParser.NfoParser(stash_scene["path"])
    file_data = nfo_parser.parse_scene()
    if file_data is None:
        re_parser = reParser.RegExParser(stash_scene["path"])
        file_data = re_parser.parse_scene()
        if file_data is None:
            log.LogDebug("No matching NFO or RE found: nothing done...")
            return
    # Update scene data from parsed info (and retrieve/create performers, studios, movies,...)
    scene_data = create_lookup_scene_data(file_data)
    # Possible improvement: enrich nfo scene index from regex matched index?
    if config.dry_mode:
        log.LogInfo("Dry mode. Would have updated scene based on: {}".format(
            json.dumps(scene_data)))
        return
    updated_scene = graphql_updateScene(scene_id, scene_data)
    if updated_scene != None and updated_scene["id"] == str(scene_id):
        log.LogInfo("Successfully updated scene id: {} using file '{}'".format(
            scene_id, file_data["file"]))
    else:
        log.LogInfo("Error updating scene id: {} from file. Enable debug log for details.".format(
            scene_id))


def create_lookup_scene_data(file_data):
    performer_ids = lookup_create_performers(file_data)
    studio_id = lookup_create_studio(file_data)
    tag_ids = lookup_create_tags(file_data)
    movie_id = lookup_create_movie(file_data, studio_id, file_data["date"])
    scene_data = {
        "source": file_data["source"],
        "title": file_data["title"],
        "details": file_data["details"],
        "date": file_data["date"],
        "rating": file_data["rating"],
        "studio_id": studio_id,
        "performer_ids": performer_ids,
        "tag_ids": tag_ids,
        "movie_id": movie_id,
        "scene_index": file_data["scene_index"],
        "cover_image": file_data["cover_image"],
    }
    return scene_data


def is_matching(text1, text2):
    # Possible improvement: levenshtein distance instead of exact match?
    return text1 == text2


def lookup_create_performers(file_data):
    performer_ids = []
    for actor in file_data["actors"]:
        performers = graphql_findPerformers(actor)
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
        if matching_id is None and config.create_missing_performers:
            new_performer = graphql_performerCreate(actor)
            performer_ids.append(new_performer["id"])
            log.LogDebug("Created missing performer '{}' with id {}".format(
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
    studios = graphql_findStudios(file_data["studio"])
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
    if matching_id is None and config.create_missing_studio:
        new_studio = graphql_studioCreate(file_data["studio"])
        studio_id = new_studio["id"]
        log.LogDebug("Created missing studio '{}' with id {}".format(
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
    for file_tag in file_data["tags"]:
        tags = graphql_findTags(file_tag)
        matching_id = None
        # Ensure direct name matche
        for tag in tags["tags"]:
            if is_matching(file_tag, tag["name"]):
                if matching_id is None:
                    matching_id = tag["id"]
        # Create a new tag when it does not exist
        if matching_id is None and config.create_missing_tags:
            new_tag = graphql_tagCreate(file_tag)
            tag_ids.append(new_tag["id"])
            log.LogDebug("Created missing tag '{}' with id {}".format(
                file_tag, new_tag["id"]))
        else:
            tag_ids.append(matching_id)
            log.LogDebug("Matched existing tag '{}' with id {}".format(
                file_tag, matching_id))
    return tag_ids


def lookup_create_movie(file_data, studio_id, date):
    if file_data["movie"] is None:
        return
    movie_id = []
    movies = graphql_findMovies(file_data["movie"])
    matching_id = None
    # Ensure direct name matche
    for movie in movies["movies"]:
        if is_matching(file_data["movie"], movie["name"]):
            if matching_id is None:
                matching_id = movie["id"]
    # Create a new movie when it does not exist
    if matching_id is None and config.create_missing_movie:
        new_movie = graphql_movieCreate(file_data["movie"], studio_id, date)
        movie_id = new_movie["id"]
        log.LogDebug("Created missing movie '{}' with id {}".format(
            file_data["movie"], new_movie["id"]))
    else:
        movie_id = matching_id
        log.LogDebug("Matched existing movie '{}' with id {}".format(
            file_data["movie"], matching_id))
    return movie_id


def callGraphQL(query, variables=None):
    # Session cookie for authentication
    graphql_port = str(FRAGMENT_SERVER["Port"])
    graphql_scheme = FRAGMENT_SERVER["Scheme"]
    graphql_cookies = {"session": FRAGMENT_SERVER["SessionCookie"]["Value"]}
    graphql_headers = {
        "Accept-Encoding": "gzip, deflate, br",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Connection": "keep-alive",
        "DNT": "1"
    }
    graphql_domain = FRAGMENT_SERVER["Host"]
    if graphql_domain == "0.0.0.0":
        graphql_domain = "localhost"
    # Stash GraphQL endpoint
    graphql_url = f"{graphql_scheme}://{graphql_domain}:{graphql_port}/graphql"

    json = {"query": query}
    if variables is not None:
        json["variables"] = variables
    try:
        # response = requests.post(
        #     graphql_url, json=json, headers=graphql_headers, cookies=graphql_cookies, timeout=20)
        response = requests.post(
            graphql_url, json=json, headers=graphql_headers, cookies=graphql_cookies, timeout=20)
    except Exception as e:
        exit_plugin(err=f"[FATAL] Error with the graphql request {e}")
    if response.status_code == 200:
        result = response.json()
        if result.get("error"):
            for error in result["error"]["errors"]:
                raise Exception(f"GraphQL error: {error}")
            return None
        if result.get("data"):
            return result.get("data")
    elif response.status_code == 401:
        exit_plugin(err="HTTP Error 401, Unauthorised.")
    else:
        raise ConnectionError(
            f"GraphQL query failed: {response.status_code} - {response.content}")


def graphql_getScene(scene_id):
    query = """
    query FindScene($id: ID!, $checksum: String) {
        findScene(id: $id, checksum: $checksum) {
            ...SceneData
        }
    }
    fragment SceneData on Scene {
        id
        organized
        path
    }
    """
    variables = {
        "id": scene_id
    }
    result = callGraphQL(query, variables)
    return result.get("findScene")


def graphql_updateScene(scene_id, scene_data):
    query = """
    mutation sceneUpdate($input: SceneUpdateInput!) {
        sceneUpdate(input: $input) {
            id
        }
    }    
    """
    input = {
        "id": scene_id,
        "title": scene_data["title"],
        "details": scene_data["details"],
        "date": scene_data["date"],
        "rating": scene_data["rating"],
        "studio_id": scene_data["studio_id"],
        "performer_ids": scene_data["performer_ids"],
        "tag_ids": scene_data["tag_ids"],
    }
    if scene_data["cover_image"] is not None:
        input.update({"cover_image": scene_data["cover_image"]})
    if config.set_organized_nfo and scene_data["source"] == "nfo":
        input.update({"organized": True})
    if scene_data["movie_id"] is not None:
        input["movies"] = {
            "movie_id": scene_data["movie_id"],
            "scene_index": scene_data["scene_index"],
        }
    variables = {
        "input": input
    }
    result = callGraphQL(query, variables)
    return result.get("sceneUpdate")


def graphql_performerCreate(name):
    query = """
    mutation performerCreate($input: PerformerCreateInput!) {
        performerCreate(input: $input) {
            id
        }
    }
    """
    variables = {
        "input": {
            "name": name
        }
    }
    result = callGraphQL(query, variables)
    return result.get("performerCreate")


def graphql_studioCreate(name):
    query = """
    mutation studioCreate($input: StudioCreateInput!) {
        studioCreate(input: $input) {
            id
        }
    }
    """
    variables = {
        "input": {
            "name": name
        }
    }
    result = callGraphQL(query, variables)
    return result.get("studioCreate")


def graphql_tagCreate(name):
    query = """
    mutation tagCreate($input: TagCreateInput!) {
        tagCreate(input: $input) {
            id
        }
    }
    """
    variables = {
        "input": {
            "name": name
        }
    }
    result = callGraphQL(query, variables)
    return result.get("tagCreate")


def graphql_movieCreate(name, studio_id, date):
    query = """
    mutation movieCreate($input: MovieCreateInput!) {
        movieCreate(input: $input) {
            id
        }
    }
    """
    variables = {
        "input": {
            "name": name,
            "studio_id": studio_id,
            "date": date
        }
    }
    result = callGraphQL(query, variables)
    return result.get("movieCreate")


def graphql_findPerformers(name):
    query = """
    query findPerformers($performer_filter: PerformerFilterType, $filter: FindFilterType) {
        findPerformers(performer_filter: $performer_filter, filter: $filter) {
            performers {
                id
                name
                aliases
            }
        }
    }
    """
    variables = {
        "performer_filter": {
            "name": {
                "value": name,
                "modifier": "INCLUDES"
            },
            "OR": {
                "aliases": {
                    "value": name,
                    "modifier": "INCLUDES"
                }
            }
        },
        "filter": {
            "per_page": -1
        },
    }
    result = callGraphQL(query, variables)
    return result.get("findPerformers")


def graphql_findStudios(name):
    query = """
    query findStudios($studio_filter: StudioFilterType, $filter: FindFilterType) {
        findStudios(studio_filter: $studio_filter, filter: $filter) {
            studios {
                id
                name
                aliases
            }
        }
    }
    """
    variables = {
        "studio_filter": {
            "name": {
                "value": name,
                "modifier": "INCLUDES"
            },
            "OR": {
                "aliases": {
                    "value": name,
                    "modifier": "INCLUDES"
                }
            }
        },
        "filter": {
            "per_page": -1
        },
    }
    result = callGraphQL(query, variables)
    return result.get("findStudios")


def graphql_findMovies(name):
    query = """
    query findMovies($movie_filter: MovieFilterType, $filter: FindFilterType) {
        findMovies(movie_filter: $movie_filter, filter: $filter) {
            movies {
                id
                name
            }
        }
    }
    """
    variables = {
        "studio_filter": {
            "name": {
                "value": name,
                "modifier": "INCLUDES"
            }
        },
        "filter": {
            "per_page": -1
        },
    }
    result = callGraphQL(query, variables)
    return result.get("findMovies")


def graphql_findTags(name):
    query = """
    query findTags($tag_filter: TagFilterType, $filter: FindFilterType) {
        findTags(tag_filter: $tag_filter, filter: $filter) {
            tags {
                id
                name
            }
        }
    }
    """
    variables = {
        "tag_filter": {
            "name": {
                "value": name,
                "modifier": "INCLUDES"
            }
        },
        "filter": {
            "per_page": -1
        },
    }
    result = callGraphQL(query, variables)
    return result.get("findTags")


def exit_plugin(msg=None, err=None):
    if msg is None and err is None:
        msg = "plugin ended"
    log.LogDebug("Execution time: {}s".format(
        round(time.time() - START_TIME, 5)))
    output_json = {"output": msg, "error": err}
    print(json.dumps(output_json))
    sys.exit()


START_TIME = time.time()
FRAGMENT = json.loads(sys.stdin.read())
FRAGMENT_SERVER = FRAGMENT["server_connection"]
# PLUGIN_DIR = FRAGMENT_SERVER["PluginDir"]
FRAGMENT_HOOK_TYPE = FRAGMENT["args"]["hookContext"]["type"]
FRAGMENT_SCENE_ID = FRAGMENT["args"]["hookContext"]["id"]

if FRAGMENT_HOOK_TYPE != "Scene.Create.Post":
    exit_plugin(
        err=f"[FATAL] Unsupported plugin trigger: {FRAGMENT_HOOK_TYPE}. This plugin only supports 'Scene.Create.Post'")

log.LogDebug(
    "Starting Hook 'hook_nfoSceneParser' for scene {}".format(FRAGMENT_SCENE_ID))

parse(FRAGMENT_SCENE_ID)

exit_plugin("Successful!")
