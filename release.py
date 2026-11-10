"""Build the current VERSION and publish it as a GitHub Release, which users then receive through the Update button.

Usage: bump VERSION in version.py, add a CHANGELOG.md entry, then run:  python release.py
Uploads the Windows EXE and Setup; GitHub Actions (.github/workflows/macos.yml) then builds the macOS disk
images from the same commit and adds them to the release a few minutes later. Push your commits first.
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


def pushed_head():
    """The current commit, which must already be on GitHub so the macOS build compiles the same code."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, check=True, capture_output=True,
                          text=True).stdout.strip()
    subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=HERE, check=True)
    on_remote = subprocess.run(["git", "branch", "-r", "--contains", head], cwd=HERE, check=True,
                               capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=HERE, check=True, capture_output=True,
                           text=True).stdout.strip()
    if dirty or not on_remote:
        sys.exit("Commit and push your changes first (git push), so the macOS build uses the same code.")
    return head


def main():
    notes = changelog_notes()
    head = pushed_head()
    subprocess.run([sys.executable, "build.py"], cwd=HERE, check=True)
    exe = os.path.join(HERE, "dist", f"PDF Editor Pro v{VERSION}.exe")  # used by the in-app updater
    setup = os.path.join(HERE, "dist", f"PDF Editor Pro Setup v{VERSION}.exe")  # for new installs
    subprocess.run([GH, "release", "create", f"v{VERSION}", exe, setup, "--repo", UPDATE_REPO,
                    "--target", head, "--title", f"PDF Editor Pro v{VERSION}", "--notes", notes], check=True)
    print(f"\nPublished v{VERSION} to https://github.com/{UPDATE_REPO}/releases/latest"
          "\nThe macOS disk images appear there when the 'macOS build' action finishes (about 10 minutes).")


if __name__ == "__main__":
    main()
