"""Let the plain EXE install itself for the current user: copy, desktop and Start Menu shortcuts, Apps list entry."""
import os
import shutil
import subprocess
import sys
import winreg

from PySide6.QtCore import QFile, QStandardPaths

from updater import fresh_env
from version import COMPANY, VERSION

APP_NAME = "PDF Editor Pro"
INSTALL_ARG = "--install"
UNINSTALL_ARG = "--uninstall"
QUIET_ARG = "--quiet"
REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PDFEditorPro"


def install_dir():
    return os.path.join(os.environ["LOCALAPPDATA"], "Programs", APP_NAME)


def installed_exe():
    return os.path.join(install_dir(), APP_NAME + ".exe")


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def is_installed():
    """True when this process is running from the install folder (also the case after using the Setup installer)."""
    return is_frozen() and os.path.normcase(os.path.dirname(sys.executable)) == os.path.normcase(install_dir())


def _shortcut_paths():
    desktop = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
    start_menu = QStandardPaths.writableLocation(QStandardPaths.ApplicationsLocation)
    return [os.path.join(d, APP_NAME + ".lnk") for d in (desktop, start_menu)]


def _register(exe):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
        for name, value in (("DisplayName", APP_NAME), ("DisplayVersion", VERSION), ("Publisher", COMPANY),
                            ("DisplayIcon", exe), ("InstallLocation", os.path.dirname(exe)),
                            ("UninstallString", f'"{exe}" {UNINSTALL_ARG}')):
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1)


def refresh_registration():
    """Keep the Apps list version right after an in-app update."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY):
            pass
    except OSError:
        return  # installed by the Setup installer, or not installed
    if is_installed():
        _register(sys.executable)


def install():
    """Copy this EXE to the install folder and register it; returns the installed EXE's path."""
    target = installed_exe()
    os.makedirs(install_dir(), exist_ok=True)
    if os.path.normcase(sys.executable) != os.path.normcase(target):
        temp = target + ".new"
        shutil.copy2(sys.executable, temp)
        try:
            os.replace(temp, target)  # fails if the installed copy is running
        except OSError:
            os.remove(temp)
            raise
    for link in _shortcut_paths():
        if os.path.exists(link):
            os.remove(link)
        if not QFile.link(target, link):
            raise OSError(f"Could not create the shortcut {link}")
    _register(target)
    return target


def launch(exe, args=()):
    subprocess.Popen([exe, *args], env=fresh_env(), close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


def uninstall():
    """Remove the shortcuts and Apps entry; a detached cmd deletes the folder once this process has exited."""
    for link in _shortcut_paths():
        if os.path.exists(link):
            os.remove(link)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
    except OSError:
        pass
    subprocess.Popen(f'cmd /c ping -n 4 127.0.0.1 >nul & rmdir /s /q "{install_dir()}"', shell=True,
                     close_fds=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                     cwd=os.environ["LOCALAPPDATA"])
