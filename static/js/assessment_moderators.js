(() => {
  const form = document.querySelector(".assessment-moderator-form");
  if (!form) {
    return;
  }

  const search = form.querySelector("[data-moderator-search]");
  const results = form.querySelector("[data-moderator-results]");
  const statusEl = form.querySelector("[data-moderator-status]");
  // Writing status must never break the search (the element is optional).
  const status = {
    set textContent(value) { if (statusEl) statusEl.textContent = value; },
  };
  if (!search || !results) {
    return;
  }
  let debounceTimer;
  let activeRequest;

  function setOptions(users) {
    results.replaceChildren(new Option(users.length ? "Select a user" : "Search for a user first", ""));
    users.forEach((user) => {
      results.add(new Option(user.user_name, user.id));
    });
  }

  search.addEventListener("input", () => {
    window.clearTimeout(debounceTimer);
    if (activeRequest) {
      activeRequest.abort();
    }

    const query = search.value.trim();
    setOptions([]);
    if (query.length < 2) {
      status.textContent = "Type at least 2 characters to search.";
      return;
    }

    status.textContent = "Searching...";
    debounceTimer = window.setTimeout(async () => {
      activeRequest = new AbortController();
      const url = new URL(form.dataset.searchUrl, window.location.origin);
      url.searchParams.set("q", query);

      try {
        const response = await fetch(url, {
          headers: { Accept: "application/json" },
          signal: activeRequest.signal,
        });
        if (!response.ok) {
          throw new Error("User search failed.");
        }
        const data = await response.json();
        setOptions(data.results);
        if (data.results.length === 1) results.value = data.results[0].id;
        status.textContent = data.results.length
          ? `${data.results.length} matching user(s). Select one to continue.`
          : "No matching users found.";
      } catch (error) {
        if (error.name !== "AbortError") {
          status.textContent = "Could not search users. Please try again.";
        }
      }
    }, 250);
  });
})();
