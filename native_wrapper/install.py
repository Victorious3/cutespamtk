#!/usr/bin/env python3

import sys, os, ctypes, json, contextlib
from pathlib import Path

EXTENSION = "moe.nightfall.booru"
DIR = Path(__file__).resolve().parent

REG_CHROME = os.path.join(r"Software\Google\Chrome\NativeMessagingHosts", EXTENSION)
REG_FF = os.path.join(r"Software\Mozilla\NativeMessagingHosts", EXTENSION)

PATH_CHROME_SYSTEM = Path("/etc/opt/chrome/native-messaging-hosts")
PATH_CHROMIUM_SYSTEM = Path("/etc/chromium/NativeMessagingHosts")
PATH_CHROME_USER = Path("~/.config/google-chrome/NativeMessagingHosts").expanduser()
PATH_CHROMIUM_USER = Path("~/.config/chromium/NativeMessagingHosts").expanduser()

if os.name == "nt":
    IS_ROOT = ctypes.windll.shell32.IsUserAnAdmin() != 0
else:
    IS_ROOT = (os.getuid() == 0)

def install():
    print("Installing native wrapper for browser extension")
    if os.name == "nt":
        import winreg
        ROOT_KEY = winreg.HKEY_LOCAL_MACHINE if IS_ROOT else winreg.HKEY_CURRENT_USER

        KEY_CHROME = winreg.CreateKey(ROOT_KEY, REG_CHROME)
        KEY_FF = winreg.CreateKey(ROOT_KEY, REG_FF)

        winreg.SetValueEx(KEY_CHROME, None, 0, winreg.REG_SZ, os.path.join(DIR, "chrome", EXTENSION + ".json"))
        winreg.SetValueEx(KEY_FF, None, 0, winreg.REG_SZ, os.path.join(DIR, "firefox", EXTENSION + ".json"))

        winreg.CloseKey(KEY_CHROME)
        winreg.CloseKey(KEY_FF)
    elif os.name == "posix":
        with open(Path(__file__).parent / "chrome" / (EXTENSION + ".json"), "r") as chrf:
            manifest_chrome = json.load(chrf)
        with open(Path(__file__).parent / "firefox" / (EXTENSION + ".json"), "r") as fff:
            manifest_ff = json.load(fff)

        native_wrapper = (Path(__file__).parent / "native-wrapper.sh").resolve().absolute()

        manifest_chrome["path"] = str(native_wrapper)
        manifest_ff["path"] = str(native_wrapper)

        if IS_ROOT:
            if PATH_CHROME_SYSTEM.parent.exists(): 
                PATH_CHROME_SYSTEM.mkdir(exist_ok = True)
                with open(PATH_CHROME_SYSTEM / (EXTENSION + ".json"), "w") as chrf: json.dump(manifest_chrome, chrf)
            if PATH_CHROMIUM_SYSTEM.parent.exists():
                PATH_CHROMIUM_SYSTEM.mkdir(exist_ok = True)
                with open(PATH_CHROMIUM_SYSTEM / (EXTENSION + ".json"), "w") as chrf: json.dump(manifest_chrome, chrf)
        else:
            if PATH_CHROME_USER.parent.exists():
                PATH_CHROME_USER.mkdir(exist_ok = True)
                with open(PATH_CHROME_USER / (EXTENSION + ".json"), "w") as chrf: json.dump(manifest_chrome, chrf)
            if PATH_CHROMIUM_USER.parent.exists():
                PATH_CHROMIUM_USER.mkdir(exist_ok = True)
                with open(PATH_CHROMIUM_USER / (EXTENSION + ".json"), "w") as chrf: json.dump(manifest_chrome, chrf)



    print("Successfully installed cutespam")

def remove():
    print("Removing native wrapper for browser extension")
    if os.name == "nt":
        import winreg
        ROOT_KEY = winreg.HKEY_LOCAL_MACHINE if IS_ROOT else winreg.HKEY_CURRENT_USER
        winreg.DeleteKey(ROOT_KEY, REG_CHROME)
        winreg.DeleteKey(ROOT_KEY, REG_FF)
    elif os.name == "posix":
        if IS_ROOT:
            with contextlib.suppress(FileNotFoundError): (PATH_CHROME_SYSTEM / (EXTENSION + ".json")).unlink()
            with contextlib.suppress(FileNotFoundError): (PATH_CHROMIUM_SYSTEM / (EXTENSION + ".json")).unlink()
        else:
            with contextlib.suppress(FileNotFoundError): (PATH_CHROME_USER / (EXTENSION + ".json")).unlink()
            with contextlib.suppress(FileNotFoundError): (PATH_CHROMIUM_USER / (EXTENSION + ".json")).unlink()

    print("Successfully removed cutespam")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Specify -install or -remove")
        sys.exit(-1)
    try:
        if sys.argv[1] == "-install":
            install()
        elif sys.argv[1] == "-remove":
            remove()
        else:
            print("Specify -install or -remove")
            sys.exit(-1)
    except Exception as e:
        print("An error has occured during installation:", str(e))
        raise e