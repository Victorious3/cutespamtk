import sys, os, ctypes
from pathlib import Path

EXTENSION = "moe.nightfall.booru"
DIR = Path(__file__).resolve().parent

REG_CHROME = os.path.join(r"Software\Google\Chrome\NativeMessagingHosts", EXTENSION)
REG_FF = os.path.join(r"Software\Mozilla\NativeMessagingHosts", EXTENSION)

if os.name == "nt":
    IS_ROOT = ctypes.windll.shell32.IsUserAnAdmin() != 0
else:
    IS_ROOT = (os.getuid() == 0)

def install():
    if os.name == "nt":
        import winreg
        ROOT_KEY = winreg.HKEY_LOCAL_MACHINE if IS_ROOT else winreg.HKEY_CURRENT_USER

        KEY_CHROME = winreg.CreateKey(ROOT_KEY, REG_CHROME)
        KEY_FF = winreg.CreateKey(ROOT_KEY, REG_FF)

        winreg.SetValueEx(KEY_CHROME, None, 0, winreg.REG_SZ, os.path.join(DIR, "chrome", EXTENSION + ".json"))
        winreg.SetValueEx(KEY_FF, None, 0, winreg.REG_SZ, os.path.join(DIR, "firefox", EXTENSION + ".json"))

        winreg.CloseKey(KEY_CHROME)
        winreg.CloseKey(KEY_FF)
        

def remove():
    if os.name == "nt":
        import winreg
        ROOT_KEY = winreg.HKEY_LOCAL_MACHINE if IS_ROOT else winreg.HKEY_CURRENT_USER
        winreg.DeleteKey(ROOT_KEY, REG_CHROME)
        winreg.DeleteKey(ROOT_KEY, REG_FF)

if __name__ == "__main__":
    if sys.argv[1] == "-install":
        install()
    elif sys.argv[1] == "-remove":
        remove()
    else:
        print("Invalid arguments to install.py")
        sys.exit(-1)