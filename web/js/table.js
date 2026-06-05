/* A 100 legrosszabbul ellátott település — rendezhető táblázat, könyvtár nélkül.
   Asztali nézet: tömör, sortörhető fejlécű táblázat (kevés vízszintes görgetés).
   Mobil nézet (<=760px): a sorok kártyákká alakulnak (label: érték), nincs vízszintes görgetés.
   Mobilon alapból csak az első 5 kártya látszik, a többit egy gomb nyitja ki.
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
      tip: "A legközelebbi működő háziorvosi rendelő tényleges közúti távolsága autóval (OSRM). Csak sivatagoknál van értéke." },
    { key: "vacant_count", label: "Betöltetlen", card: "Betöltetlen körzet", num: true,
      tip: "Ennyi, a települést ellátó háziorvosi körzet betöltetlen (nincs állandó háziorvosa)." },
    { key: "longest_vacancy_days", label: "Üres (nap)", card: "Mióta üres (nap)", num: true,
      tip: "A leghosszabb ideje betöltetlen körzet üresedésének hossza napokban." },
  ];

  let rows = [];
  let sortKey = "rank";
  let sortDir = 1; // 1 = növekvő, -1 = csökkenő
  let expander = null; // mobil "összes mutatása / kevesebb" gomb

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

  function labelFor(key) {
    const c = COLS.find((c) => c.key === key);
    return c.card || c.label;
  }

  // Custom dropdown (a native <select> renders an unstyled OS popup that on mobile opens
  // upward over the map in dark mode — this menu is styled, light, and opens downward).
  function buildControls() {
    const section = document.getElementById("worst");
    const bar = document.createElement("div");
    bar.className = "table-controls";
    const items = COLS.map((c) =>
      `<li role="option" data-key="${c.key}" tabindex="-1">${c.card || c.label}</li>`).join("");
    bar.innerHTML =
      `<span class="ctl-label">Rendezés:</span>
       <div class="dropdown" id="sort-dd">
         <button type="button" id="sort-btn" class="dropdown-btn" aria-haspopup="listbox" aria-expanded="false">
           <span id="sort-current">${labelFor(sortKey)}</span><span class="caret" aria-hidden="true">▾</span>
         </button>
         <ul id="sort-menu" class="dropdown-menu" role="listbox" aria-label="Rendezés oszlop szerint" hidden>${items}</ul>
       </div>
       <button id="sort-dir" type="button" class="sort-dir" aria-label="Rendezés iránya" title="Növekvő / csökkenő">▲</button>`;
    section.insertBefore(bar, section.querySelector(".table-wrap"));

    const dd = bar.querySelector("#sort-dd");
    const btn = bar.querySelector("#sort-btn");
    const menu = bar.querySelector("#sort-menu");
    const open = (show) => { menu.hidden = !show; btn.setAttribute("aria-expanded", String(show)); };

    btn.addEventListener("click", (e) => { e.stopPropagation(); open(menu.hidden); });
    menu.querySelectorAll("li").forEach((li) =>
      li.addEventListener("click", () => { sortKey = li.dataset.key; sortDir = 1; open(false); render(); }));
    document.addEventListener("click", (e) => { if (!dd.contains(e.target)) open(false); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") open(false); });
    bar.querySelector("#sort-dir").addEventListener("click", () => { sortDir = -sortDir; render(); });
  }

  function syncControls() {
    const cur = document.getElementById("sort-current");
    const dir = document.getElementById("sort-dir");
    const menu = document.getElementById("sort-menu");
    if (cur) cur.textContent = labelFor(sortKey);
    if (dir) dir.textContent = sortDir === 1 ? "▲" : "▼";
    if (menu) menu.querySelectorAll("li").forEach((li) =>
      li.setAttribute("aria-selected", String(li.dataset.key === sortKey)));
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
    applyCollapseUI();
  }

  // Mobile (<=760px): show only the first 5 cards; a toggle reveals the rest. CSS-driven via the
  // .cards-collapsed class on #worst100 (which render() preserves), so the visible 5 always track the
  // current sort with no JS row-slicing. Mirrors the legend collapse idiom in ui.js.
  function buildExpander() {
    const wrap = document.getElementById("worst").querySelector(".table-wrap");
    expander = document.createElement("button");
    expander.type = "button";
    expander.className = "cards-expander";
    expander.id = "cards-expander";
    expander.setAttribute("aria-controls", "worst100");
    expander.setAttribute("aria-expanded", "false");
    expander.hidden = true; // revealed once the data shows there are more than 5 rows
    wrap.insertAdjacentElement("afterend", expander); // sibling after .table-wrap → survives render()
    expander.addEventListener("click", toggleExpand);
  }

  function toggleExpand() {
    const table = document.getElementById("worst100");
    const collapsing = !table.classList.contains("cards-collapsed");
    table.classList.toggle("cards-collapsed", collapsing);
    applyCollapseUI();
    // On collapse the page shrinks — keep the toggle under the thumb (mirrors the map scrollIntoView).
    if (collapsing) expander.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function applyCollapseUI() {
    if (!expander) return;
    const table = document.getElementById("worst100");
    const hidden = rows.length - 5;
    if (hidden <= 0) { expander.hidden = true; table.classList.remove("cards-collapsed"); return; }
    expander.hidden = false;
    const collapsed = table.classList.contains("cards-collapsed");
    expander.setAttribute("aria-expanded", String(!collapsed));
    expander.textContent = collapsed ? `További ${hidden} település mutatása` : "Kevesebb mutatása";
  }

  buildControls();
  buildExpander();
  fetch("./data/worst_100.json").then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }).then((data) => {
    rows = data;
    document.getElementById("worst100").classList.add("cards-collapsed"); // start collapsed (mobile shows the first 5)
    render();
  }).catch((e) => {
    console.error("worst_100 betöltése sikertelen", e);
    const tbody = document.querySelector("#worst100 tbody");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="${COLS.length}">⚠️ A táblázat adatai nem töltöttek be. `
        + `Próbáld újratölteni az oldalt.</td></tr>`;
    }
  });
})();
