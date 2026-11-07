/* BashaByte · Staff course builder: drag reorder, question search & attach. */
(function () {
  "use strict";

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (m) return decodeURIComponent(m[1]);
    var input = document.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function post(url, data, json) {
    var opts = { method: "POST", headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" }, credentials: "same-origin" };
    if (json) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(data);
    } else {
      var fd = new FormData();
      Object.keys(data || {}).forEach(function (k) { fd.append(k, data[k]); });
      opts.body = fd;
    }
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        if (!r.ok) throw new Error(body.error || "Request failed (" + r.status + ")");
        return body;
      });
    });
  }

  function toast(text, isError) {
    var el = document.createElement("div");
    el.className = "cb-toast" + (isError ? " is-error" : "");
    el.setAttribute("role", "status");
    el.textContent = text;
    document.body.appendChild(el);
    requestAnimationFrame(function () { el.classList.add("is-shown"); });
    setTimeout(function () { el.classList.remove("is-shown"); setTimeout(function () { el.remove(); }, 300); }, 2200);
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ── Drag to reorder (SortableJS, loaded from CDN) ───────────────── */
  function initSortables() {
    if (!window.Sortable) return;
    document.querySelectorAll("[data-sortable]").forEach(function (list) {
      if (!list.querySelector(".cb-row") || list.dataset.sortableReady) return;
      list.dataset.sortableReady = "1";
      Sortable.create(list, {
        handle: ".cb-handle",
        draggable: ".cb-row",
        animation: 160,
        ghostClass: "is-ghost",
        onEnd: function (evt) {
          if (evt.oldIndex === evt.newIndex) return;
          var ids = Array.prototype.map.call(list.querySelectorAll(".cb-row"), function (row) { return row.dataset.id; });
          post(list.dataset.reorderUrl, { ids: ids }, true)
            .then(function () {
              list.querySelectorAll(".cb-row .cb-index").forEach(function (badge, i) {
                badge.textContent = badge.textContent.replace(/\d+/, function (d) {
                  var n = String(i + 1);
                  return d.length === 2 && n.length === 1 ? "0" + n : n;
                });
              });
              toast("Order saved");
            })
            .catch(function (err) { toast(err.message, true); setTimeout(function () { location.reload(); }, 900); });
        },
      });
    });
  }

  /* ── Search pickers: coding question (select into hidden input) and MCQ (attach to step) ── */
  function initPickers() {
    document.querySelectorAll("[data-picker]").forEach(function (picker) {
      var input = picker.querySelector("[data-search-input]");
      var results = picker.querySelector("[data-results]");
      var timer = null;
      var lastQuery = null;

      function render(rows) {
        if (!rows.length) {
          results.innerHTML = '<li class="cb-result-empty">No matches.</li>';
        } else {
          results.innerHTML = rows.map(function (r) {
            return '<li><button type="button" data-pick="' + r.id + '"><b>' + escapeHtml(r.title) + '</b><small>' +
              escapeHtml(r.meta) + '</small></button></li>';
          }).join("");
        }
        results.hidden = false;
        results._rows = rows;
      }

      function search() {
        var q = input.value.trim();
        if (q === lastQuery) return;
        lastQuery = q;
        var sep = picker.dataset.searchUrl.indexOf("?") === -1 ? "?" : "&";
        fetch(picker.dataset.searchUrl + sep + "q=" + encodeURIComponent(q), { credentials: "same-origin" })
          .then(function (r) { return r.json(); })
          .then(function (data) { render(data.results || []); })
          .catch(function () { toast("Search failed", true); });
      }

      input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(search, 220); });
      input.addEventListener("focus", function () { if (!results._rows) search(); else results.hidden = false; });
      input.addEventListener("keydown", function (e) { if (e.key === "Escape") results.hidden = true; });
      document.addEventListener("click", function (e) { if (!picker.contains(e.target)) results.hidden = true; });

      results.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-pick]");
        if (!btn) return;
        var row = (results._rows || []).filter(function (r) { return String(r.id) === btn.dataset.pick; })[0];
        if (picker.dataset.addUrl) {
          post(picker.dataset.addUrl, { mcq_id: btn.dataset.pick })
            .then(function () { location.hash = "questions"; location.reload(); })
            .catch(function (err) { toast(err.message, true); });
        } else {
          var hidden = document.querySelector(picker.dataset.target);
          hidden.value = row.id;
          var picked = picker.querySelector("[data-picked]");
          picked.querySelector("[data-picked-title]").textContent = row.title;
          picked.querySelector("[data-picked-meta]").textContent = row.meta;
          picked.hidden = false;
          results.hidden = true;
          input.value = "";
          toast("Selected. Save the step to keep it");
        }
      });

      var clear = picker.querySelector("[data-picked-clear]");
      if (clear) clear.addEventListener("click", function () {
        document.querySelector(picker.dataset.target).value = "";
        picker.querySelector("[data-picked]").hidden = true;
        toast("Removed. Save the step to keep the change");
      });
    });
  }

  /* ── Question rows: outcome tag + remove ─────────────────────────── */
  function initQuestionRows() {
    document.querySelectorAll("[data-question-outcome]").forEach(function (select) {
      select.addEventListener("change", function () {
        post(select.dataset.url, { outcome_id: select.value })
          .then(function () { select.classList.toggle("is-missing", !select.value); toast("Outcome saved"); })
          .catch(function (err) { toast(err.message, true); });
      });
    });
    document.querySelectorAll("[data-question-remove]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!confirm("Remove this question from the step?")) return;
        post(btn.dataset.url, {})
          .then(function () { location.hash = "questions"; location.reload(); })
          .catch(function (err) { toast(err.message, true); });
      });
    });
  }

  function init() { initSortables(); initPickers(); initQuestionRows(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  // SortableJS is deferred from a CDN; retry once it has loaded
  window.addEventListener("load", initSortables);
})();
