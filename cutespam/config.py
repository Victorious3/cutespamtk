from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

class BaseConfig:
    # Values that can't be modified (i.e they depend on other settings)
    metadbf: Path
    hashdbf: Path
    imgcache: Path

@dataclass
class Config(BaseConfig):
    service_port: int = 14400
    hash_length: int = 256

    thumbnail_size: int = 256
    thumbnail_min_filesize: int = 100

    useragent: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/73.0.3683.75 Chrome/73.0.3683.75 Safari/537.3"
    download_chunk_size: int = 4096

    image_folder: Path = "~/Pictures/Cutespam"
    cache_folder: Path = None
    log_folder: Path = None
    
    extensions: Tuple[str] = ("jpg", "png", "jpeg")
    tag_regex: str = r"[!-)+-9;-~]+"

    trace_debug: bool = False

config = Config()

NAME = "Cutespam"
ORG = "Nightfall"

IS_DEV = None # are we running a development version?

def _read_config():
    import appdirs
    import yaml

    global IS_DEV

    cfgf_name = "config.yml"
    cfgf = None
    basef = Path(__file__).parent.parent

    # first check if we're inside a git repo
    gitf = basef / ".git"
    if gitf.exists():
        IS_DEV = True
        cfgf = basef / cfgf_name
    else:
        # now look inside the config directory for the system
        cfgf = Path(appdirs.user_config_dir(NAME, ORG)) / cfgf_name

    if not cfgf.exists():
        cfgf.parent.mkdir(parents = True, exist_ok = True)
        with open(cfgf, "w") as ymlf:
            yaml.safe_dump(vars(config), ymlf, default_flow_style = False, sort_keys = False)
    else:
        with open(cfgf, "r") as ymlf:
            ymlo = yaml.safe_load(ymlf)
            if ymlo:
                vars(config).update(ymlo)

    # Sanitize values
    if not config.cache_folder:
        config.cache_folder = appdirs.user_cache_dir(NAME, ORG)
    if not config.log_folder:
        config.log_folder = appdirs.user_log_dir(NAME, ORG)

    config.image_folder = Path(config.image_folder).expanduser()
    config.image_folder.mkdir(parents = True, exist_ok = True)
    config.cache_folder = Path(config.cache_folder).expanduser()
    config.cache_folder.mkdir(parents = True, exist_ok = True)
    config.log_folder = Path(config.log_folder).expanduser()
    config.log_folder.mkdir(parents = True, exist_ok = True)

    config.metadbf = config.cache_folder / "metadata.db"
    config.hashdbf = config.cache_folder / "hashes.db"
    config.imgcache = config.cache_folder / "imgcache"
    config.imgcache.mkdir(parents = True, exist_ok = True)

    config.tag_regex = config.tag_regex.replace("'", "\\'").replace('"', '\\"')

    config.extensions = ["." + e for e in config.extensions]
_read_config()