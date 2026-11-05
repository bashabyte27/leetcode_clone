(() => {
  "use strict";

  let activeCleanup = null;
  const SPLIT_KEY_V = "bb-exam-split-v2";

  const AssessmentMCQ = {
    init({ container, question, request, onAnswerChange }) {
      this.destroy();
      const inputs = [...container.querySelectorAll('input[name^="mcq-"]')];
      const status = container.querySelector(".exam-save-state");
      const countNode = container.querySelector("[data-mcq-count]");
      const multiple = container.querySelector(".exam-mcq-options")?.dataset.multiple === "true";
      const cleanups = [];
      let saveTimer = null;
      let pending = Promise.resolve();

      const listen = (element, type, callback, options) => {
        if (!element) return;
        element.addEventListener(type, callback, options);
        cleanups.push(() => element.removeEventListener(type, callback, options));
      };

      const updateCount = () => {
        if (!countNode) return;
        const chosen = inputs.filter((input) => input.checked).length;
        countNode.textContent = multiple
          ? `${chosen} of ${inputs.length} selected`
          : (chosen ? "Answer selected" : "Not answered yet");
      };

      const save = () => {
        window.clearTimeout(saveTimer);
        const optionIds = inputs
          .filter((input) => input.checked)
          .map((input) => Number(input.value));
        pending = request("mcq", {
          question_id: question.id,
          option_ids: optionIds,
        }).then((result) => {
          if (status) status.textContent = result.queued ? "Saved locally; waiting for connection." : "Saved";
          onAnswerChange(optionIds.length > 0);
          return result;
        }).catch((error) => {
          if (status) status.textContent = `Save failed: ${error.message}`;
          throw error;
        });
        return pending;
      };

      const pop = (input) => {
        const label = input.closest(".exam-mcq-option");
        if (!label) return;
        label.classList.remove("is-pop");
        void label.offsetWidth;
        label.classList.add("is-pop");
      };

      inputs.forEach((input) => {
        listen(input, "change", () => {
          if (status) status.textContent = "Saving…";
          updateCount();
          if (input.checked) pop(input);
          onAnswerChange(inputs.some((item) => item.checked));
          window.clearTimeout(saveTimer);
          saveTimer = window.setTimeout(() => {
            save().catch(() => {});
          }, 250);
        });
      });
      updateCount();

      // Keyboard: press A, B, C… (or 1, 2, 3…) to choose; toggles when multi-select.
      listen(document, "keydown", (event) => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (event.target.matches?.("input:not([name^='mcq-']),textarea,select,[contenteditable=true],.monaco-editor")) return;
        const key = event.key.toLowerCase();
        if (key === "m") return; // reserved: mark for review
        let index = -1;
        if (/^[a-z]$/.test(key)) index = key.charCodeAt(0) - 97;
        else if (/^[1-9]$/.test(key)) index = Number(key) - 1;
        if (index < 0 || index >= inputs.length) return;
        event.preventDefault();
        const input = inputs[index];
        input.checked = multiple ? !input.checked : true;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });

      // Resizable split (shares the saved width with coding questions).
      const layout = container.querySelector(".exam-mcq-layout");
      const splitter = container.querySelector(".exam-mcq-splitter");
      let split = 50;
      try { split = Number(localStorage.getItem(SPLIT_KEY_V)) || 50; } catch (error) { split = 50; }
      const applySplit = () => {
        layout?.style.setProperty("--split-left", `${split}%`);
        splitter?.setAttribute("aria-valuenow", String(Math.round(split)));
      };
      const persist = () => {
        try { localStorage.setItem(SPLIT_KEY_V, String(split)); } catch (error) { /* convenience only */ }
      };
      if (splitter && layout) {
        listen(splitter, "pointerdown", (event) => {
          if (event.button !== undefined && event.button !== 0) return;
          event.preventDefault();
          splitter.setPointerCapture(event.pointerId);
          splitter.classList.add("is-dragging");
          document.body.classList.add("exam-resizing", "exam-resizing-x");
          const startX = event.clientX;
          const startSplit = split;
          let frame = 0;
          const onMove = (moveEvent) => {
            window.cancelAnimationFrame(frame);
            frame = window.requestAnimationFrame(() => {
              const width = layout.getBoundingClientRect().width;
              split = Math.min(70, Math.max(30, startSplit + ((moveEvent.clientX - startX) / width) * 100));
              applySplit();
              persist();
            });
          };
          const onUp = () => {
            window.cancelAnimationFrame(frame);
            try { splitter.releasePointerCapture(event.pointerId); } catch (error) { /* already released */ }
            splitter.classList.remove("is-dragging");
            document.body.classList.remove("exam-resizing", "exam-resizing-x");
            splitter.removeEventListener("pointermove", onMove);
            splitter.removeEventListener("pointerup", onUp);
            splitter.removeEventListener("pointercancel", onUp);
          };
          splitter.addEventListener("pointermove", onMove);
          splitter.addEventListener("pointerup", onUp);
          splitter.addEventListener("pointercancel", onUp);
        });
        listen(splitter, "dblclick", () => { split = 50; applySplit(); persist(); });
        listen(splitter, "keydown", (event) => {
          const step = event.shiftKey ? 10 : 2;
          if (event.key === "Home") split = 50;
          else if (event.key === "ArrowLeft") split = Math.max(30, split - step);
          else if (event.key === "ArrowRight") split = Math.min(70, split + step);
          else return;
          event.preventDefault();
          applySplit();
          persist();
        });
      }
      applySplit();

      activeCleanup = () => {
        window.clearTimeout(saveTimer);
        cleanups.forEach((cleanup) => cleanup());
        document.body.classList.remove("exam-resizing", "exam-resizing-x");
      };
      return {
        save: () => {
          window.clearTimeout(saveTimer);
          return save();
        },
        clear: () => {
          inputs.forEach((input) => { input.checked = false; });
          updateCount();
          onAnswerChange(false);
          return save();
        },
      };
    },

    destroy() {
      if (activeCleanup) activeCleanup();
      activeCleanup = null;
    },
  };

  window.AssessmentMCQ = AssessmentMCQ;
})();