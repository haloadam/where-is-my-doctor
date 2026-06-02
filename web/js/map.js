/* GP Desert Map — MapLibre + PMTiles frontend.
   All display properties are baked into the tiles, so styling/popups need no runtime
   data join. No glyphs/sprites are used (no on-map text) to keep the page dependency-free;
   settlement names appear in the click popup. */
(function () {
  "use strict";

  const BANDS = {
    desert: "#6a3d9a",
    palette: { 1: "#e31a1c", 2: "#fd8d3c", 3: "#fecc5c", 4: "#31a354" },
  };
  const CLASS_HU = { desert: "Sivatag", critical: "Kritikus", low: "Alacsony", moderate: "Közepes", ok: "Megfelelő" };
  const CLASS_TIP = {
    desert: "Minden ellátó háziorvosi körzet betöltetlen — nincs állandó háziorvos.",
    critical: "0,2-nél kevesebb betöltött körzet jut 1000 lakosra.",
    low: "0,2–0,4 betöltött körzet jut 1000 lakosra.",
    moderate: "0,4–0,6 betöltött körzet jut 1000 lakosra.",
    ok: "Legalább 0,6 betöltött háziorvosi körzet jut 1000 lakosra.",
  };

  // Register the PMTiles protocol so MapLibre can read ./data/settlements.pmtiles via byte-range.
  const protocol = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);

  const map = new maplibregl.Map({
    container: "map",
    center: [19.5033, 47.1625],
    zoom: 6.4,
    attributionControl: { compact: true },
    style: {
      version: 8,
      sources: {
        gp: { type: "vector", url: "pmtiles://./data/settlements.pmtiles",
              attribution: "NEAK · OKFŐ · KSH · © OpenStreetMap" },
      },
      layers: [
        { id: "bg", type: "background", paint: { "background-color": "#eaeaf2" } },
        {
          id: "settlements-fill", type: "fill", source: "gp", "source-layer": "settlements",
          paint: {
            "fill-color": [
              "case", ["==", ["get", "is_desert"], 1], BANDS.desert,
              ["match", ["get", "access_band"],
                1, BANDS.palette[1], 2, BANDS.palette[2], 3, BANDS.palette[3], 4, BANDS.palette[4],
                "#cccccc"],
            ],
            "fill-opacity": 0.85,
          },
        },
        {
          id: "settlements-outline", type: "line", source: "gp", "source-layer": "settlements",
          paint: { "line-color": "#ffffff", "line-width": ["interpolate", ["linear"], ["zoom"], 6, 0.15, 11, 0.7] },
        },
        {
          id: "vacant-points", type: "circle", source: "gp", "source-layer": "vacant",
          layout: { visibility: "none" },
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 2.5, 11, 6],
            "circle-color": ["case", [">", ["get", "persistently_vacant_count"], 0], "#000000", "#fd8d3c"],
            "circle-stroke-color": ["case", [">", ["get", "persistently_vacant_count"], 0], "#facc15", "#ffffff"],
            "circle-stroke-width": 1.4,
            "circle-opacity": 0.9,
          },
        },
      ],
    },
  });

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");

  function fmt(v, suffix) {
    if (v === null || v === undefined || v === "") return "–";
    return suffix ? v + suffix : v;
  }

  // [label, value, tooltip]
  function popupHtml(p) {
    const cls = p.access_class || "ok";
    const color = p.is_desert == 1 ? BANDS.desert : (BANDS.palette[p.access_band] || "#999");
    const road = p.nearest_gp_method === "road";
    const nearLabel = road ? "Legközelebbi háziorvos (közúton)" : "Legközelebbi háziorvos";
    const nearTip = road
      ? "A legközelebbi működő háziorvosi rendelő tényleges közúti távolsága és menetideje autóval (OSRM)."
      : "A legközelebbi működő háziorvosi rendelő — légvonalban × 1,4 becslés (nincs közúti útvonal).";
    const nearVal = p.nearest_gp_settlement
      ? `${p.nearest_gp_settlement} — ${fmt(p.nearest_gp_km, " km")}`
        + (road && p.nearest_gp_minutes != null ? ` · ~${p.nearest_gp_minutes} perc autóval` : "")
      : "–";
    const rows = [
      ["Lakónépesség", p.population != null ? Number(p.population).toLocaleString("hu") : "–",
        "Az állandó lakosok száma (KSH, 2025)."],
      ["Betöltött körzet", p.active_gp_count,
        "Ennyi háziorvosi körzet látja el a települést, amelyben van állandó háziorvos."],
      ["Betöltetlen körzet", p.vacant_count,
        "Ennyi ellátó körzet betöltetlen — nincs állandó háziorvosa."],
      ["Tartósan betöltetlen", p.persistently_vacant_count,
        "Több mint 6 hónapja betöltetlen körzetek száma (OKFŐ)."],
      ["Ellátottság (körzet / 1000 lakos)", p.gps_per_1000 != null ? p.gps_per_1000 : "–",
        "Betöltött háziorvosi körzetek száma 1000 lakosra. Minél kisebb, annál rosszabb (országos átlag ~0,45)."],
      [nearLabel, nearVal, nearTip],
      ["Mióta betöltetlen", p.longest_vacancy_days != null ? p.longest_vacancy_days + " nap" : "–",
        "A leghosszabb ideje betöltetlen körzet üresedése napokban."],
    ];
    return `<div class="popup"><h3>${p.name ?? "?"} <span class="muted">(${p.county ?? ""})</span></h3>
      <span class="tag" style="background:${color}" data-tip="${CLASS_TIP[cls] || ""}">${CLASS_HU[cls] || cls}</span>
      <table>${rows.map(([k, v, tip]) =>
        `<tr><td class="k" data-tip="${tip}">${k}</td><td>${v ?? "–"}</td></tr>`).join("")}</table></div>`;
  }

  map.on("load", () => {
    for (const layer of ["settlements-fill", "vacant-points"]) {
      map.on("click", layer, (e) => {
        const p = e.features[0].properties;
        new maplibregl.Popup({ maxWidth: "320px" }).setLngLat(e.lngLat).setHTML(popupHtml(p)).addTo(map);
      });
      map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
    }
  });

  document.getElementById("toggle-vacant").addEventListener("change", (e) => {
    const vis = e.target.checked ? "visible" : "none";
    map.setLayoutProperty("vacant-points", "visibility", vis);
    document.querySelector(".vac-key").hidden = !e.target.checked;
  });

  // Freshness badge from meta.json.
  fetch("./data/meta.json").then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }).then((m) => {
    const d = (m.generated || "").slice(0, 10);
    document.getElementById("freshness").textContent = `Adatok frissítve: ${d || "—"}`;
    window.__meta = m;
  }).catch((e) => {
    console.error("meta.json betöltése sikertelen", e);
    document.getElementById("freshness").textContent = "Adatok: nem elérhető";
  });

  // Surface a tile/source load failure instead of showing a blank map.
  map.on("error", (e) => {
    if (e && e.error) console.error("MapLibre hiba:", e.error.message || e.error);
  });

  // Expose flyTo for the worst-100 table.
  window.flyToSettlement = (lng, lat) => map.flyTo({ center: [lng, lat], zoom: 11 });
  window.__map = map;

  // "Back to Hungary": show a recenter button when the country scrolls out of view
  // (e.g. a fast fling on a touchscreen). Shown when Hungary covers <5% of the viewport.
  const HU = { w: 16.0, s: 45.7, e: 23.0, n: 48.6 };
  const HOME = { center: [19.5033, 47.1625], zoom: 6.4 };
  const recenterBtn = document.getElementById("recenter");
  // "Lost the country" = the centre of the view has left Hungary (a fast pan/fling). Zooming OUT
  // while still centred on Hungary does NOT trigger it — the centre is still over the country.
  function countryLost() {
    const c = map.getCenter();
    return c.lng < HU.w || c.lng > HU.e || c.lat < HU.s || c.lat > HU.n;
  }
  function updateRecenter() { if (recenterBtn) recenterBtn.hidden = !countryLost(); }
  if (recenterBtn) {
    recenterBtn.addEventListener("click", () => map.flyTo({ ...HOME, essential: true }));
    map.on("moveend", updateRecenter);
    map.on("resize", updateRecenter);
    map.on("load", updateRecenter);
  }
})();
