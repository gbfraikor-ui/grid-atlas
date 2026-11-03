"""Build the substations layer for one region from an OpenStreetMap extract.

Usage:
    uv run python pipeline/build_substations.py nova

Reads:  data/raw/<osm source>/<extract>.osm.pbf     (from fetch.py)
        data/processed/<region>/counties.geojson    (the region's boundary)
Writes: data/processed/<region>/substations.geojson (one point per substation)
"""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import yaml

from build_transmission import MIN_KV, get_tag, max_kv

ROOT = Path(__file__).resolve().parent.parent

# GDAL splits a PBF into layers by geometry, and a substation can be mapped in any of these.
# Each pairs with the OSM record type, which the map needs to link back to the right page.
LAYERS = {"points": "node", "lines": "way", "multipolygons": "multipolygon"}


def read_substations(pbf: Path) -> gpd.GeoDataFrame:
    """Read power=substation from every layer into one table of points."""
    frames = []
    for layer, osm_type in LAYERS.items():
        found = pyogrio.read_dataframe(pbf, layer=layer, where="other_tags LIKE '%\"power\"=>\"substation\"%'")
        found["osm_type"] = osm_type
        if layer == "multipolygons":
            # A plain closed way comes through with osm_way_id; a true OSM relation has osm_id.
            is_way = found["osm_way_id"].notna()
            found["osm_type"] = is_way.map({True: "way", False: "relation"})
            found["osm_id"] = found["osm_way_id"].where(is_way, found["osm_id"])
        # A point guaranteed to fall inside the shape, so all three layers can share one geometry type.
        found["geometry"] = found.geometry.representative_point()
        frames.append(found[["osm_id", "osm_type", "name", "other_tags", "geometry"]])
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=frames[0].crs)


def build(region_id: str) -> None:
    region = yaml.safe_load((ROOT / "regions" / f"{region_id}.yaml").read_text(encoding="utf-8"))
    raw_dir = ROOT / "data" / "raw" / region["osm_source"]
    record = json.loads((raw_dir / "_fetch.json").read_text(encoding="utf-8"))

    substations = read_substations(raw_dir / record["file"])
    print(f"Read {len(substations)} substations from {record['file']}")

    substations["substation_type"] = substations["other_tags"].map(lambda s: get_tag(s, "substation"))
    substations["voltage"] = substations["other_tags"].map(lambda s: get_tag(s, "voltage"))
    substations["operator"] = substations["other_tags"].map(lambda s: get_tag(s, "operator"))
    substations["max_kv"] = pd.to_numeric(substations["voltage"].map(max_kv))

    boundary = gpd.read_file(ROOT / "data" / "processed" / region_id / "counties.geojson").to_crs(substations.crs)
    in_region = substations[substations.within(boundary.union_all())]

    # Keep substations on the transmission network, or with no voltage tag (flagged, not assumed).
    # Traction substations power rail lines such as Metro, so they are left out at any voltage.
    traction = in_region["substation_type"] == "traction"
    low = in_region["max_kv"] < MIN_KV
    out = in_region[~traction & ~low].copy()
    out["voltage_known"] = out["max_kv"].notna()
    columns = ["osm_type", "osm_id", "name", "substation_type", "voltage", "max_kv", "voltage_known", "operator", "geometry"]
    out = out[columns].sort_values(["osm_type", "osm_id"])

    out_file = ROOT / "data" / "processed" / region_id / "substations.geojson"
    out.to_file(out_file, driver="GeoJSON")

    print(f"Kept {len(out)} of {len(in_region)} substations in {region['name']}")
    print(f"Left out {traction.sum()} traction and {(low & ~traction).sum()} under {MIN_KV} kV")
    print("By highest voltage:")
    print(out["max_kv"].fillna(-1).value_counts().sort_index().rename(index={-1: "no voltage tag"}).to_string())
    print("By OSM substation type:")
    print(out["substation_type"].fillna("no type tag").value_counts().to_string())
    print(f"Saved {out_file.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("region", help="region id, e.g. nova")
    build(parser.parse_args().region)


if __name__ == "__main__":
    main()
