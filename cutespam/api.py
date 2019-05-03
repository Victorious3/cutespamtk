import requests

from PIL import Image
from io import BytesIO
from dataclasses import dataclass
from typing import List

from cutespam.providers import Provider
from cutespam.iqdb import iqdb
from cutespam.config import config

class APIException(Exception): pass

__api_functions = {}

# Make sure that we don't call random stuff
def _apifun(fun):
    __api_functions[fun.__name__] = fun
    return fun
def _get_apifun(name):
    apifun = __api_functions.get(name)
    if not apifun:
        raise APIException("Invalid api function " + name)
    return apifun

@dataclass
class FetchUrlResult:
    img: str
    service: str

@_apifun
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

@_apifun
def iqdb_upscale(img, threshold = 0.9, service = None):
    results = [i for i in iqdb(url = img) if i.similarity >= threshold]
    if not results:
        raise ValueError("No result found")

    # need to download file to get size :/
    # this means we need to download it multiple times, TODO make a cache? 
    req = requests.get(img)
    with Image.open(BytesIO(req.content)) as imgf:
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

@_apifun
def get_config():
    return config

@_apifun
def set_config(**kwargs):
    vars(config).update(kwargs)