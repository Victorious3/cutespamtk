from glob import glob
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup (
    name = "cutespam",
    python_requires = ">3.6.0",
    version = "0.1.0",
    description = "Cutespam CLI",
    author = "Vic Nightfall",
    author_email = "vic@nightfall.moe",
    packages = find_packages(),
    install_requires = requirements,
    extras_require = {
        "autocomplete": ["argcomplete>=1.9.5"]
    },
    entry_points = {
        "console_scripts": [
            "cutespam = cutespam.cli.cli:main",
            "cutespam-rest = cutespam.cli.rest:main",
            "cutespam-db = cutespam.cli.service:main",
            "cutespam-app = cutespam.app.app:main",
            "iqdb = cutespam.cli.iqdb:main"
        ]
    },
    scripts = {
        "native_wrapper/install.py"
    },
    options = {
        "bdist_wininst": {
            "install_script" : "install.py", 
        }
    },
    data_files = [
        ("native_wrapper", glob("native_wrapper/native-wrapper.bat")),
        ("native_wrapper/chrome", glob("native_wrapper/chrome/*")),
        ("native_wrapper/firefox", glob("native_wrapper/firefox/*"))
    ]
)