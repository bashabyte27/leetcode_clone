# Courses changelog

## Phase 2: Catalog, course landing and enrollment (2026-11-07)

**Built**

- **Pages** (`courses/views.py`, `templates/courses/`), built on the home page's design tokens with a flat, editorial `static/css/courses.css` in both themes:
  - `/courses/`: catalog with categories, course rows and a career-path picker (shown once career paths exist).
  - `/courses/<slug>/`: course landing with facts, course outcomes, a syllabus (module → lessons, with minutes and preview links), the capstone, prerequisites, a sticky enroll card and a phone bottom bar.
  - `/courses/<slug>/preview/<module>/<lesson>/`: read-only public preview of free lessons. It never shows correct answers, explanations or hints, shuffles Parsons lines the same way on every load, and keeps a contents rail that follows your reading.
  - `POST /courses/<slug>/enroll/` and `/courses/my-learning/`.
- **`Enrollment` model**: one row per user and course; re-enrolling reactivates a dropped one; `last_lesson` drives "Continue".
- **Access rules in one place** (`courses/access.py`): drafts are staff-only (with a draft banner); premium is `is_premium` or a live subscription; premium courses keep the introduction, Module 1 and free-preview lessons open; `COURSES_PREMIUM_GATING` turns gating off.
- **Read models and caching** (`courses/catalog.py`): the catalog takes 3 queries and the course page 7, whatever the course size. Public reads are cached for `COURSES_CACHE_SECONDS` (default 300); saves and deletes clear the cache (`courses/signals.py`), and so does each sheet import.
- **SEO**: page titles and descriptions, canonical URLs, Open Graph tags and schema.org `Course` JSON-LD.
- **Shared site chrome**: the home page's nav and footer moved to `templates/partials/`, and every nav now links to Courses and My learning.
- **Accessibility**: semantic landmarks and breadcrumbs, a native `<details>` syllabus, visible focus, reduced-motion support, and dark text on the light-theme orange button (white was about 2.9:1).
- **Shared step rendering** (`courses/rendering.prepare_steps`) for the staff preview and the public preview. MCQ options now keep their line breaks in both.

**Tests**: 27 new (`courses/tests/test_public_views.py`): access for each role, drafts, enroll and re-enroll, premium rules and subscriptions, answer leakage, Parsons shuffle stability, cache invalidation, query counts, nav links. Manual QA used Playwright screenshots of all pages in both themes at 1366 px and 390 px, plus a real enroll → continue → my-learning run; there were no console errors and no horizontal scroll.

**Known limitations**

- "Continue" opens the syllabus at the student's lesson; the lesson player arrives in Phase 3.
- Career-path chips appear only after paths are created (admin); none exist yet.
- No syntax highlighting in code blocks yet (Phase 3, with Pygments).
- Core Python is still a draft, because 10 video ids are missing; visitors see the catalog's empty state until it is published.

## Phase 1: Content model and staff course builder (2026-11-07)

**Built**

- **Content models** (`courses/models.py`, migration `0003`): Category, Course (slug + version), CareerPath / CareerPathCourse, Module, Lesson, LearningOutcome, LessonStep, StepQuestion and StepHint. The legacy `courses.Courses` model, its seed commands and its list page are removed (D2).
- **Step registry** (`courses/steps.py`): 8 step types (VIDEO, TEXT, PREDICT, PLAYGROUND, PARSONS, QUIZ, FIX_BUG, CODING). Each type has a structure validator that runs on every save, so a malformed step can't be stored, and a publish-completeness check.
- **References**: QUIZ / PREDICT steps link to `assessment.McqQuestion` through the ordered `StepQuestion`, one outcome tag per question. CODING / FIX_BUG steps link to `assessment.CodingQuestion` (D1). The `assessment` app gains `McqOption.explanation` (additive, D5).
- **Staff builder** at `/staff/courses/`: course → module → lesson → step editors, drag-to-reorder (SortableJS from cdnjs), MCQ and coding-question search-and-attach, outcome tagging, 3-level hints, a read-only student-view lesson preview and a publish page with a blocking/warning report.
- **Content-sheet import** (`courses/sheet_importer.py`) at `/staff/courses/import/` and `python manage.py import_course_sheet <file> --tab "<tab>" [--apply]`. It reads one tab of the Google Sheets course workbook in the format of `docs/courses/SHEET_FORMAT.md` and creates or updates the course, modules, lessons, outcomes and steps, plus the MCQs, coding questions, test cases and hints in the `assessment` question bank. Items are matched by `code`. The flow is upload → pick tab → dry run → Apply, all-or-nothing. A CODING step with N problems becomes N coding steps. Rows removed from the sheet are reported, never deleted.
- **The Google Sheet is the source of truth** for course content. The early `seed_core_python` skeleton and the per-module spreadsheet importer were removed. Core Python Modules 0–1 (10 lessons, 83 steps, 57 MCQs, 24 coding problems) were imported locally from the sheet.
- **Model additions for the sheet:** `code` on Course, Module, Lesson and LessonStep; course-level outcomes (`LearningOutcome.course`), outcome `title`, `position` and `supports` links; an introduction module at position 0 (`Module.is_introduction`, exempt from the 6-lesson rule); `Lesson.min_coding_passes`; VIDEO `script` and `complete_at_percent`; PARSONS `use_indentation` and `explanation`; QUIZ pass mark 0 (practice only).
- **Publish rules**: every QUIZ / PREDICT question and every CODING / FIX_BUG task needs an outcome tag. Fix-the-bug steps need a coding question in fix mode. A lesson count other than 6 is only a warning.
- **Seed**: `python manage.py seed_core_python` creates Core Python v2 (12 modules, 72 lessons, 72 outcomes). It is idempotent, runs from `build.sh` and never touches authored steps.
- **Safe Markdown** (`courses/rendering.py`, Markdown + bleach allow-list), used by the preview. Added `Markdown` and `bleach` to `requirements.txt`.
- **Admin**: every content model is registered, with inlines.

**Tests**: 46 in `courses/tests/` (models, builder views, permissions, query counts, publish, preview, sheet importer, import page, command). Coverage of the courses code is 91%. The full suite passes (202 tests).

**Known limitations / carried forward**

- `courses/urls.py` (student-facing) is still empty and unmounted. The catalog arrives in Phase 2.
- Changing a step's type through an import is refused, so staff delete the step in the builder first.
- The import keeps the uploaded file in the session (max 5 MB) between steps, because Render's disk is ephemeral.
- Reference solutions (`solution_code`) are not yet run against the test cases automatically.
- Course content is visible only in the staff builder and its lesson preview until the student pages arrive (Phases 2–3).
- Pygments (syntax highlighting) is deferred to Phase 3 with the TEXT step player.
