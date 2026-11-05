(() => {
  "use strict";

  let activeQuestion = null;
  let activeCleanup = null;

  const SPLIT_KEY_V = "bb-exam-split-v2";
  const SPLIT_KEY_H = "bb-exam-split-h2";

  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const LOCK_ICON = '<svg class="exam-ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';
  const MONACO_LANGUAGES = {
    python: "python", java: "java", cpp: "cpp", c: "c", javascript: "javascript",
    typescript: "typescript", go: "go", rust: "rust", csharp: "csharp", kotlin: "kotlin",
    ruby: "ruby", php: "php", swift: "swift",
  };
  const LANGUAGE_BADGES = {
    python: "Py", java: "Jv", cpp: "C++", c: "C", javascript: "JS", typescript: "TS",
    go: "Go", rust: "Rs", csharp: "C#", kotlin: "Kt", ruby: "Rb", php: "PHP", swift: "Sw",
  };

  // Maps any judge status text onto one of: ok | fail | warn | neutral
  const statusKind = (status) => {
    const text = String(status || "").toLowerCase();
    if (/partial/.test(text)) return "warn";
    if (/wrong|incorrect|fail|reject/.test(text)) return "fail";
    if (/accept|pass|correct|success|^ok$/.test(text)) return "ok";
    if (/time|memory|runtime|compil|error|limit|exceed|crash|signal|internal/.test(text)) return "warn";
    return "neutral";
  };

  const displayValue = (value) => {
    const text = value === undefined || value === null ? "" : String(value);
    return text.length ? escapeHtml(text) : "—";
  };

  const setLabel = (button, text) => {
    if (!button) return;
    const label = button.querySelector(".btn-label");
    if (label) label.textContent = text;
    else button.textContent = text;
  };

  const AssessmentCodingQuestion = {
    init({ container, question, request, onAnswerChange, allowPaste, notify }) {
      this.destroy();
      activeQuestion = question;
      const editorNode = container.querySelector("[data-monaco-editor]");
      const languageSelect = container.querySelector("[data-coding-language]");
      const languageBadge = container.querySelector("[data-lang-badge]");
      const runButton = container.querySelector("[data-run-code]");
      const submitButton = container.querySelector("[data-submit-code]");
      const resultPanel = container.querySelector("[data-test-results]");
      const saveStateNode = container.querySelector("[data-save-state]");
      const cursorNode = container.querySelector("[data-cursor-pos]");
      const cleanups = [];
      let editor = null;
      let saveTimer = null;
      let activeLanguage = languageSelect?.value || "";
      const languageById = new Map(
        (question.languages || []).map((language) => [String(language.id), language]),
      );

      const activeLanguageData = () => languageById.get(String(activeLanguage));
      const activeSlug = () => (
        activeLanguageData()?.slug
        || languageSelect?.selectedOptions?.[0]?.dataset.slug
        || ""
      );
      const currentCode = () => editor ? editor.getValue() : "";
      const updateAttempted = () => onAnswerChange(
        Boolean(currentCode().trim()) || (question.submissions || []).length > 0,
      );

      const SAVE_LABELS = {
        saved: "Saved", saving: "Saving…", error: "Save failed", queued: "Offline · will sync",
      };
      const setSaveState = (state) => {
        if (!saveStateNode) return;
        saveStateNode.dataset.state = state;
        saveStateNode.textContent = SAVE_LABELS[state] || "Saved";
      };
      const updateLanguageBadge = () => {
        if (!languageBadge) return;
        const slug = activeSlug();
        languageBadge.textContent = LANGUAGE_BADGES[slug]
          || (slug ? slug.slice(0, 2).toUpperCase() : "{ }");
      };

      const saveCode = () => {
        window.clearTimeout(saveTimer);
        if (!editor || !activeLanguage) return Promise.resolve();
        const code = currentCode();
        updateAttempted();
        setSaveState("saving");
        return request("draft", {
          question_id: question.id,
          language_id: Number(activeLanguage),
          source_code: code,
        }).then((result) => {
          setSaveState(result?.queued ? "queued" : "saved");
          return result;
        }).catch((error) => {
          setSaveState("error");
          throw error;
        });
      };
      const scheduleSave = () => {
        window.clearTimeout(saveTimer);
        updateAttempted();
        setSaveState("saving");
        saveTimer = window.setTimeout(() => {
          saveCode().catch((error) => notify(`Draft save failed: ${error.message}`, "warning"));
        }, 700);
      };

      /* ---------------- Results rendering ---------------- */
      const activateTestTab = (name) => {
        container.querySelector(`[data-test-tab="${name}"]`)?.click();
      };

      const showLoading = (verb) => {
        if (!resultPanel) return;
        resultPanel.innerHTML = `<div class="exam-result-loading"><p><span class="exam-spinner" aria-hidden="true"></span>${escapeHtml(verb)}…</p><i></i><i></i></div>`;
        activateTestTab("result");
      };

      const showResults = (results, submitted) => {
        if (!resultPanel) return;
        const rows = (Array.isArray(results) ? results : []).map((result, index) => {
          const kind = statusKind(result.status);
          const hidden = Boolean(result.hidden || result.is_hidden)
            || (Boolean(submitted) && result.input === undefined && result.input_data === undefined);
          return { result, index, kind, hidden };
        });
        const passed = submitted && Number.isFinite(Number(submitted.passed))
          ? Number(submitted.passed)
          : rows.filter((row) => row.kind === "ok").length;
        const total = submitted && Number.isFinite(Number(submitted.total))
          ? Number(submitted.total)
          : rows.length;

        let headlineStatus;
        let headlineKind;
        if (submitted) {
          headlineStatus = submitted.status || (passed === total ? "Accepted" : "Wrong Answer");
          headlineKind = statusKind(headlineStatus);
        } else {
          const firstProblem = rows.find((row) => row.kind !== "ok");
          headlineStatus = firstProblem ? (firstProblem.result.status || "Failed") : "Samples passed";
          headlineKind = firstProblem ? firstProblem.kind : "ok";
          if (!rows.length) { headlineStatus = "No results"; headlineKind = "neutral"; }
        }
        const scoreText = submitted
          ? `<span class="exam-result-score">${escapeHtml(submitted.score)} / ${escapeHtml(submitted.max_score)} marks</span>`
          : '<span class="exam-result-score">Sample run · not graded</span>';
        const segments = rows.map((row, i) => `<i class="${row.kind === "ok" || row.kind === "fail" || row.kind === "warn" ? row.kind : ""}" style="animation-delay:${i * 40}ms"></i>`).join("");
        const summary = `<div class="exam-result-summary"><div class="exam-result-headline"><span class="exam-result-badge is-${headlineKind}">${escapeHtml(headlineStatus)}</span><strong>${passed} / ${total} cases passed</strong>${scoreText}</div>${segments ? `<div class="exam-result-bar" aria-hidden="true">${segments}</div>` : ""}</div>`;

        const allHidden = rows.length > 0 && rows.every((row) => row.hidden);
        const body = rows.map(({ result, index, kind, hidden }) => {
          const position = result.position || index + 1;
          const label = hidden ? `Hidden case ${position}` : `Case ${position}`;
          const lockChip = `<span class="exam-hidden-chip">${LOCK_ICON}Hidden</span>`;
          const input = hidden ? lockChip : displayValue(result.input ?? result.input_data);
          const expected = hidden ? lockChip : displayValue(result.expected_output);
          const actualRaw = result.actual_output ?? result.stdout ?? result.your_output ?? result.output;
          const actual = !hidden && kind !== "ok" && actualRaw !== undefined && actualRaw !== null && String(actualRaw).length
            ? `<small><b>Your output:</b> ${escapeHtml(actualRaw)}</small>`
            : "";
          const error = result.error ? `<small>${escapeHtml(result.error)}</small>` : "";
          const resultCell = `<td><span class="exam-result-status is-${kind}">${escapeHtml(result.status || "Unknown")}</span>${actual}${error}</td>`;
          const head = `<th scope="row">${escapeHtml(label)}</th>`;
          return `<tr style="--i:${index}">${head}${allHidden ? "" : `<td class="cell-code">${input}</td><td class="cell-code">${expected}</td>`}${resultCell}</tr>`;
        }).join("");
        const columns = allHidden
          ? '<th scope="col">Case</th><th scope="col">Result</th>'
          : '<th scope="col">Case</th><th scope="col">Sample input</th><th scope="col">Sample output</th><th scope="col">Result</th>';
        resultPanel.innerHTML = `${summary}${
          rows.length
            ? `<div class="exam-results-table-wrap"><table class="exam-results-table"><thead><tr>${columns}</tr></thead><tbody>${body}</tbody></table></div>`
            : "<p>No results returned.</p>"
        }`;
        activateTestTab("result");

        if (submitted) {
          const list = container.querySelector(".exam-own-submissions");
          if (list) {
            list.querySelector("p.text-secondary")?.remove();
            const details = document.createElement("details");
            details.className = "exam-own-submission";
            details.open = true;
            const summaryNode = document.createElement("summary");
            summaryNode.textContent = `${submitted.status} · ${submitted.score} marks · just now`;
            const code = document.createElement("pre");
            const source = document.createElement("code");
            source.textContent = currentCode();
            code.append(source);
            details.append(summaryNode, code);
            list.prepend(details);
          }
        }
      };

      const setBusy = (submit, busy) => {
        [runButton, submitButton].forEach((button) => { if (button) button.disabled = busy; });
        runButton?.classList.toggle("is-busy", busy && !submit);
        submitButton?.classList.toggle("is-busy", busy && submit);
        setLabel(runButton, busy && !submit ? "Running" : "Run");
        setLabel(submitButton, busy && submit ? "Submitting" : "Submit");
      };

      const run = async (submit) => {
        if (!editor) {
          notify("The code editor is still loading. Please wait a moment and try again.", "warning");
          return;
        }
        if (!runButton || !submitButton) {
          notify("The coding controls could not be loaded. Reload the assessment and try again.", "danger");
          return;
        }
        if (runButton.disabled) return;
        const action = submit ? "submit" : "run";
        setBusy(submit, true);
        showLoading(submit ? "Evaluating all test cases" : "Running sample cases");
        try {
          await saveCode();
          const endpoint = submit ? "submitCode" : "runCode";
          const result = await request(endpoint, {
            question_id: question.id,
            language_id: Number(activeLanguage),
            source_code: currentCode(),
          });
          if (result.queued) {
            notify("Code execution is unavailable offline. Your draft is saved and will sync when online.", "warning");
            if (resultPanel) resultPanel.innerHTML = '<p class="text-secondary">You are offline. Run again once you are back online.</p>';
            return;
          }
          showResults(submit ? result.test_cases : result.results, submit ? result : null);
          if (submit) updateAttempted();
          notify(submit ? "Submission evaluated." : "Sample tests completed.", "success");
        } catch (error) {
          if (resultPanel) resultPanel.innerHTML = `<p class="text-danger">Could not ${action} code: ${escapeHtml(error.message)}</p>`;
          notify(`Could not ${action} code: ${error.message}`, "danger");
        } finally {
          setBusy(submit, false);
        }
      };

      const listen = (element, type, callback, options) => {
        if (!element) return;
        element.addEventListener(type, callback, options);
        cleanups.push(() => element.removeEventListener(type, callback, options));
      };

      /* ---------------- Tabs ---------------- */
      container.querySelectorAll("[data-case-position]").forEach((button) => {
        listen(button, "click", () => {
          container.querySelectorAll("[data-case-position]").forEach((item) => item.classList.toggle("active", item === button));
          container.querySelectorAll("[data-case-content]").forEach((item) => item.classList.toggle("d-none", item.dataset.caseContent !== button.dataset.casePosition));
        });
      });
      container.querySelectorAll("[data-coding-tab]").forEach((button) => {
        listen(button, "click", () => {
          const name = button.dataset.codingTab;
          container.querySelectorAll("[data-coding-tab]").forEach((item) => {
            const selected = item === button;
            item.classList.toggle("active", selected);
            item.setAttribute("aria-selected", String(selected));
          });
          container.querySelectorAll("[data-coding-panel]").forEach((panel) => {
            const selected = panel.dataset.codingPanel === name;
            panel.classList.toggle("active", selected);
            panel.hidden = !selected;
          });
        });
      });
      container.querySelectorAll("[data-test-tab]").forEach((button) => {
        listen(button, "click", () => {
          container.querySelectorAll("[data-test-tab]").forEach((item) => {
            const selected = item === button;
            item.classList.toggle("active", selected);
            item.setAttribute("aria-selected", String(selected));
          });
          container.querySelectorAll("[data-test-panel]").forEach((panel) => {
            const selected = panel.dataset.testPanel === button.dataset.testTab;
            panel.classList.toggle("active", selected);
            panel.hidden = !selected;
          });
        });
      });
      listen(runButton, "click", () => { void run(false); });
      listen(submitButton, "click", () => { void run(true); });
      if (runButton) runButton.title = "Run sample cases (Ctrl + Enter)";

      /* ---------------- Resizable panes ---------------- */
      const verticalSplitter = container.querySelector(".exam-coding-splitter");
      const horizontalSplitter = container.querySelector(".exam-console-splitter");
      const workspace = container.querySelector(".exam-coding-workspace");
      const compiler = container.querySelector(".exam-coding-editor");
      const editorStage = container.querySelector(".exam-editor-stage");
      let splitLeft = 50;
      let bottomHeight = 210;
      try {
        splitLeft = Number(localStorage.getItem(SPLIT_KEY_V)) || 50;
        bottomHeight = Number(localStorage.getItem(SPLIT_KEY_H)) || 210;
      } catch (error) {
        notify(`Could not restore editor layout: ${error.message}`, "warning");
      }
      const persist = (key, value) => {
        try { localStorage.setItem(key, String(value)); } catch (error) { /* layout is a convenience only */ }
      };
      const applySplits = () => {
        if (workspace) workspace.style.setProperty("--split-left", `${splitLeft}%`);
        if (compiler) compiler.style.setProperty("--bottom-h", `${bottomHeight}px`);
        verticalSplitter?.setAttribute("aria-valuenow", String(Math.round(splitLeft)));
        window.assessmentEditor?.layout?.();
      };
      const dragSplitter = (splitter, axis, move) => {
        if (!splitter) return;
        listen(splitter, "pointerdown", (event) => {
          if (event.button !== undefined && event.button !== 0) return;
          event.preventDefault();
          splitter.setPointerCapture(event.pointerId);
          splitter.classList.add("is-dragging");
          document.body.classList.add("exam-resizing", `exam-resizing-${axis}`);
          const startX = event.clientX;
          const startY = event.clientY;
          const startLeft = splitLeft;
          const startHeight = bottomHeight;
          let frame = 0;
          const onMove = (moveEvent) => {
            window.cancelAnimationFrame(frame);
            frame = window.requestAnimationFrame(() => move(moveEvent, startX, startY, startLeft, startHeight));
          };
          const onUp = () => {
            window.cancelAnimationFrame(frame);
            try { splitter.releasePointerCapture(event.pointerId); } catch (error) { /* already released */ }
            splitter.classList.remove("is-dragging");
            document.body.classList.remove("exam-resizing", "exam-resizing-x", "exam-resizing-y");
            splitter.removeEventListener("pointermove", onMove);
            splitter.removeEventListener("pointerup", onUp);
            splitter.removeEventListener("pointercancel", onUp);
          };
          splitter.addEventListener("pointermove", onMove);
          splitter.addEventListener("pointerup", onUp);
          splitter.addEventListener("pointercancel", onUp);
        });
      };
      dragSplitter(verticalSplitter, "x", (event, startX, unusedY, startLeft) => {
        const bounds = workspace.getBoundingClientRect();
        splitLeft = Math.min(70, Math.max(30, startLeft + ((event.clientX - startX) / bounds.width) * 100));
        applySplits();
        persist(SPLIT_KEY_V, splitLeft);
      });
      dragSplitter(horizontalSplitter, "y", (event, unusedX, startY, unusedLeft, startHeight) => {
        const bounds = compiler.getBoundingClientRect();
        bottomHeight = Math.min(bounds.height * 0.7, Math.max(44, startHeight + startY - event.clientY));
        applySplits();
        persist(SPLIT_KEY_H, bottomHeight);
      });
      listen(verticalSplitter, "dblclick", () => { splitLeft = 50; applySplits(); persist(SPLIT_KEY_V, splitLeft); });
      listen(horizontalSplitter, "dblclick", () => { bottomHeight = bottomHeight <= 44 ? 210 : 44; applySplits(); persist(SPLIT_KEY_H, bottomHeight); });
      listen(verticalSplitter, "keydown", (event) => {
        const step = event.shiftKey ? 10 : 2;
        if (event.key === "Home") splitLeft = 50;
        else if (event.key === "ArrowLeft") splitLeft = Math.max(30, splitLeft - step);
        else if (event.key === "ArrowRight") splitLeft = Math.min(70, splitLeft + step);
        else return;
        event.preventDefault();
        applySplits();
        persist(SPLIT_KEY_V, splitLeft);
      });
      listen(horizontalSplitter, "keydown", (event) => {
        if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
        bottomHeight = Math.max(44, bottomHeight + (event.key === "ArrowUp" ? 16 : -16));
        event.preventDefault();
        applySplits();
        persist(SPLIT_KEY_H, bottomHeight);
      });
      if (window.ResizeObserver && editorStage) {
        const observer = new ResizeObserver(() => window.assessmentEditor?.layout?.());
        observer.observe(editorStage);
        cleanups.push(() => observer.disconnect());
      }
      applySplits();
      updateLanguageBadge();

      /* ---------------- Monaco ---------------- */
      const initializeEditor = () => {
        if (!window.require || !editorNode) {
          notify("The code editor could not be loaded. Check your connection and reload the assessment.", "danger");
          return;
        }
        window.require.config({
          paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs" },
        });
        window.require(["vs/editor/editor.main"], () => {
          if (!editorNode.isConnected || activeQuestion?.id !== question.id) return;
          const language = activeLanguageData();
          const monacoLanguage = MONACO_LANGUAGES[language?.slug] || "plaintext";
          editor = window.monaco.editor.create(editorNode, {
            value: language?.draft || language?.starter_code || "",
            language: monacoLanguage,
            theme: document.documentElement.dataset.theme === "light" ? "vs" : "vs-dark",
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 14,
            lineHeight: 22,
            fontFamily: '"JetBrains Mono", "SF Mono", Consolas, "Liberation Mono", monospace',
            fontLigatures: false,
            padding: { top: 14, bottom: 14 },
            lineNumbersMinChars: 3,
            scrollBeyondLastLine: false,
            smoothScrolling: true,
            cursorSmoothCaretAnimation: "on",
            cursorBlinking: "smooth",
            roundedSelection: true,
            overviewRulerBorder: false,
            renderLineHighlight: "line",
            scrollbar: { verticalScrollbarSize: 10, horizontalScrollbarSize: 10 },
          });
          window.assessmentEditor = editor;
          editor.onDidChangeModelContent(scheduleSave);
          editor.onDidChangeCursorPosition((event) => {
            if (cursorNode) cursorNode.textContent = `Ln ${event.position.lineNumber}, Col ${event.position.column}`;
          });
          editor.addCommand(
            window.monaco.KeyMod.CtrlCmd | window.monaco.KeyCode.Enter,
            () => { void run(false); },
          );
          if (!allowPaste) {
            editor.onKeyDown((event) => {
              if ((event.ctrlKey || event.metaKey) && event.keyCode === window.monaco.KeyCode.KeyV) {
                event.preventDefault();
                event.stopPropagation();
              }
            });
          }
          setSaveState("saved");
          updateAttempted();
        });
      };
      initializeEditor();

      listen(languageSelect, "change", async () => {
        try {
          await saveCode();
          activeLanguage = languageSelect.value;
          const language = activeLanguageData();
          updateLanguageBadge();
          if (editor) {
            // Keep syntax highlighting in step with the chosen language.
            window.monaco.editor.setModelLanguage(
              editor.getModel(),
              MONACO_LANGUAGES[language?.slug] || "plaintext",
            );
            editor.setValue(language?.draft || language?.starter_code || "");
          }
        } catch (error) {
          languageSelect.value = activeLanguage;
          notify(`Could not save your code before changing language: ${error.message}`, "warning");
        }
      });

      activeCleanup = () => {
        window.clearTimeout(saveTimer);
        cleanups.forEach((cleanup) => cleanup());
        document.body.classList.remove("exam-resizing", "exam-resizing-x", "exam-resizing-y");
        editor?.dispose();
        editor = null;
        if (window.assessmentEditor) window.assessmentEditor = null;
        activeQuestion = null;
      };
      return {
        save: () => saveCode(),
        clear: () => {
          if (editor) editor.setValue("");
          updateAttempted();
          return saveCode();
        },
      };
    },

    destroy() {
      activeCleanup?.();
      activeCleanup = null;
    },
  };

  window.AssessmentCodingQuestion = AssessmentCodingQuestion;
})();