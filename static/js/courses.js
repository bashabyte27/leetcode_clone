/* BashaByte courses pages: syllabus expand/collapse, jump-to-lesson, lesson-preview contents. No dependencies. */
(function () {
  "use strict";

  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── Syllabus: expand / collapse all ─────────────────────── */
  var toggle = document.querySelector("[data-syllabus-toggle]");
  var modules = $$(".cx-syllabus details");
  function syncToggle() {
    if (!toggle) return;
    var allOpen = modules.length && modules.every(function (d) { return d.open; });
    toggle.textContent = allOpen ? "Collapse all" : "Expand all";
    toggle.setAttribute("aria-expanded", String(allOpen));
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = !modules.every(function (d) { return d.open; });
      modules.forEach(function (d) { d.open = open; });
      syncToggle();
    });
    modules.forEach(function (d) { d.addEventListener("toggle", syncToggle); });
    syncToggle();
  }

  /* ── Jump to a lesson (#lesson-123): open its module, scroll, highlight ── */
  function revealLesson(hash) {
    if (!/^#lesson-\d+$/.test(hash || "")) return;
    var row = document.querySelector(hash);
    if (!row) return;
    var details = row.closest("details");
    if (details && !details.open) { details.open = true; syncToggle(); }
    row.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
    row.classList.remove("is-flash");
    void row.offsetWidth; // restart the animation
    row.classList.add("is-flash");
  }
  if (modules.length) {
    revealLesson(window.location.hash);
    window.addEventListener("hashchange", function () { revealLesson(window.location.hash); });
    $$("[data-continue]").forEach(function (a) {
      a.addEventListener("click", function (e) {
        var hash = a.getAttribute("href");
        if (hash === window.location.hash) { e.preventDefault(); revealLesson(hash); }
      });
    });
  }

  /* ── Lesson preview: highlight the step being read ───────── */
  var links = $$("[data-toc-link]");
  if (links.length && "IntersectionObserver" in window) {
    var byId = {};
    links.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var current = null;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var link = byId[entry.target.id];
        if (!link || link === current) return;
        if (current) { current.classList.remove("is-active"); current.removeAttribute("aria-current"); }
        link.classList.add("is-active");
        link.setAttribute("aria-current", "step");
        current = link;
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    $$(".cx-step").forEach(function (s) { io.observe(s); });
  }
})();
