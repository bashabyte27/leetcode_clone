(() => {
  const allowedTargets = "input, textarea, select, [contenteditable='true'], .monaco-editor, .CodeMirror";
  let config = {};
  let container = null;
  let active = false;
  let observer = null;
  let devtoolsTimer = null;
  let warningCount = 0;
  let autoSubmitHandler = null;
  let exitRequestHandler = null;
  let warningHandler = null;
  let statusHandler = null;
  let fullscreenHandler = null;
  let visibilityHandler = null;
  let blurHandler = null;
  let popstateHandler = null;
  let beforeunloadHandler = null;
  let keydownHandler = null;
  let clipboardHandler = null;
  let dragHandler = null;
  let contextMenuHandler = null;
  let onlineHandler = null;
  let queuePromise = null;

  const eventId = () => {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
      const random = Math.random() * 16 | 0;
      return (character === "x" ? random : (random & 0x3 | 0x8)).toString(16);
    });
  };

  const getCsrfToken = () => {
    const cookieToken = document.cookie.split("; ").find((cookie) => cookie.startsWith("csrftoken="));
    if (cookieToken) return decodeURIComponent(cookieToken.split("=")[1]);
    return document.querySelector("meta[name='csrf-token']")?.content || "";
  };

  const isExamTarget = (target) => (
    container && target instanceof Node && container.contains(target)
  );

  const retryFetch = async (url, options = {}, retries = 3) => {
    let lastError;
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      try {
        const response = await fetch(url, { credentials: "same-origin", ...options });
        if (response.status >= 500 && attempt < retries) {
          await new Promise((resolve) => setTimeout(resolve, 400 * (2 ** attempt)));
          continue;
        }
        return response;
      } catch (error) {
        lastError = error;
        if (attempt < retries) {
          await new Promise((resolve) => setTimeout(resolve, 400 * (2 ** attempt)));
        }
      }
    }
    throw lastError || new Error("The request could not be completed.");
  };

  const postJson = async (url, payload, options = {}) => {
    const response = await retryFetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(payload),
      keepalive: Boolean(options.keepalive),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || "The request could not be completed.");
    return body;
  };

  const updateOnlineIndicator = () => {
    const indicator = document.getElementById("online-indicator");
    if (!indicator) return;
    const online = navigator.onLine;
    indicator.classList.toggle("is-offline", !online);
    indicator.lastChild.textContent = online ? " Online" : " Offline";
  };

  const showFullscreenOverlay = (visible) => {
    const overlay = document.getElementById("fullscreen-overlay");
    if (!overlay) return;
    overlay.classList.toggle("d-none", !visible);
    document.body.classList.toggle("exam-is-blurred", visible);
    if (visible) document.getElementById("return-fullscreen")?.focus();
  };

  const sendViolation = async (type, details = {}) => {
    if (!active || !config.attemptId || !config.logUrl) return null;
    const payload = {
      attempt_id: config.attemptId,
      session_id: config.sessionId,
      event_id: eventId(),
      event_type: type,
      timestamp: new Date().toISOString(),
      details,
    };
    if (!navigator.onLine) {
      config.pendingEvents.push(payload);
      return null;
    }
    try {
      const result = await postJson(config.logUrl, payload);
      warningCount = result.violation_count || 0;
      config.warningLimit = result.warning_limit ?? config.warningLimit;
      warningHandler?.(result.warnings_remaining ?? 0, result);
      if (result.auto_submitted) {
        stop();
        autoSubmitHandler?.(result);
      }
      return result;
    } catch (error) {
      config.pendingEvents.push(payload);
      warningHandler?.(null, { error: error.message, queued: true });
      return null;
    }
  };

  const flushPendingEvents = async () => {
    if (!active || !navigator.onLine || queuePromise || !config.pendingEvents.length) return;
    queuePromise = (async () => {
      while (active && navigator.onLine && config.pendingEvents.length) {
        const payload = config.pendingEvents[0];
        try {
          const result = await postJson(config.logUrl, payload);
          config.pendingEvents.shift();
          warningCount = result.violation_count || 0;
          warningHandler?.(result.warnings_remaining ?? 0, result);
          if (result.auto_submitted) {
            stop();
            autoSubmitHandler?.(result);
          }
        } catch (error) {
          warningHandler?.(null, { error: error.message, queued: true });
          break;
        }
      }
    })().finally(() => {
      queuePromise = null;
    });
    await queuePromise;
  };

  const handleFullscreenChange = () => {
    const exited = !document.fullscreenElement && !document.webkitFullscreenElement;
    if (exited) {
      showFullscreenOverlay(true);
      void sendViolation("fullscreen_exit");
    } else {
      showFullscreenOverlay(false);
    }
  };

  const handleKeydown = (event) => {
    if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "q") {
      event.preventDefault();
      exitRequestHandler?.();
      return;
    }
    const key = event.key.toLowerCase();
    const inEditor = event.target.closest?.(".monaco-editor, .CodeMirror");
    if (
      config.allowPasteInEditor
      && inEditor
      && (event.ctrlKey || event.metaKey)
      && key === "v"
    ) return;
    const blockedShortcut = (
      (event.ctrlKey && ["c", "v", "x", "a", "p", "s", "u"].includes(key))
      || (event.ctrlKey && event.shiftKey && ["i", "j", "c"].includes(key))
      || key === "f12"
      || key === "printscreen"
    );
    if (blockedShortcut && isExamTarget(event.target)) {
      event.preventDefault();
      event.stopPropagation();
      void sendViolation("shortcut_blocked", { key: event.key });
    }
  };

  const handleClipboard = (event) => {
    if (!isExamTarget(event.target)) return;
    if (
      event.type === "paste"
      && config.allowPasteInEditor
      && event.target.closest?.(".monaco-editor, .CodeMirror")
    ) return;
    event.preventDefault();
    event.stopPropagation();
    void sendViolation(`${event.type}_blocked`);
  };

  const handleDrag = (event) => {
    if (!isExamTarget(event.target)) return;
    event.preventDefault();
    void sendViolation("drag_blocked", { event: event.type });
  };

  const handleContextMenu = (event) => {
    if (!isExamTarget(event.target)) return;
    event.preventDefault();
    void sendViolation("context_menu_blocked");
  };

  const isSuspiciousInjectedNode = (node) => {
    if (!(node instanceof Element)) return false;
    const identifiers = [
      node.id,
      node.className && typeof node.className === "string" ? node.className : "",
      node.getAttribute("data-extension-id") || "",
      node.getAttribute("data-extension") || "",
      node.getAttribute("src") || "",
    ].join(" ").toLowerCase();
    return (
      node.tagName === "IFRAME"
      || /chrome-extension:|moz-extension:|data-extension|lastpass|grammarly/.test(identifiers)
    );
  };

  const attachMutationObserver = () => {
    if (!document.body || !window.MutationObserver) return;
    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (isSuspiciousInjectedNode(node)) {
            warningHandler?.(null, { warning: "A browser extension or injected frame may be present." });
            void sendViolation("extension_warning", { tag: node.tagName });
            return;
          }
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  };

  const checkDevtools = () => {
    if (!active) return;
    const widthDifference = Math.abs(window.outerWidth - window.innerWidth);
    const heightDifference = Math.abs(window.outerHeight - window.innerHeight);
    if (widthDifference > 180 || heightDifference > 180) {
      void sendViolation("devtools_open");
    }
  };

  const trapNavigation = () => {
    history.pushState({ assessment: true }, "", window.location.href);
    popstateHandler = () => {
      history.pushState({ assessment: true }, "", window.location.href);
      void sendViolation("navigation_blocked", { action: "back" });
    };
    beforeunloadHandler = (event) => {
      event.preventDefault();
      event.returnValue = "";
      void sendViolation("navigation_blocked", { action: "refresh_or_close" });
    };
    window.addEventListener("popstate", popstateHandler);
    window.addEventListener("beforeunload", beforeunloadHandler);
  };

  const untrapNavigation = () => {
    if (popstateHandler) window.removeEventListener("popstate", popstateHandler);
    if (beforeunloadHandler) window.removeEventListener("beforeunload", beforeunloadHandler);
    popstateHandler = null;
    beforeunloadHandler = null;
  };

  const exitAction = async (eventType, pin) => {
    if (!config.attemptId || !config.logUrl) throw new Error("No active attempt is available.");
    const result = await postJson(config.logUrl, {
      attempt_id: config.attemptId,
      session_id: config.sessionId,
      event_type: eventType,
      ...(pin ? { pin } : {}),
    });
    stop();
    return result;
  };

  const Proctor = {
    init(options = {}) {
      config = { warningLimit: 3, autoSubmit: true, ...options };
      config.pendingEvents = [];
      updateOnlineIndicator();
      onlineHandler = () => {
        updateOnlineIndicator();
        void flushPendingEvents();
        if (active && config.attemptId) {
          void Proctor.refreshStatus();
        }
      };
      window.addEventListener("online", onlineHandler);
      window.addEventListener("offline", updateOnlineIndicator);
      return Proctor;
    },

    start() {
      if (active) return Proctor;
      if (!config.attemptId) throw new Error("An attempt ID is required to start proctoring.");
      active = true;
      container = container || document.getElementById("section-container");
      config.pendingEvents = config.pendingEvents || [];
      document.body.classList.add("proctor-active");
      fullscreenHandler = handleFullscreenChange;
      visibilityHandler = () => {
        if (document.visibilityState === "hidden") void sendViolation("tab_hidden");
      };
      blurHandler = () => void sendViolation("window_blur");
      keydownHandler = handleKeydown;
      clipboardHandler = handleClipboard;
      dragHandler = handleDrag;
      contextMenuHandler = handleContextMenu;
      document.addEventListener("fullscreenchange", fullscreenHandler);
      document.addEventListener("webkitfullscreenchange", fullscreenHandler);
      document.addEventListener("visibilitychange", visibilityHandler);
      window.addEventListener("blur", blurHandler);
      document.addEventListener("keydown", keydownHandler, true);
      for (const type of ["copy", "cut", "paste"]) {
        document.addEventListener(type, clipboardHandler, true);
      }
      for (const type of ["dragstart", "drop"]) {
        document.addEventListener(type, dragHandler, true);
      }
      document.addEventListener("contextmenu", contextMenuHandler, true);
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        showFullscreenOverlay(true);
      }
      trapNavigation();
      attachMutationObserver();
      devtoolsTimer = window.setInterval(checkDevtools, 2000);
      return Proctor;
    },

    stop() {
      active = false;
      document.body.classList.remove("proctor-active", "exam-is-blurred");
      showFullscreenOverlay(false);
      if (fullscreenHandler) {
        document.removeEventListener("fullscreenchange", fullscreenHandler);
        document.removeEventListener("webkitfullscreenchange", fullscreenHandler);
      }
      if (visibilityHandler) document.removeEventListener("visibilitychange", visibilityHandler);
      if (blurHandler) window.removeEventListener("blur", blurHandler);
      if (keydownHandler) document.removeEventListener("keydown", keydownHandler, true);
      for (const type of ["copy", "cut", "paste"]) {
        if (clipboardHandler) document.removeEventListener(type, clipboardHandler, true);
      }
      for (const type of ["dragstart", "drop"]) {
        if (dragHandler) document.removeEventListener(type, dragHandler, true);
      }
      if (contextMenuHandler) document.removeEventListener("contextmenu", contextMenuHandler, true);
      observer?.disconnect();
      observer = null;
      if (devtoolsTimer) window.clearInterval(devtoolsTimer);
      devtoolsTimer = null;
      untrapNavigation();
      return Proctor;
    },

    attachTo(element) {
      if (!(element instanceof Element)) throw new TypeError("Proctor.attachTo expects a DOM element.");
      container = element;
      return Proctor;
    },

    onAutoSubmit(callback) {
      autoSubmitHandler = callback;
      return Proctor;
    },

    onExitRequest(callback) {
      exitRequestHandler = callback;
      return Proctor;
    },

    onWarning(callback) {
      warningHandler = callback;
      return Proctor;
    },

    onStatus(callback) {
      statusHandler = callback;
      return Proctor;
    },

    setAttempt(attempt) {
      if (!attempt || !attempt.id) throw new TypeError("A valid attempt payload is required.");
      config.attemptId = attempt.id;
      if (attempt.session_id) config.sessionId = attempt.session_id;
      return Proctor;
    },

    setExamPolicy(policy = {}) {
      config.allowPasteInEditor = Boolean(policy.allowPasteInEditor);
      return Proctor;
    },

    async submitAndExit() {
      return exitAction("submit_and_exit");
    },

    async exitWithPin(pin) {
      return exitAction("invigilator_exit", pin);
    },

    async refreshStatus() {
      if (!config.statusUrl) return null;
      try {
        const statusUrl = new URL(config.statusUrl, window.location.origin);
        if (config.sessionId) statusUrl.searchParams.set("session_id", config.sessionId);
        if (config.attemptId) statusUrl.searchParams.set("attempt_id", config.attemptId);
        const response = await retryFetch(statusUrl.toString());
        if (!response.ok) throw new Error("Could not refresh the assessment status.");
        const result = await response.json();
        statusHandler?.(result.attempt || null, result);
        return result.attempt;
      } catch (error) {
        warningHandler?.(null, { error: error.message });
        return null;
      }
    },

    isActive() {
      return active;
    },

    async logViolation(type, details) {
      return sendViolation(type, details);
    },
  };

  window.Proctor = Proctor;
})();
