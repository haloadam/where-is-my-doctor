/* Renderer-independent shared code for both the MapLibre (WebGL) path and the Leaflet
   (Canvas2D) fallback. Holds the colour palette, the click-popup HTML, the home framing,
   and the data-freshness badge — so the two renderers can't drift apart. Exposed as window.GP
   because the app uses classic <script> tags (no bundler/modules). */
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

  // The home framing — used by both renderers and the "Back to Hungary" recenter logic.
  const HOME = { center: [19.5033, 47.1625], zoom: 6.4 }; // [lng, lat]
  const HU = { w: 16.0, s: 45.7, e: 23.0, n: 48.6 };

  // "Lost the country" = the centre of the view has left Hungary (a fast pan/fling). Works for
  // both a MapLibre LngLat and a Leaflet LatLng (both expose .lng and .lat).
  function countryLost(c) {
    return c.lng < HU.w || c.lng > HU.e || c.lat < HU.s || c.lat > HU.n;
  }

  // The fill colour for a settlement polygon — the JS equivalent of the MapLibre case/match
  // paint expression: desert wins, then the access band, then a neutral no-data grey.
  function fillColor(p) {
    if (p.is_desert == 1) return BANDS.desert;
    return BANDS.palette[p.access_band] || "#cccccc";
  }

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

  // Freshness badge from meta.json — renderer-independent, so it runs once on load.
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

  window.GP = { BANDS, CLASS_HU, CLASS_TIP, HOME, HU, countryLost, fillColor, fmt, popupHtml };
})();
