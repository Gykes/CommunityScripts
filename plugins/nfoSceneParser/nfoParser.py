import os
import xml.etree.ElementTree as xml
import base64
import glob
import re
import requests
import config
import log


class NfoParser:
    ''' Parse nfo files '''

    empty_defaults = { "actors": [], "tags": [] }

    # Max number if images to process (2 for front/back cover in movies).
    _image_Max = 2

    def __init__(self, scene_path, defaults=None, folder_mode=False):
        ''' 
        - defaults: List of previous parse() results that to use as default value
            Defaults are used when no data is found in the current nfo (or there are no nfo).
            Default are process in the order in the list. The first key match is used.
        - folder_mode: whether to look for a global folder.nfo file or a scepecif scenename.nfo.
        '''
        self._defaults = defaults or [self.empty_defaults]
        # Finds nfo file
        nfo_path = None
        if config.nfo_location.lower() == "with files":
            if folder_mode:
                dir_path = os.path.dirname(scene_path)
                nfo_path = os.path.join(dir_path, "folder.nfo")
            else:
                nfo_path = os.path.splitext(scene_path)[0] + ".nfo"
        # else:
            # TODO: supports dedicated dir instead of "with files" (compatibility with nfo exporter)
        self._nfo_file = nfo_path
        self._nfo_root = None

    def __read_cover_image_file(self):
        thumb_images = []
        path_no_ext = os.path.splitext(self._nfo_file)[0]
        file_no_ext = os.path.split(path_no_ext)[1]
        files = sorted(glob.glob(f"{path_no_ext}*.*"))
        file_pattern = re.compile("^.*" + re.escape(file_no_ext) + \
            "(-landscape\\d{0,2}|-thumb\\d{0,2}|-poster\\d{0,2}|-cover\\d{0,2}|\\d{0,2})\\.(jpe?g|png|webp)$", \
            re.I)
        index = 0
        for file in files:
            if index >= self._image_Max:
                break
            if file_pattern.match(file):
                with open(file, "rb") as img:
                    img_bytes = img.read()
                thumb_images.append(img_bytes)
                index += 1
        return thumb_images

    def ___find_thumb_urls(self, query):
        result = []
        matches = self._nfo_root.findall(query)
        for match in matches:
            result.append(match.text)
        return result

    def __download_cover_images(self):
        # Prefer "landscape" images, then "poster", otherwise take any thumbnail image...
        thumb_urls = self.___find_thumb_urls("thumb[@aspect='landscape']") \
            or self.___find_thumb_urls("thumb[@aspect='poster']") \
            or self.___find_thumb_urls("thumb")
        # Ensure there are images and the count does not exceed the max allowed...
        if len(thumb_urls) == 0:
            return []
        del thumb_urls[self._image_Max:]
        # Download images from url
        thumb_images = []
        for thumb_url in thumb_urls:
            img_bytes = None
            try:
                r = requests.get(thumb_url, timeout=10)
                img_bytes = r.content
                thumb_images.append(img_bytes)
            except Exception as e:
                log.LogDebug(
                    "Failed to download the cover image from {}: {}".format(thumb_url, e))
        return thumb_images

    def __extract_cover_images_b64(self):
        if "cover_image" in config.blacklist:
            return []
        file_images = []
        # Get image from disk (file), otherwise from <thumb> tag (url)
        thumb_images = self.__read_cover_image_file() or self.__download_cover_images()
        for thumb_image in thumb_images:
            thumb_b64img = base64.b64encode(thumb_image)
            if thumb_b64img:
                file_images.append(
                    f"data:image/jpeg;base64,{thumb_b64img.decode('utf-8')}")
        return file_images

    def __extract_nfo_rating(self):
        user_rating = round(float(self._nfo_root.findtext("userrating") or 0))
        if user_rating > 0:
            return user_rating
        # <rating> is converted to a scale of 5 if needed
        rating = None
        rating_elem = self._nfo_root.find("ratings/rating")
        if rating_elem is not None:
            max_value = float(rating_elem.attrib["max"] or 1)
            value = float(rating_elem.findtext("value") or 0)
            rating = round(value / (max_value / 5))
        return rating

    def __extract_nfo_date(self):
        # date either in <premiered> (full) or <year> (only the year)
        year = self._nfo_root.findtext("year")
        if year is not None:
            year = f"{year}-01-01"
        return self._nfo_root.findtext("premiered") or year

    def __extract_nfo_tags(self):
        file_tags = []
        # from nfo <tag>
        tags = self._nfo_root.findall("tag")
        for tag in tags:
            file_tags.append(tag.text)
        # from nfo <genre>
        genres = self._nfo_root.findall("genre")
        for genre in genres:
            file_tags.append(genre.text)
        return list(set(file_tags))

    def __extract_nfo_actors(self):
        file_actors = []
        actors = self._nfo_root.findall("actor/name")
        for actor in actors:
            file_actors.append(actor.text)
        return file_actors

    def __get_default(self, key, source=None):
        for default in self._defaults:
            # Source filter: skip default if it is not of the specified source
            if source and default.get("source") != source:
                continue
            if default.get(key) is not None:
                return default.get(key)

    def parse(self):
        ''' Parses the nfo (with xml parser) '''
        if not os.path.exists(self._nfo_file):
            return
        log.LogDebug("Parsing '{}'".format(self._nfo_file))
        # Parse NFO xml content
        try:
            with open(self._nfo_file, "r") as nfo:
                # Tolerance: strip non-standard whitespaces/new lines
                clean_nfo_content = nfo.read().strip()
            # Tolerance: replace illegal "&nbsp;"
            clean_nfo_content = clean_nfo_content.replace("&nbsp;", " ")
            self._nfo_root = xml.fromstring(clean_nfo_content)
        except Exception as e:
            log.LogError(f"Could not parse nfo '{self._nfo_file}': {e}")
            return
        # Extract data from XML tree. Spec: https://kodi.wiki/view/NFO_files/Movies
        b64_images = self.__extract_cover_images_b64()
        file_data = {
            # TODO: supports stash uniqueid to match to existing scenes (compatibility with nfo exporter)
            "file": self._nfo_file,
            "source": "nfo",
            "title": self._nfo_root.findtext("title") or self._nfo_root.findtext("originaltitle") or self._nfo_root.findtext("sorttitle") or self.__get_default("title", "re"),
            "director": self._nfo_root.findtext("director") or self.__get_default("director"),
            "details": self._nfo_root.findtext("plot") or self._nfo_root.findtext("outline") or self._nfo_root.findtext("tagline") or self.__get_default("details"),
            "studio": self._nfo_root.findtext("studio") or self.__get_default("studio"),
            "date": self.__extract_nfo_date() or self.__get_default("date"),
            "actors": self.__extract_nfo_actors() or self.__get_default("actors"),
            # tags are merged with defaults
            "tags": list(set(self.__extract_nfo_tags() + self.__get_default("tags"))),
            "rating": self.__extract_nfo_rating() or self.__get_default("rating"),
            "cover_image": None if len(b64_images) < 1 else b64_images[0],
            "other_image": None if len(b64_images) < 2 else b64_images[1],
            # Below are NFO extensions or liberal tag interpretations (not part of the standard KODI tags)
            "movie": self._nfo_root.findtext("set/name") or self.__get_default("title", "nfo"),
            "scene_index": self._nfo_root.findtext("set/index"),
            "url": self._nfo_root.findtext("url"),
        }
        return file_data
