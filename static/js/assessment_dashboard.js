/* BashaByte · Assessment dashboard interactions (visual only). */
(function () {
  "use strict";
  var shell = document.querySelector(".asx-dash");
  if (!shell) return;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Sliding underline under the active admin tab */
  var tabs = shell.querySelector(".asx-tabs");
  function placeInk() {
    if (!tabs) return;
    var ink = tabs.querySelector(".asx-tabs-ink"), active = tabs.querySelector("a.active");
    if (!ink || !active) return;
    ink.style.width = active.offsetWidth + "px";
    ink.style.transform = "translateX(" + active.offsetLeft + "px)";
  }
  placeInk();
  window.addEventListener("resize", placeInk);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(placeInk);

  /* Count-up for KPI numbers */
  if (!reduceMotion) {
    shell.querySelectorAll("[data-count]").forEach(function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10) || 0;
      if (!target) return;
      var t0 = performance.now(), dur = 900;
      el.textContent = "0";
      (function tick(now) {
        var p = Math.min((now - t0) / dur, 1);
        el.textContent = String(Math.round(target * (1 - Math.pow(1 - p, 3))));
        if (p < 1) requestAnimationFrame(tick);
      })(t0);
    });
  }

  /* Toast */
  var toast = document.getElementById("asxToast"), toastTimer;
  function showToast(text) {
    if (!toast) return;
    toast.textContent = text;
    toast.hidden = false;
    toast.classList.remove("is-shown"); void toast.offsetWidth; toast.classList.add("is-shown");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove("is-shown"); }, 2200);
  }

  /* Copy student link */
  shell.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    e.preventDefault();
    navigator.clipboard.writeText(btn.getAttribute("data-copy")).then(function () {
      btn.classList.add("is-copied");
      btn.innerHTML = '<i class="bi bi-check2"></i>';
      showToast("Student link copied to clipboard");
      setTimeout(function () { btn.classList.remove("is-copied"); btn.innerHTML = '<i class="bi bi-clipboard"></i>'; }, 1600);
    });
  });

  /* Assessment search: auto-submit after typing pauses; "/" focuses it */
  var form = shell.querySelector("[data-autosubmit]");
  var input = form && form.querySelector('input[type="search"]');
  if (form && input) {
    var initial = input.value, timer;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (input.value.trim() !== initial.trim()) { form.classList.add("is-loading"); form.submit(); }
      }, 450);
    });
    if (initial) { input.focus(); input.setSelectionRange(initial.length, initial.length); }
  }
  document.addEventListener("keydown", function (e) {
    var tag = (e.target && e.target.tagName) || "";
    if (e.key !== "/" || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.ctrlKey || e.metaKey) return;
    var target = input || shell.querySelector("[data-question-search]");
    if (target) { e.preventDefault(); target.focus(); target.select(); }
  });

  /* Card spotlight follows the pointer */
  if (!reduceMotion && window.matchMedia("(pointer: fine)").matches) {
    shell.querySelectorAll(".asx-card").forEach(function (card) {
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--mx", (e.clientX - r.left) + "px");
        card.style.setProperty("--my", (e.clientY - r.top) + "px");
      });
    });
  }
})();
