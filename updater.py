"""Self-update from the latest GitHub Release of UPDATE_REPO (no Qt here; see MainWindow for the UI)."""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from version import UPDATE_REPO, VERSION

API_URL = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{UPDATE_REPO}/releases/latest"
USER_AGENT = "PDF-Editor-Pro-Updater"
TIMEOUT = 20
SELF_TEST_ARG = "--update-self-test"


class Cancelled(Exception):
    pass


def parse_version(text):
    """'v1.4.2' -> (1, 4, 2); anything else -> None."""
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def is_newer(latest, current=VERSION):
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def can_self_update():
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def fetch_latest():
    """Return dict(version, notes, url, size, sha256) for the latest release, or None if there is none yet."""
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            rel = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    # a release also carries the Setup installer; the updater swaps in the plain EXE
    asset = next((a for a in rel.get("assets", [])
                  if a["name"].lower().endswith(".exe") and "setup" not in a["name"].lower()), None)
    if asset is None:
        return None
    digest = asset.get("digest") or ""
    return dict(version=rel["tag_name"].lstrip("v"), notes=(rel.get("body") or "").strip(),
                url=asset["browser_download_url"], size=asset["size"],
                sha256=digest[7:].lower() if digest.startswith("sha256:") else "")


def download(info, dest, progress=None, cancel=None):
    """Download the release EXE to dest and verify it; a failed or cancelled download leaves no file behind."""
    if not info["sha256"]:
        raise RuntimeError("The release has no checksum, so it cannot be verified.")
    h = hashlib.sha256()
    done = 0
    req = urllib.request.Request(info["url"], headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(dest, "wb") as fh:
            while True:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, info["size"])
        if h.hexdigest() != info["sha256"]:
            raise RuntimeError("The downloaded file is damaged (checksum mismatch).")
    except BaseException:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise
    return dest


def download_path():
    return sys.executable + ".download"


def old_path():
    return sys.executable + ".old"


def fresh_env():
    # without this a new one-file EXE would reuse this process's temporary unpack folder
    return dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")


def verify_runs(new_file):
    """Start the downloaded EXE in self-test mode, so a version Windows refuses to run never replaces this one."""
    try:
        subprocess.run([new_file, SELF_TEST_ARG], env=fresh_env(), timeout=120, check=True)
    except OSError as e:
        raise RuntimeError("Windows blocked the new version from running (Smart App Control or antivirus). "
                           f"Your current version was kept.\n\n{e}") from e
    except (subprocess.SubprocessError, ValueError) as e:
        raise RuntimeError(f"The new version failed to start. Your current version was kept.\n\n{e}") from e


def install_and_launch(new_file, args=()):
    """Swap new_file into the running EXE's path (Windows allows renaming a running EXE) and start it."""
    cur, old = sys.executable, old_path()
    if os.path.exists(old):
        os.remove(old)
    os.replace(cur, old)
    try:
        os.replace(new_file, cur)
    except OSError:
        os.replace(old, cur)
        raise
    subprocess.Popen([cur, *args], env=fresh_env(), close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


def cleanup_previous():
    """Remove what the previous version left behind; it may need a few seconds to exit, so retry in the background."""
    if not can_self_update():
        return

    def work():
        for _ in range(60):
            try:
                for p in (old_path(), download_path()):
                    if os.path.exists(p):
                        os.remove(p)
                return
            except OSError:
                time.sleep(1)

    threading.Thread(target=work, daemon=True).start()
