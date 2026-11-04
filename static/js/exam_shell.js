(() => {
  "use strict";

  const page = document.body;
  const shell = document.getElementById("exam-shell");
  if (!shell) return;

  const sectionsNode = document.getElementById("exam-section-tabs");
  const paletteNode = document.getElementById("question-palette");
  const questionNode = document.getElementById("section-container");
  const timerNode = document.getElementById("exam-timer");
  const onlineIndicator = document.getElementById("online-indicator");
  const themeToggle = document.getElementById("assessment-theme-toggle");
  const sectionNameNode = document.getElementById("current-section-name");
  const countNode = document.getElementById("section-count-summary");
  const finishDialog = document.getElementById("finish-exam-dialog");
  const finishSummary = document.getElementById("finish-exam-summary");
  const finishError = document.getElementById("finish-exam-error");
  const finalScreen = document.getElementById("exam-final-screen");
  const writeQueueKey = (attemptId) => `assessment-write-queue:${attemptId}`;
  const apiUrls = {
    state: page.dataset.examStateUrl,
    question: page.dataset.examQuestionUrl,
    mcq: page.dataset.mcqAnswerUrl,
    draft: page.dataset.codeDraftUrl,
    runCode: page.dataset.runCodeUrl,
    submitCode: page.dataset.submitCodeUrl,
    questionState: page.dataset.questionStateUrl,
    submitExam: page.dataset.submitExamUrl,
    status: page.dataset.statusUrl,
  };
  let attempt = null;
  let sessionId = "";
  let state = null;
  let currentQuestion = null;
  let activeQuestionModule = null;
  let currentSectionId = null;
  let clockOffset = 0;
  let timerInterval = null;
  let syncInterval = null;
  let saveInProgress = Promise.resolve();
  let finalizing = false;
  const notifiedThresholds = new Set();
  const queuedQuestionIds = new Set();

  const csrfToken = () => (
    document.querySelector("meta[name='csrf-token']")?.content || ""
  );
  const escapeHtml = (value) => String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
  const getQueue = () => {
    try {
      const queue = JSON.parse(localStorage.getItem(writeQueueKey(attempt.id)) || "[]");
      return Array.isArray(queue) ? queue : [];
    } catch (error) {
      notify(`Could not restore queued saves: ${error.message}`, "danger");
      return [];
    }
  };
  const saveQueue = (queue) => {
    try {
      localStorage.setItem(writeQueueKey(attempt.id), JSON.stringify(queue));
    } catch (error) {
      notify(`Could not store offline saves: ${error.message}`, "danger");
    }
  };
  const queuedPayload = (item) => item.payload || JSON.parse(item.options.body);
  const restoreQueuedAnswerState = () => {
    queuedQuestionIds.clear();
    const pending = new Map();
    getQueue().forEach((item) => {
      try {
        const payload = queuedPayload(item);
        const questionId = String(payload.question_id || "");
        if (!questionId) return;
        if (payload.action === "clear_response") pending.set(questionId, false);
        if (Array.isArray(payload.option_ids)) {
          pending.set(questionId, payload.option_ids.length > 0);
        }
        if (typeof payload.source_code === "string") {
          pending.set(questionId, Boolean(payload.source_code.trim()));
        }
      } catch (error) {
        notify(`Could not restore a queued answer: ${error.message}`, "danger");
      }
    });
    pending.forEach((hasAnswer, questionId) => {
      if (hasAnswer) queuedQuestionIds.add(questionId);
    });
  };
  const notify = (message, kind = "info") => {
    const toast = document.getElementById("exam-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.dataset.kind = kind;
    toast.classList.add("is-visible");
    window.clearTimeout(toast.hideTimer);
    toast.hideTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 4500);
  };
  const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const apiRequest = async (url, options = {}, retry = true) => {
    let response;
    try {
      for (let index = 0; index < (retry ? 3 : 1); index += 1) {
        try {
          response = await fetch(url, {
            credentials: "same-origin",
            ...options,
          });
          if (response.status < 500 || index === 2) break;
        } catch (error) {
          if (index === 2 || !retry) throw error;
          await wait(400 * (2 ** index));
        }
      }
    } catch (error) {
      throw new Error(navigator.onLine ? error.message : "You are offline.");
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 409 && /another tab or device/i.test(body.error || "")) {
        lockAsSuperseded();
      }
      throw new Error(body.error || "The assessment request failed.");
    }
    return body;
  };

  const post = async (url, payload, { queueOffline = true } = {}) => {
    const body = {
      ...payload,
      attempt_id: attempt.id,
      session_id: sessionId,
    };
    const options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        "X-Assessment-Session": sessionId,
      },
      body: JSON.stringify(body),
    };
    if (navigator.onLine && queueOffline && getQueue().length) {
      await flushQueue();
      if (getQueue().length) {
        const queue = getQueue();
        queue.push({ url, payload: body });
        saveQueue(queue);
        restoreQueuedAnswerState();
        return { queued: true };
      }
    }
    if (!navigator.onLine && queueOffline) {
      const queue = getQueue();
      queue.push({ url, payload: body });
      saveQueue(queue);
      return { queued: true };
    }
    try {
      return await apiRequest(url, options);
    } catch (error) {
      if (queueOffline && !navigator.onLine) {
        const queue = getQueue();
        queue.push({ url, payload: body });
        saveQueue(queue);
        return { queued: true };
      }
      throw error;
    }
  };

  const flushQueue = async () => {
    if (!navigator.onLine || !attempt) return;
    const queue = getQueue();
    const hadPendingWrites = queue.length > 0;
    while (queue.length) {
      try {
        const queuedRequest = queue[0];
        const payload = queuedPayload(queuedRequest);
        payload.session_id = sessionId;
        payload.attempt_id = attempt.id;
        await apiRequest(queuedRequest.url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken(),
            "X-Assessment-Session": sessionId,
          },
          body: JSON.stringify(payload),
        }, false);
        queue.shift();
        saveQueue(queue);
        restoreQueuedAnswerState();
      } catch (error) {
        if (/another tab or device|attempt has ended|expired/i.test(error.message)) {
          saveQueue([]);
          lockAsSuperseded();
        }
        notify(`Offline save sync failed: ${error.message}`, "warning");
        return;
      }
    }
    queuedQuestionIds.clear();
    if (state) renderNavigation();
    if (hadPendingWrites) notify("Offline responses synced.", "success");
  };

  const questionCollection = () => (state?.sections || []).filter(
    (section) => !section.expired,
  ).flatMap((section) => (
    section.questions.map((question) => ({ ...question, section_id: section.id }))
  ));
  const findQuestion = (questionId) => questionCollection().find(
    (question) => String(question.id) === String(questionId),
  );
  const findSection = (sectionId) => state?.sections.find(
    (section) => String(section.id) === String(sectionId),
  );
  const isAnswerPending = (questionId) => queuedQuestionIds.has(String(questionId));

  const renderNavigation = () => {
    if (!state) return;
    sectionsNode.innerHTML = state.sections.map((section) => (
      `<button type="button" class="exam-section-tab${String(section.id) === String(currentSectionId) ? " active" : ""}" data-section-id="${section.id}" role="tab" aria-selected="${String(section.id) === String(currentSectionId)}" ${section.expired ? "disabled" : ""}>
        <span>${escapeHtml(section.title)}</span><small>${section.questions.filter((question) => question.answered || isAnswerPending(question.id)).length}/${section.total} answered</small>
      </button>`
    )).join("");
    sectionsNode.querySelectorAll("[data-section-id]").forEach((button) => {
      button.addEventListener("click", () => {
        const section = findSection(button.dataset.sectionId);
        const firstQuestion = section?.questions[0];
        if (firstQuestion) void loadQuestion(firstQuestion.id);
      });
    });

    const section = findSection(currentSectionId);
    if (!section) return;
    if (section.expired) {
      paletteNode.innerHTML = "";
      countNode.textContent = "Section time expired";
      sectionNameNode.textContent = section.title;
      updateControls();
      return;
    }
    paletteNode.innerHTML = section.questions.map((question, index) => {
      let status = "not-visited";
      if (question.marked_for_review) status = "review";
      else if (question.answered || isAnswerPending(question.id)) status = "answered";
      else if (question.visited) status = "visited";
      return `<button type="button" class="question-palette-item ${status}${String(question.id) === String(currentQuestion?.id) ? " active" : ""}" data-question-id="${question.id}" aria-label="Question ${index + 1}, ${status.replace("-", " ")}">${index + 1}</button>`;
    }).join("");
    paletteNode.querySelectorAll("[data-question-id]").forEach((button) => {
      button.addEventListener("click", () => void loadQuestion(button.dataset.questionId));
    });
    const answered = section.questions.filter((question) => (
      question.answered || isAnswerPending(question.id)
    )).length;
    const marked = section.questions.filter((question) => question.marked_for_review).length;
    countNode.textContent = `${answered} of ${section.total} answered · ${marked} marked for review`;
    sectionNameNode.textContent = section.title;
    updateControls();
  };

  const setQuestionStatus = (questionId, updates) => {
    const section = (state?.sections || []).find((item) => (
      item.questions.some((question) => String(question.id) === String(questionId))
    ));
    const target = section?.questions.find(
      (question) => String(question.id) === String(questionId),
    );
    if (!target) return;
    Object.assign(target, updates);
    if (section) {
      section.answered = section.questions.filter((question) => (
        question.answered || isAnswerPending(question.id)
      )).length;
      section.marked = section.questions.filter((question) => question.marked_for_review).length;
    }
    renderNavigation();
  };

  const requestQuestion = async (questionId) => {
    const url = new URL(apiUrls.question, window.location.origin);
    url.searchParams.set("question_id", questionId);
    url.searchParams.set("attempt_id", attempt.id);
    url.searchParams.set("session_id", sessionId);
    return apiRequest(url.toString());
  };

  const moduleRequest = (kind, payload) => {
    const url = apiUrls[kind];
    if (!url) throw new Error("Question API is not configured.");
    return post(url, payload).then((result) => {
      const questionId = String(payload.question_id);
      if (!result.queued) {
        queuedQuestionIds.delete(questionId);
      } else {
        restoreQueuedAnswerState();
      }
      renderNavigation();
      return result;
    });
  };

  const loadQuestion = async (questionId) => {
    if (!findQuestion(questionId) || finalizing) return;
    if (activeQuestionModule?.save) {
      try {
        await activeQuestionModule.save();
      } catch (error) {
        if (/section's time has expired/i.test(error.message)) {
          const expiredSection = findSection(currentQuestion?.section_id);
          if (expiredSection) expiredSection.expired = true;
          window.AssessmentMCQ?.destroy();
          window.AssessmentCodingQuestion?.destroy();
          activeQuestionModule = null;
          currentQuestion = null;
          renderNavigation();
        } else {
          notify(`Could not save your response: ${error.message}`, "warning");
          return;
        }
      }
    }
    activeQuestionModule = null;
    window.AssessmentMCQ?.destroy();
    window.AssessmentCodingQuestion?.destroy();
    questionNode.innerHTML = '<div class="exam-loading-skeleton" aria-label="Loading question"><div></div><div></div><div></div></div>';
    questionNode.classList.add("is-loading");
    try {
      const question = await requestQuestion(questionId);
      currentQuestion = question;
      currentSectionId = question.section_id;
      const loadedSection = findSection(question.section_id);
      if (loadedSection) loadedSection.expires_at = question.section_expires_at;
      questionNode.innerHTML = question.html;
      questionNode.classList.remove("is-loading");
      const navQuestion = findQuestion(question.id);
      if (navQuestion) navQuestion.visited = true;
      const onAnswerChange = (answered) => {
        setQuestionStatus(question.id, { answered });
      };
      const request = (kind, payload) => {
        const endpointByKind = {
          mcq: apiUrls.mcq,
          draft: apiUrls.draft,
          runCode: apiUrls.runCode,
          submitCode: apiUrls.submitCode,
          questionState: apiUrls.questionState,
        };
        if (kind === "submitCode" || kind === "runCode") {
          return post(endpointByKind[kind], payload, { queueOffline: false });
        }
        return moduleRequest(kind === "draft" ? "draft" : kind, payload);
      };
      if (question.type === "mcq") {
        activeQuestionModule = window.AssessmentMCQ.init({
          container: questionNode,
          question,
          request: (kind, payload) => moduleRequest("mcq", payload),
          onAnswerChange,
        });
      } else {
        activeQuestionModule = window.AssessmentCodingQuestion.init({
          container: questionNode,
          question,
          request,
          onAnswerChange,
          allowPaste: Boolean(state.allow_paste_in_editor),
          notify,
        });
      }
      renderNavigation();
      currentSectionId = question.section_id;
      renderNavigation();
    } catch (error) {
      questionNode.classList.remove("is-loading");
      questionNode.innerHTML = `<div class="alert alert-warning">${escapeHtml(error.message)}</div>`;
      if (/section's time has expired/i.test(error.message)) {
        const expiredSection = findSection(findQuestion(questionId)?.section_id);
        if (expiredSection && !expiredSection.expired) expireSection(expiredSection);
      }
    }
  };

  const updateControls = () => {
    const questions = questionCollection();
    const index = questions.findIndex((question) => String(question.id) === String(currentQuestion?.id));
    document.getElementById("previous-question").disabled = index <= 0;
    document.getElementById("next-question").disabled = index < 0 || index >= questions.length - 1;
    const current = findQuestion(currentQuestion?.id);
    document.getElementById("mark-review").textContent = current?.marked_for_review
      ? "Remove Review Mark"
      : "Mark for Review";
  };

  const moveQuestion = async (offset) => {
    const questions = questionCollection();
    const index = questions.findIndex((question) => String(question.id) === String(currentQuestion?.id));
    const target = questions[index + offset];
    if (target) await loadQuestion(target.id);
  };

  const buildSummary = () => (state?.sections || []).map((section) => {
    const answered = section.questions.filter((question) => (
      question.answered || isAnswerPending(question.id)
    )).length;
    const marked = section.questions.filter((question) => question.marked_for_review).length;
    return `${section.title}: ${answered} answered, ${section.total - answered} not answered, ${marked} marked for review`;
  }).join("\n");

  const showFinalScreen = (message, status = "submitted", summary = "") => {
    finalizing = true;
    window.clearInterval(timerInterval);
    window.clearInterval(syncInterval);
    window.AssessmentMCQ?.destroy();
    window.AssessmentCodingQuestion?.destroy();
    document.querySelector(".exam-runner-layout")?.classList.add("d-none");
    sectionsNode.classList.add("d-none");
    finalScreen.classList.remove("d-none");
    document.getElementById("exam-final-title").textContent = status === "timed_out"
      ? "Time is up"
      : "Assessment submitted";
    document.getElementById("exam-final-message").textContent = message;
    document.getElementById("exam-final-summary").textContent = summary;
    document.getElementById("finish-exam").disabled = true;
    finishDialog.classList.add("d-none");
  };

  const lockAsSuperseded = () => {
    if (finalizing) return;
    finalizing = true;
    window.clearInterval(timerInterval);
    window.clearInterval(syncInterval);
    document.querySelector(".exam-runner-layout")?.classList.add("d-none");
    document.getElementById("finish-exam").disabled = true;
    window.Proctor?.stop();
    notify("This attempt is now active in another tab or device. This page is locked.", "danger");
    questionNode.innerHTML = '<div class="alert alert-danger" role="alert">This attempt is active in another tab or device. This page is locked.</div>';
  };

  const submitExam = async (timedOut = false) => {
    if (finalizing) return;
    finalizing = true;
    document.getElementById("confirm-finish-exam").disabled = true;
    finishError.textContent = "";
    try {
      try {
        await activeQuestionModule?.save?.();
      } catch (error) {
        if (!/section's time has expired/i.test(error.message)) throw error;
        notify("The current section has expired; submitting the saved responses.", "warning");
      }
      const result = await post(apiUrls.submitExam, {
        action: timedOut ? "time_expired" : "manual",
      }, { queueOffline: false });
      showFinalScreen(
        timedOut
          ? "Time is up. Your assessment has been submitted."
          : "Your assessment has been submitted successfully.",
        "submitted",
        `Score: ${result.score} / ${result.max_score} · ${result.correct} correct · ${result.incorrect} incorrect · ${result.unanswered} unanswered`,
      );
      window.Proctor?.stop();
      finishDialog.classList.add("d-none");
    } catch (error) {
      finalizing = false;
      finishError.textContent = error.message;
      document.getElementById("confirm-finish-exam").disabled = false;
      if (timedOut && /expired/i.test(error.message)) {
        try {
          const status = await apiRequest(`${apiUrls.status}?attempt_id=${attempt.id}&session_id=${sessionId}`);
          if (status.attempt?.status === "timed_out" || status.attempt?.status === "submitted") {
            showFinalScreen("Time is up. Your assessment has been submitted.", status.attempt.status);
            window.Proctor?.stop();
          }
        } catch (statusError) {
          notify(statusError.message, "danger");
        }
      }
    }
  };

  const formatTime = (seconds) => {
    const value = Math.max(0, Math.floor(seconds));
    return [Math.floor(value / 3600), Math.floor((value % 3600) / 60), value % 60]
      .map((part) => String(part).padStart(2, "0"))
      .join(":");
  };
  const expireSection = (section) => {
    section.expired = true;
    const remainingSection = state.sections.find((item) => !item.expired);
    notify(`Time for ${section.title} has ended.`, "warning");
    if (!remainingSection) {
      window.AssessmentMCQ?.destroy();
      window.AssessmentCodingQuestion?.destroy();
      activeQuestionModule = null;
      currentQuestion = null;
      sectionNameNode.textContent = section.title;
      questionNode.innerHTML = '<div class="alert alert-warning">Section time has ended. You can finish and submit the assessment.</div>';
      renderNavigation();
      return;
    }
    activeQuestionModule = null;
    currentQuestion = null;
    currentSectionId = remainingSection.id;
    window.AssessmentMCQ?.destroy();
    window.AssessmentCodingQuestion?.destroy();
    renderNavigation();
    if (remainingSection.questions.length) {
      void loadQuestion(remainingSection.questions[0].id);
    }
  };
  const renderTimer = () => {
    if (!attempt?.expires_at) return;
    const remaining = Math.max(
      0,
      Math.ceil((Date.parse(attempt.expires_at) - (Date.now() + clockOffset)) / 1000),
    );
    timerNode.textContent = formatTime(remaining);
    timerNode.classList.toggle("is-low", remaining <= 300);
    const currentSection = findSection(currentSectionId);
    const sectionTimer = document.getElementById("section-time-remaining");
    if (sectionTimer && currentSection?.expires_at && !currentSection.expired) {
      const sectionRemaining = Math.max(
        0,
        Math.ceil((Date.parse(currentSection.expires_at) - (Date.now() + clockOffset)) / 1000),
      );
      sectionTimer.textContent = `Section time: ${formatTime(sectionRemaining)}`;
      if (sectionRemaining === 0) expireSection(currentSection);
    } else if (sectionTimer) {
      sectionTimer.textContent = "";
    }
    [600, 300, 60].forEach((threshold, index, thresholds) => {
      const lowerThreshold = thresholds[index + 1] || 0;
      if (remaining <= threshold && remaining > lowerThreshold && !notifiedThresholds.has(threshold)) {
        notifiedThresholds.add(threshold);
        notify(`${Math.ceil(threshold / 60)} minute${threshold === 60 ? "" : "s"} remaining.`, "warning");
      }
    });
    if (remaining === 0) void submitExam(true);
  };

  const syncStatus = async () => {
    try {
      const status = await apiRequest(
        `${apiUrls.status}?attempt_id=${attempt.id}&session_id=${sessionId}`,
      );
      if (status.attempt?.server_time) {
        clockOffset = Date.parse(status.attempt.server_time) - Date.now();
      }
      if (status.attempt?.status === "submitted" || status.attempt?.status === "timed_out") {
        showFinalScreen(
          status.attempt.status === "timed_out"
            ? "Time is up. Your assessment has been submitted."
            : "Your assessment has already been submitted.",
          status.attempt.status,
        );
        window.Proctor?.stop();
      }
      renderTimer();
    } catch (error) {
      if (navigator.onLine) notify(`Timer sync failed: ${error.message}`, "warning");
    }
  };

  const openFinishDialog = () => {
    if (finalizing) return;
    finishSummary.textContent = buildSummary();
    finishError.textContent = "";
    finishDialog.classList.remove("d-none");
    document.getElementById("cancel-finish-exam").focus();
  };

  const init = async (initialAttempt, activeSessionId) => {
    attempt = initialAttempt;
    sessionId = activeSessionId;
    finalizing = false;
    window.Proctor?.setExamPolicy({
      allowPasteInEditor: Boolean(state?.allow_paste_in_editor),
    });
    const url = new URL(apiUrls.state, window.location.origin);
    url.searchParams.set("attempt_id", attempt.id);
    url.searchParams.set("session_id", sessionId);
    const examState = await apiRequest(url.toString());
    state = examState;
    restoreQueuedAnswerState();
    attempt = examState.attempt;
    clockOffset = Date.parse(examState.server_time) - Date.now();
    window.Proctor?.setAttempt({ ...attempt, session_id: sessionId });
    window.Proctor?.setExamPolicy({
      allowPasteInEditor: Boolean(state.allow_paste_in_editor),
    });
    currentSectionId = examState.current_section_id;
    if (!findSection(currentSectionId) || findSection(currentSectionId).expired) {
      currentSectionId = examState.sections.find((section) => !section.expired)?.id || null;
    }
    renderNavigation();
    window.clearInterval(timerInterval);
    timerInterval = window.setInterval(renderTimer, 1000);
    window.clearInterval(syncInterval);
    syncInterval = window.setInterval(() => {
      void syncStatus();
      void flushQueue();
    }, 30_000);
    window.addEventListener("online", flushQueue);
    renderTimer();
    updateOnlineIndicator();
    const preferred = findQuestion(examState.current_question_id)
      || questionCollection()[0];
    if (preferred) await loadQuestion(preferred.id);

    document.getElementById("previous-question").onclick = () => void moveQuestion(-1);
    document.getElementById("next-question").onclick = () => void moveQuestion(1);
    document.getElementById("save-next").onclick = async () => {
      try {
        await activeQuestionModule?.save?.();
        await moveQuestion(1);
      } catch (error) {
        notify(`Could not save your response: ${error.message}`, "warning");
      }
    };
    document.getElementById("mark-review").onclick = async () => {
      const question = findQuestion(currentQuestion?.id);
      if (!question) {
        notify("Load a question before marking it for review.", "warning");
        return;
      }
      const marked = !question.marked_for_review;
      setQuestionStatus(question.id, { marked_for_review: marked });
      try {
        await moduleRequest("questionState", {
          question_id: question.id,
          action: "mark_for_review",
          marked,
        });
        notify(marked ? "Question marked for review." : "Review mark removed.", "success");
      } catch (error) {
        setQuestionStatus(question.id, { marked_for_review: !marked });
        notify(`Could not update the review mark: ${error.message}`, "warning");
      }
    };
    document.getElementById("clear-response").onclick = async () => {
      if (!currentQuestion) return;
      try {
        await moduleRequest("questionState", {
          question_id: currentQuestion.id,
          action: "clear_response",
        });
        activeQuestionModule?.clear?.();
        setQuestionStatus(currentQuestion.id, {
          answered: false,
          marked_for_review: false,
        });
      } catch (error) {
        notify(error.message, "warning");
      }
    };
    document.getElementById("finish-exam").onclick = openFinishDialog;
    document.getElementById("cancel-finish-exam").onclick = () => finishDialog.classList.add("d-none");
    document.getElementById("confirm-finish-exam").onclick = () => void submitExam(false);
    themeToggle.onclick = () => {
      const root = document.documentElement;
      const theme = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = theme;
      try {
        localStorage.setItem("editorTheme", theme);
      } catch (error) {
        notify(`Could not save your theme preference: ${error.message}`, "warning");
      }
      themeToggle.textContent = theme === "light" ? "Dark theme" : "Light theme";
      if (window.assessmentEditor && window.monaco) {
        window.monaco.editor.setTheme(theme === "light" ? "vs" : "vs-dark");
      }
    };
    themeToggle.textContent = document.documentElement.dataset.theme === "light"
      ? "Dark theme"
      : "Light theme";
    document.addEventListener("keydown", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.target.matches("input,textarea,select,[contenteditable=true],.monaco-editor")) return;
      if (event.key === "ArrowRight") void moveQuestion(1);
      if (event.key === "ArrowLeft") void moveQuestion(-1);
      if (event.key.toLowerCase() === "m") document.getElementById("mark-review").click();
    });
    await flushQueue();
  };

  const updateOnlineIndicator = () => {
    if (!onlineIndicator) return;
    onlineIndicator.classList.toggle("is-offline", !navigator.onLine);
    onlineIndicator.lastChild.textContent = navigator.onLine ? " Online" : " Offline";
  };
  window.addEventListener("online", updateOnlineIndicator);
  window.addEventListener("offline", updateOnlineIndicator);

  window.AssessmentExam = {
    init,
    submit: submitExam,
    showFinalScreen,
    saveCurrent: async () => {
      try {
        await activeQuestionModule?.save?.();
      } catch (error) {
        if (!/section's time has expired/i.test(error.message)) throw error;
      }
    },
    getSessionId: () => sessionId,
    isFinalizing: () => finalizing,
    refreshQuestion: (id) => loadQuestion(id),
    notify,
  };
})();
