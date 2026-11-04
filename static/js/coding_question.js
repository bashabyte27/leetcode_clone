(() => {
  "use strict";

  let activeQuestion = null;
  let activeCleanup = null;

  const escapeHtml = (value) => String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

  const AssessmentCodingQuestion = {
    init({ container, question, request, onAnswerChange, allowPaste, notify }) {
      this.destroy();
      activeQuestion = question;
      const editorNode = container.querySelector("[data-monaco-editor]");
      const languageSelect = container.querySelector("[data-coding-language]");
      const runButton = container.querySelector("[data-run-code]");
      const submitButton = container.querySelector("[data-submit-code]");
      const resultPanel = container.querySelector("[data-test-results]");
      const cleanups = [];
      let editor = null;
      let saveTimer = null;
      let activeLanguage = languageSelect?.value || "";
      const languageById = new Map(
        (question.languages || []).map((language) => [String(language.id), language]),
      );

      const activeLanguageData = () => languageById.get(String(activeLanguage));
      const currentCode = () => editor ? editor.getValue() : "";
      const updateAttempted = () => onAnswerChange(
        Boolean(currentCode().trim()) || (question.submissions || []).length > 0,
      );
      const saveCode = () => {
        window.clearTimeout(saveTimer);
        if (!editor || !activeLanguage) return Promise.resolve();
        const code = currentCode();
        updateAttempted();
        return request("draft", {
          question_id: question.id,
          language_id: Number(activeLanguage),
          source_code: code,
        });
      };
      const scheduleSave = () => {
        window.clearTimeout(saveTimer);
        updateAttempted();
        saveTimer = window.setTimeout(() => {
          saveCode().catch((error) => notify(`Draft save failed: ${error.message}`, "warning"));
        }, 700);
      };
      const showResults = (results, submitted) => {
        if (!resultPanel) return;
        const rows = (results || []).map((result) => {
          const label = result.position ? `Case ${result.position}` : "Test";
          return `<article class="exam-run-result"><strong>${escapeHtml(label)} · ${escapeHtml(result.status)}</strong>${
            result.input !== undefined
              ? `<p>Input</p><pre>${escapeHtml(result.input)}</pre><p>Expected</p><pre>${escapeHtml(result.expected_output)}</pre><p>Actual</p><pre>${escapeHtml(result.actual_output)}</pre>`
              : ""
          }${result.error ? `<pre>${escapeHtml(result.error)}</pre>` : ""}</article>`;
        }).join("");
        const heading = submitted
          ? `Submission: ${escapeHtml(submitted.status)} · ${submitted.passed}/${submitted.total} passed · ${escapeHtml(submitted.score)}/${escapeHtml(submitted.max_score)} marks`
          : "Run results";
        resultPanel.innerHTML = `<p class="exam-run-result-summary">${heading}</p>${rows || "<p>No results returned.</p>"}`;
        container.querySelector('[data-test-tab="result"]')?.click();
        if (submitted) {
          const list = container.querySelector(".exam-own-submissions");
          if (list) {
            const details = document.createElement("details");
            details.className = "exam-own-submission";
            details.open = true;
            const summary = document.createElement("summary");
            summary.textContent = `${submitted.status} · ${submitted.score} marks · just now`;
            const code = document.createElement("pre");
            const source = document.createElement("code");
            source.textContent = currentCode();
            code.append(source);
            details.append(summary, code);
            list.prepend(details);
          }
        }
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
        runButton.disabled = true;
        submitButton.disabled = true;
        const action = submit ? "submit" : "run";
        runButton.textContent = submit ? "Run" : "Running…";
        submitButton.textContent = submit ? "Submitting…" : "Submit";
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
            return;
          }
          showResults(result.results, submit ? result : null);
          if (submit) updateAttempted();
          notify(submit ? "Submission evaluated." : "Sample tests completed.", "success");
        } catch (error) {
          notify(`Could not ${action} code: ${error.message}`, "danger");
        } finally {
          runButton.disabled = false;
          submitButton.disabled = false;
          runButton.textContent = "Run";
          submitButton.textContent = "Submit";
        }
      };
      const listen = (element, type, callback) => {
        if (!element) return;
        element.addEventListener(type, callback);
        cleanups.push(() => element.removeEventListener(type, callback));
      };
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
          const monacoLanguage = {
            python: "python",
            java: "java",
            cpp: "cpp",
            c: "c",
            javascript: "javascript",
            go: "go",
            rust: "rust",
          }[language?.slug] || "plaintext";
          editor = window.monaco.editor.create(editorNode, {
            value: language?.draft || language?.starter_code || "",
            language: monacoLanguage,
            theme: document.documentElement.dataset.theme === "light" ? "vs" : "vs-dark",
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 14,
            scrollBeyondLastLine: false,
          });
          window.assessmentEditor = editor;
          editor.onDidChangeModelContent(scheduleSave);
          if (!allowPaste) {
            editor.onKeyDown((event) => {
              if ((event.ctrlKey || event.metaKey) && event.keyCode === window.monaco.KeyCode.KeyV) {
                event.preventDefault();
                event.stopPropagation();
              }
            });
          }
          updateAttempted();
        });
      };
      initializeEditor();

      listen(languageSelect, "change", async () => {
        try {
          await saveCode();
          activeLanguage = languageSelect.value;
          const language = activeLanguageData();
          if (editor) editor.setValue(language?.draft || language?.starter_code || "");
        } catch (error) {
          languageSelect.value = activeLanguage;
          notify(`Could not save your code before changing language: ${error.message}`, "warning");
        }
      });

      activeCleanup = () => {
        window.clearTimeout(saveTimer);
        cleanups.forEach((cleanup) => cleanup());
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
