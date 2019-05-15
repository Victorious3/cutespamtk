import argparse
from cutespam.cli import argrange

DESCRIPTION = """\
Cutespam importer.

The input file is specified in JSON.

The format is as follows:
[{
    "img": Link to raw image file,
    "src": [
        List of additional sources
    ],
    "via": [
        List of links where the image is used
    ],
    "meta": {
        "author": Author of the image,
        "rating": Rating for the image. Possible values are "s", "n", "q" and "e",
        "caption": Short description of the image,

        "character": [
            List of characters seen in the image
        ]
        "keywords": [
            List of keywords for the image
        ],
        "collections": [
            List of collections to add the image to
        ]
    }
}, 
    Additional elements can follow here
]

A group can be created by wrapping multiple images inside a list"""

def main(ARGS):
    raise NotImplementedError() # TODO Need to rewrite this if needed
    
    import time
    START_TIME = time.time()

    import urllib, time, ssl, sys, json, math, os
    import urllib.error
    import urllib.request
    import atpbar

    from datetime import datetime
    from collections import Counter
    from multiprocessing import Pool
    from uuid import UUID, uuid4
    from urllib.parse import urlparse
    from pathlib import Path

    from cutespam import make_request
    from cutespam.config import config
    from cutespam.xmpmeta import CuteMeta
    from cutespam.hash import hash_img
    from cutespam.providers import Provider, Other, META_PROVIDERS, UUID_PROVIDERS # TODO This shouldn't need to happen here

    class Logger(object):
        def __init__(self, logf):
            self.terminal = sys.stdout
            self.log = open(logf, "a")

        def write(self, message):
            self.terminal.write(message)
            self.log.write(message)  

        def flush(self): pass

        def isatty(self): return self.terminal.isatty()

    def flatten_groups(jsn):
        group = 1
        group_uid = 0
        for element in jsn:
            if isinstance(element, list) and len(element) > 0:
                group_uid = element[0].get("meta", {}).get("uid", None)
                for elem in element:
                    elem["group"] = group
                    if ARGS.update_groups and group_uid:
                        meta = elem.get("meta", {})
                        meta["group_id"] = group_uid
                        elem["meta"] = meta
                    yield elem
                group += 1
            else: yield element

    def extract_groups(elements):
        res = []
        curr_group_id = 0
        curr_group = []

        for elem in elements:
            if "group" in elem:
                g = elem["group"]
                del elem["group"]
                if g != curr_group_id:
                    if curr_group: res.append(curr_group)
                    curr_group_id = g
                    curr_group = []
                curr_group.append(elem)
            else:
                if curr_group:
                    res.append(curr_group)
                    curr_group = []
                    curr_group_id = 0
                res.append(elem)

        if curr_group: res.append(curr_group)
        
        return res

    def pull_providers(jsn):
        if "img" in jsn:
            yield Provider.for_url(jsn["img"])
        if "src" in jsn:
            src = jsn["src"]
            if isinstance(src, list): 
                yield from sorted(Provider.for_url(s) for s in src)
            else: yield Provider.for_url(src)

    def filter_meta_providers(providers):
        existing_types = set()  # make sure to only pull them once
        for provider in providers:
            tprv = type(provider)
            if tprv in META_PROVIDERS and tprv not in existing_types:
                existing_types.add(tprv)
                yield provider

    def analzye(all_in):
        all_providers = []
        img_providers = []

        print("Total elements:", str(len(all_in)))

        for elem in all_in:
            provs = list(pull_providers(elem))
            assert len(provs) > 0, "broken element %s" % elem

            all_providers += provs
            img_providers.append(provs[0])

        print("Counts:")
        cnt = Counter(type(p).__name__ for p in all_providers)
        for k, v in cnt.items():
            print("{:>14}: {}".format(str(k), v))
        print("Unknown urls:", len([e.url for e in all_providers if type(e) == Other]))
        unnkown = [e.url for e in img_providers if type(e) == Other]
        print("Unknown urls after sort:", len(unnkown))
        print("\n".join(unnkown))
        cnt = Counter(e.url for e in all_providers)
        duplicate = [l for l, c in cnt.items() if c > 1]
        print("Duplicate urls:", len(duplicate))
        print("\n".join(duplicate))

    def filter_duplicates(all_in):
        # TODO Doesn't find duplicates inside a group yet
        def convert_to_hashable(e):
            if isinstance(e, list):
                return tuple(map(convert_to_hashable, e))
            elif isinstance(e, dict):
                return tuple((convert_to_hashable(k), convert_to_hashable(v)) for k, v in e.items())
            else:
                return e

        seen = set()
        filtered = []
        for elem in all_in:
            t = convert_to_hashable(elem)
            if not t in seen:
                seen.add(t)
                filtered.append(elem)
            
        print("Duplicate Entires:", len(all_in) - len(filtered))
        return filtered


    def update(elem):
        provs = list(pull_providers(elem))
        meta_provs = list(filter_meta_providers(provs))
        assert len(provs) > 0, "broken element %s" % elem
        
        for provider in provs:
            provider.fetch(update_sources = ARGS.update_sources, probe = ARGS.probe, ratelimit_retry = ARGS.ratelimit_retry)
            if ARGS.probe:
                print("%s: %s" % (provider.status, provider.url))
            elif provider.status == 200:
                meta_provs = filter(lambda p: type(p) != type(provider), meta_provs) # make sure to only query metadata once
                break
            else:
                print("Url", provider.url, "returned status", provider.status)
        else:
            if ARGS.update_sources:
                print("Couldn't find working source for element:")
                print(elem)
                return elem
        
        src = provider.src
        meta = provider.meta
        url = provider.url

        if ARGS.update_sources and ARGS.update_metadata:
            for mprov in meta_provs:
                print("Fetching additional metadata from", mprov.url)
                mprov.src = src
                mprov.meta = meta
                mprov.fetch(update_sources = ARGS.update_sources, probe = ARGS.probe, ratelimit_retry = ARGS.ratelimit_retry)  
                if mprov.status != 200:
                    print("Meta url", mprov.url, "return status", mprov.status)          


        if ARGS.update_sources and provider.src:
            if not "img" in elem:
                img = src[0]
                elem["img"] = src[0]
                print("Found source image", img, "from url", url)
            
            if len(provider.src) > 1:
                sources = set(src[1:])
                if "src" in elem: 
                    if isinstance(elem["src"], list): 
                        sources |= set(elem["src"])
                    else: sources.add(elem["src"])
                sources = list(sources) # remove duplicates
                if "img" in elem and elem["img"] in sources:
                    sources.remove(elem["img"])
                    
                elem["src"] = sources
            
            if ARGS.update_metadata and meta:
                if "meta" in elem:
                    elem["meta"].update(meta)
                else:
                    elem["meta"] = meta

        return elem

    def update_sources(sources):
        pool = Pool(ARGS.workers)
        return pool.map(update, sources)

    def update_uids(sources):
        for elem in sources:
            meta = elem["meta"] if "meta" in elem else {}
            if "uid" in meta:
                continue
            else:
                uid = None
                uuid_providers = [p for p in pull_providers(elem) if type(p) in UUID_PROVIDERS]
                if uuid_providers:
                    uuid_prov = uuid_providers[0]
                    uuid_prov._fetch() # TODO: Bit ugly
                    uid = uuid_prov.meta["uid"]
                else: uid = str(uuid4().hex)

                meta["uid"] = uid
            elem["meta"] = meta

    def download_img(source):
        
        img = source.get("img", None)
        meta = source.get("meta", {})
        uid = meta.get("uid", None)
        if not img:
            log("No image supplied for\n" + str(source))
            return
        if not uid:
            log("No uid for\n" + str(source))

        try:
            url = urlparse(img)
            filename = os.path.basename(url.path)
            _, ext = os.path.splitext(filename)
            tmpfile = Path(ARGS.out_folder) / (filename + ".tmp")
            imgfile = Path(ARGS.out_folder) / (str(UUID(uid)) + ext)

            response = make_request(img, "GET")
            header = response.info()
            cnt_type = header["Content-Type"]
            if cnt_type not in ("image/jpeg", "image/png"):
                log("Unknown content type", cnt_type, "for", img)
                return
            size = int(header["Content-Length"])
            size_mb = size / 1_000_000
            if size_mb > ARGS.max_filesize:
                log("%s is too big! You specified a maximum size of %d MB, file is %.2f MB" % (img, ARGS.max_filesize, size_mb))
                return
            
            total_chunks = math.ceil(size / config.download_chunk_size)
            with response as stream:
                with open(tmpfile, "wb") as outf:
                    log("Starting download of", img)
                    for _ in atpbar.atpbar(range(total_chunks), name = img):
                    #for _ in range(total_chunks):
                        chunk = stream.read(config.download_chunk_size)
                        if not chunk:
                            break
                        outf.write(chunk)

            os.rename(tmpfile, imgfile)

            xmpfile = imgfile.with_suffix(".xmp")
            cute_meta = CuteMeta.from_file(xmpfile)
            cute_meta.clear() # Delete all unwanted tags

            log("Generating image hash for file", imgfile)
            cute_meta.hash = hash_img(imgfile)
            log("Hashed", imgfile, "as", cute_meta.hash, "(phash, 16)")

            cute_meta.read_from_dict(meta, ignore_missing_keys = True)
            cute_meta.add_characters(*meta.get("character", []))
            cute_meta.source = img
            cute_meta.source_other = source.get("src", [])
            cute_meta.source_via = source.get("via", [])
            cute_meta.date = datetime.utcnow()
            cute_meta.write()

        except urllib.error.HTTPError as e:
            status = e.code
        except urllib.error.URLError as e:
            status = 400  
        except ssl.CertificateError:
            status = 495
        except Exception as e:
            log("An exception occured while fetching url %s: %s" % (img, str(e)))
            status = 0
        else:
            status = 200
        
        if status and status != 200:
            log("%s: %s" % (status, img))
        

    def download_images(sources):
        if ARGS.out_folder:
            assert os.path.exists(ARGS.out_folder) and not os.path.isfile(ARGS.out_folder), "Need to specify an existing folder"
        else:
            ARGS.out_folder = "."

        def init_progressbar(reporter):
            atpbar.register_reporter(reporter)

        reporter = atpbar.find_reporter()
        pool = Pool(ARGS.workers, init_progressbar, initargs = (reporter,))
        pool.map(download_img, sources)

    LOGGER = None
    def log(*args):
        #print(*args) TODO
        pass

    if ARGS.log_file:
        LOGGER = Logger(ARGS.log_file)
        sys.stdout = LOGGER

    with open(ARGS.in_file.name, "r") as file:
        all_in = json.load(file)
    all_in = list(flatten_groups(all_in))

    if ARGS.analyze:
        analzye(all_in)
    if ARGS.filter_duplicates:
        all_in = filter_duplicates(all_in)
    if ARGS.update_sources or ARGS.probe:
        all_in = update_sources(all_in)
    if ARGS.update_uids:
        update_uids(all_in)
    if ARGS.download:
        download_images(all_in)

    if not ARGS.read_only:
        with open((ARGS.out_file or ARGS.in_file).name, "w") as file:
            json.dump(extract_groups(all_in), file, indent = "\t")

    END_TIME = time.time()

    print(f"Took {END_TIME - START_TIME:.2f} seconds to complete.")

def args(parser):
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--probe", action = "store_true", help = "Checks all source urls for up status")
    o_update = options.add_argument_group("update")
    o_update.add_argument("--update-sources", action = "store_true", help = "Updates image links and pulls additional sources when available")
    o_update.add_argument("--update-meta", action = "store_true", help = "Pulls metadata from all available sources, such as author mame")
    options.add_argument("--download", action = "store_true", help = "Downloads the image and writes all metadata to it. Make sure to use --update-sources and --update-meta before.")
    
    parser.add_argument("--analyze", action = "store_true", help = "Prints various stats about the input file")
    parser.add_argument("--filter-duplicates", action = "store_true", help = "Filters duplicate entires. Useful for large data sets")
    parser.add_argument("--no-update-groups", dest = "update_groups", action = "store_false", help = "Ignores groups")
    parser.add_argument("--no-update-uids", dest = "update_uids", action = "store_false", help = "Skip missing uids")
    
    parser.add_argument("--out-file", type = argparse.FileType(),
        help = "Sets a seperate output file for the updated metadata. Useful for debugging")
    parser.add_argument("--read-only", "-r", action ="store_true", help = "Don't write processed input to file")

    extra = parser.add_argument_group("Advanced options")
    extra.add_argument("--log-file",
        help = "Redirects stdout to an additional log file")
    extra.add_argument("--workers", default = 8, type = int, choices = argrange(1, 64), metavar = "[1-64]",
        help = "Number of parallel worker threads to download")
    extra.add_argument("--delay", default = 30, type = int, choices = argrange(0, 10000), metavar = "[1-10000]",
        help = "Delay after each successful request to avoid possible rate limits")
    extra.add_argument("--ratelimit-retry", action = "store_true",
        help = "Supports HTTP status 429, retries after the time specified in the header")
    extra.add_argument("--max-filesize", default = 20, type = int, choices = argrange(1, 5000000), metavar = "[>1]")

    parser.add_argument("in_file", type = argparse.FileType(), 
        help = "Input file with json formatted list of input files")
    

    parser.add_argument("out_folder", nargs = "?", help = "Folder to download images to. Current folder if not specified.")