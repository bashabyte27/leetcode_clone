# Hosted assessments

## Exam runner

- `models.py` and migration `0006`: per-attempt question/section state, code drafts, session ownership, and the published paste policy. Migration `0007` adds the faculty restart audit event.
- `views.py` and `urls.py`: server-authoritative state, answer/draft, code run/submit, navigation, and final-submit APIs. Responses are scoped to the signed-in participant and active session.
- `templates/assessment/exam_shell.html`: persistent shell with section tabs, palette, timer, and final-submit dialog.
- `templates/assessment/partials/`: question HTML partials. The coding partial renders only Description and this attempt's Submissions; hidden tests and MCQ correctness are not serialized.
- `static/js/exam_shell.js`: navigation, offline response queue, server-clock sync, and finalization.
- `static/js/mcq_question.js` and `static/js/coding_question.js`: question modules with `init()` and `destroy()` lifecycle methods.
- `static/js/proctor.js`: shared full-screen, interaction, and violation handling.
- `test_assessment_view.py`: hosted page, attempt, proctor, restore, ownership, deadline, and idempotent submission coverage.

The hosted URL is `/assessments/<assessment-slug>/view/`. Any logged-in account can open a published assessment link; first access creates a participant record automatically. Assessment owners and staff/faculty can manage those records in the Signups tab: search by name or email, review attempt history and limits, grant up to 10 additional attempts per action, restart an active assessment, and block, remove, or restore access. A restart cancels an active attempt and preserves its answers and audit history.

The hosted URL is `/assessments/<assessment-slug>/view/`. First access by a signed-in user creates their participant record; blocked or removed users cannot re-enroll. Assessment content is read from the immutable published version.

## Adding a question type later

1. Add the immutable question data to the published snapshot and include its type and state in `get_exam_state`.
2. Render it in `get_exam_question` using a new template partial. Never send answer keys or hidden test data.
3. Implement a `window.Assessment<Type>` module in `static/js/` with `init({container, question, request, onAnswerChange})`, `save()`, `clear()`, and `destroy()`.
4. Route its saves through a participant-, attempt-, session-, and deadline-checked API. Include the type in final score calculation.
5. Dispatch the module from `static/js/exam_shell.js`; keep it inside `#section-container` so question changes never reload the shell.
6. Add tests for persistence after switching/refresh, access isolation, late writes, and data that must not reach the browser.

## Proctoring configuration

These optional Django settings control server-side policy:

```python
import os

ASSESSMENT_PROCTOR_WARNING_LIMIT = 3
ASSESSMENT_PROCTOR_AUTO_SUBMIT = True
# Set through a secret environment variable in deployment, never in source control.
ASSESSMENT_INVIGILATOR_PIN = os.environ.get("ASSESSMENT_INVIGILATOR_PIN", "")
```

With the default policy, the attempt is automatically submitted when the violation count exceeds the warning limit. The optional PIN is checked server-side using a constant-time comparison.

## Browser limitations

- Full-screen mode is user-gesture initiated and can always be exited using browser or operating-system controls; the page can only pause behind an overlay and record the event.
- Browser JavaScript cannot reliably prevent screenshots, external camera capture, operating-system shortcuts, extensions, or developer tools. Those checks are best-effort deterrents and may generate false positives.
- Focus, blur, visibility, and viewport-size signals vary by browser and operating system.
- Browsers may suppress `beforeunload` requests. Offline violation events are retried and queued in page memory, but cannot be guaranteed if the tab or browser is closed before reconnection.
- A secure exam environment or human invigilation is required for stronger enforcement.

## Manual test checklist

- [ ] Start only when full-screen support, minimum screen size, connectivity, and instruction agreement pass.
- [ ] Start an exam and confirm the page does not navigate or reload.
- [ ] Exit full-screen mode and confirm the blocking overlay appears; return to full screen.
- [ ] Try copy, cut, paste, drag/drop, right-click, and blocked keyboard shortcuts inside the exam area.
- [ ] Switch tabs and confirm a violation is recorded.
- [ ] Refresh during an attempt and confirm the attempt resumes with the server deadline and a full-screen prompt.
- [ ] Disconnect and reconnect the network; confirm the indicator and status recovery work.
- [ ] Switch sections/questions and confirm MCQ answers, code drafts by language, and review marks persist.
- [ ] Confirm sample Run responses contain sample cases only, while Submit scores all cases without returning hidden inputs or expected output.
- [ ] Let a section timer expire and confirm its questions lock while other sections remain available.
- [ ] Confirm the finish summary counts answered, unanswered, and review-marked questions; submit twice and verify a single final result.
- [ ] Confirm another user's attempt/session and late writes are rejected, and editorial/discussion requests return 403 during an active attempt.
- [ ] Open a practice problem and confirm its editor, editorial, discussion, and submissions tabs remain available.
- [ ] Submit and exit; confirm a subsequent page load reports the submitted attempt and hides Start.
- [ ] Exceed the configured warning count and confirm server-side automatic submission.
- [ ] Test an upcoming, expired, unpublished, and attempt-limit-reached assessment.
