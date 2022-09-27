import json
import os
import re
import sys
import time
import xml.etree.ElementTree as xml
from datetime import date
import config
import log
# ! BEGIN TEST DATA
import requests
# ! END TEST DATA

'''
Type definitions for supported NFO file data - For information

class Actors(TypedDict, total=False):
    name: str
    order: int
    role: str
    thumb: str

class MovieSet(TypedDict, total=False):
    name: str
    overview: int

class Thumb(TypedDict, total=False):
    _aspect: str
    _preview: str
    text: str

class Rating(TypedDict, total=False):
    _name: str
    _max: str
    _default: str
    value: str

class FileData(TypedDict, total=False):
    actor: Actors
    country: str
    credits: str
    dateadded: str
    director: str
    genre: str
    id: str
    lastplayed: str
    mpaa: str
    originaltitle: str
    outline: str
    playcount: int
    plot: str
    premiered: str
    sorttitle: str
    set: MovieSet
    studio: str
    tag: str
    tagline: str
    thumb: Thumb
    title: str
    trailer: str
    uniqueid: str
    userrating: int
    ratings: Rating
    year: int
'''

# TODO: Generic handling of file parsing type: NFO, JSON, REGEX,...
# TODO: Plan for potential substitutions (replace single name actors)
# TODO: Lookup existing values for performers and studio in main & aliases
# TODO: Option to create missing performers or studios

# TODO: Skip organized scenes


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
    file_data = parse_nfo(stash_scene["path"])
    if file_data is None:
        file_data = parse_re(stash_scene["path"])
    # Retrieve the existing id or create a new entry for satellite data (performers, studios, movies,...)
    scene_data = lookup_create_IDs(file_data)
    graphql_updateScene(scene_data)


def find_nfo_file(scene_path):
    file_path = os.path.splitext(scene_path)[0]
    nfo_path = "{}.nfo".format(file_path)
    # ! BEGIN TEST DATA
    nfo_path = nfo_path.replace(
        "/data/", "/Users/vince/mnt/rawpriv/Moviez/_STASH-TEST/")
    # ! END TEST DATA
    return nfo_path


def parse_nfo_title(nfo_root):
    title = nfo_root.find("title")
    originaltitle = nfo_root.find("originaltitle")
    sorttitle = nfo_root.find("sorttitle")
    file_title = ""
    if title is not None:
        file_title = title.text
    elif originaltitle is not None:
        file_title = originaltitle.text
    elif sorttitle is not None:
        file_title = sorttitle.text
    return file_title


def parse_nfo_details(nfo_root):
    plot = nfo_root.find("plot")
    outline = nfo_root.find("outline")
    tagline = nfo_root.find("tagline")
    file_details = ""
    if plot is not None:
        file_details = plot.text
    elif outline is not None:
        file_details = outline.text
    elif tagline is not None:
        file_details = tagline.text
    return file_details


def parse_nfo_rating(nfo_root):
    # rating is converted to a scale of 5 if needed
    file_rating = ""
    try:
        user_rating = nfo_root.find("userrating")
        if user_rating is not None:
            value = float(user_rating.text)
            file_rating = value
        else:
            rating = nfo_root.find("ratings/rating")
            if rating is not None:
                max = float(rating.attrib["max"])
                value = float(rating.find("value").text)
                file_rating = value / (max / 5)
    except Exception as e:
        log.LogDebug("Error parsing rating: {}".format(e))
    return file_rating


def parse_nfo_date(nfo_root):
    # date either in full or only the year
    file_date = ""
    try:
        premiered = nfo_root.find("premiered")
        year = nfo_root.find("year")
        if premiered is not None:
            file_date = date.fromisoformat(premiered.text)
        elif year is not None:
            file_date = date.fromisocalendar(int(year.text), 1, 1)
    except Exception as e:
        log.LogDebug("Error parsing date: {}".format(e))
    return file_date


def parse_nfo(scene_path):
    nfo_file = find_nfo_file(scene_path)
    if not os.path.exists(nfo_file):
        return
    log.LogDebug("Parsing '{}'".format(nfo_file))
    try:
        nfo_root = xml.parse(nfo_file)
    except Exception as e:
        log.LogError("Could not parse nfo '{}'".format(nfo_file, e))
        return
    file_title = parse_nfo_title(nfo_root)
    file_details = parse_nfo_details(nfo_root)
    file_rating = parse_nfo_rating(nfo_root)
    file_date = parse_nfo_date(nfo_root)
    # studio
    studio = nfo_root.find("studio")
    file_studio = ""
    if studio is not None:
        file_studio = studio.text
    # movie
    set = nfo_root.find("set/name")
    file_movie = ""
    if set is not None:
        file_movie = set.text
    # actor names
    file_actors = []
    actors = nfo_root.findall("actor/name")
    for actor in actors:
        file_actors.append(actor.text)
    # tags
    file_tags = []
    tags = nfo_root.findall("tag")
    for tag in tags:
        file_tags.append(tag.text)

    file_data = {
        "title": file_title,
        "details": file_details,
        "studio": file_studio,
        "movie": file_movie,
        "date": file_date,
        "actors": file_actors,
        "tags": file_tags,
        "rating": file_rating
    }
    return file_data


def parse_re(scene_path):
    # TODO: parse pattern...
    return


def find_re_file(scene_path):
    return


def lookup_create_IDs(file_data):
    performer_ids = lookup_create_performers(file_data)
    studio_id = lookup_create_studio(file_data)
    tag_ids = lookup_create_tags(file_data)
    movie_id = lookup_create_movie(file_data, studio_id, file_data["date"])
    scene_data = {
        "title": file_data["title"],
        "details": file_data["details"],
        "date": file_data["date"],
        "rating": file_data["rating"],
        "studio_id": studio_id,
        "performer_ids": performer_ids,
        "tag_ids": tag_ids,
        "movie_id": movie_id,
    }
    return scene_data


def is_matching(text1, text2):
    # TODO: levenshtein distance instead of exact match?
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
        if matching_id is None:
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
    if matching_id is None:
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
        if matching_id is None:
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
    movie_id = []
    movies = graphql_findMovies(file_data["movie"])
    matching_id = None
    # Ensure direct name matche
    for movie in movies["movies"]:
        if is_matching(file_data["movie"], movie["name"]):
            if matching_id is None:
                matching_id = movie["id"]
    # Create a new movie when it does not exist
    if matching_id is None:
        new_movie = graphql_movieCreate(file_data["movie"], studio_id, date.isoformat())
        movie_id = new_movie["id"]
        log.LogDebug("Created missing movie '{}' with id {}".format(
            file_data["movie"], new_movie["id"]))
    else:
        movie_id = matching_id
        log.LogDebug("Matched existing movie '{}' with id {}".format(
            file_data["movie"], matching_id))
    return movie_id


def callGraphQL(query, variables=None):
    # # Session cookie for authentication
    # graphql_port = str(FRAGMENT_SERVER["Port"])
    # graphql_scheme = FRAGMENT_SERVER["Scheme"]
    # graphql_cookies = {"session": FRAGMENT_SERVER["SessionCookie"]["Value"]}
    # graphql_headers = {
    #     "Accept-Encoding": "gzip, deflate, br",
    #     "Content-Type": "application/json",
    #     "Accept": "application/json",
    #     "Connection": "keep-alive",
    #     "DNT": "1"
    # }
    # graphql_domain = FRAGMENT_SERVER["Host"]
    # if graphql_domain == "0.0.0.0":
    #     graphql_domain = "localhost"
    # # Stash GraphQL endpoint
    # graphql_url = f"{graphql_scheme}://{graphql_domain}:{graphql_port}/graphql"
    # ! BEGIN TEST DATA
    graphql_url = f"http://10.1.1.113:9990/graphql?apikey=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiJyb290IiwiaWF0IjoxNjYzOTQyNjMyLCJzdWIiOiJBUElLZXkifQ.KFIBIks8N8LxeJLrZlmumOwn52jqXzzjPVdrCv7Rb7A&"
    graphql_headers = ""
    graphql_cookies = ""
    # ! END TEST DATA

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
    # TODO: check if path is not enough...
    query = """
    query FindScene($id: ID!, $checksum: String) {
        findScene(id: $id, checksum: $checksum) {
            ...SceneData
        }
    }
    fragment SceneData on Scene {
        id
        title
        date
        rating
        organized
        path
        studio {
            id
            name
            parent_studio {
                id
                name
            }
        }
        tags {
            id
            name
        }
        performers {
            id
            name
        }
        movies {
            movie {
                name
                date
            }
            scene_index
        }
    }
    """
    variables = {
        "id": scene_id
    }
    result = callGraphQL(query, variables)
    return result.get("findScene")


def graphql_updateScene(data):
    query = """
    mutation sceneUpdate($input: SceneUpdateInput!) {
        sceneUpdate(input: $input) {
            id
        }
    }    
    """
    variables = {
        "input": {
            "id": data["id"],
            "performer_ids": data["performer_ids"]
            # TODO: map all scene data
        }
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


DRY_MODE = config.dry_mode
START_TIME = time.time()
# FRAGMENT = json.loads(sys.stdin.read())
# FRAGMENT_SERVER = FRAGMENT["server_connection"]
# # PLUGIN_DIR = FRAGMENT_SERVER["PluginDir"]
# FRAGMENT_HOOK_TYPE = FRAGMENT["args"]["hookContext"]["type"]
# FRAGMENT_SCENE_ID = FRAGMENT["args"]["hookContext"]["id"]
# ! BEGIN TEST DATA
FRAGMENT_SCENE_ID = 3230
FRAGMENT_HOOK_TYPE = "Scene.Create.Post"
# ! END TEST DATA

if FRAGMENT_HOOK_TYPE != "Scene.Create.Post":
    exit_plugin(
        err=f"[FATAL] Unsupported plugin trigger: {FRAGMENT_HOOK_TYPE}. This plugin only supports 'Scene.Create.Post'")

log.LogDebug(
    "Starting Hook 'hook_nfoSceneParser' for scene {}".format(FRAGMENT_SCENE_ID))

parse(FRAGMENT_SCENE_ID)

exit_plugin("Successful!")
