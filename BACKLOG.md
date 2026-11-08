# Backlog

Ideas not in v1. v1 = Northern Virginia: counties + policy, transmission, substations,
data centers, minimal map. Anything here needs a named data source before it moves into scope.

## Demand side: how the built environment uses energy
- Other large-load building types (labs, hospitals, industrial, campuses).
- Residential energy use and burden by neighborhood.
- Transportation electrification (EV charging, transit, freight depots).

## Supply side: how energy shapes cities
- Existing generation by fuel type, including renewables.
- New generation: utility-scale solar and wind, storage, SMRs, fusion.
  Most SMR and all fusion projects are proposals, not built plants, so this layer would
  hold announcements with dates and sources (like policy), not infrastructure geometry.

## Events layer (projects, not rules)
- Table of project-level events: rezonings, special exceptions, court rulings, withdrawals.
  Uses the same stages as policy, including `voided`.
- First entries: PW Digital Gateway rezonings REZ2022-00032, -00033, -00036 (approved Dec 2023;
  voided after Court of Appeals order 2026-07-29), per https://www.pwcva.gov/department/planning-office/pw-digital-gateway.
  Exact approval date and votes still need a primary source.
- Frederick County: Winchester Gateway CUP #03-26 denied 2026-10-28; Virginia Technology Park withdrawn,
  per https://www.fcva.us/services/information-hub/data-centers.
- Stafford County: Accokeek Center rezoning (Ord. O26-16) and substation CUP (Res. R26-128), approved 4-3
  on 2026-10-07 per Potomac Local (reporting); Potomac Creek Campus deferred 2026-07-07 over a family
  cemetery. County records not yet read.
- Possible transmission line events: Frederick County's resolution opposing Valley Link's Valley North
  line, per https://www.fcva.us/Home/Components/News/News/1703/. Meeting date still needs a source.

## Map: "rules in force" view
- The v1 map shades each county by its latest policy row. That shows Loudoun as "proposed"
  (2026 pause) even though an adopted rule (end of by-right, 2025) is in force. Add a second
  view: strongest rule currently in force per county, once several counties have rows. Needed soon:
  Frederick's removal of data centers and Fairfax's zoning standards currently shade the same color.

## Map: individual building footprints
- The v1 basemap stops at zoom 14 (86 MB), where buildings are merged blocks. Zoom 15 has separate
  footprints but is too large for a single file in the repo (161 MB for the counties alone, measured
  2026-11-02). Would need hosting outside the repo. Goes with the site-card view with hatched parcels.

## Policy table extensions
- `deadline` column for directives with due dates (e.g. EO 22's 180-day agency reports).
- `vote` column for board decisions (e.g. 6–3).
- Non-geographic bodies (SCC, PJM): decisions that don't map to one county.

## Map and analysis ideas (not v1)
v1 adds layer toggles, the "rules in force" view, and data center locations. These come later:
- Circles sized by data center capacity (MW or GW). Needs a sourced capacity per facility; announced
  figures from reporting are uneven, so don't imply measured demand.
- Other critical technology infrastructure, such as semiconductor plants.
- Building energy use. Needs an open building-level dataset; none identified for Virginia yet.
- Population vs. energy use (Census population is easy; energy use by area is the missing piece).
- 3D view (limited by the basemap stopping at zoom 14).
- Interactive "what if we build here" scenarios for grid impact. A modeling project of its own.

## Expansion
- Additional regions beyond Northern Virginia.
