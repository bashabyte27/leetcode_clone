/**
 * problem_detail.js — BashaByte LeetCode Clone
 *
 * Run    → POST /submissions/run/<slug>/
 *            body:     { code, custom_input }   ← single input string per call
 *            response: { status, stdout, stderr, runtime_ms }
 *
 * Submit → POST /submissions/submit/<slug>/
 *            body:     { code, language }
 *            response: { submission_id, status, runtime_ms,
 *                        accepted, total, test_case_results }
 *            test_case_results (sample):
 *              { tc_num, status, input, expected, actual, runtime_ms }
 *            test_case_results (hidden):
 *              { tc_num, status, runtime_ms }
 *
 * Global constants injected by the Django template:
 *   PROBLEM_SLUG, CSRF_TOKEN, IS_AUTHENTICATED, SAMPLE_CASES,
 *   RUN_URL, SUBMIT_URL, COMMENT_URL,
 *   REPLY_URL_BASE, VOTE_URL_BASE,
 *   SOLUTIONS_URL, PROB_PANEL_URL
 */

'use strict';

/* ─────────────────────────────────────────────────────────────────
   STARTER CODE — keyed by <select> option values
───────────────────────────────────────────────────────────────── */
const STARTER_CODE = {
  python:
    'class Solution:\n    def solve(self, input_data):\n        # input_data is the raw stdin string\n        pass\n',
  javascript:
    '/**\n * @param {string} inputData\n */\nvar solve = function(inputData) {\n    \n};\n',
  cpp:
    '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    // read from cin\n    \n    return 0;\n}\n',
  java:
    'import java.util.*;\n\npublic class Solution {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        \n    }\n}\n',
  go:
    'package main\n\nimport "fmt"\n\nfunc main() {\n    \n}\n',
  rust:
    'use std::io::{self, Read};\n\nfn main() {\n    let mut input = String::new();\n    io::stdin().read_to_string(&mut input).unwrap();\n    \n}\n',
  typescript:
    'const lines: string[] = [];\nprocess.stdin.on("line", (l: string) => lines.push(l));\nprocess.stdin.on("close", () => {\n    \n});\n',
};

/* Monaco language id map */
const MONACO_LANG = {
  python: 'python', javascript: 'javascript', cpp: 'cpp',
  java: 'java', go: 'go', rust: 'rust', typescript: 'typescript',
};

/* ─────────────────────────────────────────────────────────────────
   MODULE STATE
───────────────────────────────────────────────────────────────── */
let editorInstance    = null;   // Monaco — MUST be declared outside require()
let currentLanguage   = 'python';
let submissionsLoaded = false;
let plProblemsCache   = null;
let plCurrentFilter   = 'all';

/* ─────────────────────────────────────────────────────────────────
   THEME
   Anti-flash script in <head> already set data-theme before CSS loaded.
   Here we only sync the icon button state.
───────────────────────────────────────────────────────────────── */
function initTheme() {
  const saved = localStorage.getItem('editorTheme') || 'dark';
  _syncThemeIcons(saved);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('editorTheme', theme);
  _syncThemeIcons(theme);
  if (editorInstance) {
    window.monaco.editor.setTheme(theme === 'light' ? 'vs' : 'vs-dark');
  }
}

function _syncThemeIcons(theme) {
  const moon = document.getElementById('icon-moon');
  const sun  = document.getElementById('icon-sun');
  if (!moon || !sun) return;
  moon.style.display = theme === 'light' ? 'none' : '';
  sun.style.display  = theme === 'light' ? ''     : 'none';
}

document.getElementById('theme-toggle').addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(cur === 'dark' ? 'light' : 'dark');
});

/* ─────────────────────────────────────────────────────────────────
   LEFT PANEL TABS
───────────────────────────────────────────────────────────────── */
function initLeftTabs() {
  const btns  = document.querySelectorAll('.tab-bar .tab-btn');
  const panes = document.querySelectorAll('#left-panel .tab-pane');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;

      btns.forEach(b  => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
      panes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      document.getElementById('pane-' + target).classList.add('active');

      // Lazy-load submissions only on first visit
      if (target === 'submissions' && !submissionsLoaded) {
        loadSubmissions();
      }
    });
  });
}

/* ─────────────────────────────────────────────────────────────────
   BOTTOM RESULT PANEL — sub-tabs and collapse toggle
───────────────────────────────────────────────────────────────── */
function initBottomPanel() {
  const panel       = document.getElementById('bottom-panel');
  const collapseBtn = document.getElementById('collapse-bottom');
  const subtabBtns  = document.querySelectorAll('.result-subtab');
  const panes       = document.querySelectorAll('.result-pane');

  collapseBtn.addEventListener('click', () => panel.classList.toggle('collapsed'));

  subtabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.subtab;
      subtabBtns.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
      panes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      document.getElementById('pane-' + target).classList.add('active');
    });
  });
}

function openBottomPanel(subtab) {
  document.getElementById('bottom-panel').classList.remove('collapsed');
  document.querySelectorAll('.result-subtab').forEach(b => {
    const match = b.dataset.subtab === subtab;
    b.classList.toggle('active', match);
    b.setAttribute('aria-selected', String(match));
  });
  document.querySelectorAll('.result-pane').forEach(p => {
    p.classList.toggle('active', p.id === 'pane-' + subtab);
  });
}

/* ─────────────────────────────────────────────────────────────────
   MONACO EDITOR
───────────────────────────────────────────────────────────────── */
require(['vs/editor/editor.main'], function () {
  const theme = (localStorage.getItem('editorTheme') || 'dark') === 'light' ? 'vs' : 'vs-dark';

  editorInstance = window.monaco.editor.create(
    document.getElementById('monaco-editor'),
    {
      value:               STARTER_CODE[currentLanguage],
      language:            MONACO_LANG[currentLanguage],
      theme,
      fontSize:            14,
      fontFamily:          "'JetBrains Mono', 'Fira Code', monospace",
      fontLigatures:       true,
      minimap:             { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout:     true,
      tabSize:             4,
      wordWrap:            'off',
      lineNumbers:         'on',
      renderWhitespace:    'selection',
      smoothScrolling:     true,
      cursorBlinking:      'smooth',
      padding:             { top: 12, bottom: 12 },
      scrollbar:           { vertical: 'visible', horizontal: 'visible', useShadows: false },
    }
  );

  // Language selector
  document.getElementById('lang-select').addEventListener('change', function () {
    currentLanguage = this.value;
    window.monaco.editor.setModelLanguage(editorInstance.getModel(), MONACO_LANG[currentLanguage]);
    editorInstance.setValue(STARTER_CODE[currentLanguage]);
  });

  // Reset button
  document.getElementById('reset-code-btn').addEventListener('click', () => {
    if (window.confirm('Reset editor to starter code? All your changes will be lost.')) {
      editorInstance.setValue(STARTER_CODE[currentLanguage]);
    }
  });
});

/* ─────────────────────────────────────────────────────────────────
   FETCH UTILITIES
───────────────────────────────────────────────────────────────── */
async function postJSON(url, payload) {
  const res  = await fetch(url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
    body:    JSON.stringify(payload),
  });
  const json = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
  return json;
}

async function getJSON(url) {
  const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* ─────────────────────────────────────────────────────────────────
   COLLECT TEST CASE INPUTS from editable textareas in the bottom panel
───────────────────────────────────────────────────────────────── */
function collectTestInputs() {
  const result = [];
  document.querySelectorAll('.testcase-input').forEach(ta => {
    result.push({ input: ta.value, expected: (ta.dataset.expected || '').trim() });
  });
  return result;
}

/* ─────────────────────────────────────────────────────────────────
   RUN CODE — calls POST /submissions/run/<slug>/
   The endpoint accepts one `custom_input` at a time, so we fire
   one request per test case in parallel via Promise.all.
───────────────────────────────────────────────────────────────── */
document.getElementById('run-btn').addEventListener('click', async () => {
  if (!editorInstance) return;

  const runBtn    = document.getElementById('run-btn');
  const submitBtn = document.getElementById('submit-btn');
  const code      = editorInstance.getValue().trim();

  if (!code) { showToast('Editor is empty — write some code first.', 'warn'); return; }

  setButtonLoading(runBtn, true, '⏳ Running…');
  submitBtn.disabled = true;
  openBottomPanel('testresult');
  showResultPlaceholder('Running your code…');

  const testInputs = collectTestInputs();

  try {
    /*
     * Fire all test cases in parallel.
     * Each call: POST { code, custom_input: string }
     * Response:  { status: 'success'|'runtime_error', stdout, stderr, runtime_ms }
     */
    const settled = await Promise.all(
      testInputs.map(tc =>
        postJSON(RUN_URL, { code, custom_input: tc.input })
          .then(res => ({ tc, res, err: null }))
          .catch(err => ({ tc, res: null, err }))
      )
    );

    const results = settled.map(({ tc, res, err }) => {
      if (err || !res) {
        return { input: tc.input, expected: tc.expected, actual: err ? err.message : 'Unknown error',
                 passed: false, runtime_ms: null, isError: true };
      }

      const stdout     = (res.stdout || '').trim();
      const stderr     = (res.stderr || '').trim();
      const hasError   = res.status !== 'success' || !!stderr;
      const displayed  = hasError ? (stderr || 'Runtime error') : stdout;
      const passed     = !hasError && displayed === tc.expected;

      return { input: tc.input, expected: tc.expected, actual: displayed,
               passed, runtime_ms: res.runtime_ms, isError: hasError };
    });

    renderRunResults(results);

  } catch (err) {
    showResultPlaceholder(`Error: ${err.message}`);
  } finally {
    setButtonLoading(runBtn, false, '▶ Run');
    submitBtn.disabled = false;
  }
});

/* ─────────────────────────────────────────────────────────────────
   SUBMIT CODE — calls POST /submissions/submit/<slug>/
   Response shape from submissions/views.py:
     { submission_id, status, runtime_ms, accepted, total,
       test_case_results: [{tc_num, status, input?, expected?, actual?, runtime_ms}] }
───────────────────────────────────────────────────────────────── */
document.getElementById('submit-btn').addEventListener('click', async () => {
  if (!editorInstance) return;

  if (!IS_AUTHENTICATED) {
    showToast('You must be logged in to submit.', 'warn');
    return;
  }

  const runBtn    = document.getElementById('run-btn');
  const submitBtn = document.getElementById('submit-btn');
  const code      = editorInstance.getValue().trim();

  if (!code) { showToast('Editor is empty — write some code first.', 'warn'); return; }

  setButtonLoading(submitBtn, true, '⏳ Submitting…');
  runBtn.disabled = true;
  openBottomPanel('testresult');
  showResultPlaceholder('Submitting your solution against all test cases…');

  try {
    /*
     * submissions/views.py submit_code body: { code, language }
     * language must match Language.slug in DB (e.g. 'python', 'javascript')
     */
    const data = await postJSON(SUBMIT_URL, { code, language: currentLanguage });
    renderSubmitResult(data);
    submissionsLoaded = false; // stale — force reload next Submissions tab open
  } catch (err) {
    showResultPlaceholder(`Submission failed: ${err.message}`);
  } finally {
    setButtonLoading(submitBtn, false, 'Submit');
    runBtn.disabled = false;
  }
});

/* ─────────────────────────────────────────────────────────────────
   RENDER: Run Results
   Input: normalised array of { input, expected, actual, passed, runtime_ms, isError }
───────────────────────────────────────────────────────────────── */
function renderRunResults(results) {
  const placeholder = document.getElementById('result-placeholder');
  const contentArea = document.getElementById('result-content');

  placeholder.style.display = 'none';
  contentArea.style.display = 'flex';
  contentArea.innerHTML     = '';

  const passCount = results.filter(r => r.passed).length;
  const allPassed = passCount === results.length;

  // Overall banner
  const overall = document.createElement('div');
  overall.className = 'result-overall ' + (allPassed ? 'pass' : 'fail');
  overall.innerHTML = `
    ${allPassed
      ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
      : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`}
    ${passCount} / ${results.length} test cases passed
  `;
  contentArea.appendChild(overall);

  const casesWrap = document.createElement('div');
  casesWrap.className = 'result-cases';

  results.forEach((r, idx) => {
    const card = document.createElement('div');
    card.className = `result-case fade-in ${r.passed ? 'pass' : 'fail'}`;

    let headerLabel = r.passed ? 'Passed' : (r.isError ? 'Runtime Error' : 'Wrong Answer');
    card.innerHTML = `
      <div class="result-case-header">
        ${r.passed
          ? `<svg class="case-icon-pass" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
          : `<svg class="case-icon-fail" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`}
        Case ${idx + 1} — ${headerLabel}
      </div>
      <div class="result-case-grid"></div>
    `;

    const grid = card.querySelector('.result-case-grid');
    grid.appendChild(makeResultField('Input',    r.input,    ''));
    grid.appendChild(makeResultField('Expected', r.expected, 'correct'));
    grid.appendChild(makeResultField('Output',   r.actual,   r.passed ? 'correct' : 'wrong'));
    grid.appendChild(makeResultField('Runtime',  r.runtime_ms != null ? `${r.runtime_ms} ms` : 'N/A', ''));

    casesWrap.appendChild(card);
  });

  contentArea.appendChild(casesWrap);
}

function makeResultField(label, value, cls) {
  const wrap = document.createElement('div');
  wrap.className = 'result-field';
  const code     = document.createElement('code');
  code.className = cls;
  code.textContent = String(value ?? '');
  wrap.innerHTML = `<label>${label}</label>`;
  wrap.appendChild(code);
  return wrap;
}

/* ─────────────────────────────────────────────────────────────────
   RENDER: Submit Result
   Adapts submissions/views.py response format exactly.
───────────────────────────────────────────────────────────────── */
function renderSubmitResult(data) {
  const placeholder = document.getElementById('result-placeholder');
  const contentArea = document.getElementById('result-content');

  placeholder.style.display = 'none';
  contentArea.style.display = 'flex';
  contentArea.innerHTML     = '';

  const accepted = data.status === 'Accepted' || data.status === 'accepted';
  const wrap = document.createElement('div');
  wrap.className = 'submission-result fade-in';

  // Big status badge
  const badge = document.createElement('div');
  badge.className = `submission-status-badge ${accepted ? 'accepted' : 'rejected'}`;
  badge.innerHTML = `
    ${accepted
      ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
      : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`}
    ${escapeHtml(data.status)}
  `;
  wrap.appendChild(badge);

  // "X / Y test cases passed"
  if (data.accepted !== undefined && data.total !== undefined) {
    const passLine = document.createElement('div');
    passLine.style.cssText = 'font-size:13px;color:var(--color-text-muted);margin-top:-4px;';
    passLine.textContent   = `${data.accepted} / ${data.total} test cases passed`;
    wrap.appendChild(passLine);
  }

  // Runtime stat card — submissions app returns runtime_ms as a string
  const runtimeMs = parseFloat(data.runtime_ms) || 0;
  const memoryKb  = data.memory_kb              || 0;
  const rtPct     = data.runtime_percentile      || 0;
  const memPct    = data.memory_percentile       || 0;

  const statsGrid = document.createElement('div');
  statsGrid.className = 'submission-stats';

  statsGrid.appendChild(makeStatCard(
    'Runtime',
    `${runtimeMs.toFixed(2)} ms`,
    rtPct ? `Beats ${rtPct.toFixed(1)}% of users` : '—',
    rtPct,
  ));

  if (accepted) {
    statsGrid.appendChild(makeStatCard(
      'Memory',
      memoryKb ? `${(memoryKb / 1024).toFixed(1)} MB` : '—',
      memPct ? `Beats ${memPct.toFixed(1)}% of users` : '—',
      memPct,
    ));
  }

  wrap.appendChild(statsGrid);

  // Test case breakdown
  const tcResults = data.test_case_results || [];
  if (tcResults.length > 0) {
    const breakdown = document.createElement('div');
    breakdown.className   = 'result-cases';
    breakdown.style.marginTop = '8px';

    tcResults.forEach(tc => {
      const isSample = tc.input !== undefined;   // hidden cases omit input/expected/actual
      const tcPassed = tc.status === 'Accepted' || tc.status === 'accepted';

      const card = document.createElement('div');
      card.className = `result-case fade-in ${tcPassed ? 'pass' : 'fail'}`;

      const iconHtml = tcPassed
        ? `<svg class="case-icon-pass" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
        : `<svg class="case-icon-fail" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;

      const header = document.createElement('div');
      header.className   = 'result-case-header';
      header.innerHTML   = `${iconHtml} Case ${tc.tc_num} — ${escapeHtml(tc.status)}`
        + (isSample ? '' : ` <span style="color:var(--color-text-faint);font-size:11px;margin-left:4px;">(hidden)</span>`);
      card.appendChild(header);

      if (isSample) {
        const grid = document.createElement('div');
        grid.className = 'result-case-grid';
        grid.appendChild(makeResultField('Input',    tc.input,    ''));
        grid.appendChild(makeResultField('Expected', tc.expected, 'correct'));
        grid.appendChild(makeResultField('Output',   tc.actual,   tcPassed ? 'correct' : 'wrong'));
        grid.appendChild(makeResultField('Runtime',  `${tc.runtime_ms} ms`, ''));
        card.appendChild(grid);
      }

      breakdown.appendChild(card);
    });

    wrap.appendChild(breakdown);
  }

  contentArea.appendChild(wrap);
}

function makeStatCard(label, value, beatText, pct) {
  const card = document.createElement('div');
  card.className = 'stat-card';
  card.innerHTML = `
    <div class="stat-label">${label}</div>
    <div class="stat-value">${value}</div>
    <div class="stat-beat">${beatText}</div>
    <div class="stat-bar"><div class="stat-bar-fill" style="width:0%"></div></div>
  `;
  requestAnimationFrame(() => {
    const fill = card.querySelector('.stat-bar-fill');
    if (fill) setTimeout(() => { fill.style.width = Math.min(pct, 100) + '%'; }, 80);
  });
  return card;
}

/* ─────────────────────────────────────────────────────────────────
   PLACEHOLDER — used while loading or on error
───────────────────────────────────────────────────────────────── */
function showResultPlaceholder(msg) {
  const placeholder = document.getElementById('result-placeholder');
  const contentArea = document.getElementById('result-content');
  contentArea.style.display = 'none';
  contentArea.innerHTML     = '';
  placeholder.style.display = 'flex';
  placeholder.querySelector('p').textContent = msg;
}

/* ─────────────────────────────────────────────────────────────────
   SUBMISSIONS TAB — lazy-load accepted submissions
───────────────────────────────────────────────────────────────── */
async function loadSubmissions() {
  const tbody   = document.getElementById('submissions-tbody');
  const loading = document.getElementById('submissions-loading');

  tbody.innerHTML       = '';
  loading.style.display = 'flex';
  submissionsLoaded     = true;

  try {
    const data = await getJSON(SOLUTIONS_URL);
    loading.style.display = 'none';

    // Accept either { submissions: [...] } or a bare array
    const list = Array.isArray(data) ? data : (data.submissions || []);

    if (list.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="submissions-empty-row">No accepted submissions yet.</td></tr>`;
      return;
    }

    list.forEach(sub => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="status-accepted">✓ Accepted</span></td>
        <td>${escapeHtml(sub.username || sub.user || '—')}</td>
        <td><span class="lang-badge">${escapeHtml(sub.language || '—')}</span></td>
        <td>${sub.runtime_ms != null ? `${parseFloat(sub.runtime_ms).toFixed(2)} ms` : '—'}</td>
        <td>${sub.memory_kb  != null ? `${(sub.memory_kb / 1024).toFixed(1)} MB`    : '—'}</td>
        <td>${formatDate(sub.submitted_at)}</td>
      `;
      // Click row → load code into editor
      tr.addEventListener('click', () => {
        if (!editorInstance || !sub.code) return;
        const langKey = (sub.language || '').toLowerCase();
        if (STARTER_CODE[langKey]) {
          currentLanguage = langKey;
          document.getElementById('lang-select').value = langKey;
          window.monaco.editor.setModelLanguage(editorInstance.getModel(), MONACO_LANG[langKey]);
        }
        editorInstance.setValue(sub.code);
        showToast(`Loaded ${sub.username || 'user'}'s solution into editor.`, 'info');
      });
      tbody.appendChild(tr);
    });

  } catch (err) {
    loading.style.display = 'none';
    tbody.innerHTML = `<tr><td colspan="6" class="submissions-empty-row">Failed to load: ${escapeHtml(err.message)}</td></tr>`;
  }
}

/* ─────────────────────────────────────────────────────────────────
   DISCUSSION — post top-level comment
───────────────────────────────────────────────────────────────── */
const postCommentBtn = document.getElementById('post-comment-btn');
if (postCommentBtn) {
  postCommentBtn.addEventListener('click', async () => {
    const textarea = document.getElementById('new-comment-box');
    const content  = textarea.value.trim();
    if (!content) { showToast('Comment cannot be empty.', 'warn'); return; }

    postCommentBtn.disabled    = true;
    postCommentBtn.textContent = 'Posting…';

    try {
      const data = await postJSON(COMMENT_URL, { content });
      textarea.value = '';

      const noMsg = document.getElementById('no-comments-msg');
      if (noMsg) noMsg.remove();

      document.getElementById('comments-list')
        .insertBefore(buildCommentCard(data), document.getElementById('comments-list').firstChild);

    } catch (err) {
      showToast(`Failed to post comment: ${err.message}`, 'error');
    } finally {
      postCommentBtn.disabled    = false;
      postCommentBtn.textContent = 'Post Comment';
    }
  });
}

/* ─────────────────────────────────────────────────────────────────
   DISCUSSION — vote (delegated from #comments-list)
───────────────────────────────────────────────────────────────── */
document.getElementById('comments-list').addEventListener('click', async (e) => {
  const voteBtn = e.target.closest('.vote-btn');
  if (!voteBtn) return;
  if (!IS_AUTHENTICATED) { showToast('Log in to vote.', 'warn'); return; }

  const commentId = voteBtn.dataset.id;
  const voteType  = voteBtn.dataset.type;
  voteBtn.disabled = true;

  try {
    const data = await postJSON(`${VOTE_URL_BASE}${commentId}/vote/`, { vote_type: voteType });
    const card    = document.querySelector(`[data-id="${commentId}"]`);
    const upBtn   = card?.querySelector('.upvote-btn');
    const downBtn = card?.querySelector('.downvote-btn');

    if (upBtn)   upBtn.querySelector('.vote-count').textContent   = data.upvotes;
    if (downBtn) downBtn.querySelector('.vote-count').textContent = data.downvotes;
    if (upBtn)   upBtn.classList.toggle('voted',   data.user_voted === 'up');
    if (downBtn) downBtn.classList.toggle('voted',  data.user_voted === 'down');

  } catch (err) {
    showToast(`Vote failed: ${err.message}`, 'error');
  } finally {
    voteBtn.disabled = false;
  }
});

/* ─────────────────────────────────────────────────────────────────
   DISCUSSION — reply toggle / cancel / post (delegated)
───────────────────────────────────────────────────────────────── */
document.getElementById('comments-list').addEventListener('click', async (e) => {
  // Open / close reply box
  const toggleBtn = e.target.closest('.reply-toggle-btn');
  if (toggleBtn) {
    const id      = toggleBtn.dataset.id;
    const compose = document.getElementById('reply-compose-' + id);
    if (!compose) return;
    const wasHidden = compose.classList.contains('hidden');
    compose.classList.toggle('hidden', !wasHidden);
    toggleBtn.setAttribute('aria-expanded', String(wasHidden));
    if (wasHidden) compose.querySelector('.reply-textarea').focus();
    return;
  }

  // Cancel
  const cancelBtn = e.target.closest('.cancel-reply-btn');
  if (cancelBtn) {
    const id      = cancelBtn.dataset.id;
    const compose = document.getElementById('reply-compose-' + id);
    if (compose) { compose.classList.add('hidden'); compose.querySelector('.reply-textarea').value = ''; }
    const toggle = document.querySelector(`.reply-toggle-btn[data-id="${id}"]`);
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    return;
  }

  // Post reply
  const replyBtn = e.target.closest('.post-reply-btn');
  if (!replyBtn) return;

  if (!IS_AUTHENTICATED) { showToast('Log in to reply.', 'warn'); return; }

  const parentId = replyBtn.dataset.parent;
  const compose  = document.getElementById('reply-compose-' + parentId);
  const textarea = compose.querySelector('.reply-textarea');
  const content  = textarea.value.trim();
  if (!content) { showToast('Reply cannot be empty.', 'warn'); return; }

  replyBtn.disabled    = true;
  replyBtn.textContent = 'Posting…';

  try {
    const data = await postJSON(`${REPLY_URL_BASE}${parentId}/reply/`, { content });
    textarea.value = '';
    compose.classList.add('hidden');

    const toggle = document.querySelector(`.reply-toggle-btn[data-id="${parentId}"]`);
    if (toggle) toggle.setAttribute('aria-expanded', 'false');

    const repliesBox = document.getElementById('replies-' + parentId);
    if (repliesBox) { repliesBox.classList.remove('hidden'); repliesBox.appendChild(buildReplyCard(data)); }

  } catch (err) {
    showToast(`Failed to reply: ${err.message}`, 'error');
  } finally {
    replyBtn.disabled    = false;
    replyBtn.textContent = 'Reply';
  }
});

/* ─────────────────────────────────────────────────────────────────
   DOM BUILDERS — newly posted comment / reply cards
───────────────────────────────────────────────────────────────── */
function buildCommentCard(data) {
  const card = document.createElement('div');
  card.className  = 'comment-card fade-in';
  card.dataset.id = data.id;

  const name    = data.username || data.user || 'User';
  const initial = name[0].toUpperCase();

  card.innerHTML = `
    <div class="comment-header">
      <span class="comment-avatar">${escapeHtml(initial)}</span>
      <span class="comment-username">${escapeHtml(name)}</span>
      <span class="comment-dot">·</span>
      <span class="comment-time">just now</span>
    </div>
    <div class="comment-body">${escapeHtml(data.content)}</div>
    <div class="comment-actions">
      <button class="vote-btn upvote-btn"   data-id="${data.id}" data-type="up"   aria-label="Upvote">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="12,4 22,20 2,20"/></svg>
        <span class="vote-count">0</span>
      </button>
      <button class="vote-btn downvote-btn" data-id="${data.id}" data-type="down" aria-label="Downvote">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="12,20 22,4 2,4"/></svg>
        <span class="vote-count">0</span>
      </button>
      <button class="reply-toggle-btn" data-id="${data.id}" aria-expanded="false">Reply</button>
    </div>
    <div class="reply-compose hidden" id="reply-compose-${data.id}">
      <textarea class="comment-textarea reply-textarea" placeholder="Write a reply…" rows="2"></textarea>
      <div class="compose-footer">
        <button class="btn-primary btn-sm post-reply-btn"  data-parent="${data.id}">Reply</button>
        <button class="btn-ghost   btn-sm cancel-reply-btn" data-id="${data.id}">Cancel</button>
      </div>
    </div>
    <div class="replies-container hidden" id="replies-${data.id}"></div>
  `;
  return card;
}

function buildReplyCard(data) {
  const card = document.createElement('div');
  card.className  = 'comment-card reply-card fade-in';
  card.dataset.id = data.id;

  const name    = data.username || data.user || 'User';
  const initial = name[0].toUpperCase();

  card.innerHTML = `
    <div class="comment-header">
      <span class="comment-avatar sm">${escapeHtml(initial)}</span>
      <span class="comment-username">${escapeHtml(name)}</span>
      <span class="comment-dot">·</span>
      <span class="comment-time">just now</span>
    </div>
    <div class="comment-body">${escapeHtml(data.content)}</div>
    <div class="comment-actions">
      <button class="vote-btn upvote-btn"   data-id="${data.id}" data-type="up"   aria-label="Upvote">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="12,4 22,20 2,20"/></svg>
        <span class="vote-count">0</span>
      </button>
      <button class="vote-btn downvote-btn" data-id="${data.id}" data-type="down" aria-label="Downvote">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="12,20 22,4 2,4"/></svg>
        <span class="vote-count">0</span>
      </button>
    </div>
  `;
  return card;
}

/* ─────────────────────────────────────────────────────────────────
   PROBLEM LIST PANEL
───────────────────────────────────────────────────────────────── */
function initProblemListPanel() {
  const toggleBtn   = document.getElementById('toggle-pl');
  const panel       = document.getElementById('pl-panel');
  const backdrop    = document.getElementById('pl-backdrop');
  const closeBtn    = document.getElementById('pl-close');
  const searchInput = document.getElementById('pl-search');
  const filterBtns  = document.querySelectorAll('.pl-filter');

  function openPanel()  {
    panel.classList.add('open');
    backdrop.classList.add('active');
    toggleBtn.setAttribute('aria-expanded', 'true');
    searchInput.focus();
    if (!plProblemsCache) fetchProblems();
  }
  function closePanel() {
    panel.classList.remove('open');
    backdrop.classList.remove('active');
    toggleBtn.setAttribute('aria-expanded', 'false');
  }

  toggleBtn.addEventListener('click', () =>
    panel.classList.contains('open') ? closePanel() : openPanel()
  );
  closeBtn.addEventListener('click', closePanel);
  backdrop.addEventListener('click', closePanel);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && panel.classList.contains('open')) closePanel();
  });

  searchInput.addEventListener('input', () =>
    renderProblemList(plProblemsCache, searchInput.value, plCurrentFilter)
  );
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      plCurrentFilter = btn.dataset.diff;
      renderProblemList(plProblemsCache, searchInput.value, plCurrentFilter);
    });
  });
}

async function fetchProblems() {
  const listEl = document.getElementById('pl-list');
  listEl.innerHTML = `
    <div class="pl-loading">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
        <line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/>
        <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
        <line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/>
        <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>
      </svg>
      Loading problems…
    </div>`;
  try {
    const data = await getJSON(PROB_PANEL_URL);
    plProblemsCache = data.problems || [];
    renderProblemList(plProblemsCache, '', plCurrentFilter);
  } catch (err) {
    listEl.innerHTML = `<div class="pl-loading" style="color:var(--color-fail)">Failed: ${escapeHtml(err.message)}</div>`;
  }
}

function renderProblemList(problems, query, diffFilter) {
  const listEl = document.getElementById('pl-list');
  if (!problems) { listEl.innerHTML = '<div class="pl-loading">Loading…</div>'; return; }

  const q = (query || '').toLowerCase().trim();
  const filtered = problems.filter(p => {
    const matchDiff  = diffFilter === 'all' || p.difficulty.toLowerCase() === diffFilter;
    const matchQuery = !q || p.title.toLowerCase().includes(q) || String(p.order_num).includes(q);
    return matchDiff && matchQuery;
  });

  if (filtered.length === 0) {
    listEl.innerHTML = `<div class="pl-loading" style="color:var(--color-text-faint)">No problems found.</div>`;
    return;
  }

  const ul = document.createElement('ul');
  ul.className = 'pl-items';

  filtered.forEach(prob => {
    const isCurrent = prob.slug === PROBLEM_SLUG;
    const li = document.createElement('li');
    li.className = 'pl-item' + (prob.solved ? ' solved' : '') + (isCurrent ? ' current' : '');

    const diffLabel = prob.difficulty.charAt(0).toUpperCase() + prob.difficulty.slice(1).toLowerCase();
    li.innerHTML = `
      <span class="pl-check">${prob.solved ? '✓' : ''}</span>
      <span class="pl-num">${prob.order_num}</span>
      <a class="pl-link" href="${prob.url}" title="${escapeHtml(prob.title)}">${escapeHtml(prob.title)}</a>
      <span class="pl-item-diff ${prob.difficulty.toLowerCase()}">${diffLabel}</span>
    `;
    ul.appendChild(li);
  });

  listEl.innerHTML = '';
  listEl.appendChild(ul);
}

/* ─────────────────────────────────────────────────────────────────
   DRAG DIVIDER — resize left/right panels
───────────────────────────────────────────────────────────────── */
function initDragDivider() {
  const divider   = document.getElementById('drag-divider');
  const leftPanel = document.getElementById('left-panel');
  const layout    = document.getElementById('main-layout');

  let dragging = false, startX = 0, startW = 0;

  divider.addEventListener('mousedown', e => {
    dragging = true; startX = e.clientX;
    startW   = leftPanel.getBoundingClientRect().width;
    divider.classList.add('dragging');
    document.body.style.userSelect = 'none';
    document.body.style.cursor     = 'col-resize';
  });
  document.addEventListener('mousemove', e => {
    if (!dragging) return;
    const newW = Math.min(
      Math.max(startW + (e.clientX - startX), 280),
      layout.getBoundingClientRect().width * 0.75,
    );
    leftPanel.style.width = newW + 'px';
  });
  document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    divider.classList.remove('dragging');
    document.body.style.userSelect = '';
    document.body.style.cursor     = '';
    if (editorInstance) editorInstance.layout();
  });
}

/* ─────────────────────────────────────────────────────────────────
   BUTTON LOADING STATE
───────────────────────────────────────────────────────────────── */
function setButtonLoading(btn, isLoading, label) {
  btn.disabled    = isLoading;
  btn.textContent = label;
  btn.classList.toggle('loading', isLoading);
}

/* ─────────────────────────────────────────────────────────────────
   TOAST NOTIFICATIONS
───────────────────────────────────────────────────────────────── */
(function buildToastHost() {
  if (document.getElementById('toast-container')) return;
  const el = document.createElement('div');
  el.id = 'toast-container';
  el.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
  document.body.appendChild(el);
})();

function showToast(message, type) {
  const c = { info: 'var(--color-border)', warn: 'var(--color-medium)', error: 'var(--color-fail)', success: 'var(--color-pass)' };
  const border = c[type] || c.info;
  const toast  = document.createElement('div');
  toast.style.cssText = `
    background:var(--color-panel-alt);border:1px solid ${border};
    color:${border};padding:9px 14px;border-radius:6px;font-size:13px;
    font-family:var(--font-ui,sans-serif);max-width:320px;pointer-events:all;
    box-shadow:0 4px 16px var(--color-shadow,rgba(0,0,0,.4));
    animation:fadeInUp .2s ease forwards;transition:opacity .3s ease;
  `;
  toast.textContent = message;
  document.getElementById('toast-container').appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 350); }, 3200);
}

/* ─────────────────────────────────────────────────────────────────
   UTILITIES
───────────────────────────────────────────────────────────────── */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return iso || '—'; }
}

/* ─────────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initLeftTabs();
  initBottomPanel();
  initDragDivider();
  initProblemListPanel();
});