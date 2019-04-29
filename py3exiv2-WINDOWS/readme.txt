[INSTALLING PYEXIV3 ON WINDOWS]
- get vcpkg by cloning https://github.com/Microsoft/vcpkg. Note the folder name.
- install vcpkg by running bootstrap-vcpkg.bat
- run vcpkg.exe install boost-python:x64-windows
- run vcpkg.exe install exiv2:x64-windows
- make sure to add /installed/x64-windows/bin to the PATH
- get the pyexiv2 sources from here: http://py3exiv2.tuxfamily.org/downloads
- replace setup.py with my version
- set the environment variable VCPKG to the folder where you installed it
- run pip install -e <py3exiv2-folder>