/* UI helpers: tooltips (desktop hover + mobile tap) and a collapsible legend panel.
   Body-anchored tooltip so it is never clipped by the scrollable table or the panel,
   and works for dynamically-created map-popup content via event delegation. */
(function () {
  "use strict";

  /* ---- Tooltips ---- */
  const box = document.createElement("div");
  box.className = "tooltip";
  box.setAttribute("role", "tooltip");
  box.hidden = true;
  document.body.appendChild(box);
  let current = null;

  function place(el) {
    const r = el.getBoundingClientRect();
    const bw = box.offsetWidth, bh = box.offsetHeight;
    let left = r.left + r.width / 2 - bw / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - bw - 8));
    let top = r.top - bh - 8;
    box.classList.remove("below");
    if (top < 8) { top = r.bottom + 8; box.classList.add("below"); }
    box.style.left = left + "px";
    box.style.top = top + "px";
  }
  function show(el) {
    const tip = el.getAttribute("data-tip");
    if (!tip) return;
    box.textContent = tip;
    box.hidden = false;
    current = el;
    place(el);
  }
  function hide() { box.hidden = true; current = null; }

  // Desktop: hover.
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el) show(el);
  });
  document.addEventListener("mouseout", (e) => {
    if (e.target.closest("[data-tip]") && !box.hidden) hide();
  });
  // Keyboard.
  document.addEventListener("focusin", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el) show(el);
  });
  document.addEventListener("focusout", hide);
  // Mobile / any click: tap a tip target to show it; tap elsewhere to dismiss.
  // (Always show rather than toggle — on touch, focusin fires first, so a toggle would
  //  immediately re-hide it.)
  document.addEventListener("click", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el) show(el);
    else hide();
  });
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);

  /* ---- Collapsible legend panel ---- */
  const panel = document.getElementById("legend");
  const closeBtn = document.getElementById("legend-close");
  const openBtn = document.getElementById("legend-open");

  function setOpen(open) {
    if (!panel || !openBtn) return;
    panel.hidden = !open;
    openBtn.hidden = open;
    openBtn.setAttribute("aria-expanded", String(open));
    hide();
  }
  if (closeBtn && openBtn) {
    closeBtn.addEventListener("click", (e) => { e.stopPropagation(); setOpen(false); });
    openBtn.addEventListener("click", (e) => { e.stopPropagation(); setOpen(true); });
    // Start collapsed on small screens so the legend doesn't cover the map.
    setOpen(window.matchMedia("(min-width: 760px)").matches);
  }
})();
