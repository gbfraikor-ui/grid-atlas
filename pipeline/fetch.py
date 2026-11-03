"""Download source files listed in sources/*.yaml into data/raw/.

Usage:
    uv run python pipeline/fetch.py              # fetch every source
    uv run python pipeline/fetch.py counties     # fetch one source by id
    uv run python pipeline/fetch.py counties --force   # re-download even if present

For each source, writes:
    data/raw/<id>/<filename>       the downloaded file, unchanged
    data/raw/<id>/_fetch.json      when and from where we got it, plus a checksum
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent  # the grid-atlas folder
SOURCES_DIR = ROOT / "sources"
RAW_DIR = ROOT / "data" / "raw"


def load_sources() -> dict[str, dict]:
    """Read every sources/*.yaml file into {id: config}."""
    sources = {}
    for path in sorted(SOURCES_DIR.glob("*.yaml")):
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        sources[config["id"]] = config
    return sources


def fetch(source: dict, force: bool = False) -> None:
    """Download one source and write its _fetch.json record."""
    url = source["url"]
    out_dir = RAW_DIR / source["id"]
    out_file = out_dir / url.rsplit("/", 1)[-1]  # filename = last part of the URL
    record_file = out_dir / "_fetch.json"

    if out_file.exists() and not force:
        print(f"[{source['id']}] already downloaded, skipping (use --force to re-download)")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{source['id']}] downloading {url}")

    # Stream the download in chunks so large files never sit fully in memory.
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()  # stop with an error on 404, 500, etc.

    sha256 = hashlib.sha256()
    size = 0
    with open(out_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
            sha256.update(chunk)
            size += len(chunk)

    record = {
        "id": source["id"],
        "url": url,
        "license": source["license"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "http_last_modified": response.headers.get("Last-Modified"),
        "bytes": size,
        "sha256": sha256.hexdigest(),
        "file": out_file.name,
    }
    record_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"[{source['id']}] saved {out_file.relative_to(ROOT)} ({size / 1e6:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", help="source ids to fetch (default: all)")
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()

    sources = load_sources()
    unknown = [i for i in args.ids if i not in sources]
    if unknown:
        raise SystemExit(f"Unknown source id(s): {unknown}. Known: {sorted(sources)}")

    for source_id in args.ids or sorted(sources):
        if sources[source_id].get("type") == "pmtiles_extract":
            # A whole-world file: never download it. Its own builder reads just one region.
            print(f"[{source_id}] skipping: use pipeline/build_basemap.py")
            continue
        fetch(sources[source_id], force=args.force)


if __name__ == "__main__":
    main()
