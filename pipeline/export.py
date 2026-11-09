"""Export one region's processed data for the website.

Usage:
    uv run python pipeline/export.py nova

Reads:  data/processed/<region>/counties.geojson   (from build_counties.py)
        policy/<region>.csv                        (hand-researched policy log)
        data/raw/counties/_fetch.json              (provenance)
Writes: site/data/<region>/counties.geojson        counties + a summary of their policy rows
        site/data/<region>/policy.json             every policy row, for the sidebar
        site/data/<region>/in_force.json           rules in force per jurisdiction (policy/<region>_in_force.csv)
        site/data/<region>/transmission.geojson    power lines, if build_transmission.py has run
        site/data/<region>/substations.geojson     substations, if build_substations.py has run
        site/data/<region>/basemap.pmtiles         background map, if build_basemap.py has run
        site/data/<region>/region.json             name, bounds, layer list with sources
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import yaml

from build_transmission import MIN_KV

ROOT = Path(__file__).resolve().parent.parent

# Layers the map will eventually have. Anything not built yet is shown as "pending".
PLANNED_LAYERS = ["basemap", "counties", "policy", "transmission", "substations"]


def latest_rows(policy: pd.DataFrame) -> pd.DataFrame:
    """Each jurisdiction's most recent policy row (by date; file order breaks ties)."""
    ordered = policy.reset_index().sort_values(["date", "index"])
    return ordered.groupby("geoid").tail(1).set_index("geoid")


def export(region_id: str) -> None:
    region = yaml.safe_load((ROOT / "regions" / f"{region_id}.yaml").read_text(encoding="utf-8"))
    out_dir = ROOT / "site" / "data" / region_id
    out_dir.mkdir(parents=True, exist_ok=True)

    counties = gpd.read_file(ROOT / "data" / "processed" / region_id / "counties.geojson")
    policy = pd.read_csv(ROOT / "policy" / f"{region_id}.csv", dtype=str, keep_default_na=False)

    # Join a short policy summary onto each county. Statewide rows (2-digit geoid) are not
    # attached to counties; the sidebar shows them separately. Town rows are left out too, since
    # a town's rule covers only the town, not the county it sits in.
    local = policy[(policy["geoid"].str.len() == 5) & (policy["town"] == "")]
    latest = latest_rows(local)
    counties["policy_rows"] = counties["geoid"].map(local["geoid"].value_counts()).fillna(0).astype(int)
    counties["latest_stage"] = counties["geoid"].map(latest["stage"]).fillna("not_researched")
    counties["latest_action"] = counties["geoid"].map(latest["action"]).fillna("")
    counties["latest_date"] = counties["geoid"].map(latest["date"]).fillna("")

    # Rules in force: our reading of each jurisdiction's current rules, with the policy rows it rests on.
    in_force_file = ROOT / "policy" / f"{region_id}_in_force.csv"
    in_force = pd.read_csv(in_force_file, dtype=str, keep_default_na=False) if in_force_file.exists() else pd.DataFrame(
        columns=["geoid", "town", "category", "basis", "summary"])
    cited = {pid for basis in in_force["basis"] for pid in basis.split(";")}
    missing = cited - set(policy["policy_id"])
    if missing:
        raise SystemExit(f"{in_force_file.name} cites policy_ids not in the policy table: {sorted(missing)}")
    county_level = in_force[in_force["town"] == ""].set_index("geoid")
    counties["in_force"] = counties["geoid"].map(county_level["category"]).fillna("not_researched")
    counties.to_file(out_dir / "counties.geojson", driver="GeoJSON")
    (out_dir / "in_force.json").write_text(
        json.dumps(in_force.to_dict(orient="records"), indent=2), encoding="utf-8", newline="\n"
    )

    (out_dir / "policy.json").write_text(
        json.dumps(policy.to_dict(orient="records"), indent=2), encoding="utf-8", newline="\n"
    )

    fetch_record = json.loads((ROOT / "data" / "raw" / "counties" / "_fetch.json").read_text(encoding="utf-8"))
    built = {
        "counties": {
            "status": "built",
            "file": "counties.geojson",
            "source_url": fetch_record["url"],
            "license": fetch_record["license"],
            "retrieved_at": fetch_record["retrieved_at"],
        },
        "policy": {
            "status": "built",
            "file": "policy.json",
            "rows": len(policy),
            "note": "Hand-researched; each row carries its own source_url, source_type and as_of.",
        },
    }
    # Optional layers: exported if their builder has run, otherwise they stay "pending".
    for layer in ["transmission", "substations"]:
        layer_file = ROOT / "data" / "processed" / region_id / f"{layer}.geojson"
        if not layer_file.exists():
            continue
        source = yaml.safe_load((ROOT / "sources" / f"{region['osm_source']}.yaml").read_text(encoding="utf-8"))
        osm_record = json.loads((ROOT / "data" / "raw" / source["id"] / "_fetch.json").read_text(encoding="utf-8"))
        shutil.copyfile(layer_file, out_dir / layer_file.name)
        built[layer] = {
            "status": "built",
            "file": layer_file.name,
            "source_title": source["title"],
            "source_url": osm_record["url"],
            "license": osm_record["license"],
            "license_url": source["license_url"],
            "retrieved_at": osm_record["retrieved_at"],
            "min_kv": MIN_KV,
            "note": "Volunteer-mapped OpenStreetMap data, not an official record of the grid.",
        }

    basemap_file = ROOT / "data" / "processed" / region_id / "basemap.pmtiles"
    if basemap_file.exists():
        shutil.copyfile(basemap_file, out_dir / basemap_file.name)
        record = json.loads(basemap_file.with_suffix(".json").read_text(encoding="utf-8"))
        built["basemap"] = {"status": "built", "file": basemap_file.name, **record}

    west, south, east, north = counties.total_bounds
    region_json = {
        "id": region["id"],
        "name": region["name"],
        "bounds": [round(west, 4), round(south, 4), round(east, 4), round(north, 4)],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "layers": {name: built.get(name, {"status": "pending"}) for name in PLANNED_LAYERS},
    }
    (out_dir / "region.json").write_text(json.dumps(region_json, indent=2), encoding="utf-8", newline="\n")

    print(f"Exported {region['name']} to {out_dir.relative_to(ROOT)}")
    print(counties[["geoid", "name", "policy_rows", "latest_stage", "latest_date", "in_force"]].to_string(index=False))
    print("Layers:", {k: v["status"] for k, v in region_json["layers"].items()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("region", help="region id, e.g. nova")
    export(parser.parse_args().region)


if __name__ == "__main__":
    main()
