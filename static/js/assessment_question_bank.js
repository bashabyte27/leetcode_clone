(() => {
  const form = document.querySelector("[data-question-bank]");
  if (!form) return;

  const group = form.querySelector("[data-question-group]");
  const search = form.querySelector("[data-question-search]");
  const topic = form.querySelector("[data-question-topic]");
  const subtopic = form.querySelector("[data-question-subtopic]");
  const questionSelect = form.querySelector("[data-question-select]");
  const results = document.querySelector("[data-question-results]");
  const count = document.querySelector("[data-question-count]");
  const topics = document.querySelector("#question-bank-topics");
  const subtopics = document.querySelector("#question-bank-subtopics");
  let debounceTimer;
  let activeRequest;

  const setOptions = (list, values) => {
    list.replaceChildren(...values.map((value) => {
      const option = document.createElement("option");
      option.value = value;
      return option;
    }));
  };

  const updateResults = (rows) => {
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.className = "assessment-empty";
      cell.colSpan = 4;
      cell.textContent = "No questions match these filters.";
      row.append(cell);
      results.replaceChildren(row);
    } else {
      results.replaceChildren(...rows.map((question) => {
        const row = document.createElement("tr");
        const titleCell = document.createElement("td");
        const link = document.createElement("a");
        link.href = question.edit_url;
        link.textContent = question.title;
        titleCell.append(link);
        row.append(titleCell);
        [question.question_type, question.topic, question.subtopic || "—"].forEach((value, index) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          if (index === 0) cell.dataset.type = value;
          row.append(cell);
        });
        return row;
      }));
    }

    questionSelect.replaceChildren(new Option("Select a question to edit", ""));
    rows.forEach((question) => {
      questionSelect.add(new Option(question.title, question.edit_url));
    });
  };

  const searchQuestions = async () => {
    activeRequest?.abort();
    activeRequest = new AbortController();
    const params = new URLSearchParams({
      group: group.value,
      q: search.value.trim(),
      topic: topic.value.trim(),
      subtopic: subtopic.value.trim(),
    });
    const url = new URL(form.dataset.searchUrl, window.location.origin);
    url.search = params.toString();
    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        signal: activeRequest.signal,
      });
      if (!response.ok) throw new Error("Unable to load questions. Please try again.");
      const payload = await response.json();
      updateResults(payload.results);
      setOptions(topics, payload.topics);
      setOptions(subtopics, payload.subtopics);
      count.textContent = `${payload.count} question${payload.count === 1 ? "" : "s"}`;
      const countNum = document.querySelector("[data-question-count-num]");
      if (countNum) countNum.textContent = payload.count;
      results.classList.remove("is-refreshed");
      void results.offsetWidth;
      results.classList.add("is-refreshed");
      const pageUrl = new URL(window.location.href);
      pageUrl.search = new URLSearchParams({
        tab: "questions",
        question_group: group.value,
        q: search.value.trim(),
        topic: topic.value.trim(),
        subtopic: subtopic.value.trim(),
      });
      window.history.replaceState({}, "", pageUrl);
    } catch (error) {
      if (error.name !== "AbortError") {
        count.textContent = error.message;
      }
    }
  };

  const scheduleSearch = () => {
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(searchQuestions, 250);
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    searchQuestions();
  });
  group.addEventListener("change", () => {
    topic.value = "";
    subtopic.value = "";
    searchQuestions();
  });
  search.addEventListener("input", scheduleSearch);
  topic.addEventListener("input", () => {
    subtopic.value = "";
    scheduleSearch();
  });
  subtopic.addEventListener("input", scheduleSearch);
  questionSelect.addEventListener("change", () => {
    if (questionSelect.value) window.location.assign(questionSelect.value);
  });
})();
