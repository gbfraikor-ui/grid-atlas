# Grid Atlas

A reproducible Python pipeline and interactive web map for studying how the built environment
and energy shape each other. The first region is Northern Virginia, starting with data centers,
grid infrastructure, and land-use policy.

## What's on the map

| Layer | Source | License |
|---|---|---|
| County and city boundaries | U.S. Census Bureau Cartographic Boundary Files, 2025 | Public domain |
| Transmission lines, substations | OpenStreetMap, via a dated Geofabrik extract | ODbL 1.0 |
| Background map | Protomaps Basemap, from OpenStreetMap and Natural Earth | ODbL 1.0 |
| Land-use and data center policy | Hand-researched in [policy/](policy/), with a source on every row | See each row's source |

**Read these limits before citing the map:**
- A jurisdiction marked "not yet researched" has no rows here. That does not mean it has no policy.
- OpenStreetMap is volunteer-mapped, not an official record of the grid. Coverage and tags can be
  missing or out of date. Line lengths and substation counts describe what is mapped.
- "Transmission" here means 69 kV and up. That is this project's working definition, set as
  `MIN_KV` in [pipeline/build_transmission.py](pipeline/build_transmission.py).
- County shading shows the stage of the latest policy row, not the strongest rule in force.

## Run it

You need [uv](https://docs.astral.sh/uv/). The site's data files are committed, so to view the map:

```bash
uv run python pipeline/serve.py
```

Then open http://localhost:8000. The plain `http.server` won't work, because the background map
needs HTTP range requests.

To rebuild the data from its sources:

```bash
uv run python pipeline/fetch.py
uv run python pipeline/build_counties.py nova
uv run python pipeline/build_transmission.py nova
uv run python pipeline/build_substations.py nova
uv run python pipeline/vendor_basemap.py
uv run python pipeline/build_basemap.py nova
uv run python pipeline/export.py nova
```

The Virginia extract is about 430 MB. Protomaps keeps daily builds for about a week, so
`build_basemap.py` needs a current build date in [sources/basemap.yaml](sources/basemap.yaml).

## How it's organized

```
sources/*.yaml    where each dataset comes from and its license
regions/*.yaml    which jurisdictions make up a region
policy/           hand-researched policy log; see policy/README.md
pipeline/         fetch → build → export
site/             the web map: plain HTML, CSS, and JS, with MapLibre GL JS
```

A region is a config file and a layer is a source plus a builder, so new regions and themes can be
added without rewriting the pipeline.

## License and credits

Code is under the [MIT License](LICENSE). Data in `site/data/` keeps the license of its source, and
OpenStreetMap-derived data is under the [Open Database License](https://www.openstreetmap.org/copyright).
Map data © OpenStreetMap contributors. Basemap by [Protomaps](https://github.com/protomaps/basemaps).
Vendored libraries and fonts in `site/vendor/` keep their own licenses, included beside them.
