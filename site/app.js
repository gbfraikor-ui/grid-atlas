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

// Color, line width, and circle size by highest voltage, lowest class first. "from" is the bottom of each class in kV.
const VOLTAGE_CLASSES = [
  { from: 500, label: "500 kV", color: "#ffffff", width: 2.6, radius: 6 },
  { from: 230, label: "230 kV up to 500 kV", color: "#4fd8ff", width: 1.9, radius: 4.5 },
  { from: 115, label: "115 kV up to 230 kV", color: "#3d8bff", width: 1.4, radius: 3.5 },
  { from: 0, label: "Under 115 kV", color: "#8f7bff", width: 1.1, radius: 3 },
].reverse();
const NO_VOLTAGE = { label: "No voltage tag in OSM", color: "#8a93a3", width: 1, radius: 3 };

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

function renderLegend(region) {
  const rows = Object.entries(STAGE_LABELS).map(([stage, label]) => legendRow(STAGE_COLORS[stage], label));
  const legend = [el("h2", { textContent: "Policy status" }), ...rows];

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

// A MapLibre "step" expression: pick a class value by the feature's highest voltage.
function byVoltage(property) {
  const steps = VOLTAGE_CLASSES.slice(1).flatMap((c) => [c.from, c[property]]);
  const noVoltage = ["==", ["get", "voltage_known"], false];
  return ["case", noVoltage, NO_VOLTAGE[property], ["step", ["to-number", ["get", "max_kv"], 0], VOLTAGE_CLASSES[0][property], ...steps]];
}

function renderDetails(county, policy) {
  const rows = policy.filter((r) => r.geoid === county.geoid).sort((a, b) => b.date.localeCompare(a.date));
  const body = rows.length
    ? rows.map(policyRow)
    : [el("p", { className: "hint", textContent: "Not yet researched. No rows does not mean no policy." })];
  document.getElementById("details").replaceChildren(
    el("h3", { textContent: county.name }),
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
  const [region, policy] = await Promise.all([loadJSON(`${DATA}/region.json`), loadJSON(`${DATA}/policy.json`)]);

  document.getElementById("region-name").textContent = region.name;
  renderLegend(region);
  renderStatewide(policy);

  const credits = [`Boundaries: <a href="${region.layers.counties.source_url}">U.S. Census Bureau</a>`];
  const lines = region.layers.transmission;
  if (lines.status === "built") credits.push(`Power lines and substations: &copy; <a href="${lines.license_url}">OpenStreetMap contributors</a>`);

  const map = new maplibregl.Map({
    container: "map",
    style: baseStyle(region),
    bounds: region.bounds,
    fitBoundsOptions: { padding: 40 },
    attributionControl: { compact: false, customAttribution: credits },
  });

  map.on("load", () => {
    // Our layers go under the basemap's labels, so place names stay readable on top.
    const firstLabel = region.layers.basemap.status === "built" ? basemapLabels()[0].id : undefined;
    const addLayer = (layer) => map.addLayer(layer, firstLabel);

    map.addSource("counties", { type: "geojson", data: `${DATA}/counties.geojson`, promoteId: "geoid" });

    const fillColor = ["match", ["get", "latest_stage"], ...Object.entries(STAGE_COLORS).flat(), STAGE_COLORS.withdrawn];
    addLayer({
      id: "counties-fill",
      type: "fill",
      source: "counties",
      paint: {
        "fill-color": fillColor,
        // Light enough to see the basemap through. Counties with no research get no fill at all.
        "fill-opacity": [
          "case",
          ["==", ["get", "latest_stage"], "not_researched"], ["case", ["boolean", ["feature-state", "hover"], false], 0.12, 0],
          ["boolean", ["feature-state", "hover"], false], 0.45,
          0.28,
        ],
      },
    });
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
    map.on("click", "counties-fill", (e) => renderDetails(e.features[0].properties, policy));

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

    // Built last, once every map layer exists for the checkboxes to control.
    renderLayers(region, map);
  });
}

main().catch((err) => {
  document.getElementById("details").replaceChildren(el("p", { textContent: `Error: ${err.message}` }));
  console.error(err);
});
