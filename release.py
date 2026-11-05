"""Build the current VERSION and publish it as a GitHub Release, which users then receive through the Update button.

Usage: bump VERSION in version.py, add a CHANGELOG.md entry, then run:  python release.py
Only the EXE is uploaded; the source code stays on this computer.
"""
import os
import re
import subprocess
import sys

from version import UPDATE_REPO, VERSION

HERE = os.path.dirname(os.path.abspath(__file__))
GH = r"C:\Program Files\GitHub CLI\gh.exe"


def changelog_notes():
    with open(os.path.join(HERE, "CHANGELOG.md"), encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(rf"^## {re.escape(VERSION)}\b.*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m or not m.group(1).strip():
        sys.exit(f"CHANGELOG.md has no entry for {VERSION}")
    return m.group(1).strip()


def main():
    notes = changelog_notes()
    subprocess.run([sys.executable, "build.py"], cwd=HERE, check=True)
    exe = os.path.join(HERE, "dist", f"PDF Editor Pro v{VERSION}.exe")  # used by the in-app updater
    setup = os.path.join(HERE, "dist", f"PDF Editor Pro Setup v{VERSION}.exe")  # for new installs
    subprocess.run([GH, "release", "create", f"v{VERSION}", exe, setup, "--repo", UPDATE_REPO,
                    "--title", f"PDF Editor Pro v{VERSION}", "--notes", notes], check=True)
    print(f"\nPublished v{VERSION} to https://github.com/{UPDATE_REPO}/releases/latest")


if __name__ == "__main__":
    main()
