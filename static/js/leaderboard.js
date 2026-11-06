/* BashaByte · Leaderboard interactions. No dependencies. */
(function () {
  "use strict";
  var root = document.querySelector(".lb");
  if (!root) return;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function $(s) { return root.querySelector(s); }

  /* Sliding pill under the active period tab */
  var seg = $(".lb-seg");
  function placePill(animate) {
    if (!seg) return;
    var pill = seg.querySelector(".lb-seg-pill");
    var active = seg.querySelector(".lb-tab.is-active");
    if (!pill || !active) return;
    if (!animate) pill.style.transition = "none";
    pill.style.setProperty("--x", active.offsetLeft + "px");
    pill.style.setProperty("--w", active.offsetWidth + "px");
    if (!animate) { pill.offsetWidth; pill.style.transition = ""; }
  }
  placePill(false);
  window.addEventListener("resize", function () { placePill(false); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { placePill(false); });
  if (seg) seg.addEventListener("click", function (e) {
    var tab = e.target.closest(".lb-tab");
    if (!tab || tab.classList.contains("is-active")) return;
    seg.querySelectorAll(".lb-tab").forEach(function (t) { t.classList.toggle("is-active", t === tab); });
    placePill(true); // glide while the next page loads
  });

  /* Count-up numbers */
  if (!reduceMotion && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        io.unobserve(entry.target);
        var el = entry.target, target = parseInt(el.getAttribute("data-count"), 10) || 0;
        if (!target) return;
        var t0 = performance.now(), dur = 1200;
        (function tick(now) {
          var p = Math.min((now - t0) / dur, 1);
          el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 4))));
          if (p < 1) requestAnimationFrame(tick);
        })(t0);
      });
    }, { threshold: 0.4 });
    root.querySelectorAll("[data-count]").forEach(function (el) { io.observe(el); });
  }

  /* Tier legend popover */
  var tierBtn = $("#lbTierBtn"), tierPop = $("#lbTierPop");
  if (tierBtn && tierPop) {
    tierBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = tierPop.hidden;
      tierPop.hidden = !open;
      tierBtn.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", function (e) {
      if (!tierPop.hidden && !tierPop.contains(e.target)) { tierPop.hidden = true; tierBtn.setAttribute("aria-expanded", "false"); }
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { tierPop.hidden = true; tierBtn.setAttribute("aria-expanded", "false"); } });
  }

  /* Search: "/" to focus, auto-submit after typing pauses */
  var form = $("#lbSearch"), input = $("#lbQ");
  if (form && input) {
    var timer = null, initial = input.value;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (input.value.trim() === initial.trim()) return;
        form.classList.add("is-loading");
        form.submit();
      }, 450);
    });
    document.addEventListener("keydown", function (e) {
      var tag = (e.target && e.target.tagName) || "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault(); input.focus(); input.select();
      }
    });
    if (initial) { input.focus(); input.setSelectionRange(initial.length, initial.length); }
  }

  /* Controls get a glass background once they stick */
  var controls = $(".lb-controls");
  if (controls && "IntersectionObserver" in window) {
    var sentinel = document.createElement("div");
    sentinel.style.height = "1px";
    controls.parentNode.insertBefore(sentinel, controls);
    new IntersectionObserver(function (entries) {
      controls.classList.toggle("is-stuck", !entries[0].isIntersecting);
    }, { rootMargin: "-60px 0px 0px 0px" }).observe(sentinel);
  }

  /* Jump to my row with a highlight flash */
  var me = document.getElementById("lb-me");
  function flashMe() {
    if (!me) return;
    me.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
    me.classList.remove("is-flash"); void me.offsetWidth; me.classList.add("is-flash");
  }
  root.querySelectorAll("[data-scroll-me]").forEach(function (a) {
    a.addEventListener("click", function (e) { if (me) { e.preventDefault(); flashMe(); } });
  });
  if (location.hash === "#lb-me" && me) setTimeout(flashMe, 350);

  /* Dock: show "you" pill while your row is out of view */
  var dock = $("#lbDock");
  if (dock && me && "IntersectionObserver" in window) {
    dock.hidden = false;
    new IntersectionObserver(function (entries) {
      dock.classList.toggle("is-shown", !entries[0].isIntersecting);
    }, { threshold: 0.1 }).observe(me);
  }
})();
