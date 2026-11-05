"""Build "dist/PDF Editor Pro v<VERSION>.exe" and its installer "dist/PDF Editor Pro Setup v<VERSION>.exe".

Usage: bump VERSION in version.py (and add a CHANGELOG.md entry), then run:  python build.py
"""
import os
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


def main():
    os.chdir(HERE)
    with open("version_info.txt", "w", encoding="utf-8") as fh:
        fh.write(VERSION_INFO)
    target = os.path.join("dist", NAME + ".exe")
    if os.path.exists(target):  # a file that is open/locked can still be renamed out of the way
        os.replace(target, target + ".old")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--name", NAME,
           "--icon", "app.ico", "--add-data", "app.ico;.", "--version-file", "version_info.txt",
           "--exclude-module", "tkinter", "--log-level", "WARN", "pdf_editor.py"]
    subprocess.run(cmd, check=True)
    for junk in ("build", "__pycache__", "version_info.txt", NAME + ".spec"):
        if os.path.isdir(junk):
            shutil.rmtree(junk, ignore_errors=True)
        elif os.path.exists(junk):
            os.remove(junk)
    try:
        os.remove(target + ".old")
    except OSError:
        pass
    setup = build_installer()
    print(f"\nBuilt: {os.path.abspath(target)}\nInstaller: {os.path.abspath(setup)}")


if __name__ == "__main__":
    main()
