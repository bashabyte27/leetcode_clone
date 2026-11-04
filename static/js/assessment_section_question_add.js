(() => {
  const typeSelect = document.querySelector("[data-section-question-type]");
  const categoryField = document.querySelector("[data-section-question-category]");
  const addButton = document.querySelector("[data-bulk-add]");
  const checkboxes = [...document.querySelectorAll("[data-section-question-checkbox]")];

  if (typeSelect && categoryField) {
    typeSelect.addEventListener("change", () => {
      if (typeSelect.value !== "mcq") {
        categoryField.querySelector("select").value = "";
      }
      categoryField.hidden = typeSelect.value !== "mcq";
      typeSelect.form.requestSubmit();
    });
  }

  const updateAddButton = () => {
    if (addButton) {
      addButton.disabled = !checkboxes.some((checkbox) => checkbox.checked);
    }
  };

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateAddButton);
  });
  updateAddButton();
})();
