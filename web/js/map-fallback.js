/* WebGL-free fallback renderer — Leaflet on the Canvas2D renderer (preferCanvas), loaded by
   boot.js only when WebGL is unavailable or MapLibre fails to initialise. It cannot read the
   vector PMTiles, so it draws a simplified GeoJSON of the same settlements (./data/
   settlements.web.geojson) plus a lazily-loaded vacant-points layer. Colour palette, popup HTML
   and home framing come from shared.js (window.GP) so this stays in sync with the WebGL path. */
(function () {
  "use strict";

  const GP = window.GP;
  const { fillColor, popupHtml, HOME, countryLost } = GP;
  const HOME_LATLNG = [HOME.center[1], HOME.center[0]]; // GeoJSON/MapLibre [lng,lat] -> Leaflet [lat,lng]

  const mapEl = document.getElementById("map");
  // Raise the legend/recenter above Leaflet's panes (z-index 400-1000) and paint the no-data
  // background to match the MapLibre 'bg' layer (#eaeaf2). Scoped to this class (see style.css).
  document.body.classList.add("fallback-2d");

  const map = L.map(mapEl, {
    preferCanvas: true,   // all vector layers render to one shared <canvas> — no WebGL, no SVG storm
    zoomSnap: 0,          // allow the fractional home zoom (6.4); Leaflet snaps to integers otherwise
    attributionControl: false,
  }).setView(HOME_LATLNG, HOME.zoom);

  L.control.attribution({ prefix: false })
    .addAttribution("NEAK · OKFŐ · KSH · © OpenStreetMap")
    .addTo(map);

  function onEach(feature, layer) {
    layer.bindPopup(popupHtml(feature.properties), { maxWidth: 320 });
    layer.on("mouseover", () => { mapEl.style.cursor = "pointer"; });
    layer.on("mouseout", () => { mapEl.style.cursor = ""; });
  }

  // Settlement choropleth — same palette as the WebGL fill; white hairline outlines.
  const polyStyle = (f) => ({
    fillColor: fillColor(f.properties), fillOpacity: 0.85,
    color: "#ffffff", weight: 0.5, opacity: 1,
  });
  const settlements = L.geoJSON(null, { style: polyStyle, onEachFeature: onEach }).addTo(map);
  fetch("./data/settlements.web.geojson")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((gj) => settlements.addData(gj))
    .catch((e) => console.error("settlements.web.geojson betöltése sikertelen", e));

  // Vacant points — black w/ yellow ring if persistently vacant, else orange. Fixed radius
  // (Leaflet circleMarker is in pixels and doesn't auto-scale with zoom like the WebGL layer).
  const vacantStyle = (f) => {
    const persistent = f.properties.persistently_vacant_count > 0;
    return {
      radius: 4,
      fillColor: persistent ? "#000000" : "#fd8d3c", fillOpacity: 0.9,
      color: persistent ? "#facc15" : "#ffffff", weight: 1.4, opacity: 1,
    };
  };
  let vacant = null; // built + fetched lazily on first toggle-on so the fallback's first load stays lean
  const toggle = document.getElementById("toggle-vacant");
  if (toggle) {
    toggle.addEventListener("change", (e) => {
      const on = e.target.checked;
      document.querySelector(".vac-key").hidden = !on;
      if (!on) { if (vacant) map.removeLayer(vacant); return; }
      if (!vacant) {
        vacant = L.geoJSON(null, {
          pointToLayer: (f, latlng) => L.circleMarker(latlng, vacantStyle(f)),
          onEachFeature: onEach,
        });
        fetch("./data/vacant.web.geojson")
          .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
          .then((gj) => vacant.addData(gj))
          .catch((err) => console.error("vacant.web.geojson betöltése sikertelen", err));
      }
      vacant.addTo(map);
    });
  }

  // Expose flyTo for the worst-100 table. Keep the (lng, lat) signature table.js expects;
  // swap to Leaflet's [lat, lng] internally.
  window.flyToSettlement = (lng, lat) => map.flyTo([lat, lng], 11, { duration: 0.6 });
  window.__map = map;

  // "Back to Hungary": same heuristic as the WebGL path. Leaflet getCenter() returns a LatLng
  // which also exposes .lng/.lat, so countryLost() works unchanged.
  const recenterBtn = document.getElementById("recenter");
  function updateRecenter() { if (recenterBtn) recenterBtn.hidden = !countryLost(map.getCenter()); }
  if (recenterBtn) {
    recenterBtn.addEventListener("click", () => map.flyTo(HOME_LATLNG, HOME.zoom, { duration: 0.6 }));
    map.on("moveend", updateRecenter);
    map.on("resize", updateRecenter);
    updateRecenter();
  }
})();
