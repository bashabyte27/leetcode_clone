(() => {
  const form = document.querySelector(".assessment-question-picker-form");
  if (!form) {
    return;
  }

  const typeSelect = form.querySelector("[data-question-type]");
  const typeInput = form.querySelector('input[name="question_type"]');
  const questionIdInput = form.querySelector('input[name="question_id"]');
  const searchInput = form.querySelector("[data-question-search]");
  const suggestions = form.querySelector("[data-question-suggestions], #question-suggestions");
  const status = form.querySelector("[data-question-search-status]");
  const selectedQuestion = form.querySelector("[data-selected-question]");
  const selectedTitle = form.querySelector("[data-selected-question-title]");
  const clearButton = form.querySelector("[data-clear-question]");
  let debounceTimer;
  let activeRequest;

  function clearSelection() {
    questionIdInput.value = "";
    selectedTitle.textContent = "";
    selectedQuestion.hidden = true;
    searchInput.disabled = false;
  }

  function renderSuggestions(questions) {
    suggestions.replaceChildren();
    questions.forEach((question) => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "assessment-question-suggestion";
      option.setAttribute("role", "option");

      const title = document.createElement("strong");
      title.textContent = question.title;
      option.append(title);

      const metadata = document.createElement("span");
      metadata.textContent = [
        question.topic,
        question.subtopic,
        question.mode,
      ].filter(Boolean).join(" · ");
      option.append(metadata);

      option.addEventListener("click", () => {
        typeInput.value = typeSelect.value;
        questionIdInput.value = question.id;
        selectedTitle.textContent = question.title;
        selectedQuestion.hidden = false;
        searchInput.value = "";
        searchInput.disabled = true;
        suggestions.replaceChildren();
        suggestions.hidden = true;
        status.textContent = "";
      });
      suggestions.append(option);
    });
    suggestions.hidden = questions.length === 0;
  }

  function searchQuestions() {
    window.clearTimeout(debounceTimer);
    if (activeRequest) {
      activeRequest.abort();
    }

    clearSelection();
    const query = searchInput.value.trim();
    if (query.length < 2) {
      suggestions.replaceChildren();
      suggestions.hidden = true;
      status.textContent = query ? "Type at least 2 characters to search." : "";
      return;
    }

    status.textContent = "Searching...";
    debounceTimer = window.setTimeout(async () => {
      activeRequest = new AbortController();
      const url = new URL(form.dataset.searchUrl, window.location.origin);
      url.searchParams.set("q", query);
      url.searchParams.set("type", typeSelect.value);

      try {
        const response = await fetch(url, {
          headers: { Accept: "application/json" },
          signal: activeRequest.signal,
        });
        if (!response.ok) {
          throw new Error("Question search failed.");
        }
        const data = await response.json();
        renderSuggestions(data.results);
        status.textContent = data.results.length
          ? `${data.results.length} matching question(s). Select one to continue.`
          : "No matching questions found.";
      } catch (error) {
        if (error.name !== "AbortError") {
          status.textContent = "Could not search questions. Please try again.";
        }
      }
    }, 200);
  }

  searchInput.addEventListener("input", searchQuestions);
  typeSelect.addEventListener("change", () => {
    typeInput.value = typeSelect.value;
    searchQuestions();
  });
  clearButton.addEventListener("click", () => {
    clearSelection();
    searchInput.focus();
    searchQuestions();
  });
  form.addEventListener("submit", (event) => {
    if (!questionIdInput.value) {
      event.preventDefault();
      status.textContent = "Search for a question and select a match before adding it.";
      searchInput.focus();
    }
  });
  typeInput.value = typeSelect.value;
})();
