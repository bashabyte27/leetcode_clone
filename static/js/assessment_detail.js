/* BashaByte · Assessment detail page (dialogs, copy, report charts, sheet). */
(function () {
  "use strict";
  var shell = document.querySelector(".asx-detail");
  if (!shell) return;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── Toast + copy ─────────────────────────────────────────── */
  var toast = document.getElementById("asxToast"), toastTimer;
  function showToast(text) {
    if (!toast) return;
    toast.textContent = text;
    toast.hidden = false;
    toast.classList.remove("is-shown"); void toast.offsetWidth; toast.classList.add("is-shown");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove("is-shown"); }, 2200);
  }
  shell.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    navigator.clipboard.writeText(btn.getAttribute("data-copy")).then(function () {
      btn.classList.add("is-copied");
      showToast("Student link copied to clipboard");
      setTimeout(function () { btn.classList.remove("is-copied"); }, 1500);
    });
  });

  /* ── Manage dialogs (Signups) ─────────────────────────────── */
  shell.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-open-dialog]");
    if (opener) {
      var dlg = document.getElementById(opener.getAttribute("data-open-dialog"));
      if (dlg && dlg.showModal) { dlg.showModal(); var first = dlg.querySelector("input, button:not([data-close-dialog])"); if (first) first.focus(); }
      return;
    }
    var closer = e.target.closest("[data-close-dialog]");
    if (closer) { closer.closest("dialog").close(); return; }
    if (e.target.tagName === "DIALOG") e.target.close(); // backdrop click
  });

  /* ── Count-ups ────────────────────────────────────────────── */
  if (!reduceMotion) {
    shell.querySelectorAll("[data-count]").forEach(function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10) || 0;
      if (!target) return;
      var t0 = performance.now();
      (function tick(now) {
        var p = Math.min((now - t0) / 900, 1);
        el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
        if (p < 1) requestAnimationFrame(tick);
      })(t0);
    });
  }

  /* ── Candidate sheet: sort + filter ───────────────────────── */
  var sheet = shell.querySelector("[data-sheet]");
  if (sheet) {
    var body = sheet.tBodies[0];
    var heads = sheet.querySelectorAll("tr.heads th[data-sort]");
    var countEl = shell.querySelector("[data-sheet-count]");
    function renumber() {
      var n = 0;
      Array.prototype.forEach.call(body.rows, function (row) {
        if (row.hidden) return;
        n++;
        var rn = row.querySelector("th.rn");
        if (rn) rn.textContent = String(n + 1);
      });
      if (countEl) countEl.textContent = n + (n === 1 ? " row" : " rows");
    }
    heads.forEach(function (th, idx) {
      th.tabIndex = 0;
      function sortBy() {
        var asc = th.getAttribute("aria-sort") !== "ascending";
        heads.forEach(function (h) { h.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        var col = idx + 1; // +1 skips the row-number cell
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          var ca = a.cells[col], cb = b.cells[col];
          if (!ca || !cb) return 0;
          var va = ca.getAttribute("data-v") || ca.textContent.trim();
          var vb = cb.getAttribute("data-v") || cb.textContent.trim();
          var r = th.getAttribute("data-sort") === "num"
            ? (parseFloat(va) || 0) - (parseFloat(vb) || 0)
            : va.localeCompare(vb);
          return asc ? r : -r;
        });
        rows.forEach(function (r) { body.appendChild(r); });
        renumber();
      }
      th.addEventListener("click", sortBy);
      th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sortBy(); } });
    });
    var filter = shell.querySelector("[data-sheet-filter]");
    if (filter) filter.addEventListener("input", function () {
      var q = filter.value.trim().toLowerCase();
      Array.prototype.forEach.call(body.rows, function (row) { row.hidden = q && row.textContent.toLowerCase().indexOf(q) === -1; });
      renumber();
    });
  }

  /* ── Report charts (Chart.js) ─────────────────────────────── */
  var dataEl = document.getElementById("report-data");
  if (!dataEl) return;
  var data;
  try { data = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var charts = [];

  function tokens() {
    var cs = getComputedStyle(shell);
    var v = function (n) { return cs.getPropertyValue(n).trim(); };
    return {
      series: v("--viz-1"), series2: v("--viz-2"), grid: v("--viz-grid"),
      text: v("--ab-text-muted"), ink: v("--ab-text-main"), surface: v("--ab-surface"),
      good: v("--viz-good"), critical: v("--viz-critical"), warning: v("--viz-warning"),
    };
  }

  function base(t) {
    return {
      responsive: true, maintainAspectRatio: false,
      animation: reduceMotion ? false : { duration: 900, easing: "easeOutQuart" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: t.ink, titleColor: t.surface, bodyColor: t.surface, padding: 10, cornerRadius: 8,
          displayColors: false, titleFont: { family: "Manrope", weight: "700" }, bodyFont: { family: "Manrope" },
        },
      },
      scales: {
        x: { grid: { color: t.grid, drawTicks: false }, border: { color: t.grid }, ticks: { color: t.text, font: { family: "DM Mono", size: 11 }, padding: 6 } },
        y: { grid: { color: t.grid, drawTicks: false }, border: { display: false }, ticks: { color: t.text, font: { family: "DM Mono", size: 11 }, padding: 8, precision: 0 }, beginAtZero: true },
      },
    };
  }

  function build() {
    if (!window.Chart) return;
    charts.forEach(function (c) { c.destroy(); });
    charts = [];
    var t = tokens();
    Chart.defaults.font.family = "Manrope";

    var el = document.getElementById("chartDistribution");
    if (el) {
      var o = base(t);
      o.scales.x.title = { display: true, text: "Score band", color: t.text, font: { size: 11 } };
      o.scales.y.title = { display: true, text: "Candidates", color: t.text, font: { size: 11 } };
      o.plugins.tooltip.callbacks = { label: function (c) { return c.parsed.y + " candidate" + (c.parsed.y === 1 ? "" : "s"); } };
      charts.push(new Chart(el, {
        type: "bar",
        data: { labels: data.distribution.map(function (d) { return d.label; }),
          datasets: [{ data: data.distribution.map(function (d) { return d.count; }), backgroundColor: t.series, borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: "bottom", barPercentage: 0.86, categoryPercentage: 0.92 }] },
        options: o,
      }));
    }

    el = document.getElementById("chartItems");
    if (el && data.items.length) {
      var o2 = base(t);
      o2.scales.x.min = -0.06; o2.scales.x.max = 1.06;
      o2.scales.y.min = -1.1; o2.scales.y.max = 1.1; o2.scales.y.beginAtZero = false;
      o2.scales.x.ticks.stepSize = 0.2; o2.scales.y.ticks.stepSize = 0.5;
      o2.scales.x.ticks.callback = function (v) { return v >= 0 && v <= 1 ? Number(v).toFixed(1) : ""; };
      o2.scales.y.ticks.callback = function (v) { return v >= -1 && v <= 1 ? Number(v).toFixed(1) : ""; };
      o2.scales.x.title = { display: true, text: "Difficulty p (share correct)", color: t.text, font: { size: 11 } };
      o2.scales.y.title = { display: true, text: "Discrimination D", color: t.text, font: { size: 11 } };
      o2.scales.y.ticks.precision = 1;
      o2.plugins.tooltip.callbacks = {
        title: function (c) { var it = data.items[c[0].dataIndex]; return it.label + " · " + it.title; },
        label: function (c) { var it = data.items[c.dataIndex]; return "p = " + it.p + (it.d === null ? " · D needs 2+ candidates" : " · D = " + it.d); },
      };
      // Quadrant guide: shade the "review" zone (D < 0.2)
      var zone = {
        id: "zone",
        beforeDatasetsDraw: function (chart) {
          var ctx = chart.ctx, a = chart.chartArea, y = chart.scales.y.getPixelForValue(0.2);
          ctx.save();
          ctx.fillStyle = t.critical; ctx.globalAlpha = 0.07;
          ctx.fillRect(a.left, y, a.right - a.left, a.bottom - y);
          ctx.globalAlpha = 0.9; ctx.fillStyle = t.text; ctx.font = "600 11px Manrope";
          ctx.fillText("Review zone (D < 0.2)", a.left + 8, a.bottom - 8);
          ctx.restore();
        },
      };
      charts.push(new Chart(el, {
        type: "scatter",
        data: { datasets: [{ data: data.items.map(function (i) { return { x: i.p, y: i.d === null ? 0 : i.d }; }),
          backgroundColor: t.series, borderColor: t.surface, borderWidth: 2, pointRadius: 7, pointHoverRadius: 9 }] },
        options: o2, plugins: [zone],
      }));
    }

    el = document.getElementById("chartScatter");
    if (el && data.scatter.length) {
      var o3 = base(t);
      o3.scales.x.title = { display: true, text: "Minutes taken", color: t.text, font: { size: 11 } };
      o3.scales.y.title = { display: true, text: "Score %", color: t.text, font: { size: 11 } };
      o3.scales.y.max = 105; o3.scales.y.ticks.stepSize = 20;
      o3.scales.y.ticks.callback = function (v) { return v <= 100 ? v : ""; };
      o3.layout = { padding: { right: 12 } };
      o3.plugins.tooltip.callbacks = {
        title: function (c) { return data.scatter[c[0].dataIndex].name; },
        label: function (c) { return c.parsed.y + "% in " + c.parsed.x + " min"; },
      };
      charts.push(new Chart(el, {
        type: "scatter",
        data: { datasets: [{ data: data.scatter.map(function (s) { return { x: s.x, y: s.y }; }), backgroundColor: t.series, borderColor: t.surface, borderWidth: 2, pointRadius: 7, pointHoverRadius: 9 }] },
        options: o3,
      }));
    }

    el = document.getElementById("chartTimeline");
    if (el && data.timeline.length) {
      var o4 = base(t);
      o4.interaction = { mode: "index", intersect: false };
      o4.plugins.tooltip.callbacks = { label: function (c) { return c.parsed.y + " submission" + (c.parsed.y === 1 ? "" : "s"); } };
      var ctx = el.getContext("2d");
      var grad = ctx.createLinearGradient(0, 0, 0, el.parentNode.clientHeight || 240);
      grad.addColorStop(0, t.series + "33"); grad.addColorStop(1, t.series + "00");
      charts.push(new Chart(el, {
        type: "line",
        data: { labels: data.timeline.map(function (d) { return d.label; }),
          datasets: [{ data: data.timeline.map(function (d) { return d.count; }), borderColor: t.series, backgroundColor: grad, fill: true, borderWidth: 2, cubicInterpolationMode: "monotone", pointRadius: data.timeline.length > 24 ? 0 : 4, pointHoverRadius: 6, pointBackgroundColor: t.series, pointBorderColor: t.surface, pointBorderWidth: 2 }] },
        options: o4,
      }));
    }
  }

  function whenReady() {
    if (window.Chart) { build(); return; }
    var tries = 0;
    var timer = setInterval(function () {
      if (window.Chart || ++tries > 50) { clearInterval(timer); build(); }
    }, 100);
  }
  if (document.readyState === "complete") whenReady(); else window.addEventListener("load", whenReady);

  // Re-theme charts when the site theme toggles
  new MutationObserver(function () { setTimeout(build, 50); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
