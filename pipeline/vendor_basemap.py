"""Download what the background map needs, at pinned versions.

Usage:
    uv run python pipeline/vendor_basemap.py

Writes: site/vendor/pmtiles/       reads PMTiles files in the browser
        site/vendor/protomaps/     map style, plus label fonts and icons
        tools/pmtiles.exe          command-line tool for cutting extracts; not part of the site
"""

import hashlib
import io
import platform
import shutil
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "site" / "vendor"
TOOLS = ROOT / "tools"

ASSETS_COMMIT = "028c18f713baecad011301ff7a69acc39bcc2ae7"  # protomaps/basemaps-assets, 2025-10-31
FONTS = ["Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic"]
SPRITES = ["dark.json", "dark.png", "dark@2x.json", "dark@2x.png"]

FILES = {
    "pmtiles/pmtiles.js": "https://unpkg.com/pmtiles@4.4.1/dist/pmtiles.js",
    "pmtiles/LICENSE": "https://raw.githubusercontent.com/protomaps/PMTiles/main/LICENSE",
    "protomaps/basemaps.js": "https://unpkg.com/@protomaps/basemaps@5.7.2/dist/basemaps.js",
    "protomaps/LICENSE.md": "https://raw.githubusercontent.com/protomaps/basemaps/main/LICENSE.md",
    "protomaps/sprites/LICENSE.md": "https://raw.githubusercontent.com/tangrams/icons/master/LICENSE.md",
}

TOOL_URL = "https://github.com/protomaps/go-pmtiles/releases/download/v1.31.2/go-pmtiles_1.31.2_Windows_x86_64.zip"
TOOL_SHA256 = "a658baa4d7e55020aef6ca17bd9ff9faa1582671266b36f58c52db0ac8e785a1"  # from the GitHub release


def download(url: str) -> bytes:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def vendor_files() -> None:
    for relative, url in FILES.items():
        out = VENDOR / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(download(url))
        print(f"{relative}: {out.stat().st_size} bytes")


def vendor_assets() -> None:
    """Copy only the fonts and icons the dark style uses out of the assets repo's ZIP."""
    url = f"https://github.com/protomaps/basemaps-assets/archive/{ASSETS_COMMIT}.zip"
    prefix = f"basemaps-assets-{ASSETS_COMMIT}/"
    wanted = [f"fonts/{font}/" for font in FONTS] + ["fonts/OFL.txt"] + [f"sprites/v4/{name}" for name in SPRITES]
    copied = 0
    with zipfile.ZipFile(io.BytesIO(download(url))) as archive:
        for name in archive.namelist():
            relative = name.removeprefix(prefix)
            if name.endswith("/") or not any(relative.startswith(w) for w in wanted):
                continue
            out = VENDOR / "protomaps" / relative
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(archive.read(name))
            copied += 1
    print(f"fonts and icons: {copied} files")


def get_tool() -> None:
    """Download the pmtiles tool and refuse it unless its checksum matches the release."""
    if platform.system() != "Windows":
        print("Not on Windows: install pmtiles from https://github.com/protomaps/go-pmtiles/releases")
        return
    data = download(TOOL_URL)
    if hashlib.sha256(data).hexdigest() != TOOL_SHA256:
        raise SystemExit("pmtiles download does not match its published checksum; not installing it")
    TOOLS.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive, open(TOOLS / "pmtiles.exe", "wb") as out:
        shutil.copyfileobj(archive.open("pmtiles.exe"), out)
    print("tools/pmtiles.exe: checksum verified")


if __name__ == "__main__":
    vendor_files()
    vendor_assets()
    get_tool()
