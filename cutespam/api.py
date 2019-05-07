import requests
import hashlib

from PIL import Image
from io import BytesIO
from dataclasses import dataclass
from typing import List
from pathlib import Path
from shutil import rmtree

from cutespam.hash import hash_img
from cutespam.db import find_similar_images_hash
from cutespam.providers import Provider
from cutespam.iqdb import iqdb
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
    rmtree(config.imgcache)
    config.imgcache.mkdir(parents = True, exist_ok = True)

def get_cached_file(img) -> Path:
    md5 = hashlib.md5(img.encode()).hexdigest()
    file = config.imgcache / ((md5) + ".jpg")
    if not file.exists():
        file = file.with_suffix(".png")

    if not file.exists():
        req = requests.get(img)
        mime = req.headers["content-type"]
        if mime == "image/jpeg":
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
    src: List[str]

@apifun
def iqdb_upscale(img, threshold = 0.9, service = None) -> IQDBResult:
    results = [i for i in iqdb(url = img) if i.similarity >= threshold]
    if not results:
        raise ValueError("No result found")

    # need to download file to get size :/
    # this means we need to download it multiple times, TODO make a cache? 
    with Image.open(get_cached_file(img)) as imgf:
        width, height = imgf.size
        resolution = width * height

    found_img = None
    src = []
    meta = {}

    # extract providers:
    providers = sorted([Provider.for_url(r.url) for r in results])
    for provider in providers: provider.fetch()

    for result, provider in zip(results, providers):
        if not provider.src: continue

        src += provider.src
        src += [provider.url]

        meta.update(provider.meta) # TODO This might fail if it finds multiple metas

        r_resolution = result.size[0] * result.size[1]
        if not found_img and (r_resolution > resolution or service == "twitter"):
            # Found a better image, yay
            img = provider.src[0]
            service = type(provider).service
            resolution = r_resolution

    img = found_img or img
    src = set(src)
    try: src.remove(img) 
    except: pass
    
    result = IQDBResult(img = img, src = list(src), service = service)
    result.__dict__.update(meta)
    return result

@apifun
def download(img, **kwargs):
    pass

@apifun
def download_or_show_similar(data: dict, threshold = 0.9):
    file = get_cached_file(data["img"])
    h = hash_img(file)
    similar = find_similar_images_hash(h, threshold * 100)
    if similar:
        return similar
    return None # OK
    
@apifun
def get_config():
    return config

@apifun
def set_config(**kwargs):
    vars(config).update(kwargs)