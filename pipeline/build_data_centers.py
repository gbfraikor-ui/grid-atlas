"""Build the data centers layer for one region from an OpenStreetMap extract.

Usage:
    uv run python pipeline/build_data_centers.py nova

Reads:  data/raw/<osm source>/<extract>.osm.pbf          (from fetch.py)
        data/processed/<region>/counties.geojson         (the region's boundary)
Writes: data/processed/<region>/data_centers.geojson         building outlines (a few are points)
        data/processed/<region>/data_centers_points.geojson  one point per feature, for zoomed-out views

These are data center buildings mapped by OSM volunteers: mostly built facilities, rarely approved
or planned ones, and a campus can be several buildings. Not a count of facilities, and no capacity.
"""

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import yaml
from shapely.geometry import Polygon

from build_transmission import get_tag

ROOT = Path(__file__).resolve().parent.parent

# Tags OSM mappers use for data centers; telecom=data_center is by far the most common here.
DATA_CENTER_TAG = re.compile(r'"(?:telecom|building|industrial)"=>"data_cent(?:er|re)"')


def read_data_centers(pbf: Path) -> gpd.GeoDataFrame:
    """Read data center features from every GDAL layer, with their OSM record type and id."""
    frames = []
    for layer in ["points", "lines", "multipolygons"]:
        # The multipolygons layer means assembling every shape in the state, so it is the slow one.
        print(f"Reading {layer}{' (slowest, a few minutes)' if layer == 'multipolygons' else ''}...", flush=True)
        found = pyogrio.read_dataframe(pbf, layer=layer, where="other_tags LIKE '%data_cent%'")
        if layer == "multipolygons":
            # building is its own column in this layer, so building=data_center isn't in other_tags.
            tagged = pyogrio.read_dataframe(pbf, layer=layer, where="building IN ('data_center', 'data_centre')")
            tagged["other_tags"] = tagged["other_tags"].fillna("") + ',"building"=>"data_center"'
            found = pd.concat([found, tagged]).drop_duplicates(subset=["osm_id", "osm_way_id"])
            is_way = found["osm_way_id"].notna()
            found["osm_type"] = is_way.map({True: "way", False: "relation"})
            found["osm_id"] = found["osm_way_id"].where(is_way, found["osm_id"])
        else:
            found["osm_type"] = "node" if layer == "points" else "way"
        if layer == "lines":
            # A closed outline that GDAL read as a line: turn it back into a shape.
            found = found[found.geometry.is_closed]
            found["geometry"] = found.geometry.map(lambda line: Polygon(line.coords))
        frames.append(found[["osm_type", "osm_id", "name", "other_tags", "geometry"]])
    found = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=frames[0].crs)
    return found[found["other_tags"].fillna("").str.contains(DATA_CENTER_TAG)]


def build(region_id: str) -> None:
    region = yaml.safe_load((ROOT / "regions" / f"{region_id}.yaml").read_text(encoding="utf-8"))
    raw_dir = ROOT / "data" / "raw" / region["osm_source"]
    record = json.loads((raw_dir / "_fetch.json").read_text(encoding="utf-8"))

    features = read_data_centers(raw_dir / record["file"])
    features["operator"] = features["other_tags"].map(lambda s: get_tag(s, "operator"))
    print(f"Read {len(features)} features tagged as data centers from {record['file']}")

    # Keep features whose inside point falls in the region.
    boundary = gpd.read_file(ROOT / "data" / "processed" / region_id / "counties.geojson").to_crs(features.crs)
    inside = features.geometry.representative_point().within(boundary.union_all())
    out = features[inside][["osm_type", "osm_id", "name", "operator", "geometry"]].sort_values(["osm_type", "osm_id"])

    out_dir = ROOT / "data" / "processed" / region_id
    out.to_file(out_dir / "data_centers.geojson", driver="GeoJSON")
    points = out.copy()
    points["geometry"] = out.geometry.representative_point()
    points.to_file(out_dir / "data_centers_points.geojson", driver="GeoJSON")

    by_county = gpd.sjoin(points, boundary[["name", "geometry"]], predicate="within")["name_right"].value_counts()
    print(f"Kept {len(out)} in {region['name']}: {out.geometry.geom_type.value_counts().to_dict()}")
    print(f"With a name: {out['name'].notna().sum()}, with an operator: {out['operator'].notna().sum()}")
    print("By jurisdiction (features, not facilities):")
    print(by_county.to_string())
    print(f"Saved {(out_dir / 'data_centers.geojson').relative_to(ROOT)} and data_centers_points.geojson")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("region", help="region id, e.g. nova")
    build(parser.parse_args().region)


if __name__ == "__main__":
    main()
