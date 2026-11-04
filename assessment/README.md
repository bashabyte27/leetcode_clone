# Hosted assessment landing page

## Files and integration points

- `models.py`: uses the existing assessment, version, section snapshot, participant, and attempt records; adds passing marks and `ViolationLog`.
- `views.py` and `urls.py`: hosted landing page plus start, status, and proctoring APIs.
- `templates/assessment/assessment_view.html`: standalone Bootstrap landing and exam shell. It deliberately contains only an empty `#section-container` for future section UI.
- `static/css/assessment_view.css`: responsive landing, exam-shell, and proctoring styles.
- `static/js/assessment_view.js`: system checks, start/resume flow, API calls, and server-deadline display.
- `static/js/proctor.js`: reusable full-screen, interaction, navigation, and violation handling module.
- `test_assessment_view.py`: landing and API coverage.

The hosted URL is `/assessments/<assessment-slug>/view/`. A logged-in user must have a `Participant` record for the assessment. Starting requires a published assessment and current published version.

The existing assessment-management app does not yet provide a publish workflow. Until one publishes the assessment and creates its immutable version snapshots, the hosted page intentionally stays in the not-live state.

## Adding MCQ or coding sections later

Render the new section UI inside the existing `<div id="section-container"></div>` after the start API returns successfully. Keep section navigation and answer requests asynchronous (for example, `fetch()` into this container) so the assessment shell does not reload or leave full-screen mode. Bind the section UI to `Proctor.attachTo(containerElement)` and use the shared `window.Proctor` API for automatic-submit and warning hooks. The start response includes the attempt ID, expiry timestamp, and server time; use the existing attempt-status API to restore state after reconnects.

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
- [ ] Submit and exit; confirm a subsequent page load reports the submitted attempt and hides Start.
- [ ] Exceed the configured warning count and confirm server-side automatic submission.
- [ ] Test an upcoming, expired, unpublished, and attempt-limit-reached assessment.
