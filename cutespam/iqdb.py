import requests
import re
import argparse
import validators
import time
import json
import itertools

from enum import Enum
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Tuple
from pathlib import Path

from cutespam.providers import Provider

URL = "https://iqdb.org/"

class IQDBException(Exception): pass

class Field:
    service = "service[]"
    file = "file"
    url = "url"

class Service(Enum):
    Danbooru = "Danbooru"
    Konachan = "Konachan"
    Yande_re = "yande.re"
    Gelbooru = "Gelbooru"
    Sankaku_Channel = "Sankaku Channel"
    E_shuushuu      = "e-shuushuu"
    Zerochan        = "Zerochan"
    Anime_Pictures  = "Anime-Pictures"
    Other = "Other"

@dataclass
class Result:
    provider: Service
    similarity: float
    url: str
    rating: str
    size: Tuple[int, int]

def decode_result(table):
    rows = table.select("tr")
    if len(rows) == 5: # Remove header
        rows = rows[1:]
    if len(rows) != 4:
        return None # No relevant matches

    image = rows[0]
    providers = rows[1]
    meta = rows[2]
    similarity = rows[3]

    url = image.select_one("a")["href"]
    if url.startswith("//"):
        url = "https:" + url # wtf
    
    provider = Service(providers.select_one("td").contents[1].string.strip())
    meta = re.match(r"(?P<width>[\d]+)×(?P<height>[\d]+) \[(?P<rating>.*)\]", 
        meta.select_one("td").text.strip())
    if not meta: return None

    size = int(meta["width"]), int(meta["height"])
    rating = meta["rating"]
    similarity = int(re.match(r"([\d]+)% similarity", similarity.text)[1]) / 100

    result = Result(provider, similarity, url, rating, size)
    return result

def decode_results_nao(jsn):
    data = jsn["data"]
    similarity = float(jsn["header"]["similarity"]) / 100
    if not "ext_urls" in data:
        return
    for url in data["ext_urls"]:
        yield Result(Service.Other, similarity, url, "????", (0, 0))

def iqdb(url = None, file = None, saucenao = False, threshold = None):
    if file:
        req = requests.post(URL, files = {Field.file: file})
    elif url:
        req = requests.post(URL, data = {Field.url: url})
    else:
        raise ValueError("Need to specifiy url or file")

    if req.status_code != 200:
        if req.status_code == 413:
            raise IQDBException("File size too large!")
        raise IQDBException("IQDB returned status code " + str(req.status_code))

    html = BeautifulSoup(req.text, features = "html.parser")
    data = html.select("#pages table") + html.select("#more1 .pages table")
    results = list(filter(None.__ne__, map(decode_result, data[1:]))) # First one is own image, skip that

    if saucenao:
        iqdb_urls = set(r.url for r in results)

        snlink = html.select_one('a[href*="saucenao.com"]')["href"]
        snlink += "&output_type=2"
        if snlink.startswith("//"):
             snlink = "https:" + snlink

        req = requests.get(snlink)
        data = json.loads(req.text)["results"]
        for result in itertools.chain(*map(decode_results_nao, data)):
            url = result.url
            # Convert old danbooru urls
            sr = url.split("https://danbooru.donmai.us/post/show/")
            if len(sr) > 1:
                url = "https://danbooru.donmai.us/posts/" + sr[1]

            if not url in iqdb_urls:
                results.append(result)

    results = sorted(results, key = lambda r: r.similarity, reverse = True)
    if threshold:
        results = [i for i in results if i.similarity >= threshold]
    return results


def upscale(iqdb_res, resolution, service = "file"):
    found_img = None
    src = []
    meta = {}

    # extract providers:
    providers = sorted([Provider.for_url(r.url) for r in iqdb_res])
    for provider in providers: provider.fetch()

    for result, provider in zip(iqdb_res, providers):
        if not provider.src: continue

        src += provider.src
        src += [provider.url]

        meta.update(provider.meta) # TODO This might fail if it finds multiple metas

        r_resolution = result.size[0] * result.size[1]
        if not found_img and (r_resolution > resolution or service in ("twitter", "file")):
            # Found a better image, yay
            found_img = provider.src[0]
            service = type(provider).service
            resolution = r_resolution

    meta["src"] = src

    return found_img, meta, service
