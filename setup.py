from setuptools import setup

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup (
    name = "cutespam",
    version = "0.0.1",
    description = "Cutespam CLI",
    author = "Vic Nigthtfall",
    author_email = "vic@nightfall.moe",
    packages = [
        "cutespam",
        "cutespam.cli",
        "cutespam.cli.commands"
    ],
    install_requires = requirements,
    entry_points = {
        "console_scripts": [
            'cutespam = cutespam.cli.cutespam:main',
            'cutespam-rest = cutespam.cli.rest:main',
            "iqdb = cutespam.cli.iqdb:main"
        ]
    }
)