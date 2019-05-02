from dataclasses import dataclass

@dataclass
class Config:
    service_port: int = 14400
    hash_length: int = 256

    thumbnail_size: int = 256
    thumbnail_min_filesize: int = 100

    image_folder: str = "~/Pictures/Cutespam"
    cache_folder: str = None

config = Config()

NAME = "Cutespam"
ORG = "Nightfall"

IS_DEV = None # are we running a development version?

def _read_config():
    import appdirs
    import yaml

    from pathlib import Path

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
        cfgf = Path(appdirs.user_config_dir(NAME, ORG, roaming = True)) / cfgf_name

    if not cfgf.exists():
        cfgf.parent.mkdir(parents = True, exist_ok = True)
        with open(cfgf, "w") as ymlf:
            yaml.safe_dump(vars(config), ymlf, default_flow_style = False, sort_keys = False)
    else:
        with open(cfgf, "r") as ymlf:
            ymlo = yaml.safe_load(ymlf)
            if ymlo:
                vars(config).update(ymlo)

_read_config()