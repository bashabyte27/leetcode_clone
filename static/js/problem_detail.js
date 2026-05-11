/* ─────────────────────────────────────────────
   PROBLEM DETAIL — problem_detail.js
   Globals expected: PROBLEM_SLUG, IS_AUTHENTICATED, CSRF_TOKEN
   ───────────────────────────────────────────── */
(function () {
  'use strict';

  /* ══════════════════════════
     HELPERS
  ══════════════════════════ */
  function getEditorCode() {
    return window.editor ? window.editor.getValue() : '';
  }

  function getSelectedLanguage() {
    return document.getElementById('language-select').value;
  }

  function setButtonLoading(btn, loading) {
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
    });
  }

  /* ══════════════════════════
     TIMER
  ══════════════════════════ */
  let timerInterval = null;
  let timerSeconds = 0;
  let timerRunning = false;

  const timerDisplay = document.getElementById('timer-display');
  if (timerDisplay) {
    timerDisplay.addEventListener('click', function () {
      if (timerRunning) {
        clearInterval(timerInterval);
        timerInterval = null;
        timerRunning = false;
        timerDisplay.classList.remove('running');
      } else {
        timerRunning = true;
        timerDisplay.classList.add('running');
        timerInterval = setInterval(function () {
          timerSeconds++;
          const m = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
          const s = String(timerSeconds % 60).padStart(2, '0');
          timerDisplay.textContent = m + ':' + s;
        }, 1000);
      }
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
      if (target === 'solutions') lazyLoadTab('solutions', '/problems/' + PROBLEM_SLUG + '/solutions');
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
      .then(function (html) {
        el.innerHTML = html;
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
    fetch('/problems/' + PROBLEM_SLUG + '/submissions')
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
     PILL DROPDOWNS (Topics / Companies)
  ══════════════════════════ */
  document.querySelectorAll('[data-dropdown]').forEach(function (btn) {
    const dropdownId = btn.dataset.dropdown;
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      const isOpen = dropdown.classList.contains('open');
      // Close all
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

    btnHint.textContent = 'Hint (' + hints.length + ')';

    btnHint.addEventListener('click', function () {
      if (hints.length === 0) return;
      if (currentIndex >= hints.length) {
        btnHint.textContent = 'All hints shown';
        return;
      }
      const card = document.createElement('div');
      card.className = 'hint-card';
      card.innerHTML = '<strong>Hint ' + (currentIndex + 1) + '</strong>' + escapeHtml(hints[currentIndex]);
      hintsArea.appendChild(card);
      currentIndex++;
      if (currentIndex >= hints.length) {
        btnHint.textContent = 'All hints shown';
      }
    });
  })();

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

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
      newH = Math.max(150, Math.min(panelH - 100, newH));
      editorZone.style.flex = '0 0 ' + newH + 'px';
    });

    document.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove('dragging');
      document.body.classList.remove('no-select');
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
     RESULT RENDERING
  ══════════════════════════ */
  function renderRunResult(data) {
    const container = document.getElementById('test-result-content');
    if (!container) return;

    if (data.status === 'success') {
      container.innerHTML = `
        <div class="result-header">
          <span class="result-title green">✅ Accepted</span>
        </div>
        <div class="result-meta">Runtime: ${data.runtime_ms} ms</div>
        <pre class="result-code-block">${escapeHtml(data.stdout || '')}</pre>
      `;
    } else {
      container.innerHTML = `
        <div class="result-header">
          <span class="result-title red">❌ Runtime Error</span>
        </div>
        <pre class="result-code-block error">${escapeHtml(data.stderr || data.stdout || 'Unknown error')}</pre>
      `;
    }
  }

  function renderSubmitResult(data) {
    const container = document.getElementById('test-result-content');
    if (!container) return;

    const isAccepted = data.status === 'accepted';
    const titleIcon = isAccepted ? '✅' : '❌';
    const titleText = isAccepted ? 'Accepted' : titleize(data.status);
    const titleClass = isAccepted ? 'green' : 'red';

    // Build pills
    const pillsHTML = (data.test_case_results || []).map(function (tc, i) {
      const passed = tc.status === 'accepted';
      const icon = passed ? '✅' : '❌';
      const failedClass = passed ? '' : ' failed';
      const activeClass = i === 0 ? ' active' : '';
      return `<button class="case-pill${failedClass}${activeClass}" data-index="${i}">${icon} Case ${tc.tc_num}</button>`;
    }).join('');

    container.innerHTML = `
      <div class="result-header">
        <span class="result-title ${titleClass}">${titleIcon} ${titleText}</span>
      </div>
      <div class="result-meta">
        Runtime: ${data.runtime_ms} ms &nbsp;·&nbsp;
        ${data.accepted}/${data.total} test cases passed
      </div>
      <div class="case-pills-row">${pillsHTML}</div>
      <div class="case-detail" id="case-detail-panel"></div>
    `;

    // Render first case
    const tcResults = data.test_case_results || [];
    if (tcResults.length > 0) renderCaseDetail(tcResults[0]);

    // Pill click
    container.querySelectorAll('.case-pill').forEach(function (pill) {
      pill.addEventListener('click', function () {
        container.querySelectorAll('.case-pill').forEach(function (p) { p.classList.remove('active'); });
        pill.classList.add('active');
        const idx = parseInt(pill.dataset.index, 10);
        if (tcResults[idx]) renderCaseDetail(tcResults[idx]);
      });
    });
  }

  function renderCaseDetail(tc) {
    const panel = document.getElementById('case-detail-panel');
    if (!panel) return;

    if (tc.input !== undefined) {
      // Sample case — show input/output/expected
      panel.innerHTML = `
        ${ioCard('Input', tc.input)}
        ${ioCard('Output', tc.actual)}
        ${ioCard('Expected', tc.expected)}
      `;
      panel.querySelectorAll('.copy-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
          const text = btn.dataset.copy;
          navigator.clipboard.writeText(text).then(function () {
            btn.textContent = '✓';
            setTimeout(function () { btn.textContent = '📋'; }, 1500);
          });
        });
      });
    } else {
      // Non-sample
      const statusIcon = tc.status === 'accepted' ? '✅' : '❌';
      panel.innerHTML = `
        <div style="font-size:13px;color:var(--text-secondary);padding:8px 0;">
          Case ${tc.tc_num}: ${statusIcon} ${titleize(tc.status)} (${tc.runtime_ms}ms)
        </div>
      `;
    }
  }

  function ioCard(label, value) {
    const safe = escapeHtml(value || '');
    return `
      <div class="case-io-card">
        <div class="case-io-card-header">
          ${label}
          <button class="copy-btn" data-copy="${escapeAttr(value || '')}">📋</button>
        </div>
        <div class="case-io-card-body">${safe}</div>
      </div>
    `;
  }

  function titleize(str) {
    return String(str || '').replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function escapeAttr(text) {
    return String(text).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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
            custom_input: document.getElementById('custom-input').value,
          }),
        });
        const data = await res.json();
        renderRunResult(data);
      } catch (err) {
        if (container) {
          container.innerHTML = '<div class="empty-state">Network error. Please try again.</div>';
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
      switchToTestResultTab();

      const container = document.getElementById('test-result-content');
      if (container) container.innerHTML = skeletonHTML();

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
          }),
        });
        const data = await res.json();
        renderSubmitResult(data);

        // Invalidate submissions tab cache
        const subTab = document.getElementById('tab-submissions');
        if (subTab) subTab.classList.remove('loaded');
      } catch (err) {
        if (container) {
          container.innerHTML = '<div class="empty-state">Network error. Please try again.</div>';
        }
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
      btnFullscreen.textContent = rightPanel.classList.contains('fullscreen') ? '⊠' : '⛶';
      if (window.editor) window.editor.layout();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && rightPanel.classList.contains('fullscreen')) {
        rightPanel.classList.remove('fullscreen');
        btnFullscreen.textContent = '⛶';
        if (window.editor) window.editor.layout();
      }
    });
  }

  /* ══════════════════════════
     MONACO EDITOR
  ══════════════════════════ */
  if (typeof require !== 'undefined') {
    require.config({
      paths: {
        'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs',
      },
    });

    require(['vs/editor/editor.main'], function () {
      // Define creamy theme
      monaco.editor.defineTheme('myCreamy', {
        base: 'vs',
        inherit: true,
        rules: [
          { token: 'keyword',  foreground: '1A7B4B', fontStyle: 'bold' },
          { token: 'string',   foreground: 'B45309' },
          { token: 'comment',  foreground: '9E9E9E', fontStyle: 'italic' },
          { token: 'number',   foreground: 'C0392B' },
          { token: 'type',     foreground: '069494' },
        ],
        colors: {
          'editor.background':                '#FDFBD4',
          'editor.foreground':                '#1A1A1A',
          'editor.lineHighlightBackground':   '#F5F3C0',
          'editorLineNumber.foreground':      '#9E9E9E',
          'editorLineNumber.activeForeground':'#1A7B4B',
          'editorCursor.foreground':          '#1A7B4B',
          'editor.selectionBackground':       '#C8E6C9',
          'editorGutter.background':          '#F5F3C0',
        },
      });

      window.editor = monaco.editor.create(
        document.getElementById('monaco-editor-container'),
        {
          value: '',
          language: 'python',
          theme: 'myCreamy',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 14,
          lineHeight: 22,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          wordWrap: 'off',
          lineNumbers: 'on',
          renderLineHighlight: 'line',
          cursorStyle: 'line',
          tabSize: 4,
          insertSpaces: true,
        }
      );

      // Status bar tracking
      const saveStatus = document.getElementById('editor-save-status');
      const cursorPos = document.getElementById('editor-cursor-pos');

      window.editor.onDidChangeModelContent(function () {
        if (saveStatus) {
          saveStatus.textContent = '● Unsaved';
          saveStatus.className = 'unsaved';
        }
      });

      window.editor.onDidChangeCursorPosition(function (e) {
        if (cursorPos) {
          cursorPos.textContent = 'Ln ' + e.position.lineNumber + ', Col ' + e.position.column;
        }
      });

      // Language switch triggers Monaco language change
      const langSelect = document.getElementById('language-select');
      if (langSelect) {
        const langMap = {
          'python3': 'python',
          'java':    'java',
          'cpp':     'cpp',
          'javascript': 'javascript',
          'go':      'go',
          'rust':    'rust',
        };
        langSelect.addEventListener('change', function () {
          const monacoLang = langMap[this.value] || 'python';
          const model = window.editor.getModel();
          if (model) monaco.editor.setModelLanguage(model, monacoLang);
        });
      }

      // Undo button
      const btnUndo = document.getElementById('btn-undo');
      if (btnUndo) {
        btnUndo.addEventListener('click', function () {
          window.editor.trigger('keyboard', 'undo', null);
          window.editor.focus();
        });
      }
    });
  }

  /* ══════════════════════════
     EDITOR SAVE STATUS INIT
  ══════════════════════════ */
  (function () {
    const saveStatus = document.getElementById('editor-save-status');
    if (saveStatus) {
      saveStatus.textContent = '✓ Saved';
      saveStatus.className = 'saved';
    }
  })();

})();