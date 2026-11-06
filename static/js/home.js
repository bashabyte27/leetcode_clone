/* BashaByte landing page interactions. No dependencies. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(pointer: fine)").matches;

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  /* ── Theme ─────────────────────────────────────────────────── */
  (function theme() {
    var btn = $("#themeToggle");
    var icon = $("#themeIcon");
    if (!btn || !icon) return;
    function paint(t) {
      root.setAttribute("data-theme", t);
      icon.className = t === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
      btn.setAttribute("aria-label", t === "dark" ? "Switch to light theme" : "Switch to dark theme");
    }
    paint(root.getAttribute("data-theme") || "dark");
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      try { localStorage.setItem("bb-theme", next); } catch (e) {}
      paint(next);
    });
  })();

  /* ── Nav: scrolled state + mobile menu ─────────────────────── */
  (function nav() {
    var bar = $("#nav");
    var burger = $("#navBurger");
    var links = $("#navLinks");
    if (bar) {
      var onScroll = function () { bar.classList.toggle("is-scrolled", window.scrollY > 12); };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    if (!burger || !links) return;
    function setOpen(open) {
      links.classList.toggle("is-open", open);
      burger.setAttribute("aria-expanded", String(open));
      burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
      burger.firstElementChild.className = open ? "bi bi-x-lg" : "bi bi-list";
    }
    burger.addEventListener("click", function () { setOpen(!links.classList.contains("is-open")); });
    links.addEventListener("click", function (e) { if (e.target.closest("a")) setOpen(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setOpen(false); });
    document.addEventListener("click", function (e) {
      if (!links.contains(e.target) && !burger.contains(e.target)) setOpen(false);
    });
  })();

  /* ── Reveal on scroll (with sibling stagger) ───────────────── */
  (function reveal() {
    var nodes = $$(".reveal");
    nodes.forEach(function (el) {
      var sibs = $$(":scope > .reveal", el.parentElement);
      var i = sibs.indexOf(el);
      if (i > 0) el.style.setProperty("--d", Math.min(i * 0.08, 0.4) + "s");
    });
    if (reduceMotion || !("IntersectionObserver" in window)) {
      nodes.forEach(function (el) { el.classList.add("reveal-visible"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("reveal-visible"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    nodes.forEach(function (el) { io.observe(el); });
  })();

  /* ── Counters ──────────────────────────────────────────────── */
  (function counters() {
    var els = $$("[data-count]");
    if (!els.length || reduceMotion || !("IntersectionObserver" in window)) return;
    var fmt = new Intl.NumberFormat();
    function run(el) {
      var target = parseInt(el.getAttribute("data-count"), 10) || 0;
      if (!target) return;
      var start = performance.now();
      var dur = 1400;
      (function tick(now) {
        var p = Math.min((now - start) / dur, 1);
        el.textContent = fmt.format(Math.round(target * (1 - Math.pow(1 - p, 4))));
        if (p < 1) requestAnimationFrame(tick);
      })(start);
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { run(e.target); io.unobserve(e.target); }
      });
    }, { threshold: 0.6 });
    els.forEach(function (el) { el.textContent = "0"; io.observe(el); });
  })();

  /* ── Pointer effects: hero spotlight, IDE tilt, tile glow ──── */
  (function pointer() {
    if (reduceMotion || !finePointer) return;
    var hero = $("#hero");
    var ide = $("#ide");
    if (hero) {
      var frame = 0;
      hero.addEventListener("pointermove", function (e) {
        if (frame) return;
        frame = requestAnimationFrame(function () {
          frame = 0;
          var r = hero.getBoundingClientRect();
          hero.style.setProperty("--mx", (e.clientX - r.left) + "px");
          hero.style.setProperty("--my", (e.clientY - r.top) + "px");
          if (ide && window.innerWidth > 1080) {
            var ir = ide.getBoundingClientRect();
            var dx = (e.clientX - (ir.left + ir.width / 2)) / r.width;
            var dy = (e.clientY - (ir.top + ir.height / 2)) / r.height;
            ide.style.setProperty("--ry", (-6 + dx * 8).toFixed(2) + "deg");
            ide.style.setProperty("--rx", (4 - dy * 6).toFixed(2) + "deg");
          }
        });
      });
      hero.addEventListener("pointerleave", function () {
        if (!ide) return;
        ide.style.removeProperty("--ry");
        ide.style.removeProperty("--rx");
      });
    }
    $$(".tile").forEach(function (tile) {
      tile.addEventListener("pointermove", function (e) {
        var r = tile.getBoundingClientRect();
        tile.style.setProperty("--tx", (e.clientX - r.left) + "px");
        tile.style.setProperty("--ty", (e.clientY - r.top) + "px");
      });
    });
  })();

  /* ── Headline rotator ──────────────────────────────────────── */
  (function rotator() {
    var el = $("#rotator");
    if (!el || reduceMotion) return;
    var words = ["interview-ready.", "exam-ready.", "faster.", "ranked."];
    var i = 0;
    setInterval(function () {
      if (document.hidden) return;
      el.classList.add("is-out");
      setTimeout(function () {
        i = (i + 1) % words.length;
        el.textContent = words[i];
        el.classList.remove("is-out");
      }, 350);
    }, 2800);
  })();

  /* ── IDE demo: typing + simulated run ──────────────────────── */
  (function ideDemo() {
    var codeEl = $("#ideCode");
    var fileEl = $("#ideFile");
    var runBtn = $("#ideRun");
    var verdict = $("#ideVerdict");
    var runtimeEl = $("#ideRuntime");
    var cases = $$("#ideCases .case");
    var tabs = $$(".ide-langs button");
    if (!codeEl || !runBtn) return;

    var SAMPLES = {
      python: {
        file: "solution.py", ms: [31, 48],
        code: [
          "def two_sum(nums, target):",
          "    seen = {}",
          "    for i, x in enumerate(nums):",
          "        if target - x in seen:",
          "            return [seen[target - x], i]",
          "        seen[x] = i",
          "    return []"
        ]
      },
      java: {
        file: "Solution.java", ms: [2, 6],
        code: [
          "class Solution {",
          "  int[] twoSum(int[] nums, int t) {",
          "    var seen = new HashMap<Integer, Integer>();",
          "    for (int i = 0; i < nums.length; i++) {",
          "      Integer j = seen.get(t - nums[i]);",
          "      if (j != null) return new int[]{j, i};",
          "      seen.put(nums[i], i);",
          "    }",
          "    return new int[0];",
          "  }",
          "}"
        ]
      },
      cpp: {
        file: "solution.cpp", ms: [3, 9],
        code: [
          "vector<int> twoSum(vector<int>& nums, int t) {",
          "  unordered_map<int, int> seen;",
          "  for (int i = 0; i < nums.size(); i++) {",
          "    auto it = seen.find(t - nums[i]);",
          "    if (it != seen.end()) return {it->second, i};",
          "    seen[nums[i]] = i;",
          "  }",
          "  return {};",
          "}"
        ]
      },
      js: {
        file: "solution.js", ms: [48, 70],
        code: [
          "const twoSum = (nums, target) => {",
          "  const seen = new Map();",
          "  for (let i = 0; i < nums.length; i++) {",
          "    const need = target - nums[i];",
          "    if (seen.has(need)) return [seen.get(need), i];",
          "    seen.set(nums[i], i);",
          "  }",
          "  return [];",
          "};"
        ]
      }
    };

    var KEYWORDS = /^(def|for|in|if|return|class|int|var|new|const|let|auto|null|true|false|vector|unordered_map|Integer|HashMap|Map)$/;
    var TOKEN = /(\/\/.*|#.*)|("[^"]*"|'[^']*')|(\b\d+\b)|([A-Za-z_]\w*)|(\s+)|([\s\S])/g;

    function tokenize(line) {
      var out = [];
      var m;
      TOKEN.lastIndex = 0;
      while ((m = TOKEN.exec(line))) {
        var cls = "";
        if (m[1]) cls = "c";
        else if (m[2]) cls = "s";
        else if (m[3]) cls = "n";
        else if (m[4]) {
          if (KEYWORDS.test(m[4])) cls = "k";
          else if (/^\s*\(/.test(line.slice(TOKEN.lastIndex))) cls = "f";
        }
        out.push({ cls: cls, text: m[0] });
      }
      return out;
    }

    var runId = 0;
    var timers = [];
    function later(fn, ms) { timers.push(setTimeout(fn, ms)); }
    function clearTimers() { timers.forEach(clearTimeout); timers = []; }

    function resetConsole() {
      verdict.hidden = true;
      runtimeEl.textContent = "";
      cases.forEach(function (c) { c.classList.remove("is-running", "is-pass"); });
    }

    function render(lang) {
      var sample = SAMPLES[lang];
      fileEl.textContent = sample.file;
      codeEl.textContent = "";
      var queue = [];
      sample.code.forEach(function (line) {
        var ln = document.createElement("span");
        ln.className = "ln";
        var indent = line.length - line.replace(/^\s+/, "").length;
        var col = 0;
        tokenize(line).forEach(function (tok) {
          for (var i = 0; i < tok.text.length; i++) {
            var ch = document.createElement("span");
            if (tok.cls) ch.className = tok.cls;
            ch.textContent = tok.text[i];
            ln.appendChild(ch);
            queue.push({ el: ch, lead: col < indent, eol: col === line.length - 1 });
            col++;
          }
        });
        if (!line.length) ln.appendChild(document.createTextNode(" "));
        codeEl.appendChild(ln);
      });
      return queue;
    }

    function type(lang, autoRun) {
      clearTimers();
      var id = ++runId;
      resetConsole();
      runBtn.disabled = false;
      var queue = render(lang);

      if (reduceMotion) {
        if (autoRun) run(SAMPLES[lang]);
        return;
      }

      queue.forEach(function (q) { q.el.classList.add("ch-hidden"); });
      var caret = document.createElement("span");
      caret.className = "caret";
      var i = 0;
      (function step() {
        if (id !== runId) return;
        // Leading indentation appears at once, like an editor auto-indent
        while (i < queue.length && queue[i].lead) queue[i++].el.classList.remove("ch-hidden");
        if (i >= queue.length) {
          if (caret.parentNode) caret.parentNode.removeChild(caret);
          if (autoRun) later(function () { run(SAMPLES[lang]); }, 350);
          return;
        }
        var q = queue[i++];
        q.el.classList.remove("ch-hidden");
        q.el.parentNode.insertBefore(caret, q.el.nextSibling);
        later(step, q.eol ? 90 + Math.random() * 60 : 9 + Math.random() * 14);
      })();
    }

    function run(sample) {
      var id = runId;
      resetConsole();
      runBtn.disabled = true;
      var t = reduceMotion ? 0 : 1;
      cases.forEach(function (c, idx) {
        later(function () { if (id === runId) c.classList.add("is-running"); }, t * (idx * 420 + 120));
        later(function () {
          if (id !== runId) return;
          c.classList.remove("is-running");
          c.classList.add("is-pass");
        }, t * (idx * 420 + 480));
      });
      later(function () {
        if (id !== runId) return;
        verdict.hidden = false;
        var lo = sample.ms[0], hi = sample.ms[1];
        runtimeEl.textContent = "Runtime " + Math.round(lo + Math.random() * (hi - lo)) + " ms";
        runBtn.disabled = false;
      }, t * (cases.length * 420 + 200));
    }

    var current = "python";
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var lang = tab.getAttribute("data-lang");
        if (!SAMPLES[lang] || lang === current) return;
        current = lang;
        tabs.forEach(function (t) {
          var on = t === tab;
          t.classList.toggle("is-active", on);
          t.setAttribute("aria-selected", String(on));
        });
        type(lang, true);
      });
    });
    runBtn.addEventListener("click", function () {
      clearTimers();
      runId++;
      // Make sure all code is visible if the user runs mid-typing
      $$(".ch-hidden", codeEl).forEach(function (c) { c.classList.remove("ch-hidden"); });
      var caret = $(".caret", codeEl);
      if (caret) caret.remove();
      run(SAMPLES[current]);
    });

    later(function () { type(current, true); }, 500);
  })();

  /* ── Faculty console: countdown + live proctor feed ────────── */
  (function facultyConsole() {
    var timerEl = $("#examTimer");
    var feed = $("#proctorFeed");
    var kpiSub = $("#kpiSubmitted");
    var kpiFlags = $("#kpiFlags");
    if (!timerEl || !feed) return;

    var remaining = 45 * 60;
    var visible = false;
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) { visible = entries[0].isIntersecting; }).observe(timerEl.closest(".console"));
    } else {
      visible = true;
    }

    var EVENTS = [
      { cls: "ev-warn", icon: "bi-window-stack", text: "switched tabs", flag: true },
      { cls: "ev-ok", icon: "bi-check2-circle", text: "submitted Q2", submit: true },
      { cls: "ev-info", icon: "bi-arrows-fullscreen", text: "re-entered fullscreen" },
      { cls: "ev-warn", icon: "bi-clipboard-x", text: "paste blocked", flag: true },
      { cls: "ev-ok", icon: "bi-check2-circle", text: "submitted all sections", submit: true },
      { cls: "ev-ok", icon: "bi-cpu", text: "Q3 passed 12/12 hidden tests" }
    ];

    var stamps = $$("li", feed).map(function (_, i) { return Date.now() - [0, 12, 40][i] * 1000; });

    function ago(ts) {
      var s = Math.round((Date.now() - ts) / 1000);
      if (s < 5) return "now";
      if (s < 60) return s + "s";
      return Math.floor(s / 60) + "m";
    }

    function bump(el) {
      el.textContent = String(parseInt(el.textContent, 10) + 1);
      el.classList.add("bump");
      setTimeout(function () { el.classList.remove("bump"); }, 700);
    }

    function pushEvent() {
      var ev = EVENTS[Math.floor(Math.random() * EVENTS.length)];
      var li = document.createElement("li");
      li.className = "ev " + ev.cls;
      var icon = document.createElement("i");
      icon.className = "bi " + ev.icon;
      var time = document.createElement("time");
      time.textContent = "now";
      li.appendChild(icon);
      li.appendChild(document.createTextNode(" Candidate #" + String(1 + Math.floor(Math.random() * 48)).padStart(2, "0") + " " + ev.text + " "));
      li.appendChild(time);
      feed.insertBefore(li, feed.firstChild);
      stamps.unshift(Date.now());
      while (feed.children.length > 3) { feed.removeChild(feed.lastChild); stamps.pop(); }
      if (ev.flag && kpiFlags) bump(kpiFlags);
      if (ev.submit && kpiSub) bump(kpiSub);
    }

    var tick = 0;
    setInterval(function () {
      if (!visible || document.hidden) return;
      remaining = Math.max(0, remaining - 1);
      var h = Math.floor(remaining / 3600), m = Math.floor((remaining % 3600) / 60), s = remaining % 60;
      timerEl.textContent = [h, m, s].map(function (n) { return String(n).padStart(2, "0"); }).join(":");
      $$("time", feed).forEach(function (t, i) { t.textContent = ago(stamps[i]); });
      tick++;
      if (!reduceMotion && tick % 4 === 0) pushEvent();
    }, 1000);
  })();
})();
