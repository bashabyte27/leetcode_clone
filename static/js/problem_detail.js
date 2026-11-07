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
    var label = btn.querySelector('.btn-label');
    if (label && !btn.dataset.idleLabel) btn.dataset.idleLabel = label.textContent;
    if (loading) {
      btn.classList.add('btn-loading');
      btn.disabled = true;
      if (label && btn.dataset.loadingLabel && btn.id === 'btn-' + document.body.dataset.busy) label.textContent = btn.dataset.loadingLabel;
    } else {
      btn.classList.remove('btn-loading');
      btn.disabled = false;
      if (label && btn.dataset.idleLabel) label.textContent = btn.dataset.idleLabel;
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

  function normalizeCaseText(text) {
    return String(text || '')
      .replace(/\\r\\n/g, '\n')
      .replace(/\\n/g, '\n')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n');
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
    if (btn) btn.innerHTML = saved === 'dark' ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';
  })();

  const btnTheme = document.getElementById('btn-theme-toggle');
  if (btnTheme) {
    btnTheme.addEventListener('click', function () {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('editorTheme', next);
      btnTheme.innerHTML = next === 'dark' ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon-stars"></i>';

      if (window.monaco && window.editor) {
        monaco.editor.setTheme(next === 'dark' ? 'neonMatrix' : 'bbLight');
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

  function moveInk(bar) {
    if (!bar) return;
    var ink = bar.querySelector('.tabs-ink');
    var active = bar.querySelector('.active');
    if (!ink || !active) return;
    ink.style.width = active.offsetWidth + 'px';
    ink.style.transform = 'translateX(' + active.offsetLeft + 'px)';
  }
  function syncInks() { document.querySelectorAll('.tabs-bar, .testcase-tabs-bar').forEach(moveInk); }
  document.addEventListener('click', function (e) {
    if (e.target.closest('.tab-btn, .testcase-tab-btn')) requestAnimationFrame(syncInks);
  });
  window.addEventListener('resize', syncInks);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(syncInks);
  requestAnimationFrame(syncInks);

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
    requestAnimationFrame(function () { moveInk(document.querySelector('.testcase-tabs-bar')); });
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
    cases.forEach(function (c) { c.input_data = normalizeCaseText(c.input_data); });

    if (cases.length === 0) {
      cases = [{ order_num: 1, input_data: customInput.value || '', expected_output: '' }];
    }

    /* ── One custom test case: the student's own input, remembered per problem ── */
    const customKey = 'custom_case_' + USER_ID + '_' + PROBLEM_SLUG;
    const addCustomBtn = document.getElementById('btn-add-custom-case');
    function readCustom() { try { return localStorage.getItem(customKey); } catch (_) { return null; } }
    function writeCustom(v) { try { v === null ? localStorage.removeItem(customKey) : localStorage.setItem(customKey, v); } catch (_) {} }

    let activeIdx = 0;
    window.__bbCases = cases;  // read by the Run button (students may edit inputs)

    function customIndex() {
      return cases.findIndex(function (c) { return c.custom; });
    }

    function syncActive() {
      if (cases[activeIdx]) {
        cases[activeIdx].input_data = customInput.value;
        if (cases[activeIdx].custom) writeCustom(customInput.value);
      }
    }

    function selectCase(idx) {
      if (!cases[idx]) return;
      activeIdx = idx;
      pillsRow.querySelectorAll('.case-pill').forEach(function (p) {
        p.classList.toggle('active', parseInt(p.dataset.caseIndex, 10) === idx);
      });
      const curCase = cases[idx];
      customInput.value = curCase.input_data || '';
      customInput.placeholder = curCase.custom
        ? 'Type your own input here, exactly as the program would read it...'
        : 'Enter custom input here...';
      if (expectedOutputEl) {
        expectedOutputEl.textContent = curCase.custom ? '' : normalizeCaseText(curCase.expected_output);
      }
      if (expectedCard) {
        expectedCard.style.display = (!curCase.custom && curCase.expected_output) ? 'block' : 'none';
      }
      if (curCase.custom) customInput.focus();
    }

    function renderCustomPill() {
      const old = pillsRow.querySelector('.case-pill-custom');
      if (old) old.remove();
      const idx = customIndex();
      if (addCustomBtn) addCustomBtn.hidden = idx >= 0;
      if (idx < 0) return;
      const pill = document.createElement('button');
      pill.type = 'button';
      pill.className = 'case-pill case-pill-custom';
      pill.dataset.caseIndex = String(idx);
      pill.innerHTML = '<i class="bi bi-pencil-square"></i> Custom' +
        '<span class="case-pill-remove" role="button" aria-label="Remove custom case" title="Remove custom case">&times;</span>';
      if (addCustomBtn) pillsRow.insertBefore(pill, addCustomBtn); else pillsRow.appendChild(pill);
    }

    function addCustomCase(initial) {
      if (customIndex() >= 0) { selectCase(customIndex()); return; }
      syncActive();
      cases.push({
        order_num: cases.length + 1, label: 'Custom', custom: true,
        input_data: initial != null ? initial : (cases[0] ? cases[0].input_data : ''), expected_output: '',
      });
      writeCustom(cases[cases.length - 1].input_data);
      renderCustomPill();
      selectCase(cases.length - 1);
    }

    function removeCustomCase() {
      const idx = customIndex();
      if (idx < 0) return;
      const wasActive = activeIdx === idx;
      cases.splice(idx, 1);  // the custom case is always last, so other indexes stay valid
      writeCustom(null);
      renderCustomPill();
      selectCase(wasActive ? 0 : activeIdx);
    }

    customInput.addEventListener('input', syncActive);

    pillsRow.addEventListener('click', function (e) {
      if (e.target.closest('.case-pill-remove')) { e.stopPropagation(); removeCustomCase(); return; }
      if (e.target.closest('#btn-add-custom-case')) { addCustomCase(); return; }
      const pill = e.target.closest('.case-pill');
      if (!pill) return;
      const idx = parseInt(pill.dataset.caseIndex, 10);
      if (isNaN(idx) || idx === activeIdx) return;
      syncActive();
      selectCase(idx);
    });

    // Bring back the student's saved custom input
    const savedCustom = readCustom();
    if (savedCustom !== null) {
      cases.push({ order_num: cases.length + 1, label: 'Custom', custom: true, input_data: savedCustom, expected_output: '' });
      renderCustomPill();
    }

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
            overviewRuler: { color: '#ef4444', position: monaco.editor.OverviewRulerLane.Left },
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
  var REDUCED_MOTION = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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

  var VERDICT_ICON = {
    accepted: 'bi-check-lg', wrong: 'bi-x-lg', tle: 'bi-hourglass-bottom',
    runtime: 'bi-exclamation-triangle', compile: 'bi-bug', failed: 'bi-x-lg'
  };

  function isPass(status) {
    var s = String(status || '').toLowerCase();
    return s === 'success' || s === 'accepted';
  }

  function formatMemoryKB(kb) {
    if (!kb && kb !== 0) return null;
    var val = parseFloat(kb);
    if (isNaN(val)) return null;
    if (val >= 1024) return (val / 1024).toFixed(1) + ' MB';
    return Math.round(val) + ' KB';
  }

  function formatMs(ms) {
    var v = parseFloat(ms);
    if (!isFinite(v)) return '—';
    return (v >= 100 ? Math.round(v) : v.toFixed(1).replace(/\.0$/, '')) + ' ms';
  }

  function languageLabel() {
    var sel = document.getElementById('language-select');
    return sel && sel.selectedOptions && sel.selectedOptions[0] ? sel.selectedOptions[0].textContent : getSelectedLanguage();
  }

  /* ── Celebration burst (accepted verdicts) ── */
  function celebrate(host) {
    if (REDUCED_MOTION || !host) return;
    var burst = document.createElement('div');
    burst.className = 'confetti';
    var colors = ['var(--brand)', 'var(--accent)', '#7cc4ff', '#c3a6ff', '#ffe58a'];
    for (var i = 0; i < 28; i++) {
      var piece = document.createElement('i');
      var angle = (Math.PI * 2 * i) / 28 + Math.random() * 0.4;
      var dist = 70 + Math.random() * 110;
      piece.style.setProperty('--tx', Math.cos(angle) * dist + 'px');
      piece.style.setProperty('--ty', Math.sin(angle) * dist - 40 + 'px');
      piece.style.setProperty('--r', Math.round(Math.random() * 540 - 270) + 'deg');
      piece.style.setProperty('--d', Math.round(Math.random() * 120) + 'ms');
      piece.style.background = colors[i % colors.length];
      burst.appendChild(piece);
    }
    host.appendChild(burst);
    setTimeout(function () { if (burst.parentNode) burst.parentNode.removeChild(burst); }, 1600);
  }

  /* ══════════════════════════
     JUDGE PIPELINE ANIMATION
     Purely visual: real results always come from the server response.
  ══════════════════════════ */
  var JUDGE_STAGES = {
    run: [
      ['Packaging code', 'bi-box-seam'],
      ['Compiling', 'bi-gear'],
      ['Running sample cases', 'bi-play-circle'],
      ['Comparing output', 'bi-check2-square']
    ],
    submit: [
      ['Queued on judge', 'bi-hourglass-split'],
      ['Compiling', 'bi-gear'],
      ['Running hidden tests', 'bi-shield-lock'],
      ['Scoring & ranking', 'bi-graph-up-arrow']
    ]
  };
  var STAGE_AT = [0, 650, 1500, 2900];

  function judgeSceneHTML(kind) {
    var stages = JUDGE_STAGES[kind];
    var sampleCount = document.querySelectorAll('#testcase-pills-row .case-pill').length || 1;
    var cells = '';
    var n = kind === 'submit' ? 40 : sampleCount;
    for (var i = 0; i < n; i++) cells += '<i style="--k:' + i + '"></i>';
    return '<div class="judge judge-' + kind + '" data-judge>' +
      '<div class="judge-head">' +
        '<div class="judge-orb" aria-hidden="true"><span class="orb-ring"></span><span class="orb-ring r2"></span><span class="orb-sweep"></span><i class="bi bi-cpu"></i></div>' +
        '<div class="judge-copy">' +
          '<strong class="judge-title">' + (kind === 'submit' ? 'Judging your submission' : 'Running your code') + '</strong>' +
          '<span class="judge-sub"><b class="judge-elapsed">0.0s</b><span>·</span>' + escapeHtml(languageLabel()) +
          '<span>·</span>' + (kind === 'submit' ? 'all test cases' : sampleCount + ' sample case' + (sampleCount === 1 ? '' : 's')) + '</span>' +
        '</div>' +
        '<span class="judge-pct">0%</span>' +
      '</div>' +
      '<div class="judge-track"><i class="judge-fill"></i></div>' +
      '<ol class="judge-stages">' + stages.map(function (s, i) {
        return '<li data-stage="' + i + '"><span class="st-dot"><i class="bi ' + s[1] + '"></i></span><span class="st-label">' + s[0] + '</span><span class="st-state"></span></li>';
      }).join('') + '</ol>' +
      '<div class="judge-cells' + (kind === 'run' ? ' judge-cells-run' : '') + '" aria-hidden="true">' + cells + '</div>' +
      '<div class="judge-log" aria-live="polite"></div>' +
    '</div>';
  }

  var JUDGE_LOG = {
    run: ['$ bashabyte run --lang ', '› compiling…', '› executing sample cases', '› diffing stdout against expected'],
    submit: ['$ bashabyte submit --lang ', '› build ok, sandbox ready', '› executing hidden tests in isolation', '› scoring runtime & memory']
  };

  function startJudgeScene(host, kind) {
    if (!host) return;
    host.innerHTML = judgeSceneHTML(kind);
    var scene = host.querySelector('[data-judge]');
    var stages = scene.querySelectorAll('.judge-stages li');
    var fill = scene.querySelector('.judge-fill');
    var pct = scene.querySelector('.judge-pct');
    var elapsed = scene.querySelector('.judge-elapsed');
    var log = scene.querySelector('.judge-log');
    var t0 = performance.now();
    var current = -1;
    scene._timers = [];

    function setStage(i) {
      if (!scene.isConnected) return;
      for (var k = 0; k < stages.length; k++) {
        stages[k].classList.toggle('is-done', k < i);
        stages[k].classList.toggle('is-active', k === i);
      }
      current = i;
      var line = document.createElement('div');
      line.textContent = JUDGE_LOG[kind][i] + (i === 0 ? getSelectedLanguage() : '');
      log.appendChild(line);
      while (log.children.length > 3) log.removeChild(log.firstChild);
    }
    STAGE_AT.forEach(function (at, i) {
      scene._timers.push(setTimeout(function () { setStage(i); }, REDUCED_MOTION ? 0 : at));
    });

    (function tick(now) {
      if (!scene.isConnected || scene.classList.contains('is-finished')) return;
      var t = now - t0;
      var p = 94 * (1 - Math.exp(-t / 2600));
      fill.style.transform = 'scaleX(' + (p / 100).toFixed(4) + ')';
      pct.textContent = Math.floor(p) + '%';
      elapsed.textContent = (t / 1000).toFixed(1) + 's';
      requestAnimationFrame(tick);
    })(t0);
  }

  // Completes the animation, then calls done(). Falls through immediately when no scene is showing.
  function finishJudgeScene(host, ok, done) {
    var scene = host && host.querySelector('[data-judge]');
    if (!scene || REDUCED_MOTION) { done(); return; }
    (scene._timers || []).forEach(clearTimeout);
    scene.classList.add('is-finished', ok ? 'is-ok' : 'is-fail');
    scene.querySelectorAll('.judge-stages li').forEach(function (li) { li.classList.remove('is-active'); li.classList.add('is-done'); });
    scene.querySelector('.judge-fill').style.transform = 'scaleX(1)';
    scene.querySelector('.judge-pct').textContent = '100%';
    setTimeout(done, 520);
  }

  /* ── Banner HTML (also used by error paths in the run handler) ── */
  function bannerHTML(cls, label, statsRow) {
    return '<div class="result-status-banner ' + cls + '">' +
      '<div class="vb-icon"><i class="bi ' + (VERDICT_ICON[cls] || 'bi-exclamation-triangle') + '"></i></div>' +
      '<div class="vb-copy"><div class="result-banner-title">' + label + '</div>' +
      (statsRow ? '<div class="result-stats-row">' + statsRow + '</div>' : '') +
      '</div></div>';
  }

  function casePillHTML(num, passed, active, runtime, label) {
    return '<button type="button" class="result-case-pill ' +
      (passed ? 'pill-passed' : 'pill-failed') +
      (active ? ' active' : '') +
      '" data-index="' + (num - 1) + '"><i class="bi ' + (passed ? 'bi-check-circle-fill' : 'bi-x-circle-fill') + '"></i>' +
      (label ? escapeHtml(label) : 'Case ' + num) +
      (runtime ? '<small>' + formatMs(runtime) + '</small>' : '') + '</button>';
  }

  function errorConsoleHTML(cls, message) {
    if (!message) return '';
    return '<div class="error-console ' + cls + '">' +
      '<div class="ec-head"><span class="ec-dots"><i></i><i></i><i></i></span><span>' + (cls === 'compile' ? 'Compiler output' : 'stderr') + '</span></div>' +
      '<pre>' + escapeHtml(message) + '</pre></div>';
  }

  function renderRunResult(response) {
    var container = document.getElementById('test-result-content');
    if (!container) return;

    var results = response.test_case_results || [];

    if (results.length === 0) {
      container.innerHTML = '<div class="empty-state">No test case results found.</div>';
      return;
    }

    var overallStatus = 'success';
    var errMsg = '';
    for (var k = 0; k < results.length; k++) {
      if (!isPass(results[k].status)) {
        overallStatus = results[k].status;
        errMsg = results[k].actual || '';
        break;
      }
    }
    var cls = statusClass(overallStatus);
    var label = statusLabel(overallStatus);

    if (cls === 'runtime' || cls === 'compile') {
      try { highlightErrorLines(errMsg); } catch (_) { /* Monaco not ready */ }
    } else {
      try { clearErrorHighlights(); } catch (_) {}
    }

    var totalMs = 0;
    var passedCount = 0;
    for (var j = 0; j < results.length; j++) {
      totalMs += parseFloat(results[j].runtime_ms) || 0;
      if (isPass(results[j].status)) passedCount++;
    }

    var sub = cls === 'accepted'
      ? 'All sample cases passed. Submit to run the hidden tests.'
      : passedCount + ' of ' + results.length + ' sample cases passed';
    var header = '<div class="verdict-banner v-' + cls + '">' +
      '<div class="vb-icon"><i class="bi ' + VERDICT_ICON[cls] + '"></i></div>' +
      '<div class="vb-copy"><h3>' + escapeHtml(label) + '</h3><p>' + sub + '</p></div>' +
      '<div class="vb-stats"><span><b>' + passedCount + '</b>/' + results.length + '<small>passed</small></span>' +
      '<span><b>' + formatMs(totalMs).replace(' ms', '') + '</b>ms<small>total runtime</small></span></div>' +
    '</div>';

    var selectedCase = response.selected_case ? parseInt(response.selected_case, 10) : null;
    var activeResultIndex = results.findIndex(function (result) {
      return selectedCase !== null && result.tc_num === selectedCase;
    });
    if (activeResultIndex < 0) {
      // Open the first failing case so the problem is visible immediately
      activeResultIndex = results.findIndex(function (r) { return !isPass(r.status); });
      if (activeResultIndex < 0) activeResultIndex = 0;
    }

    var pillsHTML = '<div class="result-case-pills">';
    for (var p = 0; p < results.length; p++) {
      pillsHTML += casePillHTML(results[p].tc_num, isPass(results[p].status), p === activeResultIndex, results[p].runtime_ms, results[p].label);
    }
    pillsHTML += '</div>';

    var consoleHTML = (cls === 'compile' || cls === 'runtime') ? errorConsoleHTML(cls, errMsg) : '';

    container.innerHTML = '<div class="rr rr-enter">' + header + consoleHTML + pillsHTML + '<div id="case-detail-panel"></div></div>';
    renderCaseDetail(results[activeResultIndex]);
    if (cls === 'accepted') celebrate(container.querySelector('.verdict-banner'));

    container.querySelectorAll('.result-case-pill').forEach(function (pill, idx) {
      pill.addEventListener('click', function () {
        container.querySelectorAll('.result-case-pill').forEach(function (b) { b.classList.remove('active'); });
        pill.classList.add('active');
        if (results[idx]) renderCaseDetail(results[idx]);
      });
    });
  }

  function renderSubmitResult(data) {
    // Kept for compatibility; submissions render in the editor's status view.
    var container = document.getElementById('test-result-content');
    if (!container) return;
    var cls = statusClass(data.status);
    var accepted = data.accepted || 0;
    var total = data.total || 0;
    var tcResults = data.test_case_results || [];
    var statsRow = '<span>' + formatMs(data.runtime_ms) + '</span><span>' + (formatMemoryKB(data.memory_kb) || '—') + '</span><span>' + accepted + '/' + total + ' passed</span>';
    var pillsHTML = '<div class="result-case-pills">' + tcResults.map(function (tc, i) {
      return casePillHTML(tc.tc_num, isPass(tc.status), i === 0, tc.runtime_ms);
    }).join('') + '</div>';
    container.innerHTML = bannerHTML(cls, statusLabel(data.status), statsRow) + pillsHTML + '<div id="case-detail-panel"></div>';
    if (tcResults.length > 0) renderCaseDetail(tcResults[0]);
    container.querySelectorAll('.result-case-pill').forEach(function (pill, idx) {
      pill.addEventListener('click', function () {
        container.querySelectorAll('.result-case-pill').forEach(function (b) { b.classList.remove('active'); });
        pill.classList.add('active');
        if (tcResults[idx]) renderCaseDetail(tcResults[idx]);
      });
    });
  }

  function renderCaseDetail(tc) {
    var panel = document.getElementById('case-detail-panel');
    if (!panel || !tc) return;

    if (tc.input !== undefined) {
      var actual = normalizeCaseText(tc.actual);
      var expected = normalizeCaseText(tc.expected);
      var passed = isPass(tc.status);
      var cls = statusClass(tc.status);
      var showDiff = !passed && cls === 'wrong';
      panel.innerHTML =
        ioCard('Input', normalizeCaseText(tc.input)) +
        ioCard('Output', actual, showDiff ? diffLines(actual, expected) : null, tc.custom ? '' : (passed ? 'io-pass' : 'io-fail')) +
        (tc.custom
          ? '<div class="empty-state">Custom input: there is no expected answer to compare with, so check the output yourself.</div>'
          : ioCard('Expected', expected));
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
      var ok = isPass(tc.status);
      panel.innerHTML = '<div class="result-case-summary ' + (ok ? 'case-pass' : 'case-fail') + '">' +
        '<i class="bi ' + (ok ? 'bi-shield-check' : 'bi-shield-x') + '"></i>' +
        '<div><b>Case ' + tc.tc_num + ' · ' + titleize(tc.status) + '</b><span>Hidden test case' +
        (tc.runtime_ms ? ' · ' + formatMs(tc.runtime_ms) : '') + '</span></div></div>';
    }
  }

  // Line-by-line diff of actual vs expected output (marks differing lines)
  function diffLines(actual, expected) {
    var a = String(actual || '').split('\n');
    var e = String(expected || '').split('\n');
    return a.map(function (line, i) {
      var bad = line.replace(/\s+$/, '') !== String(e[i] === undefined ? '\u0000' : e[i]).replace(/\s+$/, '');
      return '<span class="diff-line' + (bad ? ' is-bad' : '') + '">' + (escapeHtml(line) || '&nbsp;') + '</span>';
    }).join('');
  }

  function ioCard(label, value, html, extraClass) {
    var safe = html || escapeHtml(value || '');
    return '<div class="case-io-card ' + (extraClass || '') + '">' +
      '<div class="case-io-card-header">' +
        '<span class="case-header-tag">' + label + '</span>' +
        (extraClass === 'io-fail' ? '<span class="io-flag"><i class="bi bi-x-circle"></i> Differs from expected</span>' : '') +
        (extraClass === 'io-pass' ? '<span class="io-flag ok"><i class="bi bi-check-circle"></i> Matches</span>' : '') +
        '<button type="button" class="copy-btn" data-copy="' + escapeAttr(value || '') + '">Copy</button>' +
      '</div>' +
      '<div class="case-io-card-body">' + (safe || '<span class="io-empty">(empty)</span>') + '</div>' +
    '</div>';
  }

  /* ══════════════════════════
     COMPLEXITY ESTIMATOR
     A static, heuristic read of the code's structure (loops, recursion,
     sorting, allocations). It is labelled as an estimate in the UI.
  ══════════════════════════ */
  var CX_ORDER = ['O(1)', 'O(log n)', 'O(n)', 'O(n log n)', 'O(n²)', 'O(n³)', 'O(2ⁿ)'];
  var CX_NAME = ['Constant', 'Logarithmic', 'Linear', 'Linearithmic', 'Quadratic', 'Cubic', 'Exponential'];

  function cxRankOf(str) {
    var s = String(str || '').toLowerCase().replace(/\s+/g, '').replace(/\^2|\*\*2/g, '²').replace(/\^3|\*\*3/g, '³').replace(/\^n|\*\*n/g, 'ⁿ').replace(/\*/g, '');
    var table = { 'o(1)': 0, 'o(logn)': 1, 'o(n)': 2, 'o(nlogn)': 3, 'o(n²)': 4, 'o(n³)': 5, 'o(2ⁿ)': 6 };
    return table.hasOwnProperty(s) ? table[s] : -1;
  }

  function stripCode(code, lang) {
    var c = String(code || '');
    c = c.replace(/("""|''')[\s\S]*?\1/g, '""');
    c = c.replace(/"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`/g, '""');
    if (/python/i.test(lang)) c = c.replace(/#.*$/gm, '');
    else c = c.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    return c;
  }

  function estimateComplexity(code, lang) {
    var src = stripCode(code, lang);
    var isPy = /python/i.test(lang) || (/\bdef\b|\belif\b/.test(src) && !/[{};]\s*$/m.test(src));
    var lines = src.split('\n');
    var signals = [];
    var maxDepth = 0;
    var logLoops = 0;

    if (isPy) {
      var stack = []; // indents of open loops
      lines.forEach(function (raw) {
        if (!raw.trim()) return;
        var indent = raw.match(/^\s*/)[0].replace(/\t/g, '    ').length;
        while (stack.length && indent <= stack[stack.length - 1]) stack.pop();
        var t = raw.trim();
        var compFor = (t.match(/\bfor\b[^:]*\bin\b/g) || []).length;
        if (/^(for|while)\b/.test(t)) {
          stack.push(indent);
          maxDepth = Math.max(maxDepth, stack.length + Math.max(0, compFor - 1));
        } else if (compFor) {
          maxDepth = Math.max(maxDepth, stack.length + compFor);
        }
      });
    } else {
      var depth = 0;
      var braceStack = [];
      var pendingLoop = false;
      var tokens = src.match(/\b(for|while)\b|[{}]|;/g) || [];
      tokens.forEach(function (tok) {
        if (tok === 'for' || tok === 'while') { pendingLoop = true; return; }
        if (tok === '{') { braceStack.push(pendingLoop); if (pendingLoop) depth++; pendingLoop = false; maxDepth = Math.max(maxDepth, depth); return; }
        if (tok === '}') { if (braceStack.pop()) depth--; return; }
        if (tok === ';' && pendingLoop) { maxDepth = Math.max(maxDepth, depth + 1); }
      });
      // single-statement loops without braces: count once at least
      if (!maxDepth && /\b(for|while)\b/.test(src)) maxDepth = 1;
    }

    if (/(\/\/=|\/=|>>=|\*=)\s*2\b|>>\s*1\b|\bmid\b|\blo\b.*\bhi\b|\bleft\b.*\bright\b.*\/\s*2/.test(src)) {
      logLoops = 1;
      signals.push({ icon: 'bi-scissors', text: 'Search space is halved each step (logarithmic loop)' });
    }
    var sorts = /\bsorted\s*\(|\.sort\s*\(|Arrays\.sort|Collections\.sort|\bsort\s*\(|sort\.(Ints|Slice)/.test(src);
    if (sorts) signals.push({ icon: 'bi-sort-down', text: 'Sorting call detected (n log n)' });

    // Recursion: count calls to a function *inside its own body*
    var fns = [];
    var m;
    if (isPy) {
      lines.forEach(function (raw, i) {
        var dm = raw.match(/^(\s*)def\s+([A-Za-z_]\w*)/);
        if (!dm) return;
        var ind = dm[1].replace(/\t/g, '    ').length;
        var body = [];
        for (var j = i + 1; j < lines.length; j++) {
          var l = lines[j];
          if (l.trim() && l.match(/^\s*/)[0].replace(/\t/g, '    ').length <= ind) break;
          body.push(l);
        }
        fns.push({ name: dm[2], body: body.join('\n') });
      });
    } else {
      var fnRe = /\b([A-Za-z_]\w*)\s*\([^;{}()]*(?:\([^()]*\)[^;{}()]*)*\)\s*(?:const\s*|throws\s+[\w.,\s]+)?\{/g;
      while ((m = fnRe.exec(src))) {
        if (/^(if|for|while|switch|catch|main|return|else)$/.test(m[1])) continue;
        var start = m.index + m[0].length, d = 1, k = start;
        while (k < src.length && d > 0) { if (src[k] === '{') d++; else if (src[k] === '}') d--; k++; }
        fns.push({ name: m[1], body: src.slice(start, k - 1) });
      }
    }
    var recursion = 0;
    fns.forEach(function (fn) {
      var calls = (fn.body.match(new RegExp('\\b' + fn.name + '\\s*\\(', 'g')) || []).length;
      if (calls >= 2) recursion = Math.max(recursion, 2);
      else if (calls === 1) recursion = Math.max(recursion, 1);
    });
    if (recursion === 2) signals.push({ icon: 'bi-diagram-3', text: 'Branching recursion (the function calls itself more than once)' });
    else if (recursion === 1) signals.push({ icon: 'bi-arrow-return-left', text: 'Linear recursion detected' });

    if (maxDepth === 1) signals.unshift({ icon: 'bi-arrow-repeat', text: 'One loop over the input' });
    else if (maxDepth > 1) signals.unshift({ icon: 'bi-layers', text: maxDepth + ' nested loops' });

    var timeRank = 0;
    if (maxDepth > 0) {
      timeRank = maxDepth === 1 ? (logLoops ? 1 : 2) : maxDepth === 2 ? (logLoops ? 3 : 4) : 5;
    }
    if (sorts) timeRank = Math.max(timeRank, 3);
    if (recursion === 2) timeRank = 6;
    else if (recursion === 1) timeRank = Math.max(timeRank, logLoops ? 1 : 2);

    // Space
    var spaceSignals = [];
    var spaceRank = 0;
    var grid = /\[\s*\[|new\s+\w+\s*\[[^\]]+\]\s*\[|vector\s*<\s*vector|for\b[^\n]*\bfor\b[^\n]*\]/.test(src);
    var collections = /\[\s*\]|\{\s*\}|\bdict\s*\(|\bset\s*\(|\blist\s*\(|new\s+(Hash|Tree|Array|Linked)\w*|new\s+\w+\s*\[|\bvector\s*<|\bunordered_(map|set)\b|\bmake\s*\(|\bVec::|\bnew Map\b|\bnew Set\b|\[\s*0\s*\]\s*\*|\.append\(|\.push(_back)?\(|\.add\(|\.put\(/.test(src);
    if (grid) { spaceRank = 4; spaceSignals.push({ icon: 'bi-grid-3x3', text: '2-D structure allocated (grid / matrix)' }); }
    else if (collections) { spaceRank = 2; spaceSignals.push({ icon: 'bi-collection', text: 'Auxiliary collection that can grow with input' }); }
    if (recursion) { spaceRank = Math.max(spaceRank, 2); spaceSignals.push({ icon: 'bi-stack', text: 'Recursion uses call-stack space' }); }
    if (!spaceSignals.length) spaceSignals.push({ icon: 'bi-box', text: 'Only a fixed number of variables' });
    if (!signals.length) signals.push({ icon: 'bi-lightning', text: 'No loops or recursion: a fixed number of steps' });

    return { time: timeRank, space: spaceRank, timeSignals: signals, spaceSignals: spaceSignals };
  }

  function growthCurveSVG(rank) {
    var fns = [
      function () { return 1; },
      function (n) { return Math.log2(n + 1); },
      function (n) { return n; },
      function (n) { return n * Math.log2(n + 1); },
      function (n) { return n * n; },
      function (n) { return n * n * n; },
      function (n) { return Math.pow(2, n); }
    ];
    var W = 300, H = 150, cap = 40;
    var paths = fns.map(function (f, i) {
      var d = '';
      for (var s = 0; s <= 40; s++) {
        var n = 1 + (s / 40) * 15;
        var y = Math.min(f(n), cap) / cap;
        d += (s ? 'L' : 'M') + (s / 40 * W).toFixed(1) + ' ' + (H - y * H).toFixed(1);
      }
      return '<path d="' + d + '" class="gc-line' + (i === rank ? ' is-you' : '') + '" style="--i:' + i + '"/>';
    }).join('');
    return '<svg viewBox="-4 -6 ' + (W + 8) + ' ' + (H + 12) + '" class="growth" preserveAspectRatio="none" aria-hidden="true">' +
      '<line x1="0" y1="' + H + '" x2="' + W + '" y2="' + H + '" class="gc-axis"/><line x1="0" y1="0" x2="0" y2="' + H + '" class="gc-axis"/>' + paths + '</svg>';
  }

  /* ── Distribution analysis ── */
  function numbers(list, key) {
    return (list || []).map(function (item) { return parseFloat(item[key]); }).filter(function (v) { return isFinite(v); });
  }

  function quantile(sorted, q) {
    if (!sorted.length) return NaN;
    var pos = (sorted.length - 1) * q;
    var lo = Math.floor(pos), hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }

  function distributionHTML(values, current, unit, fmt, lang) {
    if (!isFinite(current)) {
      return '<div class="dist-empty"><i class="bi bi-bar-chart"></i><span>No measurement was recorded for this submission.</span></div>';
    }
    if (values.length < 2) {
      return '<div class="dist-empty"><i class="bi bi-flag"></i><span>You are the first accepted ' + escapeHtml(lang) + ' solution here, so there is nothing to compare against yet.</span></div>';
    }
    var sorted = values.slice().sort(function (a, b) { return a - b; });
    var min = sorted[0], max = sorted[sorted.length - 1];
    var span = Math.max(max - min, 1e-9);
    var B = 18;
    var bins = new Array(B).fill(0);
    values.forEach(function (v) { bins[Math.min(B - 1, Math.floor(((v - min) / span) * B))]++; });
    var peak = Math.max.apply(null, bins);
    var youBin = Math.min(B - 1, Math.floor(((current - min) / span) * B));
    var beats = Math.round(values.filter(function (v) { return v > current; }).length / values.length * 100);
    var pos = Math.max(0, Math.min(100, ((current - min) / span) * 100));
    var bars = bins.map(function (c, i) {
      return '<i class="' + (i === youBin ? 'is-you' : i < youBin ? 'is-slower' : '') + '" style="--h:' + Math.max(4, c / peak * 100) + '%;--i:' + i + '" title="' + c + ' submission' + (c === 1 ? '' : 's') + '"></i>';
    }).join('');
    return '<div class="dist">' +
      '<div class="dist-head"><div><span class="dist-beats">Beats <b>' + beats + '%</b></span><span class="dist-sub">of ' + values.length + ' accepted ' + escapeHtml(lang) + ' submissions</span></div>' +
      '<div class="dist-stats"><span>Yours<b>' + fmt(current) + '</b></span><span>Median<b>' + fmt(quantile(sorted, 0.5)) + '</b></span><span>Best<b>' + fmt(min) + '</b></span><span>P90<b>' + fmt(quantile(sorted, 0.9)) + '</b></span></div></div>' +
      '<div class="dist-plot"><div class="dist-bars">' + bars + '</div>' +
      '<div class="dist-marker" style="left:' + pos + '%"><span>You</span></div></div>' +
      '<div class="dist-axis"><span>' + fmt(min) + '</span><span>' + unit + '</span><span>' + fmt(max) + '</span></div>' +
    '</div>';
  }

  function complexityPaneHTML(kind, est, data, ref) {
    var isTime = kind === 'time';
    var rank = isTime ? est.time : est.space;
    var refStr = ref ? (isTime ? ref.time : ref.space) : '';
    var refRank = cxRankOf(refStr);
    var verdict = '';
    if (refStr) {
      if (refRank >= 0 && rank <= refRank) verdict = '<div class="cx-verdict good"><i class="bi bi-patch-check-fill"></i> Matches the editorial\'s ' + escapeHtml(refStr) + '</div>';
      else if (refRank >= 0) verdict = '<div class="cx-verdict warn"><i class="bi bi-arrow-up-circle"></i> The editorial reaches ' + escapeHtml(refStr) + ', so there is room to optimize</div>';
      else verdict = '<div class="cx-verdict"><i class="bi bi-book"></i> Editorial reference: ' + escapeHtml(refStr) + '</div>';
    }
    var signals = (isTime ? est.timeSignals : est.spaceSignals).map(function (s) {
      return '<li><i class="bi ' + s.icon + '"></i>' + escapeHtml(s.text) + '</li>';
    }).join('');
    var tone = rank <= 2 ? 'good' : rank <= 3 ? 'ok' : 'warn';
    var values = numbers(data.performance, isTime ? 'runtime_ms' : 'memory_kb');
    var current = parseFloat(isTime ? data.runtime_ms : data.memory_kb);
    var dist = data.status === 'accepted'
      ? distributionHTML(values, current, isTime ? 'runtime' : 'memory', isTime ? formatMs : function (v) { return formatMemoryKB(v) || '—'; }, data.language || languageLabel())
      : '<div class="dist-empty"><i class="bi bi-lock"></i><span>Comparison with other submissions unlocks once this solution is accepted.</span></div>';

    return '<div class="cx-grid">' +
        '<div class="cx-card cx-main">' +
          '<span class="cx-label">' + (isTime ? 'Time' : 'Space') + ' complexity · estimated</span>' +
          '<div class="cx-big cx-' + tone + '">' + CX_ORDER[rank] + '</div>' +
          '<span class="cx-name">' + CX_NAME[rank] + (isTime ? ' time' : ' extra space') + '</span>' +
          verdict +
          '<ul class="cx-signals">' + signals + '</ul>' +
          '<p class="cx-note">Estimated from the structure of your code (loops, recursion, sorting and allocations). Treat it as a guide, not a proof.</p>' +
        '</div>' +
        '<div class="cx-card cx-curve"><span class="cx-label">How it scales</span>' + growthCurveSVG(rank) +
          '<div class="gc-legend">' + CX_ORDER.map(function (c, i) { return '<span class="' + (i === rank ? 'is-you' : '') + '">' + c + '</span>'; }).join('') + '</div>' +
        '</div>' +
      '</div>' +
      '<div class="cx-card cx-dist"><span class="cx-label">' + (isTime ? 'Runtime' : 'Memory') + ' distribution</span>' + dist + '</div>';
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
    var rp = document.getElementById('right-panel');
    if (rp) rp.classList.toggle('report-open', isSubmission);
    if (!isSubmission && window.editor) window.editor.layout();
  }

  if (codeTab) codeTab.addEventListener('click', function () { activateEditorView('code'); });
  if (submissionTab) submissionTab.addEventListener('click', function () { activateEditorView('submission'); });
  function closeSubmissionTab() {
    if (!submissionTab) return;
    submissionTab.hidden = true;
    submissionTab.style.display = '';
    activateEditorView('code');
    document.querySelectorAll('#tab-submissions .submission-row.is-active').forEach(function (r) { r.classList.remove('is-active'); });
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

  function referenceComplexity() {
    var el = document.getElementById('reference-complexity');
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function monacoLangFor(name) {
    var n = String(name || '').toLowerCase();
    if (n.indexOf('python') >= 0) return 'python';
    if (n.indexOf('java') === 0 && n.indexOf('javascript') < 0) return 'java';
    if (n.indexOf('javascript') >= 0 || n === 'js') return 'javascript';
    if (n.indexOf('c++') >= 0 || n.indexOf('cpp') >= 0) return 'cpp';
    if (n === 'c') return 'c';
    if (n.indexOf('go') === 0) return 'go';
    if (n.indexOf('rust') >= 0) return 'rust';
    return 'plaintext';
  }

  function formatWhen(iso) {
    var d = iso ? new Date(iso) : null;
    if (!d || isNaN(d)) return { date: 'Just now', time: '' };
    var diff = (Date.now() - d.getTime()) / 1000;
    var rel = diff < 45 ? 'just now' : diff < 3600 ? Math.round(diff / 60) + ' min ago' : diff < 86400 ? Math.round(diff / 3600) + ' h ago' : Math.round(diff / 86400) + ' d ago';
    return {
      date: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
      time: d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) + ' · ' + rel
    };
  }

  function passRing(pct, ok) {
    var r = 26, c = 2 * Math.PI * r;
    return '<svg class="pass-ring" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="' + r + '" class="pr-track"/>' +
      '<circle cx="32" cy="32" r="' + r + '" class="pr-fill ' + (ok ? 'ok' : 'bad') + '" style="--c:' + c.toFixed(1) + ';--o:' + (c * (1 - pct / 100)).toFixed(1) + '"/></svg>';
  }

  function caseChartHTML(results) {
    if (!results.length) return '';
    var times = results.map(function (r) { return parseFloat(r.runtime_ms) || 0; });
    var peak = Math.max.apply(null, times.concat([0.0001]));
    var bars = results.map(function (r, i) {
      var ok = isPass(r.status);
      return '<i class="' + (ok ? 'ok' : 'bad') + '" style="--h:' + Math.max(6, times[i] / peak * 100) + '%;--i:' + i + '" title="Case ' + escapeAttr(r.tc_num) + ' · ' + escapeAttr(ok ? 'Passed' : titleize(r.status)) + (r.runtime_ms ? ' · ' + escapeAttr(formatMs(r.runtime_ms)) : '') + '"></i>';
    }).join('');
    var avg = times.reduce(function (a, b) { return a + b; }, 0) / times.length;
    return '<div class="case-chart"><div class="cc-bars">' + bars + '</div>' +
      '<div class="cc-axis"><span>Case 1</span><span>avg ' + formatMs(avg) + ' · slowest ' + formatMs(peak) + '</span><span>Case ' + escapeHtml(results[results.length - 1].tc_num) + '</span></div></div>';
  }

  function renderSubmissionStatusNow(data) {
    if (!submissionStatusContent || !submissionTab) return;
    const status = submissionStatusClass(data.status);
    const ok = status === 'accepted';
    const verdictCls = ok ? 'accepted' : statusClass(data.status);
    const results = data.test_case_results || data.results || [];
    const accepted = Number(data.accepted || 0);
    const total = Number(data.total || results.length);
    const pct = total ? Math.round(accepted / total * 100) : 0;
    const lang = data.language || languageLabel();
    const code = data.code || getEditorCode();
    const when = formatWhen(data.submitted_at);
    const est = estimateComplexity(code, lang);
    const ref = referenceComplexity();
    const label = ok ? 'Accepted' : titleize(data.status);

    let errMsg = '';
    if (!ok) {
      const failing = results.filter(function (r) { return !isPass(r.status); })[0];
      errMsg = (failing && (verdictCls === 'compile' || verdictCls === 'runtime') && failing.actual) || (!results.length ? (data.actual || '') : '');
    }

    const runtimeVals = numbers(data.performance, 'runtime_ms');
    const memoryVals = numbers(data.performance, 'memory_kb');
    const rt = parseFloat(data.runtime_ms), mem = parseFloat(data.memory_kb);
    function beats(vals, cur) {
      if (!ok || !isFinite(cur) || vals.length < 2) return null;
      return Math.round(vals.filter(function (v) { return v > cur; }).length / vals.length * 100);
    }
    const rtBeats = beats(runtimeVals, rt), memBeats = beats(memoryVals, mem);
    function beatsBar(b) {
      return b === null ? '<span class="kpi-sub">' + (ok ? 'Not enough data to compare' : 'Compared once accepted') + '</span>'
        : '<span class="kpi-sub">Beats <b>' + b + '%</b></span><span class="kpi-meter"><i style="--w:' + b + '%"></i></span>';
    }

    const failedCases = results.filter(function (r) { return !isPass(r.status); });
    const cases = results.map(function (result) {
      const passed = isPass(result.status);
      const hasIO = result.input !== undefined;
      const details = passed ? '' : '<div class="submission-case-details">' + (hasIO
        ? '<div><b>Input</b><pre>' + escapeHtml(normalizeCaseText(result.input)) + '</pre></div><div><b>Expected</b><pre>' + escapeHtml(normalizeCaseText(result.expected)) + '</pre></div><div><b>Actual</b><pre class="is-bad">' + escapeHtml(normalizeCaseText(result.actual)) + '</pre></div>'
        : '<p class="hidden-note"><i class="bi bi-eye-slash"></i> This is a hidden test case, so its input and output stay private.</p>') + '</div>';
      return '<div class="submission-case ' + (passed ? 'passed' : 'failed') + '"><button type="button" class="submission-case-row" data-case-toggle' + (passed ? ' disabled' : '') + '><span class="submission-case-indicator" aria-hidden="true"></span><span>Case ' + escapeHtml(result.tc_num) + (result.input === undefined ? ' <small>hidden</small>' : '') + '</span>' + (result.runtime_ms ? '<em>' + formatMs(result.runtime_ms) + '</em>' : '<em></em>') + '<strong>' + (passed ? 'Passed' : titleize(result.status)) + '</strong>' + (passed ? '' : '<i class="bi bi-chevron-down"></i>') + '</button>' + details + '</div>';
    }).join('');

    submissionTab.hidden = false;
    submissionTab.style.display = '';
    submissionTab.className = 'editor-view-tab editor-view-tab-submission status-' + status + ' active';
    document.getElementById('editor-view-tab-submission-label').textContent = label;

    const lineCount = String(code).split('\n').length;
    submissionStatusContent.innerHTML =
      '<div class="sr sr-enter v-' + verdictCls + '">' +
        '<header class="sr-hero">' +
          '<div class="sr-verdict"><span class="sr-icon"><i class="bi ' + (ok ? 'bi-check-lg' : (VERDICT_ICON[verdictCls] || 'bi-x-lg')) + '"></i></span>' +
            '<div><span class="sr-kicker">' + (data.submission_id ? 'Submission #' + escapeHtml(data.submission_id) + ' · ' : '') + escapeHtml(lang) + '</span>' +
            '<h3>' + escapeHtml(label) + '</h3>' +
            '<p>' + accepted + ' / ' + total + ' test cases passed</p></div></div>' +
          '<div class="sr-when"><b>' + escapeHtml(when.date) + '</b><span>' + escapeHtml(when.time) + '</span></div>' +
        '</header>' +
        errorConsoleHTML(verdictCls === 'compile' ? 'compile' : 'runtime', errMsg) +
        '<section class="sr-kpis">' +
          '<div class="kpi"><span class="kpi-label"><i class="bi bi-stopwatch"></i> Runtime</span><strong>' + (isFinite(rt) ? formatMs(rt) : '—') + '</strong>' + beatsBar(rtBeats) + '</div>' +
          '<div class="kpi"><span class="kpi-label"><i class="bi bi-memory"></i> Memory</span><strong>' + (formatMemoryKB(data.memory_kb) || '—') + '</strong>' + beatsBar(memBeats) + '</div>' +
          '<div class="kpi kpi-ring">' + passRing(pct, ok) + '<div><span class="kpi-label">Pass rate</span><strong>' + pct + '%</strong><span class="kpi-sub">' + accepted + ' of ' + total + ' cases</span></div></div>' +
        '</section>' +
        '<section class="sr-card sr-analysis">' +
          '<div class="sr-tabs" role="tablist">' +
            '<button type="button" class="sr-tab active" data-sr-tab="time"><i class="bi bi-stopwatch"></i> Time complexity <b>' + CX_ORDER[est.time] + '</b></button>' +
            '<button type="button" class="sr-tab" data-sr-tab="space"><i class="bi bi-memory"></i> Space complexity <b>' + CX_ORDER[est.space] + '</b></button>' +
          '</div>' +
          '<div class="sr-pane active" data-sr-pane="time">' + complexityPaneHTML('time', est, data, ref) + '</div>' +
          '<div class="sr-pane" data-sr-pane="space">' + complexityPaneHTML('space', est, data, ref) + '</div>' +
        '</section>' +
        (results.length ? '<section class="sr-card"><div class="sr-card-head"><h4>Test case breakdown</h4><span class="sr-legend"><i class="ok"></i>Passed <i class="bad"></i>Failed</span></div>' +
          caseChartHTML(results) +
          (failedCases.length ? '<div class="submission-section-label">Failed cases</div>' : '') +
          '<div class="submission-cases' + (failedCases.length ? '' : ' all-passed') + '">' + cases + '</div></section>' : '') +
        '<section class="sr-card sr-code"><div class="sr-card-head"><h4>Submitted code</h4><span class="sr-code-meta">' + escapeHtml(lang) + ' · ' + lineCount + ' line' + (lineCount === 1 ? '' : 's') + '</span><button type="button" class="copy-btn" data-copy-code>Copy</button></div>' +
          '<pre class="submitted-code"><code>' + String(code).split('\n').map(function (l) { return '<span class="ln">' + (escapeHtml(l) || ' ') + '</span>'; }).join('') + '</code></pre></section>' +
      '</div>';

    // Interactions
    submissionStatusContent.querySelectorAll('[data-case-toggle]').forEach(function (button) {
      button.addEventListener('click', function () {
        const details = button.nextElementSibling;
        if (details) { details.classList.toggle('open'); button.classList.toggle('open'); }
      });
    });
    submissionStatusContent.querySelectorAll('[data-sr-tab]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        submissionStatusContent.querySelectorAll('[data-sr-tab]').forEach(function (t) { t.classList.toggle('active', t === tab); });
        submissionStatusContent.querySelectorAll('[data-sr-pane]').forEach(function (p) { p.classList.toggle('active', p.dataset.srPane === tab.dataset.srTab); });
      });
    });
    const copyCode = submissionStatusContent.querySelector('[data-copy-code]');
    if (copyCode) copyCode.addEventListener('click', function () {
      navigator.clipboard.writeText(code).then(function () {
        copyCode.textContent = 'Copied';
        setTimeout(function () { copyCode.textContent = 'Copy'; }, 1500);
      });
    });

    // Syntax-highlight the submitted code once Monaco is available
    const codeEl = submissionStatusContent.querySelector('.submitted-code code');
    if (codeEl && window.monaco && monaco.editor && monaco.editor.colorize) {
      monaco.editor.colorize(String(code), monacoLangFor(lang), { tabSize: 4 }).then(function (html) {
        if (!codeEl.isConnected) return;
        codeEl.innerHTML = html.split(/<br\s*\/?>/).map(function (l) { return '<span class="ln">' + (l || ' ') + '</span>'; }).join('');
      }).catch(function () {});
    }

    activateEditorView('submission');
    submissionStatusContent.scrollTop = 0;
    if (ok && data._fresh) celebrate(submissionStatusContent.querySelector('.sr-hero'));
  }

  function renderSubmissionStatus(data) {
    if (!submissionStatusContent) return;
    // Let the judging animation complete before revealing the verdict
    finishJudgeScene(submissionStatusContent, submissionStatusClass(data.status) === 'accepted', function () {
      renderSubmissionStatusNow(data);
    });
  }

  function renderSubmissionPending(mode) {
    if (!submissionTab || !submissionStatusContent) return;
    submissionTab.hidden = false;
    submissionTab.style.display = '';
    submissionTab.className = 'editor-view-tab editor-view-tab-submission status-pending active';
    document.getElementById('editor-view-tab-submission-label').textContent = mode === 'history' ? 'Loading' : 'Judging';
    if (mode === 'history') {
      submissionStatusContent.innerHTML = '<div class="sr-loading"><div class="skeleton skeleton-line w-1-2 h-tall"></div><div class="sr-loading-kpis"><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-block"></div></div><div class="skeleton skeleton-block tall"></div><div class="skeleton skeleton-line w-full"></div><div class="skeleton skeleton-line w-3-4"></div></div>';
    } else {
      startJudgeScene(submissionStatusContent, 'submit');
    }
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

      document.body.dataset.busy = 'run';
      setButtonLoading(btnRun, true);
      setButtonLoading(btnSubmit, true);
      switchToTestResultTab();

      const container = document.getElementById('test-result-content');
      startJudgeScene(container, 'run');

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
            cases: (window.__bbCases || []).map(function (c, i) {
              return { tc_num: c.order_num || (i + 1), input: c.input_data || '', label: c.label || '' };
            }),
            selected_case: (document.querySelector('.case-pill.active') || {}).textContent.replace(/\D/g, '') || null,
          }),
        });

        const bodyText = await res.text().catch(function () { return ''; });
        let data;
        try {
          data = JSON.parse(bodyText);
        } catch (_) {
          // Server returned non-JSON (e.g. HTML error page) — show what we can
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
        var allPassed = (data.test_case_results || []).length > 0 &&
          (data.test_case_results || []).every(function (r) { return isPass(r.status); });
        finishJudgeScene(container, allPassed, function () { renderRunResult(data); });
      } catch (err) {
        if (container) {
          container.innerHTML = '<div class="empty-state">Network error: ' + escapeHtml(err.message || err) + '</div>';
        }
      } finally {
        setButtonLoading(btnRun, false);
        setButtonLoading(btnSubmit, false);
        delete document.body.dataset.busy;
      }
    });
  }

  /* Poll a queued submission until it has a final status (max ~3 minutes). */
  async function waitForVerdict(url) {
    var delay = 700;
    var deadline = Date.now() + 180000;
    while (Date.now() < deadline) {
      await new Promise(function (r) { setTimeout(r, delay); });
      delay = Math.min(delay + 300, 2000);
      try {
        var res = await fetch(url, { headers: { 'Accept': 'application/json' } });
        if (!res.ok) continue;
        var data = await res.json();
        if (!data.pending) return data;
      } catch (_) { /* network blip: keep waiting */ }
    }
    return { status: 'internal_error', accepted: 0, total: 0,
             actual: 'Judging is taking longer than usual. Check the Submissions tab in a minute.',
             code: getEditorCode(), language: getSelectedLanguage() };
  }

  /* ══════════════════════════
     SUBMIT BUTTON
  ══════════════════════════ */
  if (btnSubmit) {
    btnSubmit.addEventListener('click', async function () {
      if (!IS_AUTHENTICATED) { alert('Please login to submit code.'); return; }
      const code = getEditorCode().trim();
      if (!code) { alert('Please write some code first.'); return; }

      document.body.dataset.busy = 'submit';
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

        const bodyText = await res.text().catch(function () { return ''; });
        let data;
        try {
          data = JSON.parse(bodyText);
        } catch (_) {
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
        // Judging runs in the background: poll until the verdict is ready
        if (data.queued) {
          data = await waitForVerdict(data.poll_url || ('/submissions/detail/' + data.submission_id + '/'));
        }
        data._fresh = true;
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
        delete document.body.dataset.busy;
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
      // BashaByte dark theme (name kept for compatibility)
      monaco.editor.defineTheme('neonMatrix', {
        base: 'vs-dark',
        inherit: true,
        rules: [
          { token: '', foreground: 'E6EFE9' },
          { token: 'identifier', foreground: 'E6EFE9' },
          { token: 'variable', foreground: 'E6EFE9' },
          { token: 'variable.parameter', foreground: 'E6EFE9' },
          { token: 'keyword', foreground: 'C3A6FF' },
          { token: 'keyword.control', foreground: 'C3A6FF' },
          { token: 'keyword.operator', foreground: '9CADA3' },
          { token: 'operator', foreground: '9CADA3' },
          { token: 'string', foreground: 'FFB45C' },
          { token: 'string.escape', foreground: '79C0FF' },
          { token: 'comment', foreground: '5F6F66', fontStyle: 'italic' },
          { token: 'number', foreground: '79C0FF' },
          { token: 'type', foreground: '8DE0A3' },
          { token: 'type.identifier', foreground: '8DE0A3' },
          { token: 'function', foreground: '8DE0A3' },
          { token: 'delimiter', foreground: '7D8D84' },
          { token: 'tag', foreground: '8DE0A3' },
          { token: 'attribute.name', foreground: '8DE0A3' },
          { token: 'attribute.value', foreground: 'FFB45C' },
        ],
        colors: {
          'editor.background':                '#0B110E',
          'editor.foreground':                '#E6EFE9',
          'editor.lineHighlightBackground':   '#121B16',
          'editor.lineHighlightBorder':       '#00000000',
          'editorLineNumber.foreground':      '#3A4A41',
          'editorLineNumber.activeForeground':'#8DE0A3',
          'editorCursor.foreground':          '#8DE0A3',
          'editor.selectionBackground':       '#8DE0A333',
          'editor.inactiveSelectionBackground':'#8DE0A31A',
          'editor.selectionHighlightBackground':'#8DE0A31F',
          'editor.findMatchBackground':       '#FFA11644',
          'editor.findMatchHighlightBackground':'#FFA11622',
          'editorGutter.background':          '#0B110E',
          'editorIndentGuide.background':     '#18231D',
          'editorIndentGuide.activeBackground':'#2C3D33',
          'editorBracketMatch.background':    '#8DE0A322',
          'editorBracketMatch.border':        '#8DE0A366',
          'editorOverviewRuler.border':       '#00000000',
          'editorWidget.background':          '#121A16',
          'editorSuggestWidget.background':   '#121A16',
          'editorSuggestWidget.border':       '#24312A',
          'editorSuggestWidget.selectedBackground': '#1C2A22',
          'scrollbarSlider.background':       '#8DE0A31A',
          'scrollbarSlider.hoverBackground':  '#8DE0A333',
          'scrollbarSlider.activeBackground': '#8DE0A355',
        },
      });

      monaco.editor.defineTheme('bbLight', {
        base: 'vs',
        inherit: true,
        rules: [
          { token: '', foreground: '1B241E' },
          { token: 'keyword', foreground: '7A4FD6' },
          { token: 'keyword.control', foreground: '7A4FD6' },
          { token: 'string', foreground: 'B4610A' },
          { token: 'number', foreground: '0B69C7' },
          { token: 'comment', foreground: '8A968E', fontStyle: 'italic' },
          { token: 'type', foreground: '1D8A4B' },
          { token: 'type.identifier', foreground: '1D8A4B' },
          { token: 'function', foreground: '1D8A4B' },
          { token: 'delimiter', foreground: '66746B' },
        ],
        colors: {
          'editor.background':                '#FFFFFF',
          'editor.lineHighlightBackground':   '#F4F2EB',
          'editor.lineHighlightBorder':       '#00000000',
          'editorLineNumber.foreground':      '#B9C0B9',
          'editorLineNumber.activeForeground':'#1D8A4B',
          'editorCursor.foreground':          '#1D8A4B',
          'editor.selectionBackground':       '#1D8A4B26',
          'editorGutter.background':          '#FFFFFF',
          'editorIndentGuide.background':     '#ECEAE2',
          'scrollbarSlider.background':       '#1D8A4B1A',
          'scrollbarSlider.hoverBackground':  '#1D8A4B33',
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
          theme: currentTheme === 'dark' ? 'neonMatrix' : 'bbLight',
          fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
          fontLigatures: true,
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
    document.querySelectorAll('#tab-submissions .submission-row').forEach(function (r) { r.classList.toggle('is-active', r === row); });
    renderSubmissionPending('history');
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
