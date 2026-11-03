"""Cut one region's background map out of the Protomaps world file.

Usage:
    uv run python pipeline/build_basemap.py nova
    uv run python pipeline/build_basemap.py nova --force   # cut it again

Reads:  sources/basemap.yaml                        (which build, how far to zoom)
        data/processed/<region>/counties.geojson    (the region's bounds)
Writes: data/processed/<region>/basemap.pmtiles
        data/processed/<region>/basemap.json        where it came from
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import yaml

ROOT = Path(__file__).resolve().parent.parent
GITHUB_FILE_LIMIT_MB = 100  # the file gets committed, and GitHub rejects anything larger


def build(region_id: str, force: bool = False) -> None:
    source = yaml.safe_load((ROOT / "sources" / "basemap.yaml").read_text(encoding="utf-8"))
    out_dir = ROOT / "data" / "processed" / region_id
    out_file = out_dir / "basemap.pmtiles"

    if out_file.exists() and not force:
        print(f"{out_file.relative_to(ROOT)} already exists, skipping (use --force to cut it again)")
        return

    tool = shutil.which("pmtiles") or shutil.which(str(ROOT / "tools" / "pmtiles"))
    if not tool:
        raise SystemExit("pmtiles tool not found. Run: uv run python pipeline/vendor_basemap.py")

    # The box to cut: the region's bounds, plus a margin.
    west, south, east, north = gpd.read_file(out_dir / "counties.geojson").total_bounds.tolist()
    margin = source["margin_deg"]
    bbox = [round(west - margin, 2), round(south - margin, 2), round(east + margin, 2), round(north + margin, 2)]

    print(f"Cutting {source['url']} to box {bbox}, up to zoom {source['max_zoom']}")
    subprocess.run(
        [tool, "extract", source["url"], str(out_file), f"--bbox={','.join(map(str, bbox))}", f"--maxzoom={source['max_zoom']}"],
        check=True,
    )

    size_mb = out_file.stat().st_size / 1e6
    record = {
        "id": source["id"],
        "region": region_id,
        "source_title": source["title"],
        "source_url": source["url"],
        "license": source["license"],
        "license_url": source["license_url"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bbox": bbox,
        "max_zoom": source["max_zoom"],
        "bytes": out_file.stat().st_size,
        "sha256": hashlib.sha256(out_file.read_bytes()).hexdigest(),
    }
    (out_dir / "basemap.json").write_text(json.dumps(record, indent=2), encoding="utf-8", newline="\n")
    print(f"Saved {out_file.relative_to(ROOT)} ({size_mb:.1f} MB)")

    if size_mb > GITHUB_FILE_LIMIT_MB:
        raise SystemExit(f"Too big to commit: over GitHub's {GITHUB_FILE_LIMIT_MB} MB limit. Lower max_zoom or margin_deg.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("region", help="region id, e.g. nova")
    parser.add_argument("--force", action="store_true", help="cut the extract again")
    args = parser.parse_args()
    build(args.region, force=args.force)


if __name__ == "__main__":
    main()
