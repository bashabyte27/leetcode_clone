(() => {
  "use strict";

  let activeCleanup = null;

  const AssessmentMCQ = {
    init({ container, question, request, onAnswerChange }) {
      this.destroy();
      const inputs = [...container.querySelectorAll('input[name^="mcq-"]')];
      const status = container.querySelector(".exam-save-state");
      let saveTimer = null;
      let pending = Promise.resolve();

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

      inputs.forEach((input) => {
        input.addEventListener("change", () => {
          if (status) status.textContent = "Saving…";
          onAnswerChange(inputs.some((item) => item.checked));
          window.clearTimeout(saveTimer);
          saveTimer = window.setTimeout(() => {
            save().catch(() => {});
          }, 250);
        });
      });

      activeCleanup = () => {
        window.clearTimeout(saveTimer);
      };
      return {
        save: () => {
          window.clearTimeout(saveTimer);
          return save();
        },
        clear: () => {
          inputs.forEach((input) => { input.checked = false; });
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
