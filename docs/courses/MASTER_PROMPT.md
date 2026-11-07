# BashaByte Courses — Master Prompt for Claude Code

> **How to use this file**
> 1. Save it in the repo as `docs/courses/MASTER_PROMPT.md`.
> 2. Add one line to your `CLAUDE.md`: `For any work on the courses app, read docs/courses/MASTER_PROMPT.md first and follow it.`
> 3. Start every phase with the short "Start prompt" given under that phase. Do one phase at a time. Do not start the next phase until the current one passes its acceptance checklist.

---

## PART A — Master prompt (Claude Code reads this every time)

### 1. Your role

You are the lead engineer building the **Courses** product inside BashaByte, an existing Django platform. The goal is a world-class learning platform, at the level of GeeksforGeeks, Coding Ninjas, CS50 and the Helsinki Python MOOC. Quality matters more than speed: clean models, tested code, fast pages, and an experience students enjoy.

### 2. Project context (verify by reading the code; trust the code over this file)

- **BashaByte** is a LeetCode-style platform built with Django 5.x, PostgreSQL, Django templates, Bootstrap 5 and vanilla JavaScript.
- **Existing apps:** `users` (custom user model `users.Users`, UUID primary key, email login, platform roles user/moderator/admin), `problems`, `submissions`, `contests`, `discussions`, `premium`, `study_plans`, `colleges`, `courses` (empty, nothing built yet), and an MCQ question bank.
- **Problem detail page:** Monaco editor, resizable panels and run/submit. Code execution happens through the submissions flow. Find out whether it uses `subprocess` or Judge0, and reuse that same path.
- **Assessments:** faculty create and conduct assessments (MCQ + coding). The MCQ bank is reusable and is designed for an Assessment → AssessmentQuestion → MCQ structure.
- **Staff area:** `/staff/` (is_staff only) holds problem CRUD, CSV/XLSX import, user management and progress exports.
- **Colleges app:** College, Department, CollegeMembership (COLLEGE_ADMIN / HOD / FACULTY / STUDENT), AcademicYear, Section, AcademicSession and StudentAcademicAssignment. `colleges` depends on `users`; `users` must never depend on `colleges`.
- **Themes:** light (warm cream + charcoal + #FFA116 accent) and dark (near-black + green). Avoid generic AI-template UI: no glassmorphism, excess gradients or card overload.
- **Deployed** on Render. Keep anything that needs workers (Celery) optional, behind settings.

### 3. Product we are building (summary of the curriculum spec)

- **Catalog:** 13 categories (Core Python + 12 specialisations such as DSA, Web, Data Analytics, Data Science, AI Engineering, Data Engineering, QA Automation, Cloud/DevOps, LLD & System Design). Students choose a **career path**, which is an ordered list of courses.
- **Structure:** Course → Module (Core has 12, each specialisation has 8) → Lesson (exactly 6 per module) → Steps. Every module and lesson has **learning outcomes**, and every question or task is tagged to one outcome.
- **Lesson flow (8 steps):** Hook (text) → Concept video (5–8 min) → Notes (text) → Predict-the-output MCQs → Try it in the compiler (playground) → Parsons problem → Quick-check MCQs + Fix-the-bug → 3–4 coding tasks.
- **Lesson completion rule:** video watched (or marked), quick check ≥ 60%, at least 2 coding tasks passing all tests. A module unlocks when the previous module's exam is passed.
- **Module exam:** 75 minutes, 100 marks, pass mark 60. 20 MCQs (concept + output/debug) + 3 coding problems + 5 revision MCQs from earlier modules. Questions are drawn randomly from pools, with a retake cooldown of 24 hours.
- **Capstone (Project Standard):** GitHub repo, README, tests, 3-minute demo video, and an approved proposal. Graded on a rubric: works 30, code quality 20, tests 20, design 15, communication 15.
- **AI policy:** a hint-only AI tutor is allowed; it never gives graded solutions.
- **Feedback:** three hint levels per task and plain-English error explanations.
- **Placement test** lets students skip Core modules. **Certificates** are verifiable.

### 4. Non-negotiable engineering rules

1. **Do not break existing features.** The public problem-solving flow, contests, leaderboard, assessments, colleges and staff area must keep working. Run the full test suite before and after every phase.
2. **No new frontend framework.** Use Django templates, Bootstrap 5 and vanilla JS. A small, CDN-loaded, single-purpose library (e.g. SortableJS for drag-and-drop) is allowed only if you explain why.
3. **Reuse, don't duplicate.** Use the existing submissions/judge for code, the MCQ bank for questions, `discussions` for Q&A, `/staff/` patterns for staff UI, and `colleges` for cohorts. Create a new model only when no existing one fits, and say why.
4. **Migrations only via `makemigrations` / `migrate`.** Never hand-write migration files. Keep migrations small and reversible.
5. **Plan before code.** At the start of each phase, explore the relevant code. Then write a plan (models, URLs, views, templates, tests, risks) and **wait for my approval** before changing files.
6. **Small slices.** Implement in vertical slices (model → view → template → test). After each slice run tests and tell me what changed.
7. **Tests are required.** Write model, view, permission and edge-case tests for every feature. Target at least 85% coverage of new code. Never weaken an existing test to make it pass.
8. **Security and permissions.** Check permissions on every view: student, faculty, staff and college roles. Never trust client-side completion data; verify on the server. Treat uploaded files and URLs as untrusted.
9. **Performance.** No N+1 queries (use `select_related` / `prefetch_related` and check the query count in tests). Paginate lists. Cache read-heavy catalog pages.
10. **Settings and secrets.** Every external service (video host, AI provider, email) is configured through environment variables, with a feature flag so the site works without it.
11. **Accessibility.** Use semantic HTML, labels, keyboard navigation, visible focus, and enough contrast in both themes. Layouts must work at phone width.
12. **Documentation.** At the end of each phase, update `docs/courses/CHANGELOG.md` and the courses section in `bashabyte_context.txt`.
13. **Ask when unsure.** If a decision is irreversible or the spec is ambiguous, stop and ask me. Do not guess.

### 5. Phase protocol (follow it every phase)

1. **Explore:** read the code relevant to this phase and list what already exists that we can reuse.
2. **Plan:** list models and fields, URLs, views, templates, JS, tests, migrations and risks. Wait for my "approved".
3. **Build:** work slice by slice. Run `python manage.py check`, `makemigrations --check` and the tests after each slice.
4. **Verify:** run the full test suite. Do a manual QA walkthrough (give me the exact URLs and steps). Check both themes and phone width.
5. **Report:** what was built, files changed, tests added, known limitations, and anything to do before the next phase.

---

## PART B — The phases

### Phase 0 — Discovery and architecture (no feature code)

**Goal:** understand the codebase and lock the design before building anything.

- Map the existing apps, models and URLs relevant to courses: users, problems, submissions/judge, MCQ bank, assessments, discussions, premium, colleges and the staff area.
- Document how code execution works (subprocess vs Judge0), including its time/memory limits and how test cases are stored.
- Write `docs/courses/ARCHITECTURE.md` containing:
  - an ER diagram (Mermaid) of the planned course models;
  - the step-type design;
  - which existing models are reused;
  - the permission matrix (anonymous, student, faculty, staff, college roles);
  - URL map;
  - feature-flag list.
- Propose the step-content design: a typed model per step type vs a JSON `content` field with schema validation. Explain the trade-offs and recommend one.

**Acceptance:** I have approved `ARCHITECTURE.md`. No migrations yet.

**Start prompt:** `Read docs/courses/MASTER_PROMPT.md. Start Phase 0. Explore the codebase and produce docs/courses/ARCHITECTURE.md. Do not write feature code.`

---

### Phase 1 — Content model and staff course builder

**Goal:** staff can build a full course (Core Python v2) in the admin and the `/staff/` area.

**Models** (adjust to the approved architecture):

- `Category` (title, slug, order, icon, description)
- `CareerPath` (title, ordered courses)
- `Course` (category, title, slug, level, version, prerequisites, est_weeks, is_published, is_free_preview)
- `Module` (course, order, title, intro_video, mini_project_brief, outcomes)
- `Lesson` (module, order, title, est_minutes, outcomes)
- `LearningOutcome` (text, module/lesson, code like `PY-M3-L2-O1`)
- `LessonStep` (lesson, order, step_type, title, required, content, outcome tags)
- **Step types:** VIDEO, TEXT, PREDICT, PLAYGROUND, PARSONS, QUIZ, FIX_BUG, CODING
- **Links to existing models:** QUIZ/PREDICT → MCQ bank (ordered M2M); CODING/FIX_BUG → `problems.Problem`

**Features:**

- Admin registration with inlines.
- Staff UI: create and edit course → modules → lessons → steps. Drag to reorder. Search and attach existing MCQs and problems. Tag outcomes.
- Lesson preview as a student would see it (read-only).
- Bulk import of a module from an XLSX/CSV template (lessons, steps, MCQ references), with a dry-run report. Reuse the existing import logic patterns.
- Validation rules:
  - exactly 6 lessons per module (warning, not a hard block, while drafting);
  - every QUIZ question and CODING task must carry an outcome tag before publishing.
- Seed command: `python manage.py seed_core_python` creates the Core Python v2 skeleton (12 modules, 72 lessons with titles).

**Acceptance:** Core Python skeleton seeded. Staff can build one complete lesson with all 8 step types (content can be placeholder). Publish validation works. Tests pass.

**Start prompt:** `Start Phase 1 per docs/courses/MASTER_PROMPT.md. Begin with the plan and wait for approval.`

---

### Phase 2 — Catalog, career paths and enrollment

**Goal:** students discover courses and enroll.

- **Catalog page:** categories, course cards (modules, lessons, weeks, level, prerequisites) and a career-path picker ("I want: placement / backend / data / AI / QA / DevOps").
- **Course landing page:** outcomes, full syllabus accordion (module → lessons), capstone, prerequisites, free preview lessons, and an enroll button.
- `Enrollment` model (user, course, status, started_at, completed_at, current_module). Enrollment respects `premium` for paid courses (reuse the premium app). The first module or preview lessons are free.
- **"My learning" dashboard:** enrolled courses, progress bar, "continue where you left off".
- SEO: clean URLs, meta tags, Open Graph. Cache catalog pages.

**Acceptance:** an anonymous user can browse and preview; a logged-in user can enroll; premium gating works; query counts are tested.

---

### Phase 3 — Lesson player and progress (VIDEO, TEXT, PLAYGROUND)

**Goal:** the core learning experience.

- **Lesson player layout:** left = step list with status icons; centre = current step; top = module/lesson breadcrumb; Next/Previous buttons. It must work on phones (the step list collapses into a drawer).
- **VIDEO:** embed by provider ID (unlisted YouTube or a video CDN, set in settings). Track progress through the player API; mark watched at ≥ 80%. Show chapters and transcript text, with search inside the transcript.
- **TEXT:** Markdown rendered safely (sanitised HTML), code blocks with syntax highlighting and a "Copy" button, and a "Common mistakes" callout style.
- **PLAYGROUND:** Monaco editor preloaded with starter code; Run only (no grading), using the existing execution path. Show stdout/stderr and the time taken.
- `StepProgress` (user, step, status, score, attempts, last_position, completed_at) and `LessonProgress` / `ModuleProgress` (computed or cached).
- Server-side completion rules from Part A §3. Module locking and unlocking. Resume at the last position.

**Acceptance:** a student can complete a lesson made of VIDEO + TEXT + PLAYGROUND steps; progress persists across devices; locked modules cannot be opened by URL; tests cover the completion rules.

---

### Phase 4 — Interactive practice and feedback

**Goal:** practice that teaches, not just grades.

- **QUIZ and PREDICT:** reuse the MCQ bank. Show an explanation for every option after answering. Score is stored per attempt; best score counts.
- **PARSONS:** drag-and-drop lines with indentation levels; the order is checked on the server; optional distractor lines.
- **FIX_BUG:** buggy starter code + hidden tests, graded through the existing judge.
- **CODING:** embed the existing problem solve experience inside the lesson. Hidden tests, partial marks, and a clear first-failing-case message (where the problem allows showing it).
- **Tiered hints** per CODING/FIX_BUG step: 3 levels, each unlocked after an attempt. Hint usage is logged.
- **Error explainer:** a rule-based mapper from common Python tracebacks (NameError, IndentationError, TypeError, IndexError, KeyError, ZeroDivisionError, etc.) to plain-English explanations with a fix tip. It must be data-driven so staff can add rules.
- Outcome mastery per student, calculated from tagged questions.

**Acceptance:** all 8 step types work end to end; the lesson completion rule uses real scores; hints and the error explainer appear correctly; tests cover grading edge cases.

---

### Phase 5 — Module exams and placement test

**Goal:** fair, cheat-resistant assessment.

- Build on the planned `Assessment → AssessmentQuestion → MCQ` structure, extended to coding problems. Do not create a parallel exam system.
- `ModuleExam` with a blueprint (counts per section and per outcome/topic). Each attempt draws random questions from pools; MCQ options are shuffled.
- Exam runner: timer, auto-save, auto-submit on timeout, section navigation. Reuse the existing exam-runner UI styles.
- **Integrity:** log tab switches, paste events and full-screen exits. Show these to staff; do not auto-fail on them.
- **Result page:** section scores, topic/outcome-wise breakdown, links back to weak lessons. Pass unlocks the next module. Retake cooldown of 24 hours with a fresh question draw.
- **Placement test** for Core Python: passing a module's section marks that module as tested-out.

**Acceptance:** two attempts by the same student get different question sets; the timer is enforced on the server; unlocking works; faculty/staff can view attempts and logs.

---

### Phase 6 — Projects, certificates and portfolio

**Goal:** proof of skill that employers trust.

- `ProjectProposal` and `ProjectSubmission`: GitHub URL, demo video URL, README check, status (draft → submitted → in review → changes requested → passed).
- Staff/mentor review screen with the rubric (5 criteria, weights from Part A §3), written feedback and a resubmission flow.
- **Certificates:** generated when all module exams and the capstone are passed. PDF with a unique ID and QR code; public verification page `/certificates/<id>/`; lists modules and projects completed.
- **Project gallery:** staff-picked passing projects, filterable by course.
- **Public portfolio profile:** courses completed, certificates, projects, solved problems and streaks. The student can make it private.

**Acceptance:** the full capstone flow works with review and resubmission; the certificate verifies publicly; the profile respects privacy settings.

---

### Phase 7 — Engagement, revision and community

**Goal:** students keep coming back and remember what they learned.

- **Spaced revision queue:** `ReviewItem` (user, MCQ, due_on, interval, ease). Wrong or old answers come back on a schedule. Show "5 for today" on the dashboard.
- **Streaks and daily goals:** badges only for real milestones (module passed, 7-day streak, capstone passed).
- **Progress dashboard:** module completion, outcome mastery map (heatmap by module), weak topics, and next best lesson.
- **Lesson discussions:** reuse the `discussions` app, attached to lessons and steps. Mentor answers are highlighted.
- **Notifications:** email + on-site for streak reminders, exam results, review feedback and new content. Rate-limited, with user-controlled preferences.
- **Cohorts:** batch groups with shared deadlines and a cohort leaderboard.

**Acceptance:** the review queue schedules correctly (tested with frozen time); notifications respect preferences; discussions work inside the lesson player.

---

### Phase 8 — AI tutor and AI code review (behind feature flags)

**Goal:** 24×7 help that guides without giving away answers.

- **Provider adapter:** set through environment variables; the platform works fully with the AI flag off.
- **Hint-only tutor** inside the lesson player and on coding steps:
  - context = lesson notes, the step and the student's current code;
  - a system prompt that refuses full graded solutions and asks guiding questions;
  - per-user daily limits;
  - every conversation logged for staff review;
  - a visible AI policy link.
- **AI code review** after a correct submission: comments on naming, structure, edge cases and complexity. It never appears before the student passes.
- Prompt-injection safety: treat student code and text as data, not instructions.
- Staff dashboard: usage, cost estimate, flagged conversations.

**Acceptance:** the tutor refuses "give me the full solution" for graded steps (covered by tests with a mocked provider); limits and logging work; the flag off hides everything cleanly.

---

### Phase 9 — Notebook mode and code visualiser

**Goal:** first-class experience for the data tracks and for beginners.

- **Notebook mode** for Data Analytics, Data Science, AI and Data Engineering lessons: cell-based editor with preloaded datasets. Evaluate an in-browser Python runtime (Pyodide / JupyterLite) against a server kernel; recommend one with trade-offs before building.
- **Output-based grading** for notebook tasks, e.g. a DataFrame's shape or columns, or a metric above a threshold.
- **Code visualiser** for Core Python: step through code line by line, showing variables, lists/dicts and the call stack (Python Tutor-style), embedded as a step option.

**Acceptance:** a pandas lesson runs fully in the notebook step on a mid-range laptop and a phone; the visualiser handles loops, functions and recursion examples from Core Modules 5–6.

---

### Phase 10 — Analytics, colleges, integrity and scale

**Goal:** run the platform like a world-class product.

- **Content analytics for staff:** drop-off per step, average time per lesson, MCQ difficulty and discrimination index, problem pass rates, and the most-used hints. Export to XLSX.
- **College integration:** assign courses to college sections/sessions (reuse `colleges`), faculty dashboards for their students, and cohort exports.
- **Plagiarism:** code similarity between submissions of the same task (e.g. token-based), with a flag list for staff.
- **Proctoring for certificate finals** (webcam snapshot opt-in, logs) — check legal and privacy rules first.
- **Content versioning:** course v2 → v3 with a migration plan for enrolled students.
- **Performance:**
  - Redis caching for catalog and syllabus pages;
  - CDN for static files and videos;
  - query audit;
  - Lighthouse score ≥ 90 on lesson pages.
- **Accessibility audit** (WCAG AA) and subtitles in more languages (Telugu, Hindi).
- **Privacy:** data export and delete-my-data, aligned with India's DPDP Act. Admin audit log.

**Acceptance:** analytics numbers are verified against raw data in tests; the college flow works end to end; performance and accessibility targets are met.

---

## PART C — Definition of "done" for the whole Courses product

- [ ] Core Python v2 fully loaded: 12 modules, 72 lessons, all step types, exams and capstone.
- [ ] A student can go from catalog → enroll → lessons → exams → capstone → verified certificate without staff help.
- [ ] Staff can build and import a new course without a developer.
- [ ] All existing BashaByte features still pass their tests.
- [ ] Pages load fast on mobile data; both themes polished; accessible.
- [ ] Analytics show where students struggle, so content can improve after every batch.