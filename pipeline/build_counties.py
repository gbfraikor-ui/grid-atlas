"""Build the counties layer for one region.

Usage:
    uv run python pipeline/build_counties.py nova

Reads:  data/raw/counties/<census zip>   (from fetch.py)
        regions/<region>.yaml            (which jurisdictions to keep)
Writes: data/processed/<region>/counties.geojson
"""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "counties"
PROCESSED_DIR = ROOT / "data" / "processed"


def build(region_id: str) -> None:
    region = yaml.safe_load((ROOT / "regions" / f"{region_id}.yaml").read_text(encoding="utf-8"))

    # Full 5-digit GEOID = 2-digit state FIPS + 3-digit county FIPS, e.g. "51" + "107".
    wanted = {region["state_fips"] + j["fips"]: j["name"] for j in region["jurisdictions"]}

    # The fetch record tells us which file to open.
    record = json.loads((RAW_DIR / "_fetch.json").read_text(encoding="utf-8"))
    counties = gpd.read_file(RAW_DIR / record["file"])
    print(f"Read {len(counties)} counties nationwide, CRS {counties.crs}")

    # Keep only the region's jurisdictions.
    selected = counties[counties["GEOID"].isin(wanted)]

    # Check: every code was found, and the Census name matches the name in our config.
    missing = set(wanted) - set(selected["GEOID"])
    if missing:
        raise SystemExit(f"FIPS codes not found in Census file: {sorted(missing)}")
    for geoid, census_name in zip(selected["GEOID"], selected["NAMELSAD"]):
        if census_name != wanted[geoid]:
            raise SystemExit(f"Name mismatch for {geoid}: config says {wanted[geoid]!r}, Census says {census_name!r}")

    # Keep a few clear columns. ALAND/AWATER are land and water area in square meters.
    out = selected[["GEOID", "NAMELSAD", "ALAND", "AWATER", "geometry"]].rename(
        columns={"GEOID": "geoid", "NAMELSAD": "name", "ALAND": "land_m2", "AWATER": "water_m2"}
    )

    # Census files use NAD83 (EPSG:4269). Web maps and the GeoJSON standard expect WGS84 (EPSG:4326).
    out = out.to_crs("EPSG:4326").sort_values("geoid")

    out_dir = PROCESSED_DIR / region_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "counties.geojson"
    out.to_file(out_file, driver="GeoJSON")

    west, south, east, north = out.total_bounds
    print(f"Kept {len(out)} jurisdictions, all FIPS codes and names match the region config")
    print(f"Bounds (lon/lat): west {west:.3f}, south {south:.3f}, east {east:.3f}, north {north:.3f}")
    print(f"Saved {out_file.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("region", help="region id, e.g. nova")
    build(parser.parse_args().region)


if __name__ == "__main__":
    main()
