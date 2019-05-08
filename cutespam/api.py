import requests
import hashlib
import shutil

from PIL import Image
from io import BytesIO
from dataclasses import dataclass
from typing import List
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime

from cutespam.meta import CuteMeta, Rating
from cutespam.hash import hash_img
from cutespam.db import find_similar_images_hash, filename_for_uid
from cutespam.providers import Provider
from cutespam.iqdb import iqdb, upscale
from cutespam.config import config

class APIException(Exception): pass

__api_functions = {}

# Make sure that we don't call random stuff
def apifun(fun):
    __api_functions[fun.__name__] = fun
    return fun
def get_apifun(name):
    apifun = __api_functions.get(name)
    if not apifun:
        raise APIException("Invalid api function " + name)
    return apifun

@apifun
def clear_cache():
    shutil.rmtree(config.imgcache)
    config.imgcache.mkdir(parents = True, exist_ok = True)

def get_cached_file(img) -> Path:
    md5 = hashlib.md5(img.encode()).hexdigest()
    file = config.imgcache / ((md5) + ".jpg")
    if not file.exists():
        file = file.with_suffix(".png")

    if not file.exists():
        req = requests.get(img)
        mime = req.headers["content-type"]
        if mime == "image/jpeg":    # TODO respect config.extensions
            ext = ".jpg"
        elif mime == "image/png":
            ext = ".png"
        else: raise APIException("Incompatible image format")

        file = file.with_suffix(ext)
        with open(file, "wb") as fp:
            fp.write(req.content)
    
    return file

@dataclass
class FetchUrlResult:
    img: str
    service: str

@apifun
def fetch_url(url) -> FetchUrlResult:
    provider = Provider.for_url(url)
    provider.fetch()

    result = FetchUrlResult(
        img = provider.src[0] if provider.src else url, 
        service = type(provider).service
    )

    if provider.meta:
        result.__dict__.update(provider.meta)
    
    return result

@dataclass
class IQDBResult:
    img: str
    service: str
    # Other parameters as part of dict

@apifun
def iqdb_upscale(img, threshold = 0.9, service = None) -> IQDBResult:
    results = iqdb(url = img, threshold = threshold)
    if not results:
        raise ValueError("No result found")

    # need to download file to get size :/
    with Image.open(get_cached_file(img)) as imgf:
        width, height = imgf.size
        resolution = width * height

    found_img, meta, service = upscale(results, resolution, service)

    img = found_img or img
    
    src = set(meta["src"])
    src.discard(img)
    meta["src"] = list(src)
    
    result = IQDBResult(img = img, service = service)
    result.__dict__.update(meta)
    return result

@dataclass
class SimilarImage:
    similarity: float
    uid: UUID
    file: str

@apifun
def download_or_show_similar(data: dict, threshold = 0.9) -> List[SimilarImage]:
    file = get_cached_file(data["img"])
    h = hash_img(file)
    similar = find_similar_images_hash(h, threshold)
    if similar:
        return [SimilarImage(s[0], s[1], filename_for_uid(s[1]).name) for s in similar]
    return download(data)

@apifun
def download(data: dict):
    file = get_cached_file(data["img"])
    meta: CuteMeta = CuteMeta.from_file(file)
    if "uid" in data:
        meta.uid = UUID(data["uid"])
    else:
        meta.uid = uuid4()

    meta.source = data["img"]
    meta.keywords = set()
    meta.hash = hash_img(file)
    meta.date = datetime.utcnow()

    if "author" in data: 
        meta.author = data["author"]
    if "caption" in data:
        meta.caption = data["caption"]
    if "character" in data: 
        meta.keywords |= set("character:" + c for c in data["character"])
    if "collections" in data: 
        meta.collections = set(data["collections"])
    if "rating" in data:
        meta.rating = Rating(data["rating"])
    if "src" in data:
        meta.source_other = set(data["src"])
    if "via" in data:
        meta.source_via = set(data["via"])
    
    meta.generate_keywords()
    meta.write()
    meta.release() # Windows hack
    shutil.move(str(file), str(config.image_folder / (str(meta.uid) + file.suffix)))

    
@apifun
def get_config():
    return config

@apifun
def set_config(**kwargs):
    vars(config).update(kwargs)