#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import glob
import subprocess

from setuptools import setup, find_packages, Extension

from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the relevant file
with open(path.join(here, 'DESCRIPTION.rst'), encoding='utf-8') as f:
    long_description = f.read()

def get_libboost_name():
    """Returns the name of the lib libboost_python 3

    """
    # libboost libs are provided without .pc files, so we can't use pkg-config
    places = ('/usr/lib/', '/usr/local/lib/', '/usr/')
    for place in places:
        cmd = ['find', place, '-name', 'libboost_python*']
        rep = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
        if not rep:
            continue

        # rep is type bytes
        libs = rep.decode(sys.getfilesystemencoding()).split('\n')
        for l in libs:
            _, l = os.path.split(l)
            if '.so' in l:
                l = l.split('.so')[0]
                # Assume there's no longer python2.3 in the wild
                if '3' in l[-2:]:
                    return l.replace('libboost', 'boost')

if os.name == 'nt':
    basep = os.environ["VCPKG"] + r"\installed\x64-windows"
    os.environ["INCLUDE"] = basep + r"\include"
    libboost = basep + r"\lib\boost_python37-vc140-mt"
    libexiv = basep + r"\lib\exiv2"
    extra_compile_args = []
else:
    libboost = get_libboost_name()
    extra_compile_args = ['-g']
    libexiv = 'exiv2'

setup(
    name='py3exiv2',
    version='0.7.0',
    description='A Python3 binding to the library exiv2',
    long_description=long_description,
    url='https://launchpad.net/py3exiv2',
    author='Vincent Vande Vyvre',
    author_email='vincent.vandevyvre@oqapy.eu',
    license='GPL-3',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: C++',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    keywords='exiv2 pyexiv2 EXIF IPTC XMP image metadata',
    packages = find_packages('src'),
    package_dir = {'': 'src'},
    package_data={'':['src/*.cpp', 'src/*.hpp',]},
    #cmdclass={'install': install}
    ext_modules=[
    Extension('libexiv2python',
        ['src/exiv2wrapper.cpp', 'src/exiv2wrapper_python.cpp'],
        include_dirs=[],
        library_dirs=[],
        libraries=[libboost, libexiv],
        extra_compile_args=extra_compile_args
        )
    ],
)

