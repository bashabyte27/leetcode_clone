(() => {
  const formsets = {
    "mcq-options": {
      container: document.getElementById("option-forms"),
      template: document.getElementById("option-form-template"),
      prefix: "form",
    },
    languages: {
      container: document.getElementById("language-forms"),
      template: document.getElementById("language-form-template"),
      prefix: "languages",
    },
    "test-cases": {
      container: document.getElementById("test-case-forms"),
      template: document.getElementById("test-case-form-template"),
      prefix: "test-cases",
    },
  };
  const languageForms = formsets.languages.container;
  const modeSelect = document.getElementById("id_coding_mode");
  const questionTypeSelect = document.getElementById("id_question_type");
  const mcqLanguageField = document.querySelector("[data-mcq-programming-language]");
  let previousMode = modeSelect?.value;

  function updateMcqLanguageField() {
    if (!questionTypeSelect || !mcqLanguageField) {
      return;
    }

    const required = questionTypeSelect.value === "programming";
    mcqLanguageField.hidden = !required;
    const languageSelect = mcqLanguageField.querySelector("select");
    if (languageSelect) {
      languageSelect.required = required;
    }
  }

  function updateLanguageFields() {
    if (!languageForms || !modeSelect) {
      return;
    }

    const isScratch = modeSelect.value === "scratch";
    const rows = Array.from(languageForms.querySelectorAll("[data-language-row]"));
    if (previousMode === "scratch" && !isScratch) {
      rows.slice(1).forEach((row) => {
        const language = row.querySelector('select[name$="-language"]');
        if (language && !row.hasAttribute("data-existing-language")) {
          language.value = "";
        }
      });
    }
    if (previousMode !== "scratch" && isScratch) {
      rows.forEach((row) => {
        row.querySelectorAll('[data-code-field] textarea').forEach((field) => {
          field.value = "";
        });
      });
    }

    rows.forEach((row, index) => {
      const language = row.querySelector('select[name$="-language"]');
      const hasLanguage = Boolean(language?.value);
      const addedForOtherMode = row.dataset.addedForOtherMode === "true";
      row.hidden = isScratch
        ? !hasLanguage
        : !hasLanguage && index > 0 && !addedForOtherMode;

      row.querySelectorAll("[data-code-field]").forEach((field) => {
        field.hidden = isScratch || field.dataset.codeField !== modeSelect.value;
      });
    });

    const addLanguageButton = document.querySelector('[data-add-form="languages"]');
    if (addLanguageButton) {
      addLanguageButton.hidden = isScratch;
    }
    previousMode = modeSelect.value;
  }

  function addForm(formsetName) {
    const formset = formsets[formsetName];
    if (!formset?.container || !formset.template) {
      return;
    }

    if (formsetName === "languages" && modeSelect?.value !== "scratch") {
      const unusedRow = Array.from(
        formset.container.querySelectorAll("[data-language-row]"),
      ).find((row) => {
        const language = row.querySelector('select[name$="-language"]');
        return row.hidden && language && !language.value;
      });
      if (unusedRow) {
        unusedRow.dataset.addedForOtherMode = "true";
        unusedRow.hidden = false;
        updateLanguageFields();
        return;
      }
    }

    const totalForms = document.querySelector(
      `input[name="${formset.prefix}-TOTAL_FORMS"]`,
    );
    if (!totalForms) {
      return;
    }

    const index = Number.parseInt(totalForms.value, 10);
    const html = formset.template.innerHTML.replace(/__prefix__/g, String(index));
    formset.container.insertAdjacentHTML("beforeend", html);
    totalForms.value = String(index + 1);

    if (formsetName === "languages") {
      const newRow = formset.container.lastElementChild;
      if (modeSelect?.value !== "scratch") {
        newRow.dataset.addedForOtherMode = "true";
      }
      updateLanguageFields();
    }
  }

  document.querySelectorAll("[data-add-form]").forEach((button) => {
    button.addEventListener("click", () => addForm(button.dataset.addForm));
  });

  document.addEventListener("change", (event) => {
    if (event.target.matches("#id_question_type")) {
      updateMcqLanguageField();
    }
    if (
      event.target.matches(
        'select[name$="-language"], #id_coding_mode',
      )
    ) {
      updateLanguageFields();
    }
  });

  updateLanguageFields();
  updateMcqLanguageField();
})();
