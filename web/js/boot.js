/* Chooses the map renderer at load time and lazy-loads only what's needed:
   - WebGL available  -> maplibre-gl.js + pmtiles.js + map.js  (vector tiles, the rich path)
   - WebGL missing    -> leaflet.js/.css + map-fallback.js     (Canvas2D, no WebGL)

   "Uncaught error: failed to initialize WebGL" hits many real devices (iOS Lockdown Mode,
   GPU driver blocklists, in-app webviews, hardware-accel off). We gate on a pre-flight probe
   AND let map.js fall back at runtime if MapLibre still fails after a passing probe.
   Each renderer is loaded only when chosen, so the happy path never downloads Leaflet/GeoJSON
   and a no-WebGL device never downloads MapLibre or the 4 MB pmtiles. */
(function () {
  "use strict";

  // Pre-flight WebGL check. WebGL1-tolerant on purpose: the vendored MapLibre is v4.7.1, which
  // runs on WebGL1 — probing for WebGL2 only would needlessly fall back WebGL1-only devices.
  // (If MapLibre is ever upgraded to v5, which requires WebGL2, tighten this to webgl2 only.)
  function webglOK() {
    if (typeof window.WebGLRenderingContext === "undefined") return false;
    const canvas = document.createElement("canvas");
    let gl = null;
    try {
      gl = canvas.getContext("webgl2") || canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    } catch (e) {
      return false; // getContext can throw when WebGL is disabled by policy/lockdown.
    }
    if (!gl || typeof gl.getParameter !== "function") return false;
    if (typeof gl.isContextLost === "function" && gl.isContextLost()) return false; // exists but already lost
    // Free the probe context so it doesn't count against the browser's ~16-per-page limit.
    const lose = gl.getExtension && gl.getExtension("WEBGL_lose_context");
    if (lose) lose.loseContext();
    return true;
  }

  const ALLOW_OVERRIDE = location.search.indexOf("nowebgl=1") !== -1; // test hook: force the fallback

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error("load failed: " + src));
      document.body.appendChild(s);
    });
  }
  function loadCss(href) {
    const l = document.createElement("link");
    l.rel = "stylesheet";
    l.href = href;
    document.head.appendChild(l);
  }

  // Mount the WebGL-free Leaflet fallback. Idempotent — map.js may call it after a runtime
  // WebGL failure, and the pre-flight may also call it; only the first call does work.
  let mounted2D = false;
  function mount2D() {
    if (mounted2D) return Promise.resolve();
    mounted2D = true;
    loadCss("./vendor/leaflet.css");
    return loadScript("./vendor/leaflet.js")
      .then(() => loadScript("./js/map-fallback.js"))
      .catch((e) => console.error("2D fallback betöltése sikertelen", e));
  }
  window.__mount2D = mount2D;

  function mountMapLibre() {
    loadCss("./vendor/maplibre-gl.css");
    return loadScript("./vendor/maplibre-gl.js")
      .then(() => loadScript("./vendor/pmtiles.js"))
      .then(() => loadScript("./js/map.js")); // map.js calls window.__mount2D() if init fails
  }

  if (!ALLOW_OVERRIDE && webglOK()) {
    mountMapLibre().catch((e) => {
      console.warn("MapLibre betöltése sikertelen, 2D tartalék:", e && e.message);
      mount2D();
    });
  } else {
    mount2D();
  }
})();
