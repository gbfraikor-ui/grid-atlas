// Grid Atlas front end. Styling and UI only: every fact comes from site/data/<region>/.

const REGION = "nova";
const DATA = `data/${REGION}`;

// Fill color for each county, by the stage of its most recent policy row.
const STAGE_COLORS = {
  adopted: "#e8735a",
  effective: "#e8735a",
  proposed: "#e8b04a",
  withdrawn: "#5b6b88",
  failed: "#5b6b88",
  rescinded: "#5b6b88",
  voided: "#5b6b88",
  not_researched: "#1c222d",
};
const STAGE_LABELS = {
  adopted: "Latest action adopted / in effect",
  proposed: "Latest action proposed",
  withdrawn: "Latest action withdrawn, failed, rescinded, or voided",
  not_researched: "Not yet researched",
};

// Fill color by the rules a new data center applicant faces today (policy/<region>_in_force.csv).
const IN_FORCE = {
  not_allowed: { label: "Not allowed in any zoning district", color: "#d9534f" },
  approval_only: { label: "Board approval required for every new one", color: "#e8a94a" },
  by_right_limited: { label: "By right in limited areas", color: "#6dbb7a" },
  unclear: { label: "Rules adopted, category unclear", color: "#5b6b88" },
  not_researched: { label: "Not yet researched", color: "#1c222d" },
};

// The two ways to shade counties. Each names the county property it reads and its legend entries.
const VIEWS = {
  in_force: {
    label: "Rules in force",
    property: "in_force",
    colors: Object.fromEntries(Object.entries(IN_FORCE).map(([key, c]) => [key, c.color])),
    legend: Object.values(IN_FORCE).map((c) => [c.color, c.label]),
  },
  latest: {
    label: "Latest action",
    property: "latest_stage",
    colors: STAGE_COLORS,
    legend: Object.entries(STAGE_LABELS).map(([stage, label]) => [STAGE_COLORS[stage], label]),
  },
};
let view = "in_force";
let mapRef = null;  // set once the map exists, so the view switch can recolor it

function fillColor() {
  const v = VIEWS[view];
  return ["match", ["get", v.property], ...Object.entries(v.colors).flat(), "#5b6b88"];
}

// Light enough to see the basemap through. Counties with no research get no fill at all.
function fillOpacity() {
  const hover = ["boolean", ["feature-state", "hover"], false];
  return ["case", ["==", ["get", VIEWS[view].property], "not_researched"], ["case", hover, 0.12, 0], hover, 0.45, 0.28];
}

// Color, line width, and circle size by highest voltage, lowest class first. "from" is the bottom of each class in kV.
const VOLTAGE_CLASSES = [
  { from: 500, label: "500 kV", color: "#ffffff", width: 2.6, radius: 6 },
  { from: 230, label: "230 kV up to 500 kV", color: "#4fd8ff", width: 1.9, radius: 4.5 },
  { from: 115, label: "115 kV up to 230 kV", color: "#3d8bff", width: 1.4, radius: 3.5 },
  { from: 0, label: "Under 115 kV", color: "#8f7bff", width: 1.1, radius: 3 },
].reverse();
const NO_VOLTAGE = { label: "No voltage tag in OSM", color: "#8a93a3", width: 1, radius: 3 };

// Data center buildings: outlines from this zoom level in, a heat map of footprint below it.
const DATA_CENTER_COLOR = "#ff5fa2";
const DATA_CENTER_ZOOM = 12;
// Heat map colors from low to high density: clear, through the data center pink, to near white.
const HEAT_STOPS = [[0, "rgba(255,95,162,0)"], [0.2, "rgba(255,95,162,0.35)"], [0.5, "#ff5fa2"], [0.8, "#ffb3d6"], [1, "#fff4f9"]];
const HEAT_COLORS = ["interpolate", ["linear"], ["heatmap-density"], ...HEAT_STOPS.flat()];

// --- small helpers ---------------------------------------------------------

async function loadJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Could not load ${path} (${response.status})`);
  return response.json();
}

// Build an element. Text always goes in via textContent, never as HTML.
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  for (const child of children) node.append(child);
  return node;
}

function stageBadge(stage) {
  const badge = el("span", { className: "stage", textContent: stage });
  badge.style.background = STAGE_COLORS[stage] || STAGE_COLORS.withdrawn;
  return badge;
}

function policyRow(row) {
  const source = row.source_url
    ? el("a", { href: row.source_url, target: "_blank", rel: "noopener", textContent: row.source_title || "source" })
    : "no source";
  return el("div", { className: "policy-row" }, [
    row.town ? el("div", { className: "town", textContent: `Town of ${row.town}` }) : "",
    el("div", { className: "meta" }, [stageBadge(row.stage), ` ${row.date} · ${row.action.replaceAll("_", " ")}`]),
    el("p", { textContent: row.summary }),
    el("p", { className: "meta" }, [source, ` (${row.source_type}, checked ${row.as_of})`]),
    row.notes ? el("details", {}, [el("summary", { textContent: "Notes" }), row.notes]) : "",
  ]);
}

// --- sidebar sections ------------------------------------------------------

function legendRow(color, label, className = "swatch") {
  const swatch = el("span", { className });
  swatch.style.background = color;
  return el("div", { className: "legend-row" }, [swatch, label]);
}

// Two radio buttons that switch the county shading between views.
function viewSwitch(region) {
  return el("div", { className: "view-switch" }, Object.entries(VIEWS).map(([key, v]) => {
    const radio = el("input", { type: "radio", name: "view", value: key, checked: key === view });
    radio.addEventListener("change", () => {
      view = key;
      if (mapRef) {
        mapRef.setPaintProperty("counties-fill", "fill-color", fillColor());
        mapRef.setPaintProperty("counties-fill", "fill-opacity", fillOpacity());
      }
      renderLegend(region);
    });
    return el("label", {}, [radio, v.label]);
  }));
}

function renderLegend(region) {
  const rows = VIEWS[view].legend.map(([color, label]) => legendRow(color, label));
  const legend = [el("h2", { textContent: "County shading" }), viewSwitch(region), ...rows];
  if (view === "in_force") {
    legend.push(el("p", { className: "hint", textContent: "Our reading of what a new data center applicant faces today. Click a county for the basis." }));
  }

  const lines = region.layers.transmission;
  if (lines.status === "built") {
    legend.push(
      el("h2", { textContent: `Transmission lines, ${lines.min_kv} kV and up` }),
      ...[...VOLTAGE_CLASSES].reverse().map((c) => legendRow(c.color, c.label, "swatch-line")),
      legendRow(NO_VOLTAGE.color, NO_VOLTAGE.label, "swatch-line"),
    );
    if (region.layers.substations.status === "built") {
      legend.push(legendRow("#d8dee9", "Substation, colored by highest voltage", "swatch-dot"));
    }
    legend.push(el("p", { className: "hint", textContent: lines.note }));
  }

  const dcs = region.layers.data_centers;
  if (dcs.status === "built") {
    legend.push(
      el("h2", { textContent: "Data centers" }),
      legendRow(`linear-gradient(to right, ${HEAT_STOPS.slice(1).map(([, c]) => c).join(", ")})`, "Concentration of mapped footprint (zoomed out)", "swatch-heat"),
      legendRow(DATA_CENTER_COLOR, "Data center building mapped in OSM (zoom in)"),
      el("p", { className: "hint", textContent: dcs.note }),
    );
  }
  document.getElementById("legend").replaceChildren(...legend);
}

// Popup for a clicked power line, with a link to its OSM record so anyone can check it.
function linePopup(line) {
  const voltage = line.voltage_known ? `${line.max_kv} kV` : "No voltage tag in OSM";
  return el("div", { className: "line-popup" }, [
    el("strong", { textContent: line.name || `Power ${line.power}` }),
    el("div", { textContent: voltage }),
    el("div", { textContent: line.operator || "No operator tag in OSM" }),
    el("a", { href: `https://www.openstreetmap.org/way/${line.osm_id}`, target: "_blank", rel: "noopener", textContent: "View in OpenStreetMap" }),
  ]);
}

// Popup for a clicked substation. OSM tags are shown as mapped, so a blank says so.
function substationPopup(sub) {
  const voltage = sub.voltage_known ? `Highest voltage ${sub.max_kv} kV` : "No voltage tag in OSM";
  return el("div", { className: "line-popup" }, [
    el("strong", { textContent: sub.name || "Unnamed substation" }),
    el("div", { textContent: voltage }),
    el("div", { textContent: sub.operator || "No operator tag in OSM" }),
    el("div", { textContent: sub.substation_type ? `OSM type: ${sub.substation_type}` : "No type tag in OSM" }),
    el("a", { href: `https://www.openstreetmap.org/${sub.osm_type}/${sub.osm_id}`, target: "_blank", rel: "noopener", textContent: "View in OpenStreetMap" }),
  ]);
}

// Popup for a clicked data center building.
function dataCenterPopup(dc) {
  return el("div", { className: "line-popup" }, [
    el("strong", { textContent: dc.name || "Unnamed data center" }),
    el("div", { textContent: dc.operator || "No operator tag in OSM" }),
    dc.footprint_m2 > 0 ? el("div", { textContent: `Footprint about ${Math.round((dc.footprint_m2 * 10.7639) / 1000) * 1000} sq ft (ground area)` }) : "",
    el("a", { href: `https://www.openstreetmap.org/${dc.osm_type}/${dc.osm_id}`, target: "_blank", rel: "noopener", textContent: "View in OpenStreetMap" }),
  ]);
}

// A MapLibre "step" expression: pick a class value by the feature's highest voltage.
function byVoltage(property) {
  const steps = VOLTAGE_CLASSES.slice(1).flatMap((c) => [c.from, c[property]]);
  const noVoltage = ["==", ["get", "voltage_known"], false];
  return ["case", noVoltage, NO_VOLTAGE[property], ["step", ["to-number", ["get", "max_kv"], 0], VOLTAGE_CLASSES[0][property], ...steps]];
}

// The rules-in-force reading for a county and any towns in it, with the policy rows it rests on.
function inForceBlock(entry) {
  const category = IN_FORCE[entry.category] || IN_FORCE.unclear;
  const badge = el("span", { className: "stage", textContent: category.label });
  badge.style.background = category.color;
  return el("div", { className: "in-force" }, [
    entry.town ? el("div", { className: "town", textContent: `Town of ${entry.town}` }) : "",
    badge,
    el("p", { textContent: entry.summary }),
    el("p", { className: "meta", textContent: `Based on: ${entry.basis.replaceAll(";", ", ")} · as of ${entry.as_of}` }),
    entry.notes ? el("details", {}, [el("summary", { textContent: "Notes" }), entry.notes]) : "",
  ]);
}

function renderDetails(county, policy, inForce) {
  const rows = policy.filter((r) => r.geoid === county.geoid).sort((a, b) => b.date.localeCompare(a.date));
  const readings = inForce.filter((r) => r.geoid === county.geoid).sort((a, b) => a.town.localeCompare(b.town));
  const body = rows.length
    ? rows.map(policyRow)
    : [el("p", { className: "hint", textContent: "Not yet researched. No rows does not mean no policy." })];
  document.getElementById("details").replaceChildren(
    el("h3", { textContent: county.name }),
    ...readings.map(inForceBlock),
    el("p", { className: "meta", textContent: `${rows.length} policy rows, newest first` }),
    ...body,
  );
}

function renderStatewide(policy) {
  const rows = policy.filter((r) => r.geoid.length === 2);
  document.getElementById("statewide").replaceChildren(el("h2", { textContent: "Statewide" }), ...rows.map(policyRow));
}

// Which map layers each layer toggle controls. The basemap's own layers are found by their source.
const LAYER_TOGGLES = {
  basemap: { label: "Background map", ids: (map) => map.getStyle().layers.filter((l) => l.source === "protomaps").map((l) => l.id) },
  counties: { label: "County and city boundaries", ids: () => ["counties-glow", "counties-line"] },
  policy: { label: "Policy status shading", ids: () => ["counties-fill"] },
  transmission: { label: "Transmission lines", ids: () => ["transmission-glow", "transmission-line", "transmission-hit"] },
  substations: { label: "Substations", ids: () => ["substations-circle"] },
  data_centers: { label: "Data center buildings", ids: () => ["data-centers-heat", "data-centers-fill", "data-centers-line"] },
};

// One checkbox per layer. Unbuilt layers stay listed as "pending" so readers can see what's coming.
function renderLayers(region, map) {
  const rows = Object.entries(region.layers).map(([name, layer]) => {
    const toggle = LAYER_TOGGLES[name];
    const ids = toggle ? toggle.ids(map).filter((id) => map.getLayer(id)) : [];
    const box = el("input", { type: "checkbox", checked: ids.length > 0, disabled: ids.length === 0 });
    box.addEventListener("change", () => {
      for (const id of ids) map.setLayoutProperty(id, "visibility", box.checked ? "visible" : "none");
    });
    const status = layer.status === "built" ? "" : el("span", { className: "pending", textContent: layer.status });
    return el("label", { className: "layer-row" }, [box, el("span", { textContent: toggle ? toggle.label : name }), status]);
  });
  document.getElementById("layers").replaceChildren(el("h2", { textContent: "Layers" }), ...rows);
}

// --- map -------------------------------------------------------------------

// The basemap's label layers, on their own, so we can draw our data underneath them.
function basemapLabels() {
  return basemaps.layers("protomaps", basemaps.namedFlavor("dark"), { lang: "en", labelsOnly: true });
}

// The map's starting style: the Protomaps dark basemap, or a plain background if it is not built.
function baseStyle(region) {
  const basemap = region.layers.basemap;
  if (basemap.status !== "built") {
    return { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#0b0e14" } }] };
  }
  // PMTiles reads tiles out of one file using range requests. This teaches MapLibre the pmtiles:// address.
  maplibregl.addProtocol("pmtiles", new pmtiles.Protocol().tile);
  const root = new URL(".", location.href).href;  // MapLibre needs full URLs here
  return {
    version: 8,
    glyphs: `${root}vendor/protomaps/fonts/{fontstack}/{range}.pbf`,
    sprite: `${root}vendor/protomaps/sprites/v4/dark`,
    sources: {
      protomaps: {
        type: "vector",
        url: `pmtiles://${root}${DATA}/${basemap.file}`,
        attribution: `Basemap: <a href="https://github.com/protomaps/basemaps">Protomaps</a> &copy; <a href="${basemap.license_url}">OpenStreetMap</a>`,
      },
    },
    layers: basemaps.layers("protomaps", basemaps.namedFlavor("dark"), { lang: "en" }),
  };
}

async function main() {
  const [region, policy, inForce] = await Promise.all([
    loadJSON(`${DATA}/region.json`), loadJSON(`${DATA}/policy.json`), loadJSON(`${DATA}/in_force.json`),
  ]);

  document.getElementById("region-name").textContent = region.name;
  renderLegend(region);
  renderStatewide(policy);

  const credits = [`Boundaries: <a href="${region.layers.counties.source_url}">U.S. Census Bureau</a>`];
  const lines = region.layers.transmission;
  if (lines.status === "built") credits.push(`Power lines, substations, data centers: &copy; <a href="${lines.license_url}">OpenStreetMap contributors</a>`);

  const map = new maplibregl.Map({
    container: "map",
    style: baseStyle(region),
    bounds: region.bounds,
    fitBoundsOptions: { padding: 40 },
    attributionControl: { compact: false, customAttribution: credits },
  });
  mapRef = map;

  map.on("load", () => {
    // Our layers go under the basemap's labels, so place names stay readable on top.
    const firstLabel = region.layers.basemap.status === "built" ? basemapLabels()[0].id : undefined;
    const addLayer = (layer) => map.addLayer(layer, firstLabel);

    map.addSource("counties", { type: "geojson", data: `${DATA}/counties.geojson`, promoteId: "geoid" });

    addLayer({ id: "counties-fill", type: "fill", source: "counties", paint: { "fill-color": fillColor(), "fill-opacity": fillOpacity() } });
    // Two outline layers: a wide blurred one for glow, a thin sharp one on top.
    addLayer({ id: "counties-glow", type: "line", source: "counties", paint: { "line-color": "#8ab4f8", "line-width": 6, "line-blur": 6, "line-opacity": 0.25 } });
    addLayer({ id: "counties-line", type: "line", source: "counties", paint: { "line-color": "#c9d6ea", "line-width": 0.8 } });

    let hovered = null;
    map.on("mousemove", "counties-fill", (e) => {
      if (hovered !== null) map.setFeatureState({ source: "counties", id: hovered }, { hover: false });
      hovered = e.features[0].id;
      map.setFeatureState({ source: "counties", id: hovered }, { hover: true });
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "counties-fill", () => {
      if (hovered !== null) map.setFeatureState({ source: "counties", id: hovered }, { hover: false });
      hovered = null;
      map.getCanvas().style.cursor = "";
    });
    map.on("click", "counties-fill", (e) => renderDetails(e.features[0].properties, policy, inForce));

    const dcs = region.layers.data_centers;
    if (dcs.status === "built") {
      map.addSource("data-centers", { type: "geojson", data: `${DATA}/${dcs.file}` });
      map.addSource("data-centers-points", { type: "geojson", data: `${DATA}/${dcs.points_file}` });
      addLayer({ id: "data-centers-fill", type: "fill", source: "data-centers", minzoom: DATA_CENTER_ZOOM, paint: { "fill-color": DATA_CENTER_COLOR, "fill-opacity": 0.55 } });
      addLayer({ id: "data-centers-line", type: "line", source: "data-centers", minzoom: DATA_CENTER_ZOOM, paint: { "line-color": DATA_CENTER_COLOR, "line-width": 1 } });
      map.on("click", "data-centers-fill", (e) => {
        new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(dataCenterPopup(e.features[0].properties)).addTo(map);
      });
      map.on("mouseenter", "data-centers-fill", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "data-centers-fill", () => { map.getCanvas().style.cursor = ""; });
    }

    if (lines.status === "built") {
      map.addSource("transmission", { type: "geojson", data: `${DATA}/${lines.file}` });
      // Same two-layer idea as the county outlines: blurred glow underneath, sharp line on top.
      addLayer({ id: "transmission-glow", type: "line", source: "transmission", paint: { "line-color": byVoltage("color"), "line-width": 7, "line-blur": 6, "line-opacity": 0.35 } });
      addLayer({ id: "transmission-line", type: "line", source: "transmission", paint: { "line-color": byVoltage("color"), "line-width": byVoltage("width") } });
      // Thin lines are hard to click, so an invisible wide layer catches the mouse.
      addLayer({ id: "transmission-hit", type: "line", source: "transmission", paint: { "line-width": 12, "line-opacity": 0 } });
      map.on("click", "transmission-hit", (e) => {
        // A substation sits on top of its lines, so let its own popup win.
        if (map.getLayer("substations-circle") && map.queryRenderedFeatures(e.point, { layers: ["substations-circle"] }).length) return;
        new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(linePopup(e.features[0].properties)).addTo(map);
      });
      map.on("mouseenter", "transmission-hit", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "transmission-hit", () => { map.getCanvas().style.cursor = ""; });
    }

    const subs = region.layers.substations;
    if (subs.status === "built") {
      map.addSource("substations", { type: "geojson", data: `${DATA}/${subs.file}` });
      addLayer({
        id: "substations-circle",
        type: "circle",
        source: "substations",
        paint: {
          "circle-color": byVoltage("color"),
          "circle-radius": byVoltage("radius"),
          "circle-stroke-color": "#0b0e14",
          "circle-stroke-width": 1,
        },
      });
      map.on("click", "substations-circle", (e) => {
        new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(substationPopup(e.features[0].properties)).addTo(map);
      });
      map.on("mouseenter", "substations-circle", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "substations-circle", () => { map.getCanvas().style.cursor = ""; });
    }

    // Zoomed out: a heat map of mapped data center footprint, on top so the concentration reads at a
    // glance (it's translucent, so lines and substations show through). It fades out as the building
    // outlines fade in at DATA_CENTER_ZOOM.
    if (dcs.status === "built") {
      addLayer({
        id: "data-centers-heat",
        type: "heatmap",
        source: "data-centers-points",
        maxzoom: DATA_CENTER_ZOOM + 1,
        paint: {
          // Bigger footprints count more, capped so one campus-sized outline can't swamp the map.
          "heatmap-weight": ["interpolate", ["linear"], ["get", "footprint_m2"], 0, 0.25, 12000, 0.6, 50000, 1],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 7, 0.8, 12, 2],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 7, 14, 10, 24, 12, 34],
          "heatmap-color": HEAT_COLORS,
          "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], DATA_CENTER_ZOOM - 0.5, 0.75, DATA_CENTER_ZOOM + 1, 0],
        },
      });
    }


    // Built last, once every map layer exists for the checkboxes to control.
    renderLayers(region, map);
  });
}

main().catch((err) => {
  document.getElementById("details").replaceChildren(el("p", { textContent: `Error: ${err.message}` }));
  console.error(err);
});
