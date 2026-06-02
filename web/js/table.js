/* A 100 legrosszabbul ellátott település — rendezhető táblázat, könyvtár nélkül.
   Asztali nézet: tömör, sortörhető fejlécű táblázat (kevés vízszintes görgetés).
   Mobil nézet (<=720px): a sorok kártyákká alakulnak (label: érték), nincs vízszintes görgetés.
   A fejlécek mellett rendező legördülő is van, hogy mobilon is lehessen rendezni. */
(function () {
  "use strict";

  // label  = rövid asztali fejléc; card = mobil kártya-címke; tip = magyarázat.
  const COLS = [
    { key: "rank", label: "#", card: "Helyezés", num: true,
      tip: "Rangsor: 1 = a legrosszabbul ellátott település." },
    { key: "name", label: "Település",
      tip: "A település hivatalos neve (KSH)." },
    { key: "county", label: "Vármegye",
      tip: "Az a vármegye, amelyhez a település tartozik." },
    { key: "population", label: "Lakosság", card: "Lakónépesség", num: true,
      tip: "Az állandó lakosok száma (KSH, 2025)." },
    { key: "active_gp_count", label: "Betöltött körzet", num: true,
      tip: "Ennyi háziorvosi körzet látja el a települést, amelyben VAN állandó háziorvos. Ha 0, a település sivatag." },
    { key: "gps_per_1000", label: "Ellátottság", card: "Ellátottság (körzet / 1000 lakos)", num: true,
      tip: "Betöltött háziorvosi körzetek száma 1000 lakosra vetítve. Minél kisebb, annál rosszabb az ellátás (országos átlag ~0,45)." },
    { key: "nearest_gp_km", label: "Távolság (km)", card: "Legközelebbi háziorvos (km)", num: true,
      tip: "A legközelebbi működő háziorvosi rendelő távolsága (légvonal × 1,4 közelítés). Csak sivatagoknál van értéke." },
    { key: "vacant_count", label: "Betöltetlen", card: "Betöltetlen körzet", num: true,
      tip: "Ennyi, a települést ellátó háziorvosi körzet betöltetlen (nincs állandó háziorvosa)." },
    { key: "longest_vacancy_days", label: "Üres (nap)", card: "Mióta üres (nap)", num: true,
      tip: "A leghosszabb ideje betöltetlen körzet üresedésének hossza napokban." },
  ];

  let rows = [];
  let sortKey = "rank";
  let sortDir = 1; // 1 = növekvő, -1 = csökkenő

  function val(r, k) {
    const v = r[k];
    return v === null || v === undefined ? (COLS.find((c) => c.key === k).num ? -Infinity : "") : v;
  }

  function fmtCell(c, r) {
    let v = r[c.key];
    if (v === null || v === undefined) return "–";
    if (c.num && c.key === "population") return Number(v).toLocaleString("hu");
    return v;
  }

  function setSort(key) {
    if (key === sortKey) sortDir = -sortDir;
    else { sortKey = key; sortDir = 1; }
    render();
  }

  function buildControls() {
    const section = document.getElementById("worst");
    const bar = document.createElement("div");
    bar.className = "table-controls";
    const opts = COLS.map((c) => `<option value="${c.key}">${c.card || c.label}</option>`).join("");
    bar.innerHTML =
      `<label for="sort-by">Rendezés:</label>
       <select id="sort-by" aria-label="Rendezés oszlop szerint">${opts}</select>
       <button id="sort-dir" type="button" aria-label="Rendezés iránya" title="Növekvő / csökkenő">▲</button>`;
    section.insertBefore(bar, section.querySelector(".table-wrap"));
    bar.querySelector("#sort-by").addEventListener("change", (e) => { sortKey = e.target.value; sortDir = 1; render(); });
    bar.querySelector("#sort-dir").addEventListener("click", () => { sortDir = -sortDir; render(); });
  }

  function syncControls() {
    const sel = document.getElementById("sort-by");
    const btn = document.getElementById("sort-dir");
    if (sel) sel.value = sortKey;
    if (btn) btn.textContent = sortDir === 1 ? "▲" : "▼";
  }

  function render() {
    const thead = document.querySelector("#worst100 thead");
    const tbody = document.querySelector("#worst100 tbody");
    thead.innerHTML = "<tr>" + COLS.map((c) => {
      const aria = c.key === sortKey ? ` aria-sort="${sortDir === 1 ? "ascending" : "descending"}"` : "";
      return `<th data-key="${c.key}" data-tip="${c.tip}"${aria}>${c.label}</th>`;
    }).join("") + "</tr>";

    const sorted = [...rows].sort((a, b) => {
      const x = val(a, sortKey), y = val(b, sortKey);
      if (typeof x === "number" && typeof y === "number") return (x - y) * sortDir;
      return String(x).localeCompare(String(y), "hu") * sortDir;
    });

    tbody.innerHTML = sorted.map((r) => {
      const cls = r.is_desert == 1 ? ' class="desert"' : "";
      const cells = COLS.map((c) =>
        `<td class="${c.num ? "num" : ""}" data-label="${c.card || c.label}">${fmtCell(c, r)}</td>`
      ).join("");
      return `<tr${cls} data-lng="${r.centroid_lon ?? ""}" data-lat="${r.centroid_lat ?? ""}">${cells}</tr>`;
    }).join("");

    thead.querySelectorAll("th").forEach((th) =>
      th.addEventListener("click", () => setSort(th.dataset.key)));

    tbody.querySelectorAll("tr").forEach((tr) =>
      tr.addEventListener("click", () => {
        const lng = parseFloat(tr.dataset.lng), lat = parseFloat(tr.dataset.lat);
        if (!isNaN(lng) && !isNaN(lat) && window.flyToSettlement) {
          window.flyToSettlement(lng, lat);
          document.getElementById("map").scrollIntoView({ behavior: "smooth" });
        }
      }));

    syncControls();
  }

  buildControls();
  fetch("./data/worst_100.json").then((r) => r.json()).then((data) => {
    rows = data;
    render();
  }).catch((e) => console.error("worst_100 betöltése sikertelen", e));
})();
