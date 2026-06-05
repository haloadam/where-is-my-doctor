/* GP Desert Map — MapLibre + PMTiles frontend (the WebGL path).
   Loaded by boot.js only after a WebGL pre-flight passes. All display properties are baked into
   the tiles, so styling/popups need no runtime data join. No glyphs/sprites are used (no on-map
   text); settlement names appear in the click popup. Colour palette, popup HTML and home framing
   live in shared.js (window.GP) so the Leaflet fallback stays in sync.

   Belt-and-suspenders: even after a passing pre-flight, MapLibre can still fail to initialise
   WebGL (the probe canvas differs from the real one; the context can be lost between probe and
   init). The constructor throws synchronously on failure, and 'webglcontextlost'/'error' fire
   asynchronously — in either case we tear the half-created map down and hand off to the 2D
   fallback via window.__mount2D(). */
(function () {
  "use strict";

  const GP = window.GP;
  const { BANDS, popupHtml, HOME, countryLost } = GP;

  // Register the PMTiles protocol so MapLibre can read ./data/settlements.pmtiles.
  const PMTILES_URL = "./data/settlements.pmtiles";
  const protocol = new pmtiles.Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);

  // GitHub Pages (and its CDN) doesn't reliably honour HTTP Range requests: it often
  // answers a byte-range request with "200 OK" + the whole body, which makes PMTiles
  // throw "...supports HTTP Byte Serving". The archive is small (~4 MB), so fetch it
  // once and serve byte ranges from memory — no server-side byte serving needed.
  // The fetch is lazy (on first tile/header read) and cached, and getKey() must match
  // the URL the style references (the part after "pmtiles://") so protocol.add() wires up.
  const bufferedSource = (url) => {
    let bufferPromise = null;
    return {
      getKey: () => url,
      getBytes: async (offset, length) => {
        if (!bufferPromise) {
          bufferPromise = fetch(url).then((r) => {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.arrayBuffer();
          });
        }
        const buffer = await bufferPromise;
        return { data: buffer.slice(offset, offset + length) };
      },
    };
  };
  protocol.add(new pmtiles.PMTiles(bufferedSource(PMTILES_URL)));

  let fellBack = false;
  function toFallback(reason, err) {
    if (fellBack) return;
    fellBack = true;
    if (err) console.warn("WebGL hiba (" + reason + "), 2D tartalék:", err.message || err);
    let canvas = null;
    try { canvas = map && map.getCanvas(); } catch (_) {}
    try { if (map) { map.off(); map.remove(); } } catch (_) {} // remove() can itself throw on a half-init map
    try {
      const gl = canvas && (canvas.getContext("webgl2") || canvas.getContext("webgl"));
      const lose = gl && gl.getExtension("WEBGL_lose_context");
      if (lose) lose.loseContext();
    } catch (_) {}
    if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
    if (window.__mount2D) window.__mount2D();
  }

  let map;
  try {
    map = new maplibregl.Map({
      container: "map",
      center: HOME.center,
      zoom: HOME.zoom,
      attributionControl: { compact: true },
      style: {
        version: 8,
        sources: {
          gp: { type: "vector", url: `pmtiles://${PMTILES_URL}`,
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
  } catch (e) {
    // Synchronous "Failed to initialize WebGL" from the Map constructor (_setupPainter).
    toFallback("init", e);
    return;
  }

  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");

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

  // Surface a tile/source load failure instead of showing a blank map; fall back on WebGL loss.
  map.on("error", (e) => {
    const msg = (e && e.error && (e.error.message || e.error)) + "";
    if (/webgl/i.test(msg)) toFallback("error", e.error);
    else if (e && e.error) console.error("MapLibre hiba:", msg);
  });
  map.on("webglcontextlost", () => toFallback("contextlost"));

  // Expose flyTo for the worst-100 table.
  window.flyToSettlement = (lng, lat) => map.flyTo({ center: [lng, lat], zoom: 11, speed: 3.6 });
  window.__map = map;

  // "Back to Hungary": show a recenter button when the country scrolls out of view
  // (e.g. a fast fling on a touchscreen). Shown when the view centre has left Hungary.
  const recenterBtn = document.getElementById("recenter");
  function updateRecenter() { if (recenterBtn) recenterBtn.hidden = !countryLost(map.getCenter()); }
  if (recenterBtn) {
    recenterBtn.addEventListener("click", () => map.flyTo({ center: HOME.center, zoom: HOME.zoom, essential: true, speed: 3.6 }));
    map.on("moveend", updateRecenter);
    map.on("resize", updateRecenter);
    map.on("load", updateRecenter);
  }
})();
