import os
import xml.etree.ElementTree as xml
import config
import log

# TODO: supports scene number in the movie
# TODO: supports movie nfo to get all movie details


def find_nfo_file(scene_path):
    file_path = os.path.splitext(scene_path)[0]
    nfo_path = "{}.nfo".format(file_path)
    return nfo_path


def parse_nfo_title(nfo_root):
    file_title = None
    if "title" not in config.blacklist:
        file_title = nfo_root.findtext("title") or nfo_root.findtext("originaltitle") or nfo_root.findtext("sorttitle")
    return file_title


def parse_nfo_details(nfo_root):
    file_details = None
    if "details" not in config.blacklist:
        file_details = nfo_root.findtext("plot") or nfo_root.findtext("outline") or nfo_root.findtext("tagline")
    return file_details


def parse_nfo_rating(nfo_root):
    # rating is converted to a scale of 5 if needed
    file_rating = None
    if "rating" not in config.blacklist:
        try:
            user_rating = nfo_root.find("userrating")
            if user_rating is not None:
                file_rating = round(float(user_rating.text))
            else:
                rating = nfo_root.find("ratings/rating")
                if rating is not None:
                    max = float(rating.attrib["max"])
                    value = float(rating.findtext("value"))
                    file_rating = round(value / (max / 5))
        except Exception as e:
            log.LogDebug("Error parsing rating: {}".format(e))
    return file_rating


def parse_nfo_date(nfo_root):
    # date either in full or only the year
    file_date = None
    if "date" not in config.blacklist:
        try:
            premiered = nfo_root.find("premiered")
            year = nfo_root.find("year")
            if premiered is not None:
                file_date = premiered.text
            elif year is not None:
                file_date = "{}-01-01".format(year.text)
        except Exception as e:
            log.LogDebug("Error parsing date: {}".format(e))
    return file_date


def parse(scene_path):
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
    file_studio = None
    if studio is not None and "studio" not in config.blacklist:
        file_studio = studio.text
    # movie
    set = nfo_root.find("set/name")
    file_movie = None
    if set is not None and "movie" not in config.blacklist:
        file_movie = set.text
    # actor names
    file_actors = []
    if "performers" not in config.blacklist:
        actors = nfo_root.findall("actor/name")
        # TODO: Manage <type> tags to filter...
        for actor in actors:
            file_actors.append(actor.text)
    # tags
    file_tags = []
    if "tags" not in config.blacklist:
        tags = nfo_root.findall("tag")
        # TODO: Manage <genre> tags to filter...
        for tag in tags:
            file_tags.append(tag.text)

    file_data = {
        "file": nfo_file,
        "source": "nfo",
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
