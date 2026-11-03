"""Build the transmission layer for one region from an OpenStreetMap extract.

Usage:
    uv run python pipeline/build_transmission.py nova

Reads:  data/raw/<osm source>/<extract>.osm.pbf     (from fetch.py)
        data/processed/<region>/counties.geojson    (the region's boundary)
Writes: data/processed/<region>/transmission.geojson
"""

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import yaml

ROOT = Path(__file__).resolve().parent.parent

# Our working definition of transmission, not an official one. Below this is treated as
# distribution. It is a single number here so it is easy to change and to state in a write-up.
MIN_KV = 69


def get_tag(other_tags: str | None, key: str) -> str | None:
    """Pull one value out of GDAL's other_tags text, e.g. '"voltage"=>"230000","cables"=>"3"'."""
    match = re.search(rf'"{key}"=>"([^"]*)"', other_tags or "")
    return match.group(1) if match else None


def max_kv(voltage: str | float) -> float | None:
    """Highest voltage in kV. OSM stores volts as text, with ';' between circuits: '500000;230000'."""
    if not isinstance(voltage, str):  # pandas turns a missing value into NaN, a float
        return None
    values = [float(v) for v in re.split(r"[;,]", voltage) if v.strip().isdigit() and int(v) > 0]
    return max(values) / 1000 if values else None


def build(region_id: str) -> None:
    region = yaml.safe_load((ROOT / "regions" / f"{region_id}.yaml").read_text(encoding="utf-8"))
    raw_dir = ROOT / "data" / "raw" / region["osm_source"]
    record = json.loads((raw_dir / "_fetch.json").read_text(encoding="utf-8"))

    # A PBF holds all of OSM for the area. Read only line features with a power tag.
    lines = pyogrio.read_dataframe(raw_dir / record["file"], layer="lines", where="other_tags LIKE '%\"power\"=>%'")
    print(f"Read {len(lines)} power-tagged line features from {record['file']}")

    lines["power"] = lines["other_tags"].map(lambda s: get_tag(s, "power"))
    lines["voltage"] = lines["other_tags"].map(lambda s: get_tag(s, "voltage"))
    lines["operator"] = lines["other_tags"].map(lambda s: get_tag(s, "operator"))
    lines["circuits"] = lines["other_tags"].map(lambda s: get_tag(s, "circuits"))
    lines["max_kv"] = pd.to_numeric(lines["voltage"].map(max_kv))

    # Cut to the region's boundary, so lengths and the map stop at its edge.
    boundary = gpd.read_file(ROOT / "data" / "processed" / region_id / "counties.geojson").to_crs(lines.crs)
    in_region = gpd.clip(lines[lines["power"].isin(["line", "cable", "minor_line"])], boundary.union_all())

    # Keep: anything tagged at or above MIN_KV, plus power=line with no usable voltage, since OSM
    # mappers use power=line for high-voltage lines. Those stay flagged, not assumed to be a voltage.
    known = in_region["power"].isin(["line", "cable"]) & (in_region["max_kv"] >= MIN_KV)
    unknown = (in_region["power"] == "line") & in_region["max_kv"].isna()
    out = in_region[known | unknown].copy()
    out["voltage_known"] = out["max_kv"].notna()
    out = out[["osm_id", "name", "power", "voltage", "max_kv", "voltage_known", "circuits", "operator", "geometry"]]

    out_file = ROOT / "data" / "processed" / region_id / "transmission.geojson"
    out.sort_values("osm_id").to_file(out_file, driver="GeoJSON")

    # Measure length in meters, which needs a projected CRS rather than lon/lat degrees.
    km = out.geometry.to_crs(out.estimate_utm_crs()).length / 1000
    print(f"Kept {len(out)} of {len(in_region)} power features in {region['name']}, {km.sum():.0f} km")
    print(f"Left out {(in_region['power'] == 'minor_line').sum()} minor_line and "
          f"{((in_region['max_kv'] < MIN_KV) & (in_region['power'] != 'minor_line')).sum()} features under {MIN_KV} kV")
    print("Length by voltage (km):")
    print(km.groupby(out["max_kv"].fillna(-1)).sum().round(0).rename(index={-1: "no voltage tag"}).to_string())
    print(f"Saved {out_file.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("region", help="region id, e.g. nova")
    build(parser.parse_args().region)


if __name__ == "__main__":
    main()
