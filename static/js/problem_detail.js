/* ─────────────────────────────────────────────────────────────
   LEETCODE PROBLEM DETAIL — problem_detail.js
   Globals expected: PROBLEM_SLUG, IS_AUTHENTICATED, CSRF_TOKEN
   ───────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  /* ══════════════════════════
     HELPERS
  ══════════════════════════ */
  function getEditorCode() {
    return window.editor ? window.editor.getValue() : '';
  }

  function getSelectedLanguage() {
    const el = document.getElementById('language-select');
    return el ? el.value : 'python';
  }

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
      btn.classList.add('btn-loading');
      btn.disabled = true;
    } else {
      btn.classList.remove('btn-loading');
      btn.disabled = false;
    }
  }

  function skeletonHTML() {
    return `
      <div class="skeleton skeleton-line w-3-4 h-tall" style="margin-bottom:12px"></div>
      <div class="skeleton skeleton-line w-full"></div>
      <div class="skeleton skeleton-line w-full"></div>
      <div class="skeleton skeleton-line w-1-2"></div>
      <div class="skeleton skeleton-block" style="margin-top:16px"></div>
      <div class="skeleton skeleton-line w-full" style="margin-top:12px"></div>
      <div class="skeleton skeleton-line w-3-4"></div>
    `;
  }

  function escapeHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escapeAttr(text) {
    return String(text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function titleize(str) {
    return String(str || '').replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  /* ══════════════════════════
     THEME TOGGLE
  ══════════════════════════ */
  (function initTheme() {
    const saved = localStorage.getItem('editorTheme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    const btn = document.getElementById('btn-theme-toggle');
    if (btn) btn.textContent = saved === 'dark' ? '☀' : '🌙';
  })();

  const btnTheme = document.getElementById('btn-theme-toggle');
  if (btnTheme) {
    btnTheme.addEventListener('click', function () {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('editorTheme', next);
      btnTheme.textContent = next === 'dark' ? '☀' : '🌙';

      if (window.monaco && window.editor) {
        monaco.editor.setTheme(next === 'dark' ? 'neonMatrix' : 'vs');
      }
    });
  }

  /* ══════════════════════════
     TIMER (Toolbar) — auto-starts on page load
  ══════════════════════════ */
  let timerInterval = null;
  let timerSeconds = 0;
  let timerRunning = false;

  const timerDisplay = document.getElementById('timer-display');

  function updateTimerDisplay() {
    if (!timerDisplay) return;
    const m = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
    const s = String(timerSeconds % 60).padStart(2, '0');
    const timeText = m + ':' + s;
    const textEl = timerDisplay.querySelector('.timer-text');
    if (textEl) {
      textEl.textContent = timeText;
    } else {
      timerDisplay.textContent = timeText;
    }
  }

  function startTimerInterval() {
    if (timerRunning) return;
    timerRunning = true;
    if (timerDisplay) timerDisplay.classList.add('running');
    timerInterval = setInterval(function () {
      timerSeconds++;
      updateTimerDisplay();
    }, 1000);
  }

  function pauseTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
    timerRunning = false;
    if (timerDisplay) timerDisplay.classList.remove('running');
  }

  function resetTimer() {
    timerSeconds = 0;
    updateTimerDisplay();
  }

  // Fresh timer per page-visit. Not persisted across reloads/users, so
  // switching accounts always starts at 0 for the current session.
  (function initTimer() {
    timerSeconds = 0;
    updateTimerDisplay();
    startTimerInterval();
  })();

  // Click to pause/resume
  if (timerDisplay) {
    timerDisplay.addEventListener('click', function () {
      if (timerRunning) {
        pauseTimer();
      } else {
        startTimerInterval();
      }
    });
  }

  const timerReset = document.getElementById('timer-reset');
  if (timerReset) {
    timerReset.addEventListener('click', function () {
      resetTimer();
    });
  }

  /* ══════════════════════════
     LEFT PANEL TABS
  ══════════════════════════ */
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const target = btn.dataset.tab;
      tabBtns.forEach(function (b) { b.classList.remove('active'); });
      tabContents.forEach(function (c) { c.classList.remove('active'); });
      btn.classList.add('active');
      const contentEl = document.getElementById('tab-' + target);
      if (contentEl) contentEl.classList.add('active');

      // Lazy loading
      if (target === 'editorial') lazyLoadTab('editorial', '/problems/' + PROBLEM_SLUG + '/editorial');
      if (target === 'discussion') lazyLoadTab('discussion', '/discussions/problems/' + PROBLEM_SLUG + '/');
      if (target === 'submissions') lazyLoadSubmissions();
    });
  });

  function lazyLoadTab(tabName, url) {
    const el = document.getElementById('tab-' + tabName);
    if (!el || el.classList.contains('loaded')) return;
    el.innerHTML = skeletonHTML();
    fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error('Network response was not ok');
        return r.text();
      })
      .then(function (text) {
        // The discussion endpoint returns JSON {html: "..."} — unwrap it.
        // Editorial/submissions return raw HTML directly.
        if (tabName === 'discussion') {
          try {
            const parsed = JSON.parse(text);
            text = parsed.html || text;
          } catch (e) { /* not JSON — leave as-is */ }
        }
        el.innerHTML = text;
        el.classList.add('loaded');
      })
      .catch(function () {
        el.innerHTML = '<div class="empty-state">' +
          (tabName === 'editorial' ? 'Editorial not available.' : 'Failed to load. Please try again.') +
          '</div>';
      });
  }

  function lazyLoadSubmissions() {
    const el = document.getElementById('tab-submissions');
    if (!el) return;
    if (!IS_AUTHENTICATED) {
      el.innerHTML = '<div class="empty-state">Please log in to view your submissions.</div>';
      return;
    }
    if (el.classList.contains('loaded')) return;
    el.innerHTML = skeletonHTML();
    fetch('/submissions/' + PROBLEM_SLUG + '/')
      .then(function (r) { return r.text(); })
      .then(function (html) {
        el.innerHTML = html;
        el.classList.add('loaded');
      })
      .catch(function () {
        el.innerHTML = '<div class="empty-state">Failed to load submissions.</div>';
      });
  }

  /* ══════════════════════════
     DISCUSSION TAB ACTIONS (event-delegated — tab content is AJAX-injected)
  ══════════════════════════ */
  const discussionTabEl = document.getElementById('tab-discussion');

  function discussionFetch(url, opts, callback) {
    fetch(url, opts)
      .then(function (r) {
        if (r.status === 403) { throw new Error('Permission denied.'); }
        return r.json();
      })
      .then(callback)
      .catch(function (err) {
        alert('Could not complete the request: ' + err.message);
      });
  }

  function handleDiscussionVote(btn) {
    if (!IS_AUTHENTICATED) { alert('Please login to vote.'); return; }
    const commentId = btn.dataset.commentId;
    const value = parseInt(btn.dataset.value, 10);

    discussionFetch('/discussions/comments/' + commentId + '/vote/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF_TOKEN,
      },
      body: JSON.stringify({ value: value }),
    }, function (data) {
      // Update count + active styles in place (no full reload)
      const countEl = document.querySelector('[data-count-id="' + data.comment_id + '"]');
      if (countEl) countEl.textContent = data.vote_count;
      const card = btn.closest('.comment-card');
      if (card) {
        card.querySelectorAll('.vote-btn').forEach(function (b) {
          b.classList.remove('active-up', 'active-down');
        });
        const up = card.querySelector('[data-value="1"]');
        const down = card.querySelector('[data-value="-1"]');
        if (data.user_vote === 1 && up) up.classList.add('active-up');
        if (data.user_vote === -1 && down) down.classList.add('active-down');
      }
    });
  }

  function toggleReplyForm(btn) {
    const parentId = btn.dataset.parentId;
    const form = document.querySelector('[data-reply-form="' + parentId + '"]');
    if (form) form.classList.toggle('open');
  }

  function closeReplyForm(btn) {
    const wrapper = btn.closest('.reply-form-wrapper');
    if (wrapper) {
      wrapper.classList.remove('open');
      const ta = wrapper.querySelector('.reply-form-input');
      if (ta) ta.value = '';
    }
  }

  function postDiscussionComment(btn, isReply) {
    if (!IS_AUTHENTICATED) { alert('Please login to comment.'); return; }
    const slug = btn.dataset.slug || PROBLEM_SLUG;

    let content, parentId = null;
    if (isReply) {
      const wrapper = btn.closest('.reply-form-wrapper');
      if (!wrapper) return;
      const ta = wrapper.querySelector('.reply-form-input');
      content = ta ? ta.value.trim() : '';
      parentId = btn.dataset.parentId || null;
    } else {
      const ta = document.getElementById('new-comment-input');
      content = ta ? ta.value.trim() : '';
    }

    if (!content) { alert('Please write a comment first.'); return; }

    discussionFetch('/discussions/problems/' + slug + '/comment/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-CSRFToken': CSRF_TOKEN,
      },
      body: 'content=' + encodeURIComponent(content) +
            (parentId ? '&parent_id=' + encodeURIComponent(parentId) : ''),
    }, function (data) {
      if (data.html) {
        discussionTabEl.innerHTML = data.html;
      } else if (data.error) {
        alert(data.error);
      }
    });
  }

  if (discussionTabEl) {
    discussionTabEl.addEventListener('click', function (e) {
      const target = e.target.closest('[data-action]');
      if (!target || !discussionTabEl.contains(target)) return;
      switch (target.dataset.action) {
        case 'vote':           handleDiscussionVote(target); break;
        case 'toggle-reply':   toggleReplyForm(target);       break;
        case 'cancel-reply':   closeReplyForm(target);        break;
        case 'post-comment':   postDiscussionComment(target, false); break;
        case 'post-reply':     postDiscussionComment(target, true);  break;
      }
    });
  }

  /* ══════════════════════════
     PILL DROPDOWNS (Topics / Companies)
  ══════════════════════════ */
  document.querySelectorAll('[data-dropdown]').forEach(function (btn) {
    const dropdownId = btn.dataset.dropdown;
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = dropdown.classList.contains('open');
      document.querySelectorAll('.pill-dropdown.open').forEach(function (d) { d.classList.remove('open'); });
      if (!isOpen) dropdown.classList.add('open');
    });
  });

  document.addEventListener('click', function () {
    document.querySelectorAll('.pill-dropdown.open').forEach(function (d) { d.classList.remove('open'); });
  });

  /* ══════════════════════════
     HINTS
  ══════════════════════════ */
  (function initHints() {
    const hintsDataEl = document.getElementById('hints-data');
    const btnHint = document.getElementById('btn-hint');
    const hintsArea = document.getElementById('hints-area');
    if (!hintsDataEl || !btnHint || !hintsArea) return;

    let hints = [];
    try { hints = JSON.parse(hintsDataEl.textContent); } catch (e) { hints = []; }
    let currentIndex = 0;

    btnHint.addEventListener('click', function () {
      if (hints.length === 0) return;
      if (currentIndex >= hints.length) {
        btnHint.innerHTML = '<span>All hints shown</span>';
        return;
      }
      const card = document.createElement('div');
      card.className = 'hint-card';
      card.innerHTML = '<strong>Hint ' + (currentIndex + 1) + '</strong>' + escapeHtml(hints[currentIndex]);
      hintsArea.appendChild(card);
      currentIndex++;
      if (currentIndex >= hints.length) {
        btnHint.innerHTML = '<span>All hints shown</span>';
      }
    });
  })();

  /* ══════════════════════════
     VERTICAL RESIZE HANDLE
  ══════════════════════════ */
  (function initVerticalResize() {
    const handle = document.getElementById('resize-handle-vertical');
    const leftPanel = document.getElementById('left-panel');
    if (!handle || !leftPanel) return;

    let dragging = false;

    handle.addEventListener('mousedown', function (e) {
      e.preventDefault();
      dragging = true;
      handle.classList.add('dragging');
      document.body.classList.add('no-select');
    });

    document.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      let newWidth = e.clientX;
      const minW = 280;
      const maxW = window.innerWidth * 0.65;
      newWidth = Math.max(minW, Math.min(maxW, newWidth));
      leftPanel.style.flexBasis = newWidth + 'px';
    });

    document.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove('dragging');
      document.body.classList.remove('no-select');
      if (window.editor) window.editor.layout();
    });
  })();

  /* ══════════════════════════
     HORIZONTAL RESIZE HANDLE
  ══════════════════════════ */
  (function initHorizontalResize() {
    const handle = document.getElementById('resize-handle-horizontal');
    const editorZone = document.getElementById('editor-zone');
    const rightPanel = document.getElementById('right-panel');
    if (!handle || !editorZone || !rightPanel) return;

    let dragging = false;
    let startY = 0;
    let startHeight = 0;

    handle.addEventListener('mousedown', function (e) {
      e.preventDefault();
      dragging = true;
      startY = e.clientY;
      startHeight = editorZone.offsetHeight;
      handle.classList.add('dragging');
      document.body.classList.add('no-select');
    });

    document.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      const delta = e.clientY - startY;
      const panelH = rightPanel.offsetHeight;
      let newH = startHeight + delta;
      newH = Math.max(140, Math.min(panelH - 120, newH));
      editorZone.style.flex = '0 0 ' + newH + 'px';
    });

    document.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove('dragging');
      document.body.classList.remove('no-select');
      if (window.editor) window.editor.layout();
    });
  })();

  /* ══════════════════════════
     TESTCASE TABS
  ══════════════════════════ */
  document.querySelectorAll('.testcase-tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const target = btn.dataset.tctab;
      document.querySelectorAll('.testcase-tab-btn').forEach(function (b) { b.classList.remove('active'); });
      document.querySelectorAll('.testcase-tab-content').forEach(function (c) { c.classList.remove('active'); });
      btn.classList.add('active');
      const el = document.getElementById('tc-tab-' + target);
      if (el) el.classList.add('active');
    });
  });

  function switchToTestResultTab() {
    document.querySelectorAll('.testcase-tab-btn').forEach(function (b) { b.classList.remove('active'); });
    document.querySelectorAll('.testcase-tab-content').forEach(function (c) { c.classList.remove('active'); });
    const resultBtn = document.querySelector('[data-tctab="result"]');
    const resultContent = document.getElementById('tc-tab-result');
    if (resultBtn) resultBtn.classList.add('active');
    if (resultContent) resultContent.classList.add('active');
  }

  /* ══════════════════════════
     TESTCASE SELECTOR & SYNC
  ══════════════════════════ */
  (function initTestcases() {
    const dataEl = document.getElementById('sample-cases-data');
    const pillsRow = document.getElementById('testcase-pills-row');
    const customInput = document.getElementById('custom-input');
    const expectedOutputEl = document.getElementById('tc-expected-output');
    const expectedCard = document.getElementById('tc-expected-card');
    const copyInputBtn = document.getElementById('btn-copy-tc-input');
    const copyExpectedBtn = document.getElementById('btn-copy-tc-expected');

    if (!pillsRow || !customInput) return;

    let cases = [];
    try {
      cases = dataEl ? JSON.parse(dataEl.textContent) : [];
    } catch (e) {
      cases = [];
    }

    if (cases.length === 0) {
      cases = [{ order_num: 1, input_data: customInput.value || '', expected_output: '' }];
    }

    let activeIdx = 0;

    customInput.addEventListener('input', function () {
      if (cases[activeIdx]) {
        cases[activeIdx].input_data = customInput.value;
      }
    });

    pillsRow.querySelectorAll('.case-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        const idx = parseInt(pill.dataset.caseIndex, 10);
        if (isNaN(idx) || idx === activeIdx || !cases[idx]) return;

        if (cases[activeIdx]) {
          cases[activeIdx].input_data = customInput.value;
        }

        pillsRow.querySelectorAll('.case-pill').forEach(function (p) {
          p.classList.remove('active');
        });
        pill.classList.add('active');

        activeIdx = idx;
        const curCase = cases[activeIdx];
        customInput.value = curCase.input_data || '';

        if (expectedOutputEl) {
          expectedOutputEl.textContent = curCase.expected_output || '';
        }
        if (expectedCard) {
          expectedCard.style.display = curCase.expected_output ? 'block' : 'none';
        }
      });
    });

    if (copyInputBtn) {
      copyInputBtn.addEventListener('click', function () {
        navigator.clipboard.writeText(customInput.value).then(function () {
          copyInputBtn.textContent = 'Copied!';
          setTimeout(function () { copyInputBtn.textContent = 'Copy'; }, 1500);
        });
      });
    }

    if (copyExpectedBtn && expectedOutputEl) {
      copyExpectedBtn.addEventListener('click', function () {
        navigator.clipboard.writeText(expectedOutputEl.textContent).then(function () {
          copyExpectedBtn.textContent = 'Copied!';
          setTimeout(function () { copyExpectedBtn.textContent = 'Copy'; }, 1500);
        });
      });
    }
  })();

  /* ══════════════════════════
     ERROR LINE HIGHLIGHTING (Monaco editor)
     Parses compiler/runtime error messages, highlights the offending
     source line(s) with a red gutter marker + wavy underline.
  ══════════════════════════ */
  var errorDecorations = [];

  function clearErrorHighlights() {
    if (!window.monaco || !window.editor) return;
    errorDecorations = window.editor.deltaDecorations(errorDecorations, []);
  }

  function highlightErrorLines(message) {
    if (!window.monaco || !window.editor) return;
    clearErrorHighlights();

    var text = String(message || '');
    if (!text) return;

    var lines = [];
    // Extract 1-based line numbers from common compiler messages.
    // Patterns: "Main.java:9"  "main.c:12:"  "stdin:9"  "solution.py:line 4"
    //           C++: "solution.cc:In function 'main':" ... "solution.cc:7:5:"
    //           Python tracebacks: 'File ".../Main.py", line 5, in <module>'
    //           JavaScript/Node: 'evalmachine.<anonymous>:3'  /  '...foo.js:3:5'
    var lineRe = /\b(?:[A-Za-z0-9_.\-]+\.(?:java|c|cpp|c\+\+|cc|py|go|rs|js|ts)|stdin|Main|solution|main|Input|Code)\s*:?\s*(\d+)/gi;
    var match;
    while ((match = lineRe.exec(text)) !== null) {
      var n = parseInt(match[1], 10);
      if (n >= 1 && lines.indexOf(n) === -1) lines.push(n);
    }
    // Also catch "line N" style used by Python / Node tracebacks
    var pythonRe = /line\s+(\d+)/gi;
    while ((match = pythonRe.exec(text)) !== null) {
      var n3 = parseInt(match[1], 10);
      if (n3 >= 1 && lines.indexOf(n3) === -1) lines.push(n3);
    }
    // Also catch "captured identification" style: ".js:9:5" / "9:9" col-form
    var colRe = /([A-Za-z0-9_.\-]+\.[a-z]+)\s*:\s*(\d+)/gi;
    while ((match = colRe.exec(text)) !== null) {
      var n2 = parseInt(match[2], 10);
      if (n2 >= 1 && lines.indexOf(n2) === -1) lines.push(n2);
    }
    // Node.js (Judge0): 'evalmachine.<anonymous>:3'
    var nodeRe = /evalmachine\.<anonymous>\s*:\s*(\d+)/gi;
    while ((match = nodeRe.exec(text)) !== null) {
      var n4 = parseInt(match[1], 10);
      if (n4 >= 1 && lines.indexOf(n4) === -1) lines.push(n4);
    }

    if (lines.length === 0) {
      // No line info — highlight line 1 as a fallback hint
      lines.push(1);
    }

    var model = window.editor.getModel();
    if (!model) return;
    var lineCount = model.getLineCount();
    var decos = lines
      .filter(function (ln) { return ln <= lineCount; })
      .map(function (ln) {
        return {
          range: new monaco.Range(ln, 1, ln, model.getLineMaxColumn(ln)),
          options: {
            isWholeLine: true,
            className: 'error-highlight-line',
            linesDecorationsClassName: 'error-highlight-line-number',
            hoverMessage: { value: escapeHtml(text) },
            overviewRuler: { color: '#ef4444', position: monaco.editor.OverviewRulerPosition.Left },
          },
        };
      })
      .filter(Boolean);

    if (decos.length > 0) {
      errorDecorations = window.editor.deltaDecorations(errorDecorations, decos);
    }
  }

    /* ══════════════════════════
     RESULT RENDERING
  ══════════════════════════ */

  // Status helpers
  function statusClass(status) {
    var s = String(status || '').toLowerCase().replace(/ /g, '_');
    if (s === 'success' || s === 'accepted') return 'accepted';
    if (s === 'wrong_answer' || s === 'wrong answer') return 'wrong';
    if (s === 'time_limit_exceeded' || s === 'time limit exceeded') return 'tle';
    if (s === 'runtime_error' || s === 'runtime error') return 'runtime';
    if (s === 'compile_error' || s === 'compile error') return 'compile';
    return 'runtime';
  }

  function statusLabel(status) {
    var s = String(status || '').toLowerCase();
    if (s === 'success' || s === 'accepted') return 'Accepted';
    return titleize(status);
  }

  function formatMemoryKB(kb) {
    if (!kb && kb !== 0) return null;
    var val = parseFloat(kb);
    if (isNaN(val)) return null;
    if (val >= 1024) return (val / 1024).toFixed(1) + ' MB';
    return Math.round(val) + ' KB';
  }

  /* ── Banner HTML ──
     Status text is bold + text-shadow for accepted,
     bold + red-tinted for errors. No emojis. */
  function bannerHTML(cls, label, statsRow) {
    return '<div class="result-status-banner ' + cls + '">' +
      '<div class="result-banner-title">' + label + '</div>' +
      (statsRow ? '<div class="result-stats-row">' + statsRow + '</div>' : '') +
      '</div>';
  }

  /* ── Case pill ──
     Filled green background for pass, filled red for fail.
     No emoji tick/cross — just the text "Case N". */
  function casePillHTML(num, passed, active) {
    return '<button class="result-case-pill ' +
      (passed ? 'pill-passed' : 'pill-failed') +
      (active ? ' active' : '') +
      '" data-index="' + (num - 1) + '">Case ' + num + '</button>';
  }

  function renderRunResult(response) {
    var container = document.getElementById('test-result-content');
    if (!container) return;

    var results = response.test_case_results || [];

    if (results.length === 0) {
      container.innerHTML = '<div class="empty-state">No test case results found.</div>';
      return;
    }

    // Determine overall status from first non-success result
    var overallStatus = 'success';
    for (var k = 0; k < results.length; k++) {
      if (results[k].status !== 'success' && results[k].status !== 'accepted') {
        overallStatus = results[k].status;
        break;
      }
    }
    var cls = statusClass(overallStatus);
    var label = statusLabel(overallStatus);

    // Highlight the offending source line for runtime / compile errors
    if (cls === 'runtime' || cls === 'compile') {
      var errMsg = '';
      for (var e = 0; e < results.length; e++) {
        if (results[e].status !== 'success' && results[e].status !== 'accepted') {
          errMsg = results[e].actual || '';
          break;
        }
      }
      try { highlightErrorLines(errMsg); } catch (_) { /* Monaco not ready */ }
    } else {
      try { clearErrorHighlights(); } catch (_) {}
    }

    // Compute total runtime
    var totalMs = 0;
    for (var j = 0; j < results.length; j++) {
      totalMs += parseFloat(results[j].runtime_ms) || 0;
    }
    totalMs = totalMs.toFixed(1);

    var header = bannerHTML(cls, label, '<span>' + totalMs + ' ms</span>');

    // Case pills (for multi-case run)
    var pillsHTML = '';
    if (results.length > 1) {
      pillsHTML = '<div class="result-case-pills">';
      for (var p = 0; p < results.length; p++) {
        var passed = results[p].status === 'success' || results[p].status === 'accepted';
        pillsHTML += casePillHTML(results[p].tc_num, passed, p === 0);
      }
      pillsHTML += '</div>';
    }

    container.innerHTML = header + pillsHTML + '<div id="case-detail-panel"></div>';

    // Render first case detail
    if (results.length > 0) renderCaseDetail(results[0]);

    // Wire up pill clicks
    container.querySelectorAll('.result-case-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        container.querySelectorAll('.result-case-pill').forEach(function (b) { b.classList.remove('active'); });
        pill.classList.add('active');
        var idx = parseInt(pill.dataset.index, 10);
        if (results[idx]) renderCaseDetail(results[idx]);
      });
    });
  }

  function renderSubmitResult(data) {
    var container = document.getElementById('test-result-content');
    if (!container) return;

    var cls = statusClass(data.status);
    var label = statusLabel(data.status);
    var accepted = data.accepted || 0;
    var total = data.total || 0;
    var pct = total > 0 ? Math.round((accepted / total) * 100) : 0;

    // Highlight the offending source line for runtime / compile errors
    if (cls === 'runtime' || cls === 'compile') {
      var errMsg = '';
      var tcResultsErr = data.test_case_results || [];
      for (var ee = 0; ee < tcResultsErr.length; ee++) {
        if (tcResultsErr[ee].status !== 'accepted' && tcResultsErr[ee].status !== 'success') {
          errMsg = tcResultsErr[ee].actual || '';
          break;
        }
      }
      try { highlightErrorLines(errMsg); } catch (_) { /* Monaco not ready */ }
    } else {
      try { clearErrorHighlights(); } catch (_) {}
    }

    // Stats
    var runtimeStr = data.runtime_ms ? (parseFloat(data.runtime_ms)).toFixed(1) + ' ms' : '—';
    var memStr = formatMemoryKB(data.memory_kb) || '—';

    var statsRow = '<span>' + runtimeStr + '</span>' +
      '<span>' + memStr + '</span>' +
      '<span>' + accepted + '/' + total + ' passed</span>';

    var header = bannerHTML(cls, label, statsRow);

    // Progress bar
    header += '<div class="result-progress-bar"><div class="result-progress-fill" style="width:' + pct + '%"></div></div>';

    // Case pills
    var tcResults = data.test_case_results || [];
    var pillsHTML = '<div class="result-case-pills">';
    for (var i = 0; i < tcResults.length; i++) {
      var tc = tcResults[i];
      var passed = tc.status === 'accepted' || tc.status === 'success';
      pillsHTML += casePillHTML(tc.tc_num, passed, i === 0);
    }
    pillsHTML += '</div>';

    container.innerHTML = header + pillsHTML + '<div id="case-detail-panel"></div>';

    // Render first case detail
    if (tcResults.length > 0) renderCaseDetail(tcResults[0]);

    // Wire up pill clicks
    container.querySelectorAll('.result-case-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        container.querySelectorAll('.result-case-pill').forEach(function (b) { b.classList.remove('active'); });
        pill.classList.add('active');
        var idx = parseInt(pill.dataset.index, 10);
        if (tcResults[idx]) renderCaseDetail(tcResults[idx]);
      });
    });
  }

  function renderCaseDetail(tc) {
    var panel = document.getElementById('case-detail-panel');
    if (!panel) return;

    // If IO data is available (sample / run mode), show full cards
    if (tc.input !== undefined) {
      panel.innerHTML =
        ioCard('Input', tc.input) +
        ioCard('Output', tc.actual) +
        ioCard('Expected', tc.expected);
      panel.querySelectorAll('.copy-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var text = btn.dataset.copy;
          navigator.clipboard.writeText(text).then(function () {
            btn.textContent = 'Copied';
            setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
          });
        });
      });
    } else {
      // Hidden test case — compact summary only
      var passed = tc.status === 'accepted' || tc.status === 'success';
      panel.innerHTML = '<div class="result-case-summary ' + (passed ? 'case-pass' : 'case-fail') + '">' +
        'Case ' + tc.tc_num + ': ' + titleize(tc.status) +
        (tc.runtime_ms ? ' - ' + tc.runtime_ms + ' ms' : '') + '</div>';
    }
  }

  function ioCard(label, value) {
    var safe = escapeHtml(value || '');
    return '<div class="case-io-card">' +
      '<div class="case-io-card-header">' +
        '<span class="case-header-tag">' + label + '</span>' +
        '<button class="copy-btn" data-copy="' + escapeAttr(value || '') + '">Copy</button>' +
      '</div>' +
      '<div class="case-io-card-body">' + safe + '</div>' +
    '</div>';
  }

  /* ══════════════════════════
     SUBMISSION STATUS TAB
  ══════════════════════════ */
  const submissionTab = document.getElementById('editor-view-tab-submission');
  const submissionTabClose = document.getElementById('editor-view-tab-submission-close');
  const codeTab = document.getElementById('editor-view-tab-code');
  const codePanel = document.getElementById('editor-view-code');
  const submissionPanel = document.getElementById('editor-view-submission');
  const submissionStatusContent = document.getElementById('submission-status-content');

  function activateEditorView(view) {
    const isSubmission = view === 'submission';
    if (codeTab) codeTab.classList.toggle('active', !isSubmission);
    if (submissionTab) submissionTab.classList.toggle('active', isSubmission);
    if (codePanel) codePanel.classList.toggle('active', !isSubmission);
    if (submissionPanel) submissionPanel.classList.toggle('active', isSubmission);
    if (!isSubmission && window.editor) window.editor.layout();
  }

  if (codeTab) codeTab.addEventListener('click', function () { activateEditorView('code'); });
  if (submissionTab) submissionTab.addEventListener('click', function () { activateEditorView('submission'); });
  function closeSubmissionTab() {
    if (!submissionTab) return;
    submissionTab.hidden = true;
    submissionTab.style.display = '';
    activateEditorView('code');
  }
  if (submissionTabClose) {
    submissionTabClose.addEventListener('click', function (event) {
      event.stopPropagation();
      closeSubmissionTab();
    });
    submissionTabClose.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      event.stopPropagation();
      closeSubmissionTab();
    });
  }

  function submissionStatusClass(status) {
    return String(status || '').toLowerCase() === 'accepted' ? 'accepted' : 'failed';
  }

  function statusAcknowledgement(status) {
    const accepted = submissionStatusClass(status) === 'accepted';
    return '<span class="submission-ack ' + (accepted ? 'ack-success' : 'ack-failure') + '" aria-hidden="true"></span>';
  }

  function performanceGraph(data) {
    const samples = data.performance || [];
    const runtimeSamples = samples.map(function (item) { return parseFloat(item.runtime_ms); }).filter(Number.isFinite);
    const memorySamples = samples.map(function (item) { return parseFloat(item.memory_kb); }).filter(Number.isFinite);
    let mode = 'runtime';

    function graphMarkup(kind) {
      const values = kind === 'runtime' ? runtimeSamples : memorySamples;
      const current = parseFloat(kind === 'runtime' ? data.runtime_ms : data.memory_kb);
      if (!Number.isFinite(current) || values.length === 0) {
        return '<div class="performance-empty">Performance distribution is not available yet.</div>';
      }
      const all = values.concat([current]).sort(function (a, b) { return a - b; });
      const min = all[0];
      const max = all[all.length - 1] || min + 1;
      const bins = Array(10).fill(0);
      values.forEach(function (value) {
        const index = Math.min(9, Math.floor(((value - min) / Math.max(1, max - min)) * 10));
        bins[index] += 1;
      });
      const peak = Math.max.apply(null, bins.concat([1]));
      const position = ((current - min) / Math.max(1, max - min)) * 100;
      const percent = Math.round((values.filter(function (value) { return value >= current; }).length / values.length) * 100);
      return '<div class="performance-chart" data-graph-kind="' + kind + '">' +
        '<div class="performance-y-axis"><span>100%</span><span>50%</span><span>0%</span></div>' +
        '<div class="performance-plot"><div class="performance-grid"></div><div class="performance-bars">' + bins.map(function (count) { return '<i style="height:' + Math.max(3, (count / peak) * 100) + '%"></i>'; }).join('') + '</div><div class="performance-marker" style="left:' + position + '%"><b></b><span>' + current + (kind === 'runtime' ? ' ms' : ' KB') + '<small>' + percent + '% of submissions</small></span></div><div class="performance-x-axis"><span>' + min.toFixed(1) + '</span><span>' + ((min + max) / 2).toFixed(1) + '</span><span>' + max.toFixed(1) + '</span></div></div></div>';
    }

    function render() {
      const graph = document.getElementById('submission-performance-graph');
      if (graph) graph.innerHTML = graphMarkup(mode);
      document.querySelectorAll('[data-performance-mode]').forEach(function (button) { button.classList.toggle('active', button.dataset.performanceMode === mode); });
    }

    const controls = '<div class="performance-head"><div><span class="submission-section-label">Performance</span><h4>How your submission compares</h4></div><div class="performance-switch"><button type="button" data-performance-mode="runtime">Runtime</button><button type="button" data-performance-mode="memory">Memory</button></div></div><div id="submission-performance-graph"></div>';
    return { html: controls, init: function () { document.querySelectorAll('[data-performance-mode]').forEach(function (button) { button.addEventListener('click', function () { mode = button.dataset.performanceMode; render(); }); }); render(); } };
  }

  function renderSubmissionStatus(data) {
    if (!submissionStatusContent || !submissionTab) return;
    const status = submissionStatusClass(data.status);
    const accepted = Number(data.accepted || 0);
    const total = Number(data.total || (data.test_case_results || []).length);
    const results = data.test_case_results || data.results || [];
    const graph = status === 'accepted' ? performanceGraph(data) : null;
    const cases = results.map(function (result) {
      const passed = result.status === 'accepted' || result.status === 'success';
      const details = passed ? '' : '<div class="submission-case-details"><div><b>Input</b><pre>' + escapeHtml(result.input || '') + '</pre></div><div><b>Expected</b><pre>' + escapeHtml(result.expected || '') + '</pre></div><div><b>Actual</b><pre>' + escapeHtml(result.actual || '') + '</pre></div></div>';
      return '<div class="submission-case ' + (passed ? 'passed' : 'failed') + '"><button type="button" class="submission-case-row" data-case-toggle><span class="submission-case-indicator" aria-hidden="true"></span><span>Case ' + escapeHtml(result.tc_num) + '</span><strong>' + (passed ? 'Passed' : titleize(result.status)) + '</strong></button>' + details + '</div>';
    }).join('');
    submissionTab.hidden = false;
    submissionTab.style.display = '';
    submissionTab.className = 'editor-view-tab editor-view-tab-submission status-' + status + ' active';
    document.getElementById('editor-view-tab-submission-label').textContent = status === 'accepted' ? 'Accepted' : titleize(data.status);
    submissionStatusContent.innerHTML = '<div class="submission-status-header"><div><span class="submission-section-label">Submission status</span><h3>' + statusAcknowledgement(data.status) + (status === 'accepted' ? 'Accepted' : titleize(data.status)) + '</h3><p>' + accepted + ' / ' + total + ' test cases passed</p></div><span class="submission-status-time">' + escapeHtml(data.submitted_at || 'Just now') + '</span></div>' +
      '<div class="submission-meta"><span>Language<strong>' + escapeHtml(data.language || getSelectedLanguage()) + '</strong></span><span>Runtime<strong>' + escapeHtml(data.runtime_ms || '—') + ' ms</strong></span><span>Memory<strong>' + escapeHtml(data.memory_kb || '—') + ' KB</strong></span><span>Passed<strong>' + accepted + ' / ' + total + '</strong></span></div>' +
      (graph ? '<div class="submission-performance">' + graph.html + '</div>' : '') +
      '<div class="submission-section-label">Test cases</div><div class="submission-cases">' + cases + '</div>' +
      '<div class="submission-section-label submitted-code-label">Submitted code</div><pre class="submitted-code"><code>' + escapeHtml(data.code || getEditorCode()) + '</code></pre>';
    submissionStatusContent.querySelectorAll('[data-case-toggle]').forEach(function (button) { button.addEventListener('click', function () { const details = button.nextElementSibling; if (details) details.classList.toggle('open'); }); });
    if (graph) graph.init();
    activateEditorView('submission');
  }

  function renderSubmissionPending() {
    if (!submissionTab || !submissionStatusContent) return;
    submissionTab.hidden = false;
    submissionTab.style.display = '';
    submissionTab.className = 'editor-view-tab editor-view-tab-submission status-pending active';
    document.getElementById('editor-view-tab-submission-label').textContent = 'Pending';
    submissionStatusContent.innerHTML = '<div class="submission-pending"><span class="pending-loader"></span><div><strong>Pending</strong><span>Your submission is being evaluated.</span></div></div>';
    activateEditorView('submission');
  }

  /* ══════════════════════════
     RUN BUTTON
  ══════════════════════════ */
  const btnRun = document.getElementById('btn-run');
  const btnSubmit = document.getElementById('btn-submit');

  if (btnRun) {
    btnRun.addEventListener('click', async function () {
      const code = getEditorCode().trim();
      if (!code) { alert('Please write some code first.'); return; }

      setButtonLoading(btnRun, true);
      setButtonLoading(btnSubmit, true);
      switchToTestResultTab();

      const container = document.getElementById('test-result-content');
      if (container) container.innerHTML = skeletonHTML();

      try {
        const res = await fetch('/submissions/run/' + PROBLEM_SLUG + '/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN,
          },
          body: JSON.stringify({
            code: getEditorCode(),
            language: getSelectedLanguage(),
            custom_input: (document.getElementById('custom-input') || {}).value || '',
          }),
        });

        let data;
        try {
          data = await res.json();
        } catch (_) {
          // Server returned non-JSON (e.g. HTML error page) — show what we can
          const bodyText = await res.text().catch(function () { return ''; });
          const snippet = bodyText.substring(0, 200);
          if (container) container.innerHTML = '<div class="result-status-banner compile">' +
            '<div class="result-banner-title">Server error (' + res.status + ')</div>' +
            '<div class="result-stats-row"><span>' + escapeHtml(snippet) + '</span></div></div>';
          return;
        }

        if (data.error) {
          // Backend refused (e.g. forgot to read input) — show message
          if (container) {
            container.innerHTML = '<div class="result-status-banner runtime">' +
              '<div class="result-banner-title">' + escapeHtml(data.error) + '</div>' +
              '</div>';
          }
          return;
        }
        renderRunResult(data);
      } catch (err) {
        if (container) {
          container.innerHTML = '<div class="empty-state">Network error: ' + escapeHtml(err.message || err) + '</div>';
        }
      } finally {
        setButtonLoading(btnRun, false);
        setButtonLoading(btnSubmit, false);
      }
    });
  }

  /* ══════════════════════════
     SUBMIT BUTTON
  ══════════════════════════ */
  if (btnSubmit) {
    btnSubmit.addEventListener('click', async function () {
      if (!IS_AUTHENTICATED) { alert('Please login to submit code.'); return; }
      const code = getEditorCode().trim();
      if (!code) { alert('Please write some code first.'); return; }

      setButtonLoading(btnRun, true);
      setButtonLoading(btnSubmit, true);
      renderSubmissionPending();

      try {
        const res = await fetch('/submissions/submit/' + PROBLEM_SLUG + '/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': CSRF_TOKEN,
          },
          body: JSON.stringify({
            code: getEditorCode(),
            language: getSelectedLanguage(),
            elapsed_seconds: timerSeconds,
          }),
        });

        let data;
        try {
          data = await res.json();
        } catch (_) {
          const bodyText = await res.text().catch(function () { return ''; });
          const snippet = bodyText.substring(0, 200);
          renderSubmissionStatus({ status: 'compile_error', accepted: 0, total: 0, actual: snippet, code: getEditorCode(), language: getSelectedLanguage() });
          try { clearErrorHighlights(); } catch (_) {}
          const subTab = document.getElementById('tab-submissions');
          if (subTab) subTab.classList.remove('loaded');
          return;
        }

        if (data.error) {
          try { clearErrorHighlights(); } catch (_) {}
          renderSubmissionStatus({ status: 'runtime_error', accepted: 0, total: 0, actual: data.error, code: getEditorCode(), language: getSelectedLanguage() });
          const subTab = document.getElementById('tab-submissions');
          if (subTab) subTab.classList.remove('loaded');
          return;
        }
        renderSubmissionStatus(data);

        // Reset timer once the solution passes every test case
        if (data.status === 'accepted') {
          resetTimer();
        }

        // Invalidate submissions tab cache
        const subTab = document.getElementById('tab-submissions');
        if (subTab) subTab.classList.remove('loaded');
      } catch (err) {
        renderSubmissionStatus({ status: 'runtime_error', accepted: 0, total: 0, actual: err.message || err, code: getEditorCode(), language: getSelectedLanguage() });
      } finally {
        setButtonLoading(btnRun, false);
        setButtonLoading(btnSubmit, false);
      }
    });
  }

  /* ══════════════════════════
     PROBLEM LIST DRAWER
  ══════════════════════════ */
  const drawer = document.getElementById('problem-list-drawer');
  const backdrop = document.getElementById('drawer-backdrop');
  const drawerContent = document.getElementById('drawer-content');
  const btnProblemList = document.getElementById('btn-problem-list');
  const btnDrawerClose = document.getElementById('drawer-close');

  function openDrawer() {
    if (!drawer || !backdrop) return;
    if (!drawer.classList.contains('loaded')) {
      drawerContent.innerHTML = skeletonHTML();
      fetch('/problems/problems-panel/')
        .then(function (r) { return r.text(); })
        .then(function (html) {
          drawerContent.innerHTML = html;
          drawer.classList.add('loaded');
          initDrawerSearch();
        })
        .catch(function () {
          drawerContent.innerHTML = '<div class="empty-state">Failed to load problem list.</div>';
        });
    }
    drawer.classList.add('open');
    backdrop.classList.add('open');
  }

  function closeDrawer() {
    if (drawer) drawer.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
  }

  function initDrawerSearch() {
    const searchInput = document.getElementById('drawer-search-input');
    if (!searchInput) return;
    searchInput.addEventListener('input', function () {
      const q = this.value.toLowerCase();
      document.querySelectorAll('.problem-row').forEach(function (row) {
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }

  if (btnProblemList) btnProblemList.addEventListener('click', openDrawer);
  if (btnDrawerClose) btnDrawerClose.addEventListener('click', closeDrawer);
  if (backdrop) backdrop.addEventListener('click', closeDrawer);

  /* ══════════════════════════
     FULLSCREEN
  ══════════════════════════ */
  const btnFullscreen = document.getElementById('btn-fullscreen');
  const rightPanel = document.getElementById('right-panel');

  if (btnFullscreen && rightPanel) {
    btnFullscreen.addEventListener('click', function () {
      rightPanel.classList.toggle('fullscreen');
      if (window.editor) window.editor.layout();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && rightPanel.classList.contains('fullscreen')) {
        rightPanel.classList.remove('fullscreen');
        if (window.editor) window.editor.layout();
      }
    });
  }

  /* ══════════════════════════
     MONACO EDITOR SETUP
  ══════════════════════════ */
  let editorFontSize = 14;

  const btnZoomIn = document.getElementById('btn-zoom-in');
  const btnZoomOut = document.getElementById('btn-zoom-out');

  if (btnZoomIn) {
    btnZoomIn.addEventListener('click', function () {
      if (window.editor && editorFontSize < 28) {
        editorFontSize += 2;
        window.editor.updateOptions({ fontSize: editorFontSize, lineHeight: Math.round(editorFontSize * 1.55) });
      }
    });
  }

  if (btnZoomOut) {
    btnZoomOut.addEventListener('click', function () {
      if (window.editor && editorFontSize > 10) {
        editorFontSize -= 2;
        window.editor.updateOptions({ fontSize: editorFontSize, lineHeight: Math.round(editorFontSize * 1.55) });
      }
    });
  }

  if (typeof require !== 'undefined') {
    require.config({
      paths: {
        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs',
      },
    });

    require(['vs/editor/editor.main'], function () {
      // Define Premium Futuristic Black + Neon Green Theme (Dark Mode)
      // Typing code is crisp white/green, standard tokens have clear standard syntax colors
      monaco.editor.defineTheme('neonMatrix', {
        base: 'vs-dark',
        inherit: true,
        rules: [
          // Typing identifiers, plain text and variables: white (#FFFFFF)
          { token: '', foreground: 'FFFFFF' },
          { token: 'identifier', foreground: 'FFFFFF' },
          { token: 'variable', foreground: 'FFFFFF' },
          { token: 'variable.parameter', foreground: 'FFFFFF' },

          // Regular syntax colors:
          { token: 'keyword', foreground: '00FF88', fontStyle: 'bold' },
          { token: 'keyword.control', foreground: '00FF88', fontStyle: 'bold' },
          { token: 'keyword.operator', foreground: '22FFA0' },
          { token: 'operator', foreground: '00FF88' },
          { token: 'string', foreground: 'FDE047' },
          { token: 'string.escape', foreground: '38BDF8' },
          { token: 'comment', foreground: '64748B', fontStyle: 'italic' },
          { token: 'number', foreground: '38BDF8' },
          { token: 'type', foreground: '34D399', fontStyle: 'bold' },
          { token: 'type.identifier', foreground: '34D399' },
          { token: 'function', foreground: '2DD4BF' },
          { token: 'delimiter', foreground: '94A3B8' },
          { token: 'tag', foreground: '00FF88' },
          { token: 'attribute.name', foreground: '34D399' },
          { token: 'attribute.value', foreground: 'FDE047' },
        ],
        colors: {
          'editor.background':                '#070B09',
          'editor.foreground':                '#FFFFFF',
          'editor.lineHighlightBackground':   '#0E1712',
          'editor.lineHighlightBorder':       '#00FF8815',
          'editorLineNumber.foreground':      '#274233',
          'editorLineNumber.activeForeground':'#00FF88',
          'editorCursor.foreground':          '#00FF88',
          'editor.selectionBackground':       '#00FF8828',
          'editor.inactiveSelectionBackground':'#00FF8814',
          'editor.selectionHighlightBackground':'#00FF8818',
          'editor.findMatchBackground':       '#00FF8844',
          'editor.findMatchHighlightBackground':'#00FF8822',
          'editorGutter.background':          '#070B09',
          'editorIndentGuide.background':     '#13231B',
          'editorIndentGuide.activeBackground':'#00FF8835',
          'editorBracketMatch.background':    '#00FF8820',
          'editorBracketMatch.border':        '#00FF8866',
          'editorOverviewRuler.border':       '#00000000',
          'scrollbarSlider.background':       '#00FF8815',
          'scrollbarSlider.hoverBackground':  '#00FF8830',
          'scrollbarSlider.activeBackground': '#00FF8850',
        },
      });

      const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';

      // ── Auto-save: restore draft from localStorage ──
      var draftKey = 'draft_code_' + USER_ID + '_' + PROBLEM_SLUG;
      var draftLangKey = 'draft_lang_' + USER_ID + '_' + PROBLEM_SLUG;
      var savedCode = localStorage.getItem(draftKey) || '';
      var savedLang = localStorage.getItem(draftLangKey) || 'python';

      // Restore saved language in the <select> before editor init
      var langSelectInit = document.getElementById('language-select');
      if (langSelectInit && savedLang) {
        langSelectInit.value = savedLang;
      }

      var langMapInit = {
        'python': 'python', 'python3': 'python', 'java': 'java',
        'cpp': 'cpp', 'javascript': 'javascript', 'go': 'go', 'rust': 'rust',
      };

      window.editor = monaco.editor.create(
        document.getElementById('monaco-editor-container'),
        {
          value: savedCode,
          language: langMapInit[savedLang] || 'python',
          theme: currentTheme === 'dark' ? 'neonMatrix' : 'vs',
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          fontSize: editorFontSize,
          lineHeight: 22,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordWrap: 'off',
          lineNumbers: 'on',
          renderLineHighlight: 'all',
          cursorStyle: 'line',
          cursorBlinking: 'smooth',
          cursorSmoothCaretAnimation: 'on',
          tabSize: 4,
          insertSpaces: true,
          padding: { top: 12, bottom: 12 },
          roundedSelection: true,
          smoothScrolling: true,
        }
      );

      // Status bar tracking
      const saveStatus = document.getElementById('editor-save-status');
      const cursorPos = document.getElementById('editor-cursor-pos');

      // ── Auto-save: debounced write to localStorage ──
      var autoSaveTimer = null;
      function scheduleAutoSave() {
        if (autoSaveTimer) clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(function () {
          localStorage.setItem(draftKey, window.editor.getValue());
          if (saveStatus) {
            saveStatus.className = 'saved';
            var textSpan = saveStatus.querySelector('.status-text');
            if (textSpan) textSpan.textContent = 'Saved';
          }
        }, 500);
      }

      window.editor.onDidChangeModelContent(function () {
        if (saveStatus) {
          saveStatus.className = 'unsaved';
          const textSpan = saveStatus.querySelector('.status-text');
          if (textSpan) textSpan.textContent = 'Unsaved';
        }
        scheduleAutoSave();
      });

      window.editor.onDidChangeCursorPosition(function (e) {
        if (cursorPos) {
          cursorPos.textContent = 'Ln ' + e.position.lineNumber + ', Col ' + e.position.column;
        }
      });

      // Language switcher
      const langSelect = document.getElementById('language-select');
      if (langSelect) {
        const langMap = {
          'python':     'python',
          'python3':    'python',
          'java':       'java',
          'cpp':        'cpp',
          'javascript': 'javascript',
          'go':         'go',
          'rust':       'rust',
        };
        langSelect.addEventListener('change', function () {
          const monacoLang = langMap[this.value] || 'python';
          const model = window.editor.getModel();
          if (model) monaco.editor.setModelLanguage(model, monacoLang);
          // Persist language choice so it is restored next time
          localStorage.setItem(draftLangKey, this.value);
        });
      }
    });
  }

  /* ══════════════════════════
     HISTORICAL SUBMISSION DETAILS
  ══════════════════════════ */
  function submissionStatusLabel(status) {
    return titleize(status || 'Unknown');
  }

  function submissionDetailHTML(data) {
    const results = data.results || [];
    const accepted = results.filter(function (result) {
      return result.status === 'accepted' || result.status === 'success';
    }).length;
    const statusClass = data.status === 'accepted' ? 'accepted' : 'failed';
    const resultRows = results.map(function (result, index) {
      const passed = result.status === 'accepted' || result.status === 'success';
      const details = passed ? '' :
        '<div class="submission-detail-case-body">' +
        (result.input !== undefined ? '<div><b>Input</b><pre>' + escapeHtml(result.input) + '</pre></div>' : '') +
        (result.expected !== undefined ? '<div><b>Expected</b><pre>' + escapeHtml(result.expected) + '</pre></div>' : '') +
        (result.actual !== undefined ? '<div><b>Actual</b><pre>' + escapeHtml(result.actual) + '</pre></div>' : '') +
        '</div>';
      return '<div class="submission-detail-case ' + (passed ? 'passed' : 'failed') + '">' +
        '<button type="button" class="submission-detail-case-head" data-case-toggle="' + index + '">' +
        '<span>' + (passed ? '✓' : '✕') + ' Case ' + escapeHtml(result.tc_num) + '</span>' +
        '<span>' + submissionStatusLabel(result.status) + '</span></button>' + details + '</div>';
    }).join('');

    return '<div class="submission-detail-panel">' +
      '<div class="submission-detail-header"><div><button type="button" class="submission-detail-back" data-submission-back>← Back to submissions</button>' +
      '<h3>Submission #' + escapeHtml(data.submission_id) + '</h3></div><span class="submission-detail-status ' + statusClass + '">' + submissionStatusLabel(data.status) + '</span></div>' +
      '<div class="submission-detail-meta"><span>Language<strong>' + escapeHtml(data.language || '—') + '</strong></span>' +
      '<span>Runtime<strong>' + escapeHtml(data.runtime_ms || '—') + ' ms</strong></span>' +
      '<span>Memory<strong>' + escapeHtml(data.memory_kb || '—') + ' KB</strong></span>' +
      '<span>Passed<strong>' + accepted + ' / ' + results.length + '</strong></span>' +
      '<span>Submitted<strong>' + escapeHtml(data.submitted_at || '—') + '</strong></span></div>' +
      '<div class="submission-detail-code"><div class="submission-detail-section-title">Submitted code</div><pre><code>' + escapeHtml(data.code || '') + '</code></pre></div>' +
      '<div class="submission-detail-section-title">Test cases</div><div class="submission-detail-cases">' + (resultRows || '<div class="empty-state">No testcase results available.</div>') + '</div></div>';
  }

  function loadHistoricalSubmission(row) {
    const url = row && row.dataset.detailUrl;
    if (!url) return;
    renderSubmissionPending();
    fetch(url)
      .then(function (response) {
        if (!response.ok) throw new Error('Could not load this submission.');
        return response.json();
      })
      .then(function (data) {
        renderSubmissionStatus({
          submission_id: data.submission_id,
          code: data.code,
          status: data.status,
          language: data.language,
          runtime_ms: data.runtime_ms,
          memory_kb: data.memory_kb,
          submitted_at: data.submitted_at,
          performance: data.performance,
          results: data.results,
          accepted: (data.results || []).filter(function (result) { return result.status === 'accepted'; }).length,
          total: (data.results || []).length,
        });
      })
      .catch(function (error) {
        renderSubmissionStatus({ status: 'runtime_error', accepted: 0, total: 0, actual: error.message, code: '', language: '' });
      });
  }

  const submissionsTab = document.getElementById('tab-submissions');
  if (submissionsTab) {
    submissionsTab.addEventListener('click', function (event) {
      const row = event.target.closest('[data-submission-trigger]');
      if (row) loadHistoricalSubmission(row);
    });
    submissionsTab.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      const row = event.target.closest('[data-submission-trigger]');
      if (!row) return;
      event.preventDefault();
      loadHistoricalSubmission(row);
    });
  }

  /* ══════════════════════════
     EDITOR SAVE STATUS INIT
  ══════════════════════════ */
  (function () {
    const saveStatus = document.getElementById('editor-save-status');
    if (saveStatus) {
      saveStatus.className = 'saved';
      const textSpan = saveStatus.querySelector('.status-text');
      if (textSpan) textSpan.textContent = 'Saved';
    }
  })();

})();
