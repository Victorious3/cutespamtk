
import urllib
import urllib.error
import urllib.request

import ssl
import validators
import json
import re

from bs4 import BeautifulSoup
from xml.dom import minidom

from cutespam import log
from cutespam import make_request, decode_all
from cutespam.config import config


class Provider:
    regex = None
    service = None
    def __init__(self, url, regm = None):
        self.url = url
        self.src = []
        self.meta = {}
        self.status = 200
        self.exception = None
        self._regm = regm or re.match(self.regex, url)

    def _fetch(self): return

    def fetch(self, update_sources = True, probe = False, ratelimit_retry = False):
        try:
            if update_sources and probe:
                make_request(self.url, 'HEAD', ratelimit_retry)
            if update_sources:
                self._fetch()
        except urllib.error.HTTPError as e:
            self.status = e.code
        except urllib.error.URLError as e:
            self.status = 400  
        except ssl.CertificateError:
            self.status = 495
        except Exception as e:
            self.exception = e
            self.status = 400

        if type(self) == Other: self.status == 200

    def __lt__(self, other):
        si = ALL_PROVIDERS.index(type(self))
        oi = ALL_PROVIDERS.index(type(other))
        return si < oi

    @staticmethod
    def for_url(url):
        for pr in PROVIDERS:
            rm = re.match(pr.regex, url)
            if rm:
                return pr(url, rm)
        return Other(url)

class Other(Provider):
    regex = r".*"

class Direct(Provider):
    regex = r".*(" + "|".join(config.extensions) + ")$"
    def _fetch(self):
        self.src = [self.url]

class DanbooruImage(Direct):
    regex = r".*donmai.us.*__.*drawn_by_(?P<author>.*)__(?P<uid>[A-z0-9]+)\.(?P<ext>.*)"
    service = "danbooru"

    def _fetch(self):
        self.meta["author"] = self._regm["author"]
        self.meta["uid"] = self._regm["uid"]
        self.src = [self.url]

class DanbooruImageFmt2(Direct):
    regex = r".*donmai.us.*/(?P<uid>[A-z0-9]+)\.(jpg|jpeg|png)$"
    service = "danbooru"

    def _fetch(self):
        self.meta["uid"] = self._regm["uid"]

class SafebooruImage(Direct):
    regex = r".*safebooru.org/(/)?images/.*"
    service = "safebooru"

class TwitterImage(Direct):
    regex = r".*pbs.twimg.com.*"
    service = "twitter"

class DanbooruPost(Provider):
    regex = r".*danbooru.donmai.us/posts/(?P<id>.*)"
    service = "danbooru"

    def _fetch(self):
        response = make_request("https://danbooru.donmai.us/posts/" + self._regm["id"] + ".json", "GET")
        with response as file:
            text = decode_all(file)
            data = json.loads(text)
            if "tag_string_artist" in data: self.meta["author"] = data["tag_string_artist"]
            if "tag_string_character" in data:
                characters = data["tag_string_character"].strip()
                if characters: self.meta["character"] = characters.split(" ")

            self.meta["rating"] = data["rating"]
            self.meta["uid"] = data["md5"]
            self.src.append(data["file_url"])
            if "source" in data:
                dsrc = data["source"]
                if validators.url(dsrc):
                    self.src.append(dsrc)

class SafebooruPost(Provider):
    regex = r".*safebooru.org.*(id=(?P<id>[\d]+)).*"
    service = "safebooru"

    def _fetch(self):
        url = "https://safebooru.org/index.php?page=dapi&s=post&q=index&limit=1&id=" + self._regm.group("id")
        response = make_request(url, "GET")
        with response as file:
            text = decode_all(file)

        data = minidom.parseString(text).childNodes[0].childNodes[0]
        
        self.src.append("http:" + data.getAttribute("file_url"))
        source = data.getAttribute("source")
        if source and validators.url(source): self.src.append(source)
        rating = data.getAttribute("rating")
        if rating: self.meta["rating"] = rating

class Zerochan(Provider):
    regex = r".*zerochan.net/(full/)?(?P<id>[\d]+)"
    service = "zerochan"

    def _fetch(self):
        response = make_request("https://www.zerochan.net/full/" + self._regm.group("id"), "GET") # TODO Can't access nsfw pictures
        with response as file:
            text = decode_all(file)
        
        html = BeautifulSoup(text, features = "html.parser")
        data = html.select('img[alt*="Tags"]')[0]
        self.src.append(data["src"])

class ShuuShuu(Provider):
    regex = r".*e-shuushuu.net/image/.*"
    service = "shuushuu"

    def _fetch(self):
        response = make_request(self.url, "GET")
        with response as file:
            text = decode_all(file)

        html = BeautifulSoup(text, features = "html.parser")
        data = html.select("a.thumb_image")[0]
        url = "http://e-shuushuu.net" + data["href"]
        self.src.append(url)

class TwitterStatus(Provider):
    regex = r".*twitter.com.*/status/\d*(/photo/(?P<photo_nr>[\d]))?"
    service = "twitter"

    def _fetch(self):
        response = make_request(self.url, "GET")
        with response as file:
            text = decode_all(file)

        html = BeautifulSoup(text, features = "html.parser")
        #data = [(e.parent.parent["class"], e) for e in html.select("div[data-image-url]")]
        #
        #first = data[0]
        #if   "AdaptiveMedia-doublePhoto" in first[0]: amount = 2
        #elif "AdaptiveMedia-triplePhoto" in first[0]: amount = 3
        #elif "AdaptiveMedia-quadPhoto"   in first[0]: amount = 4
        #else: amount = 1 # TODO Check if format was changed
        #
        #self.src.append(first[1]["data-image-url"])
        #if amount > 1:
        #    self.meta["additional"] = [e[1]["data-image-url"] for i, e in enumerate(data) if 0 < i < amount]

        index = int(self._regm.group("photo_nr") or 1) - 1
        data = html.select("div[tabindex='0']")[0].select("div[data-image-url]")[index]
        self.src.append(data["data-image-url"])

class HoloCroma(Provider):
    regex = r".*holo.croma25td.com/.*"

    def _fetch(self):
        raise urllib.error.URLError("holo.croma25td.com has shut down")

PROVIDERS = [DanbooruImage, DanbooruImageFmt2, SafebooruImage, TwitterImage, HoloCroma, Direct, DanbooruPost, SafebooruPost, Zerochan, ShuuShuu, TwitterStatus]
META_PROVIDERS = [DanbooruPost, SafebooruPost]
UUID_PROVIDERS = [DanbooruImage, DanbooruImageFmt2]
ALL_PROVIDERS = PROVIDERS + [Other]