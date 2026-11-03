# Policy data

Policy facts live here and only here, never in code.

## One row = one policy action at one stage

`<region>.csv` is a log of events, not a status table. A county that proposes a data center
ordinance in March and adopts it in July gets **two rows** sharing one `policy_id`. The map
works out each jurisdiction's current status from its latest row, and the year histogram
comes from the dates.

| column | meaning |
|---|---|
| `policy_id` | shared id linking all stages of one policy, e.g. `VA-EO-22-2026` or a county ordinance number |
| `geoid` | 5-digit county FIPS (e.g. `51107`), or 2-digit state FIPS (`51`) for statewide actions |
| `jurisdiction` | name as in `regions/<region>.yaml`, or the state name for statewide actions |
| `date` | date this stage happened (YYYY-MM-DD), taken from the source |
| `stage` | `proposed` · `adopted` · `effective` · `withdrawn` · `failed` · `rescinded` (reversed by the body that adopted it) · `voided` (struck down by a court) |
| `action` | `zoning_amendment` · `comprehensive_plan` · `moratorium` · `application_pause` · `executive_order` · `legislation` · `other` |
| `threshold_mw` | size cutoff in MW if the policy sets one, else blank |
| `topics` | semicolon-separated: `siting` · `incentives` · `transparency` · `noise` · `air` · `water` · `energy_cost` · `grid` · `workforce` |
| `summary` | one plain sentence on what it does, no adjectives |
| `source_title` | title of the document or article |
| `source_url` | link to it |
| `source_type` | `primary` (ordinance, minutes, staff report, official site) · `reporting` (news) · `none` |
| `as_of` | date we last checked the source (YYYY-MM-DD) |
| `notes` | anything uncertain or easy to misread, with page or section references |

## Rules
- No row without a date that appears in the source.
- Record every stage. If a source says a policy took effect on signing, add both an
  `adopted` and an `effective` row with the same date.
- `moratorium` = a ban on accepting or approving applications. `application_pause` = the governing
  body pauses its own final votes while applications keep moving (e.g. Loudoun 2026). Use the
  term the source's legal framing supports, not the headline's.
- Deferrals and rescheduled votes go in `notes`, not in their own rows.
- Rules vs. projects: this table holds rules that apply across an area (ordinances, comprehensive
  plan changes, orders, laws). Approvals for specific projects on specific parcels, such as a
  rezoning for one data center campus, belong in the events layer, not here.
- `reporting` rows are allowed but get upgraded to `primary` when we find the document.
- A jurisdiction with no rows shows on the map as "not yet researched", not "no policy".
