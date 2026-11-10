"""Build "dist/PDF Editor Pro v<VERSION>.exe" and its installer "dist/PDF Editor Pro Setup v<VERSION>.exe".
On macOS it builds "dist/PDF Editor Pro.app" and "dist/PDF Editor Pro v<VERSION> macOS <arch>.dmg" instead.

Usage: bump VERSION in version.py (and add a CHANGELOG.md entry), then run:  python build.py
"""
import os
import platform
import plistlib
import shutil
import subprocess
import sys

from version import COMPANY, COPYRIGHT, VERSION

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = f"PDF Editor Pro v{VERSION}"
nums = [int(x) for x in VERSION.split(".")] + [0] * 4
v4 = ", ".join(str(n) for n in nums[:4])

VERSION_INFO = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v4}), prodvers=({v4}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{COMPANY}'),
      StringStruct('FileDescription', 'PDF Editor Pro'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'PDF Editor Pro'),
      StringStruct('LegalCopyright', '{COPYRIGHT}'),
      StringStruct('OriginalFilename', '{NAME}.exe'),
      StringStruct('ProductName', 'PDF Editor Pro'),
      StringStruct('ProductVersion', '{VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def find_iscc():
    roots = (os.environ.get("LOCALAPPDATA", "") + r"\Programs", os.environ.get("ProgramFiles(x86)", ""),
             os.environ.get("ProgramFiles", ""))
    for root in roots:
        path = os.path.join(root, "Inno Setup 6", "ISCC.exe")
        if os.path.exists(path):
            return path
    sys.exit("Inno Setup 6 is not installed (winget install JRSoftware.InnoSetup)")


def build_installer():
    subprocess.run([find_iscc(), "/Q", f"/DAppVersion={VERSION}", f"/DPublisher={COMPANY}",
                    f"/DCopyright={COPYRIGHT}", "installer.iss"], check=True)
    return os.path.join("dist", f"PDF Editor Pro Setup v{VERSION}.exe")


def clean(*names):
    for junk in ("build", "__pycache__", *names):
        if os.path.isdir(junk):
            shutil.rmtree(junk, ignore_errors=True)
        elif os.path.exists(junk):
            os.remove(junk)


def mac_dmg_name():
    arch = "Apple Silicon" if platform.machine() == "arm64" else "Intel"
    return os.path.join("dist", f"PDF Editor Pro v{VERSION} macOS {arch}.dmg")


def build_mac():
    """An unsigned .app (ad-hoc signed, which Apple Silicon requires) packed in a drag-to-Applications disk image."""
    app_name = "PDF Editor Pro"
    app = os.path.join("dist", app_name + ".app")
    shutil.rmtree(app, ignore_errors=True)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed", "--name", app_name,
           "--icon", "app.ico", "--add-data", f"app.ico{os.pathsep}.",
           "--osx-bundle-identifier", "com.camboads.pdfeditorpro",
           "--exclude-module", "tkinter", "--log-level", "WARN", "pdf_editor.py"]
    subprocess.run(cmd, check=True)
    clean(app_name + ".spec")
    shutil.rmtree(os.path.join("dist", app_name), ignore_errors=True)  # the loose onedir copy beside the .app

    plist_path = os.path.join(app, "Contents", "Info.plist")
    with open(plist_path, "rb") as fh:
        info = plistlib.load(fh)
    info.update({
        "CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION, "NSHumanReadableCopyright": COPYRIGHT,
        "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0",
        # lets Finder offer the app for PDFs (Open With, double-click once chosen as default)
        "CFBundleDocumentTypes": [{"CFBundleTypeName": "PDF document", "CFBundleTypeRole": "Editor",
                                   "LSHandlerRank": "Alternate", "LSItemContentTypes": ["com.adobe.pdf"]}],
    })
    with open(plist_path, "wb") as fh:
        plistlib.dump(info, fh)
    # changing Info.plist breaks PyInstaller's signature, so sign again (ad hoc: no Apple certificate)
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app], check=True)

    dmg = mac_dmg_name()
    stage = os.path.join("build", "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    subprocess.run(["ditto", app, os.path.join(stage, app_name + ".app")], check=True)
    os.symlink("/Applications", os.path.join(stage, "Applications"))
    if os.path.exists(dmg):
        os.remove(dmg)
    subprocess.run(["hdiutil", "create", "-volname", f"{app_name} {VERSION}", "-srcfolder", stage,
                    "-format", "UDZO", "-ov", dmg], check=True)
    clean()
    print(f"\nBuilt: {os.path.abspath(app)}\nDisk image: {os.path.abspath(dmg)}")


def main():
    os.chdir(HERE)
    if sys.platform == "darwin":
        build_mac()
        return
    with open("version_info.txt", "w", encoding="utf-8") as fh:
        fh.write(VERSION_INFO)
    target = os.path.join("dist", NAME + ".exe")
    if os.path.exists(target):  # a file that is open/locked can still be renamed out of the way
        os.replace(target, target + ".old")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--name", NAME,
           "--icon", "app.ico", "--add-data", "app.ico;.", "--version-file", "version_info.txt",
           "--exclude-module", "tkinter", "--log-level", "WARN", "pdf_editor.py"]
    subprocess.run(cmd, check=True)
    clean("version_info.txt", NAME + ".spec")
    try:
        os.remove(target + ".old")
    except OSError:
        pass
    setup = build_installer()
    print(f"\nBuilt: {os.path.abspath(target)}\nInstaller: {os.path.abspath(setup)}")


if __name__ == "__main__":
    main()
