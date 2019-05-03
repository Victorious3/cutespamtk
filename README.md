# Cutespam Toolkit

Keeps track of your cute images. The metadata is stored directly on the image files in the form of IPTC and XMP tags.
This makes it easy to share the image folder with a third party p2p service such as [syncthing](https://syncthing.net/).

## Installation

There are two parts, the cli and the browser extension. The CLI can be installed with pip, the extension needs a bit more work.

### Requirements
 - [Python](https://www.python.org/downloads/) 3.6 or later
 - A working `py3exiv2` (see note below)
 - Chrome, Firefox or any other compatible browser for the extension

In either case, clone the repository:
```bash
git clone https://github.com/Victorious3/cutespamtk
```
Or download it here [https://github.com/Victorious3/cutespamtk/archive/master.zip](https://github.com/Victorious3/cutespamtk/archive/master.zip) and unpack the zip folder.

### CLI
```bash
pip install -e ./cutespamtk --user
```
You should be able to use `cutespam` and `iqdb` from the command line now

#### Note for Windows:
If you are on Windows then installing `py3exiv2` is going to fail. For instructions to fix this error consult [py3exiv2-WINDOWS/readme.txt](py3exiv2-WINDOWS/readme.txt).

### Browser Extension
When you have successfully installed the cli you can go ahead and install the browser extension.

It needs to communicate with `cutespam` so you need to install a native messaging host first.
```bash
./cutespamtk/native_wrapper/install.py -install
```

Or if you are on Windows:
```bash
py -3 \cutespamtk\native_wrapper\install.py -install
```
This is going to add a few registry keys, look at the script if you are curious about what it does.

For a system wide installation simply run the file as root. 
For removing it again, run the same command with `-remove` instead of `-install`

The extension works on both Windows and Linux and has been tested with Chrome and Firefox. It probably works with Opera and Edge as well but for that you need to figure out how to add native messaging hosts to those browsers and install it yourself. Same if you are using Firefox on Linux, my script currently doesn't handle that case. 

Afer you've installed the native messaging host you just need to load the unpackaged extension. For Chrome this means going to [chrome://extensions/](chrome://extensions/), enabling developer mode and loading the folder `./cutespamtk/extension`. Instructions for other browsers will vary.