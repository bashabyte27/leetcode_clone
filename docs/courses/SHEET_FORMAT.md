# Course content sheet format

This is the format for writing a BashaByte course in Google Sheets so the importer can load it without manual fixes. It follows the layout already used in the `courses` spreadsheet, so the existing Core Python rows (Modules 0 and 1) are already valid.

- **One tab = one course.** For example `Core Python`, `Java`, `DSA Using Python`.
- **One row = one item:** the course, a module, a lesson, an outcome, a step, an MCQ, a coding problem, a test case or a hint.
- **The `code` column is each item's permanent identity.** Re-importing a tab updates items by code. It never creates duplicates.

---

## 1. Columns

Keep these 26 headers, in this order, in row 1 (A to Z). The importer reads columns by header name, so the order is a convention, but the spelling must be exact.

| Col | Header | Meaning |
|---|---|---|
| A | `record_type` | `COURSE`, `MODULE`, `LESSON`, `OUTCOME`, `STEP`, `MCQ`, `PROBLEM`, `TESTCASE`, `HINT` |
| B | `code` | Permanent unique id (see §3) |
| C | `parent_code` | Code of the item this row belongs to |
| D | `order` | Position inside the parent: a whole number, 1, 2, 3… (0 only for an introduction module) |
| E | `module_no` | Module number. For readability and filtering only; must agree with `code` |
| F | `lesson_no` | Lesson number. For readability and filtering only; must agree with `code` |
| G | `title` | Short title shown to students |
| H | `step_type` | Only on `STEP` rows (see §5) |
| I | `outcome_codes` | Outcome codes separated by `;` |
| J | `difficulty` | `BEGINNER` / `INTERMEDIATE` / `ADVANCED` on `COURSE`; `EASY` / `MEDIUM` / `HARD` on `MCQ` and `PROBLEM` |
| K | `body` | Main text, in Markdown. Its meaning depends on the row type |
| L–O | `option_a` … `option_d` | MCQ options |
| P | `correct_option` | `A`–`D`, or several separated by `;` (e.g. `A;C`) |
| Q | `explanation` | Shown after answering or solving |
| R | `starter_code` | Code the student starts with (buggy code on fix-the-bug problems) |
| S | `solution_code` | Reference solution (never shown to students), or the correct program for Parsons |
| T | `input` | Standard input (test cases, playground) |
| U | `expected_output` | Expected standard output (test cases) |
| V | `is_hidden` | `TRUE` / `FALSE` (test cases) |
| W | `language` | On PROBLEM and PLAYGROUND rows: a runnable language slug from the platform (`python`, `java`, `cpp`, `c`, `javascript`, …). On MCQ and PARSONS rows it only sets syntax colouring, so `shell`, `text` and the like are fine too |
| X | `points` | Whole number. Used as the test-case weight; recorded but not used elsewhere yet |
| Y | `meta_json` | Extra settings as JSON (see each row type) |
| Z | `status` | `DRAFT`, `REVIEW` or `READY`. For your workflow only (see §7) |

Columns not listed for a row type are ignored; leave them blank.

---

## 2. General rules

Every course tab already has the 26 headers, a frozen header row and first two columns, and drop-down lists for `record_type`, `step_type`, `difficulty`, `is_hidden` and `status`. The drop-downs warn about a wrong value but don't block it. To start a new course, duplicate an empty tab (for example `Java`) and rename it.


1. **Keep the sheet formatted as plain text.** Every tab is already set up this way, and new tabs should copy it. Select all cells, then choose **Format → Number → Plain text**. Without this, Google Sheets silently changes values: `3.10` becomes `3.1`, `1:30` becomes a time, `1/2` becomes a date, `007` becomes `7`, and a cell that starts with `=` becomes a formula. Expected outputs and code are where this does the most damage.
2. **Multi-line text:** press Ctrl + Enter (⌘ + Enter on a Mac) inside a cell. Leading spaces in code are kept and count; indent with 4 spaces, not tabs.
3. **`meta_json` must be valid JSON.** Keys not described here (for example `review_every_months`, `style_check`, `rubric`, `offline_task`) are kept for later phases and never cause an error. The rules: double quotes only (`"key": "value"`), `true` / `false` in lowercase, no trailing commas. Leave it blank if there is nothing to set.
4. **Blank rows are skipped.** Row order does not matter, because positions come from `order`, so you can group rows however you like.
5. **A cell can hold at most 50,000 characters** (a Google Sheets limit). Split very long notes into two TEXT steps.
6. **Never change or reuse a code** once a row has been imported. A changed code is treated as a new item, and the old one stays in the database.
7. **Deleting a row does not delete anything in the app.** The import report lists items that are in the app but no longer in the sheet; staff delete them in the builder. This protects student progress.

---

## 3. Codes

All codes start with the course code (`PY` for Core Python). Number with two digits where shown (`S01`, `Q01`).

| Item | Pattern | Example | `parent_code` |
|---|---|---|---|
| Course | `{C}` | `PY` | blank |
| Module | `{C}-M{m}` | `PY-M1` | `PY` |
| Lesson | `{C}-M{m}-L{l}` | `PY-M1-L2` | `PY-M1` |
| Course outcome | `{C}-O{n}` | `PY-O3` | `PY` |
| Module outcome | `{C}-M{m}-O{n}` | `PY-M1-O2` | `PY-M1` |
| Lesson outcome | `{C}-M{m}-L{l}-O{n}` | `PY-M1-L2-O1` | `PY-M1-L2` |
| Step | `{lesson}-S{nn}` | `PY-M1-L2-S04` | the lesson |
| Predict MCQ | `{lesson}-P{nn}` | `PY-M1-L2-P01` | its PREDICT step |
| Quiz MCQ | `{lesson}-Q{nn}` | `PY-M1-L2-Q03` | its QUIZ step |
| Fix-the-bug problem | `{lesson}-FB{nn}` | `PY-M1-L2-FB01` | its FIX_BUG step |
| Coding problem | `{lesson}-C{nn}` | `PY-M1-L2-C02` | its CODING step |
| Mini-project | `{module}-MP{nn}` | `PY-M1-MP01` | the module |
| Test case | `{problem}-T{n}` | `PY-M1-L2-C02-T1` | the problem |
| Hint | `{problem}-H{1-3}` | `PY-M1-L2-C02-H2` | the problem |

MCQ and problem codes also become their IDs in the shared question bank (lowercased), so the course prefix keeps them unique across all courses.

---

## 4. Row types

### COURSE (one per tab)

| Column | Use |
|---|---|
| `title` | Course name |
| `difficulty` | `BEGINNER` / `INTERMEDIATE` / `ADVANCED` |
| `body` | Course description |
| `language` | Main language, e.g. `python` |
| `meta_json` | `category` (catalog category name, required); `version` (`"v2"` or `2`); `est_weeks`; `prerequisites` (list of course codes); `access` (`"free"` / `"premium"`, default free); `subtitle`; `capstone_brief`; `placement_test` (true / false). `course_outcomes` is an optional check: if present, it must list exactly the course's OUTCOME rows. `modules` (planned module count) only produces a warning while the course is being written. |

### MODULE

| Column | Use |
|---|---|
| `order` | Module number. `0` is allowed only with `"is_introduction": true` |
| `title`, `body` | Title and one-paragraph summary |
| `outcome_codes` | Optional check: if filled, it must list exactly the module's OUTCOME rows |
| `meta_json` | `is_introduction` (introduction modules have no exam and no 6-lesson rule); `free_preview`; `has_exam` (default true, false for introductions); `intro_video` `{"provider": "youtube", "video_id": "", "duration_sec": 150}`; `mini_project` (title, optional; the brief itself is the MP PROBLEM row) |

A normal module should have **6 lessons**. Any other count is reported as a warning, not an error.

### LESSON

| Column | Use |
|---|---|
| `order`, `title` | Position in the module and title |
| `body` | Summary of what the lesson covers |
| `outcome_codes` | Optional check against the lesson's OUTCOME rows |
| `meta_json` | `est_minutes` (default 45); `free_preview` (default false); `min_coding_to_pass` (default: the number of coding tasks or 2, whichever is smaller) |

### OUTCOME

| Column | Use |
|---|---|
| `parent_code` | Sets the level: course, module or lesson |
| `order`, `title` | Order and short name ("Dry-run a program") |
| `body` | The full statement, written as "The student can …". **At most 300 characters.** |
| `outcome_codes` | The higher-level outcome(s) this supports: lesson → module outcome, module → course outcome. Optional, but needed for mastery reports |
| `meta_json` | Ignored on import |

### STEP

Common columns: `order` (position in the lesson), `title`, `step_type`, `outcome_codes` (the lesson outcomes this step teaches or checks), `body` and `meta_json`. See §5 for what each step type uses.

### MCQ (belongs to a PREDICT or QUIZ step)

| Column | Use |
|---|---|
| `order` | Position inside the step |
| `title` | Short name (staff only) |
| `outcome_codes` | **Exactly one** lesson outcome (required to publish) |
| `difficulty` | `EASY` / `MEDIUM` / `HARD` |
| `body` | The question. Put code in a fenced block (` ```python `) |
| `option_a`–`option_d` | 2 to 4 options; leave unused ones blank |
| `correct_option` | `B`, or `A;C` for "choose all that apply" |
| `explanation` | Why the answer is right; shown after answering |
| `language` | Language of any code in the question |
| `meta_json` | `mcq_kind` (`concept` / `output` / `debug`, used later by module exams); `tags` (list); optional `option_explanations` `{"A": "…", "C": "…"}` for per-option feedback |

### PROBLEM (belongs to a FIX_BUG step, a CODING step, or a module as a mini-project)

| Column | Use |
|---|---|
| `order` | Task order inside the step |
| `title` | Task title |
| `outcome_codes` | One or more lesson outcomes (required to publish) |
| `difficulty` | `EASY` / `MEDIUM` / `HARD` |
| `body` | Task statement (Markdown) |
| `explanation` | Shown after a correct solution |
| `starter_code` | Fix-the-bug: the buggy program. Coding: the starting template (e.g. `# Write your code below`) |
| `solution_code` | Reference solution. Never shown to students. Kept in the sheet for reviewers (automatic checking against the test cases is planned) |
| `language` | e.g. `python` |
| `meta_json` | `problem_kind` (`fix_bug` / `coding` / `mini_project`, required); `time_limit_ms` (default 2000, whole seconds only: 1000, 2000, 3000…); `memory_limit_mb` (default 256); optional `input_format`, `output_format`, `constraints`; `no_input` (true when the program reads nothing); `error_hint_rule` (kept for the error explainer, Phase 4) |

A `fix_bug` problem needs `starter_code` (the bug). A `coding` problem needs at least one TESTCASE.

### TESTCASE (belongs to a problem)

| Column | Use |
|---|---|
| `order` | Run order |
| `title` | What it checks (staff only) |
| `input` | stdin; blank if the program reads nothing |
| `expected_output` | Exact expected output. Trailing spaces and trailing blank lines are ignored |
| `is_hidden` | `FALSE` = sample shown to the student; `TRUE` = hidden, used only for grading |
| `points` | Weight, a whole number ≥ 1 (default 1). Partial marks are weighted by this |
| `meta_json` | `compare`: only `exact_trim_trailing` for now (the default) |

**Problems that read input** should have at least one sample (`FALSE`) and at least one hidden (`TRUE`) test case with different inputs, so a student can't pass by printing the expected text. **Problems that read nothing** (`"no_input": true`, or every test case's `input` is blank, as in all of Module 1) need just one visible test case: with no input, a hidden test would run the same program and check the same output, so it adds nothing.

### HINT (belongs to a problem)

| Column | Use |
|---|---|
| `order` | Level, `1`, `2` or `3` (1 = nudge, 2 = approach, 3 = near solution) |
| `title` | Label (staff only) |
| `body` | The hint text |
| `meta_json` | `unlock_after_attempts` (default = the level) |

---

## 5. Step types

| `step_type` | `body` | Other columns / `meta_json` | Children |
|---|---|---|---|
| `TEXT` | Markdown notes. A "## Common mistakes" section is styled as a callout | optional `callouts` `[{"kind": "tip" \| "mistake" \| "note", "markdown": "…"}]` | — |
| `VIDEO` | The production script (staff only, never shown to students) | `provider` (`youtube` / `bunny`), `video_id` (needed to publish), `duration_sec` (needed to publish), `chapters` `[[0, "Hook"], [45, "…"]]`, `complete_at_percent` (default 80), optional `transcript` | — |
| `PREDICT` | Instruction shown above the questions | — | 1+ MCQ |
| `QUIZ` | Instruction shown above the questions | `pass_percent` 0–100 (default 60; **0 = practice only, does not count toward completion**) | 1+ MCQ |
| `PLAYGROUND` | Instructions | `starter_code`, `input` (sample stdin), `language`; `run_only` is implied | — |
| `PARSONS` | Instructions | `solution_code` = the correct program, one line per block, indented with 4 spaces; `explanation`; `distractors` (list of wrong lines); `use_indentation` (default true; false = order only). A `lines` list, if present, must match `solution_code` | — |
| `FIX_BUG` | Framing shown above the task | — | exactly 1 PROBLEM (`fix_bug`) |
| `CODING` | Framing shown above the tasks | `min_to_pass` (sets the lesson's `min_coding_to_pass`) | 1+ PROBLEM (`coding`) |

**How CODING steps are imported.** Each coding problem becomes its own coding step in the app, with its own hints and outcome tags. Your one "Coding tasks" step with 3 problems therefore becomes three steps in a row, and every later step in the lesson moves down. A student completes the lesson by passing `min_coding_to_pass` of them (2 by default). You keep writing it as one step in the sheet.

`points` on STEP rows is ignored: lessons are scored by percentage.

---

## 6. Checks the importer runs

**Errors** (nothing is saved until they are fixed):

- An unknown `record_type` or `step_type`, a duplicate `code`, or a code that doesn't match its pattern.
- A `parent_code` that doesn't exist or is the wrong kind of parent (e.g. an MCQ under a TEXT step).
- Duplicate `order` values inside the same parent.
- Invalid `meta_json`, or a number or `TRUE` / `FALSE` cell that can't be read.
- An MCQ with fewer than 2 options, no correct option, or a correct option that points to a blank option.
- An outcome code in `outcome_codes` that isn't defined in this tab.
- An outcome `body` over 300 characters.
- A FIX_BUG step without exactly one problem, or a `fix_bug` problem without `starter_code`.

**Warnings** (import continues):

- A module with a lesson count other than 6.
- Missing `video_id`.
- A problem whose test cases give input but none of them is hidden.
- Items in the app that are no longer in the sheet.
- A step or question without an outcome tag (it blocks publishing, not importing).

Every import starts as a **dry run** that shows these checks and the counts of new and updated items. Nothing is written until you confirm.

---

## 7. Status column

`status` is for your writing workflow (`DRAFT` → `REVIEW` → `READY`). The importer loads every row whatever its status and shows the counts in its report. Students see a course only after staff publish it in the builder. That publish step has its own checks, so draft content never reaches students by accident.

---

## 8. How a tab gets into the app

1. In Google Sheets choose **File → Download → Microsoft Excel (.xlsx)**.
2. On the staff course import page, upload the file and pick the tab, e.g. `Core Python`. (The command line works too: `python manage.py import_course_sheet file.xlsx --tab "Core Python" --dry-run`.)
3. Read the dry-run report, fix anything in the sheet, and upload again.
4. Click **Apply**. Re-importing later only updates what changed.

Reading straight from Google Sheets, with no download step, can be added later behind a setting. It needs a Google service account key on the server.
