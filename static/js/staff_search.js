(() => {
  const forms = document.querySelectorAll('[data-staff-live-search]');
  forms.forEach(form => {
    const input = form.querySelector('input[name="q"]');
    if (!input || !form.parentElement.querySelector('.staff-panel')) return;

    let timer;
    let request;

    const search = () => {
      const url = new URL(window.location.href);
      const query = input.value.trim();
      if (query) url.searchParams.set('q', query);
      else url.searchParams.delete('q');
      url.searchParams.delete('page');

      if (request) request.abort();
      request = new AbortController();
      form.setAttribute('aria-busy', 'true');

      fetch(url, {
        headers: {'X-Requested-With': 'XMLHttpRequest'},
        signal: request.signal,
      })
        .then(response => response.text())
        .then(html => {
          const replacement = new DOMParser()
            .parseFromString(html, 'text/html')
            .querySelector('.staff-panel');
          if (!replacement) return;
          const currentPanel = form.parentElement.querySelector('.staff-panel');
          if (currentPanel) currentPanel.replaceWith(replacement);
          window.history.replaceState({}, '', url);
        })
        .catch(error => {
          if (error.name !== 'AbortError') console.error(error);
        })
        .finally(() => form.removeAttribute('aria-busy'));
    };

    form.addEventListener('submit', event => {
      event.preventDefault();
      search();
    });

    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(search, 180);
    });
  });
})();
