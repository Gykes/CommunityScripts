import os
import xml.etree.ElementTree as xml
import base64
import config
import log
import requests

class NfoParser:

    # Searched in the list order. First found is the one used.
    _image_formats = ["jpg", "jpeg", "png"]
    _image_suffixes = ["-landscape", "-thumb", "-cover", "-poster", ""]

    def __init__(self, scene_path):
        self._scene_path = scene_path
        self._nfo_file = self.__find_nfo_file()

    def __find_nfo_file(self):
        # TODO: supports movie nfo to get all movie details
        nfo_path = None
        if config.nfo_path.lower() == "with files":
            file_path = os.path.splitext(self._scene_path)[0]
            nfo_path = "{}.nfo".format(file_path)
        # else:
            # TODO: supports dedicated dir instead of "with files" (and scene id as well as scene filename)
        return nfo_path

    def __read_cover_image_file(self):
        file_path = os.path.splitext(self._scene_path)[0]
        for suffix in self._image_suffixes:
            for format in self._image_formats:
                image_path = "{}{}.{}".format(file_path, suffix, format)
                if os.path.exists(image_path):
                    with open(image_path, "rb") as img:
                        img_bytes = img.read()
                    return img_bytes

    def __download_cover_image(self, nfo_root):
        # Prefer landscape image, but otherwise take any thumbnail image...
        thumb_url = nfo_root.findtext(
            "thumb[@aspect='landscape']") or nfo_root.findtext("thumb")
        if thumb_url is None:
            return
        # Download image from url
        img_bytes = None
        try:
            r = requests.get(thumb_url, timeout=10)
            img_bytes = r.content
        except Exception as e:
            log.LogDebug(
                "Failed to download the cover image from {}: {}".format(thumb_url, e))
        return img_bytes

    def __extract_cover_image_b64(self, nfo_root):
        if "cover_image" in config.blacklist:
            return
        # 1st prio: get image from <thumb> tag (url), otherwise get from disk (file)
        img_bytes = self.__download_cover_image(
            nfo_root) or self.__read_cover_image_file()
        if img_bytes is None:
            return
        b64img_bytes = base64.b64encode(img_bytes)
        if not b64img_bytes:
            return
        file_image = f"data:image/jpeg;base64,{b64img_bytes.decode('utf-8')}"
        return file_image

    def __extract_nfo_title(self, nfo_root):
        if "title" in config.blacklist:
            return
        return nfo_root.findtext("title") or nfo_root.findtext("originaltitle") or nfo_root.findtext("sorttitle")

    def __extract_nfo_details(self, nfo_root):
        if "details" in config.blacklist:
            return
        return nfo_root.findtext("plot") or nfo_root.findtext("outline") or nfo_root.findtext("tagline")

    def __extract_nfo_rating(self, nfo_root):
        if "rating" in config.blacklist:
            return
        user_rating = round(float(nfo_root.findtext("userrating") or 0))
        # <rating> is converted to a scale of 5 if needed
        rating = None
        rating_elem = nfo_root.find("ratings/rating")
        if rating_elem is not None:
            max = float(rating_elem.attrib["max"])
            value = float(rating_elem.findtext("value"))
            rating = round(value / (max / 5))
        return user_rating or rating

    def __extract_nfo_date(self, nfo_root):
        if "date" in config.blacklist:
            return
        # date either in <premiered> (full) or <year> (only the year)
        year = nfo_root.findtext("year")
        if year is not None:
            year = "{}-01-01".format(year.text)
        return nfo_root.findtext("premiered") or year

    def __extract_nfo_tags(self, nfo_root):
        if "tags" in config.blacklist:
            return []
        file_tags = []
        # from nfo <tag>
        tags = nfo_root.findall("tag")
        for tag in tags:
            file_tags.append(tag.text)
        # from nfo <genre>
        genres = nfo_root.findall("genre")
        for genre in genres:
            file_tags.append(genre.text)
        return file_tags

    def __extract_nfo_studio(self, nfo_root):
        if "studio" in config.blacklist:
            return
        return nfo_root.findtext("studio")

    def __extract_nfo_movie(self, nfo_root):
        if "movie" in config.blacklist:
            return
        # TODO: extract also from folder.nfo or dirname.nfo
        return nfo_root.findtext("set/name")

    def __extract_nfo_actors(self, nfo_root):
        if "performers" in config.blacklist:
            return
        file_actors = []
        actors = nfo_root.findall("actor/name")
        for actor in actors:
            file_actors.append(actor.text)
        return file_actors

    def parse_scene(self):
        if not os.path.exists(self._nfo_file):
            return
        log.LogDebug("Parsing '{}'".format(self._nfo_file))
        # Parse NFO xml content
        try:
            nfo_root = xml.parse(self._nfo_file)
        except Exception as e:
            log.LogError("Could not parse nfo '{}'".format(self._nfo_file, e))
            return
        # Extract data from XML tree
        file_data = {
            "file": self._nfo_file,
            "source": "nfo",
            "title": self.__extract_nfo_title(nfo_root),
            "details": self.__extract_nfo_details(nfo_root),
            "studio": self.__extract_nfo_studio(nfo_root),
            "movie": self.__extract_nfo_movie(nfo_root),
            "scene_index": None,
            "date": self.__extract_nfo_date(nfo_root),
            "actors": self.__extract_nfo_actors(nfo_root),
            "tags": self.__extract_nfo_tags(nfo_root),
            "rating": self.__extract_nfo_rating(nfo_root),
            "cover_image": self.__extract_cover_image_b64(nfo_root),
        }
        return file_data


'''
Type definitions for NFO file spec - For information

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
