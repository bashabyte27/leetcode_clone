/* BashaByte · Problems page interactions. No dependencies. */
(function () {
  "use strict";

  var page = document.querySelector(".bb-problems");
  if (!page) return;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function $(s, c) { return (c || document).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }

  /* ── Greeting + date (client clock = user's timezone) ─────── */
  var now = new Date();
  var greet = $("#ppGreet");
  if (greet) {
    var h = now.getHours();
    greet.textContent = h < 5 ? "Burning the midnight oil" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  }
  var todayEl = $("#ppToday");
  if (todayEl) todayEl.textContent = now.toLocaleDateString(undefined, { month: "short", day: "numeric" });

  /* ── Entrance: ring, bars, heatmap, counters ──────────────── */
  var heat = $("#ppHeat");
  if (heat && !reduceMotion) heat.closest(".pp-activity").classList.add("js-hm");
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      page.classList.add("is-ready");
      var act = $(".pp-activity");
      if (act) act.classList.add("is-ready");
    });
  });

  if (!reduceMotion) {
    $$("[data-count]", page).forEach(function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10) || 0;
      if (!target) return;
      var start = performance.now() + 250, dur = 1100;
      el.textContent = "0";
      (function tick(t) {
        var p = Math.max(0, Math.min((t - start) / dur, 1));
        el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 4))));
        if (p < 1) requestAnimationFrame(tick);
      })(performance.now());
    });
  }

  /* ── Heatmap: tooltip + show most recent weeks on narrow screens ── */
  var tip = $("#ppTip");
  if (heat && tip) {
    function show(cell) {
      var n = parseInt(cell.getAttribute("data-n"), 10) || 0;
      tip.innerHTML = "<b>" + (n ? n + " submission" + (n === 1 ? "" : "s") : "No submissions") + "</b> on " + cell.getAttribute("data-d");
      var r = cell.getBoundingClientRect();
      tip.style.left = Math.min(Math.max(r.left + r.width / 2, 110), window.innerWidth - 110) + "px";
      tip.style.top = r.top + "px";
      tip.hidden = false;
    }
    heat.addEventListener("pointerover", function (e) {
      var cell = e.target.closest("i[data-d]");
      if (cell) show(cell);
    });
    heat.addEventListener("pointerleave", function () { tip.hidden = true; });
    window.addEventListener("scroll", function () { tip.hidden = true; }, { passive: true });
    var scroller = $("#ppHeatScroll");
    if (scroller && scroller.scrollWidth - scroller.clientWidth > 8) scroller.scrollLeft = scroller.scrollWidth;
  }

  /* ── List: filter, sort, smooth reflow ────────────────────── */
  var list = $("#ppList");
  var rows = list ? $$(".pp-row", list) : [];
  if (!rows.length) return;

  var search = $("#ppSearch");
  var sortSel = $("#ppSort");
  var countEl = $("#ppCount");
  var emptyEl = $("#ppEmpty");
  var segs = $$(".pp-seg");
  var DIFF_RANK = { easy: 0, medium: 1, hard: 2 };
  var original = rows.slice();

  var state = { q: "", diff: "all", status: "all", sort: "num" };
  try {
    var saved = JSON.parse(sessionStorage.getItem("pp-filters") || "null");
    if (saved) Object.keys(state).forEach(function (k) { if (typeof saved[k] === "string") state[k] = saved[k]; });
  } catch (e) {}
  if (!$("#ppStatus")) state.status = "all";

  // Segmented controls with a sliding pill
  function placePill(seg, animate) {
    var pill = $(".pp-seg-pill", seg);
    var active = $("button.is-active", seg);
    if (!pill || !active) return;
    if (!animate) pill.style.transition = "none";
    pill.style.setProperty("--x", active.offsetLeft + "px");
    pill.style.setProperty("--w", active.offsetWidth + "px");
    if (!animate) { pill.offsetWidth; pill.style.transition = ""; }
  }
  function syncSeg(seg, value, animate) {
    $$("button", seg).forEach(function (b) {
      var on = b.getAttribute("data-value") === value;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-pressed", String(on));
    });
    placePill(seg, animate);
  }

  function matches(row) {
    var q = state.q.trim().toLowerCase();
    if (state.diff !== "all" && row.getAttribute("data-diff") !== state.diff) return false;
    if (state.status === "solved" && row.getAttribute("data-solved") !== "1") return false;
    if (state.status === "todo" && row.getAttribute("data-solved") === "1") return false;
    if (q && row.getAttribute("data-title").indexOf(q) === -1 && row.getAttribute("data-num").indexOf(q) === -1) return false;
    return true;
  }

  function sorted() {
    var arr = original.slice();
    var num = function (r) { return parseFloat(r.getAttribute("data-num")) || 0; };
    var acc = function (r) { return parseFloat(r.getAttribute("data-acc")); };
    if (state.sort === "acc-desc") arr.sort(function (a, b) { return acc(b) - acc(a) || num(a) - num(b); });
    else if (state.sort === "acc-asc") arr.sort(function (a, b) {
      var x = acc(a), y = acc(b);
      if (x < 0) x = 101; if (y < 0) y = 101; // unjudged last
      return x - y || num(a) - num(b);
    });
    else if (state.sort === "diff") arr.sort(function (a, b) {
      return DIFF_RANK[a.getAttribute("data-diff")] - DIFF_RANK[b.getAttribute("data-diff")] || num(a) - num(b);
    });
    return arr;
  }

  // FLIP: measure, mutate, then animate rows from old to new position
  function flip(mutate, animate) {
    if (!animate || reduceMotion || rows.length > 250 || !list.animate) { mutate(); return; }
    var before = new Map();
    rows.forEach(function (r) { if (!r.hidden) before.set(r, r.getBoundingClientRect().top); });
    mutate();
    rows.forEach(function (r) {
      if (r.hidden) return;
      var top = r.getBoundingClientRect().top;
      if (!before.has(r)) {
        r.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 260, easing: "cubic-bezier(.22,1,.36,1)" });
      } else if (Math.abs(before.get(r) - top) > 1) {
        r.animate([{ transform: "translateY(" + (before.get(r) - top) + "px)" }, { transform: "none" }], { duration: 380, easing: "cubic-bezier(.22,1,.36,1)" });
      }
    });
  }

  function apply(animate) {
    flip(function () {
      var visible = 0;
      var order = sorted();
      var current = $$(".pp-row", list);
      var reorder = order.some(function (r, i) { return r !== current[i]; });
      if (reorder) list.classList.add("is-sorted"); // moved nodes must not replay entrance animations
      order.forEach(function (r) {
        var ok = matches(r);
        r.hidden = !ok;
        if (ok) visible++;
        if (reorder) list.appendChild(r);
      });
      countEl.innerHTML = "<b>" + visible + "</b> " + (visible === 1 ? "problem" : "problems");
      emptyEl.hidden = visible !== 0;
      list.hidden = visible === 0;
    }, animate);
    try { sessionStorage.setItem("pp-filters", JSON.stringify(state)); } catch (e) {}
  }

  segs.forEach(function (seg) {
    var key = seg.id === "ppStatus" ? "status" : "diff";
    syncSeg(seg, state[key], false);
    seg.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-value]");
      if (!b) return;
      state[key] = b.getAttribute("data-value");
      syncSeg(seg, state[key], true);
      apply(true);
    });
  });
  window.addEventListener("resize", function () { segs.forEach(function (s) { placePill(s, false); }); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { segs.forEach(function (s) { placePill(s, false); }); });

  if (sortSel) {
    sortSel.value = state.sort;
    sortSel.addEventListener("change", function () { state.sort = sortSel.value; apply(true); });
  }

  if (search) {
    search.value = state.q;
    var raf = 0;
    search.addEventListener("input", function () {
      state.q = search.value;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () { apply(false); });
    });
    search.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { search.value = ""; state.q = ""; apply(false); }
      if (e.key === "ArrowDown") {
        var first = rows.filter(function (r) { return !r.hidden; })[0];
        if (first) { e.preventDefault(); first.focus(); }
      }
    });
  }

  var reset = $("#ppReset");
  if (reset) reset.addEventListener("click", function () {
    state = { q: "", diff: "all", status: "all", sort: state.sort };
    if (search) search.value = "";
    segs.forEach(function (s) { syncSeg(s, "all", true); });
    apply(true);
  });

  // Keyboard: "/" focuses search, arrows move between rows
  document.addEventListener("keydown", function (e) {
    var t = e.target, tag = (t && t.tagName) || "";
    if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT" && !e.ctrlKey && !e.metaKey && search) {
      e.preventDefault(); search.focus(); search.select(); return;
    }
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && t.classList && t.classList.contains("pp-row")) {
      e.preventDefault();
      var vis = $$(".pp-row", list).filter(function (r) { return !r.hidden; });
      var i = vis.indexOf(t) + (e.key === "ArrowDown" ? 1 : -1);
      if (i < 0 && search) { search.focus(); return; }
      if (vis[i]) vis[i].focus();
    }
  });

  // Toolbar gets a glass background once it sticks
  var sentinel = $("#ppSentinel"), toolbar = $("#ppToolbar");
  if (sentinel && toolbar && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      toolbar.classList.toggle("is-stuck", !entries[0].isIntersecting);
    }, { rootMargin: "-51px 0px 0px 0px" }).observe(sentinel);
  }

  apply(false);
})();
