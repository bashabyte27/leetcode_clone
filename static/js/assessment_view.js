(() => {
  const page = document.body;
  const startButton = document.getElementById("start-exam");
  const agreement = document.getElementById("agree-instructions");
  const instructionsPanel = document.getElementById("instructions-panel");
  const examShell = document.getElementById("exam-shell");
  const alertBox = document.getElementById("page-alert");
  const timer = document.getElementById("exam-timer");
  const statusLabel = document.getElementById("attempt-status-label");
  const warningCounter = document.getElementById("warning-counter");
  const config = JSON.parse(document.getElementById("proctor-config").textContent);
  const initialAttemptElement = document.getElementById("attempt-state");
  const initialAttempt = initialAttemptElement ? JSON.parse(initialAttemptElement.textContent) : null;
  const systemChecks = new Map();
  const sessionId = window.crypto?.randomUUID
    ? window.crypto.randomUUID()
    : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
      const random = Math.floor(Math.random() * 16);
      return (character === "x" ? random : (random & 0x3) | 0x8).toString(16);
    });
  let attempt = initialAttempt;
  let examInitAttemptId = null;
  let clockOffset = 0;
  let timerInterval = null;
  let startCountdownInterval = null;

  const setAlert = (message, type = "danger") => {
    if (!alertBox) return;
    alertBox.className = `alert alert-${type}`;
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  };

  const clearAlert = () => {
    alertBox?.classList.add("d-none");
  };

  const apiRequest = async (url, options = {}, retries = 3) => {
    let lastError;
    for (let index = 0; index <= retries; index += 1) {
      try {
        const response = await fetch(url, {
          credentials: "same-origin",
          ...options,
        });
        if (response.redirected) {
          const error = new Error("Your session may have expired. Sign in again, then reopen this assessment.");
          error.retryable = false;
          throw error;
        }
        const body = await response.json().catch(() => ({}));
        if (response.status >= 500 && index < retries) {
          await new Promise((resolve) => setTimeout(resolve, 400 * (2 ** index)));
          continue;
        }
        if (!response.ok) {
          const error = new Error(body.error || "The request could not be completed.");
          error.retryable = false;
          throw error;
        }
        return body;
      } catch (error) {
        if (error.retryable === false) throw error;
        lastError = error;
        if (index < retries) {
          await new Promise((resolve) => setTimeout(resolve, 400 * (2 ** index)));
        }
      }
    }
    throw lastError || new Error("The request could not be completed.");
  };

  const csrfToken = () => (
    document.querySelector("meta[name='csrf-token']")?.content || ""
  );

  const browserChecks = () => {
    const fullscreenSupported = Boolean(
      typeof document.documentElement.requestFullscreen === "function"
      || typeof document.documentElement.webkitRequestFullscreen === "function",
    );
    const screenSuitable = window.screen.width >= 1024 && window.screen.height >= 600;
    const online = navigator.onLine;
    updateCheck("fullscreen", fullscreenSupported, fullscreenSupported ? "Supported" : "Not supported");
    updateCheck("screen", screenSuitable, screenSuitable ? "Ready" : "Increase your display size");
    updateCheck("online", online, online ? "Connected" : "No connection");
    updateStartButton();
  };

  const updateCheck = (name, passed, message) => {
    systemChecks.set(name, passed);
    const row = document.querySelector(`[data-check="${name}"]`);
    if (!row) return;
    row.dataset.result = passed ? "pass" : "fail";
    row.querySelector(".check-state").textContent = message;
  };

  const updateStartButton = () => {
    if (!startButton || page.dataset.assessmentState === "upcoming") {
      if (startButton) startButton.disabled = true;
      return;
    }
    const checksPassed = [...systemChecks.values()].length === 3
      && [...systemChecks.values()].every(Boolean);
    startButton.disabled = !checksPassed || !agreement?.checked;
  };

  const formatTime = (seconds) => {
    const safeSeconds = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const remaining = safeSeconds % 60;
    return [hours, minutes, remaining].map((part) => String(part).padStart(2, "0")).join(":");
  };

  const syncClock = (serverTime) => {
    const serverTimestamp = Date.parse(serverTime);
    if (Number.isFinite(serverTimestamp)) clockOffset = serverTimestamp - Date.now();
  };
  syncClock(page.dataset.serverTime);

  const renderTimer = () => {
    if (!attempt?.expires_at || !timer) return;
    const remaining = Math.max(0, Math.ceil((Date.parse(attempt.expires_at) - (Date.now() + clockOffset)) / 1000));
    timer.textContent = formatTime(remaining).split(":").join(" : ");
    timer.classList.toggle("is-low", remaining <= 300);
    if (remaining === 0) {
      timer.textContent = "00 : 00 : 00";
      window.clearInterval(timerInterval);
      void window.AssessmentExam?.submit(true);
    }
  };

  const startTimer = (payload) => {
    attempt = payload;
    syncClock(payload.server_time);
    renderTimer();
    window.clearInterval(timerInterval);
    timerInterval = window.setInterval(renderTimer, 1000);
  };

  const enterExamShell = (payload) => {
    attempt = payload;
    page.classList.add("exam-active");
    window.scrollTo(0, 0);
    config.attemptId = payload.id;
    config.sessionId = sessionId;
    Proctor.setAttempt({ ...payload, session_id: sessionId });
    startTimer(payload);
    statusLabel.textContent = "In progress";
    instructionsPanel.classList.add("is-leaving");
    return new Promise((resolve, reject) => {
      window.setTimeout(() => {
        instructionsPanel.classList.add("d-none");
        examShell.classList.remove("d-none");
        examShell.classList.add("is-entering");
        window.requestAnimationFrame(() => examShell.classList.remove("is-entering"));
        Proctor.start();
        if (examInitAttemptId !== payload.id) {
          examInitAttemptId = payload.id;
          window.AssessmentExam.init(payload, sessionId).then(resolve, (error) => {
            examInitAttemptId = null;
            setAlert(`Could not restore the exam: ${error.message}`, "danger");
            reject(error);
          });
        } else {
          resolve();
        }
      }, 240);
    });
  };

  const finishShell = (message, status = "Submitted") => {
    page.classList.add("exam-active");
    Proctor.stop();
    window.clearInterval(timerInterval);
    statusLabel.textContent = status;
    if (startButton) startButton.classList.add("d-none");
    if (agreement) agreement.disabled = true;
    examShell.classList.remove("d-none");
    instructionsPanel.classList.add("d-none");
    window.AssessmentExam?.showFinalScreen(
      message,
      status.toLowerCase() === "expired" ? "timed_out" : "submitted",
    );
  };

  const refreshAttemptStatus = async () => {
    try {
      const statusUrl = new URL(page.dataset.statusUrl, window.location.origin);
      statusUrl.searchParams.set("session_id", sessionId);
      if (attempt?.id) statusUrl.searchParams.set("attempt_id", attempt.id);
      const body = await apiRequest(statusUrl.toString());
      updateWarningCounter(body.warnings_remaining);
      if (!body.attempt) return null;
      if (body.attempt.status === "in_progress") {
        if (!Proctor.isActive()) enterExamShell(body.attempt);
        else startTimer(body.attempt);
      } else if (body.attempt.status === "submitted") {
        finishShell("Your assessment attempt has already been submitted.", "Submitted");
      } else if (body.attempt.status === "timed_out") {
        finishShell("Your assessment attempt has expired.", "Expired");
      }
      return body.attempt;
    } catch (error) {
      setAlert(`Could not refresh your attempt status: ${error.message}`, "warning");
      return null;
    }
  };

  const requestFullscreen = () => {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      return Promise.resolve();
    }
    const request = document.documentElement.requestFullscreen
      || document.documentElement.webkitRequestFullscreen;
    if (!request) return Promise.reject(new Error("This browser does not support full-screen mode."));
    try {
      const result = request.call(document.documentElement);
      return result && typeof result.then === "function" ? result : Promise.resolve();
    } catch (error) {
      return Promise.reject(error);
    }
  };

  const handleStart = async () => {
    if (!startButton || startButton.disabled) return;
    startButton.disabled = true;
    clearAlert();
    if (!window.Proctor || !window.AssessmentExam) {
      setAlert("The exam components did not load. Refresh the page and try again.", "danger");
      updateStartButton();
      return;
    }
    const fullscreenPromise = requestFullscreen();
    try {
      await fullscreenPromise;
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        throw new Error("The browser did not enter full-screen mode.");
      }
    } catch (error) {
      setAlert(`Full-screen mode could not be enabled: ${error.message}`, "warning");
      updateStartButton();
      return;
    }
    try {
      const body = await apiRequest(page.dataset.startUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({ session_id: sessionId }),
      });
      await enterExamShell(body.attempt);
    } catch (error) {
      if (document.exitFullscreen && document.fullscreenElement) {
        await document.exitFullscreen().catch(() => {});
      }
      setAlert(error.message, "danger");
      updateStartButton();
    }
  };

  const updateWarningCounter = (remaining, result = {}) => {
    if (remaining !== null && remaining !== undefined) {
      const previous = warningCounter.dataset.remaining;
      warningCounter.textContent = `${remaining} Warnings`;
      warningCounter.dataset.remaining = String(remaining);
      warningCounter.dataset.level = Number(remaining) <= 1 ? "critical" : "ok";
      if (previous !== undefined && previous !== String(remaining)) {
        warningCounter.classList.remove("is-bump");
        void warningCounter.offsetWidth;
        warningCounter.classList.add("is-bump");
      }
    } else if (result.error) {
      warningCounter.textContent = result.queued
        ? "Offline: proctoring event queued"
        : "Proctoring connection needs attention";
    } else if (result.warning) {
      warningCounter.textContent = result.warning;
    }
  };

  const exitDialog = document.getElementById("exit-dialog");
  const exitError = document.getElementById("exit-error");
  const pinField = document.getElementById("invigilator-pin-field");
  const pinInput = document.getElementById("invigilator-pin");
  const pinButton = document.getElementById("pin-exit");

  const openExitDialog = () => {
    exitError.textContent = "";
    exitDialog.classList.remove("d-none");
    if (config.invigilatorPinEnabled) {
      pinField.classList.remove("d-none");
      pinInput.classList.remove("d-none");
      pinButton.classList.remove("d-none");
    }
    document.getElementById("cancel-exit").focus();
  };

  const closeExitDialog = () => {
    exitDialog.classList.add("d-none");
    document.getElementById("submit-exit").focus();
  };

  const handleSubmitExit = async () => {
    const button = document.getElementById("submit-exit");
    button.disabled = true;
    try {
      await window.AssessmentExam.submit(false);
      exitDialog.classList.add("d-none");
    } catch (error) {
      exitError.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };

  const handlePinExit = async () => {
    pinButton.disabled = true;
    try {
      await window.AssessmentExam.saveCurrent?.();
      await Proctor.exitWithPin(pinInput.value);
      finishShell("Your invigilator authorized and submitted the attempt.", "Submitted");
    } catch (error) {
      exitError.textContent = error.message;
    } finally {
      pinButton.disabled = false;
    }
  };

  const updateStartCountdown = () => {
    const countdown = document.getElementById("start-countdown");
    if (!countdown) return;
    const startTimestamp = Date.parse(countdown.dataset.deadline);
    const remaining = Math.ceil((startTimestamp - (Date.now() + clockOffset)) / 1000);
    if (remaining <= 0) {
      countdown.textContent = "00:00:00";
      if (page.dataset.assessmentState === "not_live") {
        countdown.closest(".assessment-state-message").lastElementChild.textContent = "The scheduled start time has arrived. Waiting for the organizer to make the assessment live.";
        window.clearInterval(startCountdownInterval);
        return;
      }
      page.dataset.assessmentState = "ready";
      const stateMessage = countdown.closest(".assessment-state-message");
      stateMessage.innerHTML = "<strong>Assessment is live</strong><span>Complete the system checks to begin.</span>";
      startButton?.classList.remove("d-none");
      updateStartButton();
      window.clearInterval(startCountdownInterval);
      return;
    }
    countdown.textContent = formatTime(remaining);
  };

  const updateAssessmentWindow = () => {
    const endTimestamp = Date.parse(page.dataset.endTime || "");
    if (Number.isFinite(endTimestamp) && endTimestamp <= Date.now() + clockOffset) {
      page.dataset.assessmentState = "expired";
      if (startButton) {
        startButton.disabled = true;
        startButton.classList.add("d-none");
      }
      if (agreement) agreement.disabled = true;
      statusLabel.textContent = "Expired";
      const stateMessage = document.querySelector(".assessment-state-message");
      if (stateMessage) {
        stateMessage.innerHTML = "<strong>Assessment expired</strong><span>This assessment is no longer accepting attempts.</span>";
      }
      setAlert("This assessment has expired and is no longer accepting attempts.", "warning");
      window.clearInterval(startCountdownInterval);
      return;
    }
    updateStartCountdown();
  };

  browserChecks();
  window.addEventListener("resize", browserChecks);
  window.addEventListener("online", browserChecks);
  window.addEventListener("offline", browserChecks);
  agreement?.addEventListener("change", updateStartButton);
  startButton?.addEventListener("click", handleStart);
  window.addEventListener("error", (event) => {
    if (!systemChecks.size) {
      ["fullscreen", "screen", "online"].forEach((name) => {
        updateCheck(name, false, "Could not run checks; refresh the page");
      });
      setAlert(`Assessment page setup failed: ${event.message || "A required script did not load."}`, "danger");
    }
  });

  if (!window.Proctor) {
    if (startButton) startButton.disabled = true;
    setAlert("The proctoring script did not load. Refresh the page before starting.", "danger");
  } else {
    Proctor.init({
      ...config,
      statusUrl: page.dataset.statusUrl,
      sessionId,
    });
    Proctor.attachTo(examShell);
    Proctor.onWarning(updateWarningCounter);
    Proctor.onExitRequest(openExitDialog);
    Proctor.onStatus((serverAttempt, statusResponse) => {
      updateWarningCounter(statusResponse.warnings_remaining);
      if (!serverAttempt) return;
      if (serverAttempt.status === "in_progress") {
        startTimer(serverAttempt);
      } else if (serverAttempt.status === "submitted") {
        finishShell("Your assessment attempt has already been submitted.", "Submitted");
      } else if (serverAttempt.status === "timed_out") {
        finishShell("Your assessment attempt has expired.", "Expired");
      }
    });
    Proctor.onAutoSubmit(() => {
      finishShell("Your attempt was automatically submitted after the proctoring warning limit was exceeded.", "Submitted");
    });
    updateWarningCounter(config.warningsRemaining);
  }

  document.getElementById("return-fullscreen")?.addEventListener("click", async () => {
    try {
      await requestFullscreen();
      document.getElementById("fullscreen-overlay").classList.add("d-none");
      document.body.classList.remove("exam-is-blurred");
    } catch (error) {
      setAlert(`Full-screen mode could not be enabled: ${error.message}`, "warning");
    }
  });
  document.getElementById("cancel-exit").addEventListener("click", closeExitDialog);
  document.getElementById("submit-exit").addEventListener("click", handleSubmitExit);
  pinButton.addEventListener("click", handlePinExit);

  const startDeadline = document.getElementById("start-countdown");
  if (startDeadline || page.dataset.endTime) {
    startCountdownInterval = window.setInterval(updateAssessmentWindow, 1000);
    updateAssessmentWindow();
  }

  if (attempt?.status === "in_progress") {
    void enterExamShell(attempt)
      .then(refreshAttemptStatus)
      .catch(() => {});
  } else {
    void refreshAttemptStatus();
  }
})();