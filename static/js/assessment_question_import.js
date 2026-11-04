(() => {
  const prompt = document.getElementById("question-import-ai-prompt");
  const copyButton = document.querySelector("[data-copy-import-prompt]");
  const status = document.querySelector("[data-copy-prompt-status]");
  if (!prompt || !copyButton || !status) {
    return;
  }

  copyButton.addEventListener("click", async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(prompt.value);
      } else {
        prompt.focus();
        prompt.select();
        const copied = document.execCommand("copy");
        if (!copied) {
          throw new Error("Copy command was not available.");
        }
      }
      status.textContent = "Prompt copied.";
    } catch {
      prompt.focus();
      prompt.select();
      status.textContent = "Copy failed. Select the prompt and copy it manually.";
    }
  });
})();
