"""
assessment/reports.py
---------------------
Analytics for one assessment: KPIs, funnel, score distribution, section and
item analysis (classical test theory), coding verdicts, proctoring, and the
candidate sheet - plus Excel and PDF exports of the same numbers.

Every figure is derived from finalized results and recorded activity; nothing
is estimated. Item statistics follow the usual conventions:

* difficulty index  p = share of ranked candidates who answered correctly
* discrimination    D = p(top 27%) - p(bottom 27%) by total score
"""

from collections import Counter, OrderedDict, defaultdict
from datetime import timedelta
from io import BytesIO
from statistics import median, pstdev

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    AssessmentQuestionSnapshot,
    AssessmentSectionResult,
    AssessmentSubmission,
    Attempt,
    AttemptAnswer,
    ViolationLog,
)

FINAL_ATTEMPT = (Attempt.Status.SUBMITTED, Attempt.Status.TIMED_OUT)
VERDICT_TONE = {
    "accepted": "good",
    "wrong_answer": "critical",
    "compilation_error": "serious",
    "runtime_error": "serious",
    "time_limit_exceeded": "warning",
    "memory_limit_exceeded": "warning",
    "internal_error": "neutral",
    "pending": "neutral",
    "processing": "neutral",
}
VIOLATION_LABELS = {
    "fullscreen_exit": "Left fullscreen",
    "tab_hidden": "Switched tab",
    "window_blur": "Window lost focus",
    "devtools_open": "Opened devtools",
    "copy_blocked": "Copy attempt",
    "cut_blocked": "Cut attempt",
    "paste_blocked": "Paste attempt",
    "drag_blocked": "Drag attempt",
    "context_menu_blocked": "Right-click",
    "shortcut_blocked": "Blocked shortcut",
    "extension_warning": "Extension warning",
    "navigation_blocked": "Navigation attempt",
}


def _f(value):
    return float(value or 0)


def _pct(part, whole):
    return round(part * 100 / whole, 1) if whole else 0.0


def _fmt_seconds(seconds):
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _quantile(sorted_values, q):
    if not sorted_values:
        return 0.0
    pos = (len(sorted_values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def _question_outcomes(attempt_ids):
    """
    {(attempt_id, snapshot_id): {"attempted", "correct", "partial", "score"}}
    from MCQ answers and coding submissions. Coding uses the best submission.
    """
    out = defaultdict(lambda: {"attempted": False, "correct": False, "partial": False, "score": 0.0})
    answers = (
        AttemptAnswer.objects.filter(attempt_id__in=attempt_ids)
        .filter(Q(text_answer__gt="") | Q(code_answer__gt="") | Q(selected_options__isnull=False))
        .values("attempt_id", "assessment_question_snapshot_id", "is_correct", "score")
        .distinct()
    )
    for a in answers:
        row = out[(a["attempt_id"], a["assessment_question_snapshot_id"])]
        row["attempted"] = True
        row["correct"] = row["correct"] or a["is_correct"] is True
        row["score"] = max(row["score"], _f(a["score"]))
    subs = AssessmentSubmission.objects.filter(attempt_id__in=attempt_ids).values(
        "attempt_id", "assessment_question_snapshot_id", "status", "score"
    )
    for s in subs:
        row = out[(s["attempt_id"], s["assessment_question_snapshot_id"])]
        row["attempted"] = True
        row["correct"] = row["correct"] or s["status"] == AssessmentSubmission.Status.ACCEPTED
        row["score"] = max(row["score"], _f(s["score"]))
    for row in out.values():
        row["partial"] = not row["correct"] and row["score"] > 0
    return out


def build_report(assessment, leaderboard):
    """All numbers for the Reports tab and the exports."""
    now = timezone.now()
    participants = list(assessment.participants.select_related("user"))
    attempts = list(
        Attempt.objects.filter(participant__assessment=assessment).select_related("participant__user")
    )
    attempts_by_participant = defaultdict(list)
    for attempt in attempts:
        attempts_by_participant[attempt.participant_id].append(attempt)

    signups = len(participants)
    started = sum(1 for p in participants if attempts_by_participant.get(p.pk))
    submitted = sum(
        1 for p in participants
        if any(a.status in FINAL_ATTEMPT for a in attempts_by_participant.get(p.pk, []))
    )
    ranked = len(leaderboard)
    pass_mark = _f(assessment.passing_marks)

    # ── Scores ──
    rows = []
    for row in leaderboard:
        result = row["result"]
        max_score = _f(result.max_score)
        score = _f(result.total_score)
        rows.append({
            "row": row,
            "score": score,
            "max": max_score,
            "pct": round(score * 100 / max_score, 1) if max_score else 0.0,
            "passed": score >= pass_mark,
            "seconds": row["duration_seconds"],
        })
    pcts = sorted(r["pct"] for r in rows)
    passed = sum(1 for r in rows if r["passed"])
    avg_seconds = sum(r["seconds"] for r in rows) / ranked if ranked else 0

    distribution = [0] * 10
    for value in pcts:
        distribution[min(9, int(value // 10))] += 1

    # ── Violations ──
    violations = list(
        ViolationLog.objects.filter(attempt__participant__assessment=assessment)
        .values("event_type", "attempt__participant_id", "attempt__participant__user__user_name")
    )
    violations_by_type = Counter(v["event_type"] for v in violations)
    violations_by_participant = Counter(v["attempt__participant_id"] for v in violations)
    flagged = [
        {"username": name, "count": count}
        for (pid, name), count in Counter(
            (v["attempt__participant_id"], v["attempt__participant__user__user_name"]) for v in violations
        ).most_common(6)
    ]

    # ── Sections (best attempt per ranked candidate) ──
    best_result_ids = [r["row"]["result"].pk for r in rows]
    sections = OrderedDict()
    for sr in (
        AssessmentSectionResult.objects.filter(result_id__in=best_result_ids)
        .select_related("section_snapshot")
        .order_by("section_snapshot__position")
    ):
        key = sr.section_snapshot.title
        bucket = sections.setdefault(key, {"title": key, "score": 0.0, "max": 0.0, "n": 0})
        bucket["score"] += _f(sr.score)
        bucket["max"] += _f(sr.max_score)
        bucket["n"] += 1
    section_rows = [
        {**s, "avg_pct": _pct(s["score"], s["max"]), "avg_score": round(s["score"] / s["n"], 2) if s["n"] else 0}
        for s in sections.values()
    ]

    # ── Item analysis ──
    best_attempt_ids = [r["row"]["attempt"].pk for r in rows]
    version_ids = {r["row"]["attempt"].assessment_version_id for r in rows if r["row"]["attempt"].assessment_version_id}
    snapshots = list(
        AssessmentQuestionSnapshot.objects.filter(section__version_id__in=version_ids)
        .select_related("section", "mcq_snapshot", "coding_snapshot")
        .order_by("section__position", "position")
    )
    outcomes = _question_outcomes(best_attempt_ids)
    by_score = sorted(rows, key=lambda r: r["score"], reverse=True)
    group = max(1, round(ranked * 0.27)) if ranked >= 2 else 0
    upper = {r["row"]["attempt"].pk for r in by_score[:group]}
    lower = {r["row"]["attempt"].pk for r in by_score[-group:]} if group else set()

    items = OrderedDict()
    for snap in snapshots:
        key = snap.source_assessment_question_id or f"t:{snap.section.title}:{snap.position}"
        q = snap.mcq_snapshot or snap.coding_snapshot
        item = items.setdefault(key, {
            "title": q.title if q else "Question",
            "kind": "MCQ" if snap.mcq_snapshot_id else "Coding",
            "section": snap.section.title,
            "difficulty_label": (q.difficulty or "").title() if q else "",
            "max_score": _f(snap.max_score),
            "snap_ids": set(),
        })
        item["snap_ids"].add(snap.pk)

    item_rows = []
    for idx, item in enumerate(items.values(), start=1):
        attempted = correct = partial = 0
        score_total = 0.0
        up_correct = low_correct = 0
        for r in rows:
            aid = r["row"]["attempt"].pk
            o = next((outcomes[(aid, sid)] for sid in item["snap_ids"] if (aid, sid) in outcomes), None)
            if not o:
                continue
            attempted += o["attempted"]
            correct += o["correct"]
            partial += o["partial"]
            score_total += o["score"]
            if o["correct"] and aid in upper:
                up_correct += 1
            if o["correct"] and aid in lower:
                low_correct += 1
        p = round(correct / ranked, 2) if ranked else 0.0
        d = round((up_correct - low_correct) / group, 2) if group else None
        flags = []
        if ranked:
            if p >= 0.9:
                flags.append(("Too easy", "warning"))
            elif p <= 0.2:
                flags.append(("Too hard", "serious"))
            if d is not None and ranked >= 4 and d < 0.2:
                flags.append(("Low discrimination", "critical"))
        item_rows.append({
            "no": idx,
            "title": item["title"],
            "kind": item["kind"],
            "section": item["section"],
            "level": item["difficulty_label"],
            "attempted": attempted,
            "attempt_rate": _pct(attempted, ranked),
            "correct": correct,
            "partial": partial,
            "p": p,
            "d": d,
            "avg_score": round(score_total / ranked, 2) if ranked else 0.0,
            "max_score": item["max_score"],
            "flags": flags,
        })

    # ── Coding verdicts, languages, timeline ──
    subs = AssessmentSubmission.objects.filter(attempt__participant__assessment=assessment)
    verdict_counts = dict(subs.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    status_labels = dict(AssessmentSubmission.Status.choices)
    total_subs = sum(verdict_counts.values())
    verdicts = sorted(
        [
            {"status": s, "label": status_labels.get(s, s.title()), "count": n,
             "pct": _pct(n, total_subs), "tone": VERDICT_TONE.get(s, "neutral")}
            for s, n in verdict_counts.items()
        ],
        key=lambda v: -v["count"],
    )
    languages = [
        {"label": name or "Unknown", "count": n}
        for name, n in subs.values_list("language__name").annotate(n=Count("id")).order_by("-n").values_list("language__name", "n")
    ]
    times = list(subs.values_list("submitted_at", flat=True)) + list(
        AttemptAnswer.objects.filter(attempt__participant__assessment=assessment)
        .filter(Q(text_answer__gt="") | Q(code_answer__gt="") | Q(selected_options__isnull=False))
        .values_list("answered_at", flat=True).distinct()
    )
    times = sorted(timezone.localtime(t) for t in times if t)
    timeline = []
    if times:
        span = times[-1] - times[0]
        hourly = span <= timedelta(days=2)
        buckets = Counter(
            t.replace(minute=0, second=0, microsecond=0) if hourly else t.replace(hour=0, minute=0, second=0, microsecond=0)
            for t in times
        )
        fmt = "%b %d %H:00" if hourly else "%b %d"
        timeline = [{"label": k.strftime(fmt), "count": buckets[k]} for k in sorted(buckets)]

    # ── Candidate sheet (ranked first, then everyone else) ──
    sheet = []
    ranked_pids = set()
    for r in rows:
        row, result = r["row"], r["row"]["result"]
        pid = row["attempt"].participant_id
        ranked_pids.add(pid)
        sheet.append({
            "rank": row["rank"],
            "username": row["user"].user_name,
            "email": row["user"].email,
            "status": "Completed",
            "score": r["score"],
            "max": r["max"],
            "pct": r["pct"],
            "correct": result.correct_count,
            "incorrect": result.incorrect_count,
            "partial": result.partially_correct_count,
            "unanswered": result.unanswered_count,
            "time": row["time_taken"],
            "seconds": r["seconds"],
            "attempts": len(attempts_by_participant.get(pid, [])),
            "violations": violations_by_participant.get(pid, 0),
            "result": "Pass" if r["passed"] else "Fail",
            "submitted_at": row["attempt"].submitted_at,
        })
    for p in participants:
        if p.pk in ranked_pids:
            continue
        p_attempts = attempts_by_participant.get(p.pk, [])
        sheet.append({
            "rank": None, "username": p.user.user_name, "email": p.user.email,
            "status": "In progress" if any(a.status == Attempt.Status.IN_PROGRESS for a in p_attempts)
            else ("Awaiting result" if p_attempts else "Not started"),
            "score": None, "max": None, "pct": None, "correct": None, "incorrect": None,
            "partial": None, "unanswered": None, "time": "", "seconds": None,
            "attempts": len(p_attempts), "violations": violations_by_participant.get(p.pk, 0),
            "result": "", "submitted_at": None,
        })

    kpis = {
        "signups": signups,
        "started": started,
        "submitted": submitted,
        "ranked": ranked,
        "completion_rate": _pct(submitted, signups),
        "avg_pct": round(sum(pcts) / ranked, 1) if ranked else 0.0,
        "median_pct": round(median(pcts), 1) if pcts else 0.0,
        "stdev_pct": round(pstdev(pcts), 1) if len(pcts) > 1 else 0.0,
        "p25": round(_quantile(pcts, 0.25), 1),
        "p75": round(_quantile(pcts, 0.75), 1),
        "max_pct": pcts[-1] if pcts else 0.0,
        "min_pct": pcts[0] if pcts else 0.0,
        "passed": passed,
        "pass_rate": _pct(passed, ranked),
        "pass_mark": pass_mark,
        "avg_time": _fmt_seconds(avg_seconds),
        "violations": len(violations),
        "flagged_candidates": sum(1 for c in violations_by_participant.values() if c >= 3),
        "total_submissions": total_subs,
        "acceptance_rate": _pct(verdict_counts.get("accepted", 0), total_subs),
    }

    report = {
        "generated_at": now,
        "kpis": kpis,
        "funnel": [
            {"label": "Signed up", "count": signups},
            {"label": "Started", "count": started},
            {"label": "Submitted", "count": submitted},
            {"label": "Passed", "count": passed},
        ],
        "distribution": [{"label": f"{i * 10}-{i * 10 + 10}%", "count": c} for i, c in enumerate(distribution)],
        "sections": section_rows,
        "items": item_rows,
        "verdicts": verdicts,
        "languages": languages,
        "timeline": timeline,
        "violation_types": [
            {"label": VIOLATION_LABELS.get(k, k.replace("_", " ").title()), "count": n}
            for k, n in violations_by_type.most_common()
        ],
        "flagged": flagged,
        "scatter": [
            {"x": round(r["seconds"] / 60, 1), "y": r["pct"], "name": r["row"]["user"].user_name} for r in rows
        ],
        "sheet": sheet,
    }
    report["insights"] = _insights(report)
    report["chart_data"] = {
        "funnel": report["funnel"],
        "distribution": report["distribution"],
        "sections": [{"label": s["title"], "value": s["avg_pct"]} for s in section_rows],
        "items": [{"label": f"Q{i['no']}", "title": i["title"], "p": i["p"], "d": i["d"]} for i in item_rows],
        "verdicts": verdicts,
        "languages": languages,
        "timeline": timeline,
        "violations": report["violation_types"],
        "scatter": report["scatter"],
        "pass_mark_pct": None,
    }
    return report


def _insights(report):
    k = report["kpis"]
    out = []
    if not k["signups"]:
        return [{"tone": "neutral", "text": "No one has opened the assessment link yet. Share it to start collecting results."}]
    dropped = k["signups"] - k["submitted"]
    if dropped:
        out.append({"tone": "warning" if k["completion_rate"] < 70 else "neutral",
                    "text": f"{k['completion_rate']}% completion: {dropped} of {k['signups']} signups have not submitted."})
    if k["ranked"]:
        spread = "a wide" if k["stdev_pct"] >= 20 else "a moderate" if k["stdev_pct"] >= 10 else "a narrow"
        out.append({"tone": "neutral",
                    "text": f"Average score is {k['avg_pct']}% (median {k['median_pct']}%) with {spread} spread (SD {k['stdev_pct']} pts)."})
        out.append({"tone": "good" if k["pass_rate"] >= 60 else "serious",
                    "text": f"{k['passed']} of {k['ranked']} ranked candidates passed ({k['pass_rate']}%) at a pass mark of {k['pass_mark']:g}."})
    hardest = min(report["items"], key=lambda i: i["p"], default=None)
    if hardest and k["ranked"]:
        out.append({"tone": "serious" if hardest["p"] <= 0.2 else "neutral",
                    "text": f"Hardest question: Q{hardest['no']} “{hardest['title']}”, solved by {round(hardest['p'] * 100)}% of candidates."})
    weak = [i for i in report["items"] if any(f[0] == "Low discrimination" for f in i["flags"])]
    if weak:
        out.append({"tone": "critical", "text": f"{len(weak)} question(s) do not separate strong from weak candidates; consider revising them."})
    if report["verdicts"]:
        top = report["verdicts"][0]
        out.append({"tone": "neutral", "text": f"Most common coding verdict: {top['label']} ({top['pct']}% of {k['total_submissions']} submissions)."})
    if k["flagged_candidates"]:
        out.append({"tone": "critical", "text": f"{k['flagged_candidates']} candidate(s) triggered 3 or more proctoring events; review their attempts."})
    elif k["violations"] == 0 and k["started"]:
        out.append({"tone": "good", "text": "No proctoring events were recorded."})
    return out


# ─────────────────────────── Excel export ───────────────────────────

def xlsx_response(assessment, report):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    head_fill = PatternFill("solid", fgColor="1D8A4B")
    head_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="D9DDD9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def table(ws, start_row, headers, data, widths=None):
        for c, h in enumerate(headers, start=1):
            cell = ws.cell(row=start_row, column=c, value=h)
            cell.fill, cell.font, cell.border = head_fill, head_font, border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for r, values in enumerate(data, start=start_row + 1):
            for c, v in enumerate(values, start=1):
                cell = ws.cell(row=r, column=c, value=v)
                cell.border = border
        for c, w in enumerate(widths or [], start=1):
            ws.column_dimensions[get_column_letter(c)].width = w
        return start_row + len(data)

    # Summary
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = f"{assessment.name} — assessment report"
    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"] = f"Generated {timezone.localtime(report['generated_at']):%d %b %Y %H:%M}"
    ws["A2"].font = Font(italic=True, color="66776D")
    k = report["kpis"]
    kpi_rows = [
        ("Signups", k["signups"]), ("Started", k["started"]), ("Submitted", k["submitted"]),
        ("Ranked (finalized)", k["ranked"]), ("Completion rate %", k["completion_rate"]),
        ("Average score %", k["avg_pct"]), ("Median score %", k["median_pct"]),
        ("Std deviation (pts)", k["stdev_pct"]), ("Highest %", k["max_pct"]), ("Lowest %", k["min_pct"]),
        ("Pass mark", k["pass_mark"]), ("Passed", k["passed"]), ("Pass rate %", k["pass_rate"]),
        ("Average time", k["avg_time"]), ("Coding submissions", k["total_submissions"]),
        ("Coding acceptance %", k["acceptance_rate"]), ("Proctoring events", k["violations"]),
    ]
    table(ws, 4, ["Metric", "Value"], kpi_rows, [28, 18])
    dist_start = 4
    ws.cell(row=dist_start, column=4, value="Score band").fill = head_fill
    ws.cell(row=dist_start, column=5, value="Candidates").fill = head_fill
    for col in (4, 5):
        ws.cell(row=dist_start, column=col).font = head_font
    for i, d in enumerate(report["distribution"], start=dist_start + 1):
        ws.cell(row=i, column=4, value=d["label"]).border = border
        ws.cell(row=i, column=5, value=d["count"]).border = border
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 12
    chart = BarChart()
    chart.title = "Score distribution"
    chart.y_axis.title = "Candidates"
    chart.legend = None
    chart.add_data(Reference(ws, min_col=5, min_row=dist_start, max_row=dist_start + 10), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=4, min_row=dist_start + 1, max_row=dist_start + 10))
    chart.height, chart.width = 7.5, 15
    ws.add_chart(chart, "G4")
    if report["insights"]:
        row = len(kpi_rows) + 7
        ws.cell(row=row, column=1, value="Key insights").font = Font(bold=True, size=12)
        for i, ins in enumerate(report["insights"], start=row + 1):
            ws.cell(row=i, column=1, value=f"• {ins['text']}")

    # Candidates
    ws = wb.create_sheet("Candidates")
    headers = ["Rank", "Name", "Email", "Status", "Score", "Max", "Score %", "Correct", "Incorrect",
               "Partial", "Unanswered", "Time taken", "Attempts", "Proctoring events", "Result", "Submitted at"]
    data = [[
        s["rank"], s["username"], s["email"], s["status"], s["score"], s["max"], s["pct"], s["correct"],
        s["incorrect"], s["partial"], s["unanswered"], s["time"], s["attempts"], s["violations"], s["result"],
        timezone.localtime(s["submitted_at"]).strftime("%Y-%m-%d %H:%M") if s["submitted_at"] else "",
    ] for s in report["sheet"]]
    last = table(ws, 1, headers, data, [7, 18, 28, 15, 9, 8, 9, 9, 10, 9, 11, 12, 10, 17, 9, 18])
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(last, 1)}"
    if data:
        ws.conditional_formatting.add(f"O2:O{last}", CellIsRule(operator="equal", formula=['"Pass"'], fill=PatternFill("solid", fgColor="D8F2E1")))
        ws.conditional_formatting.add(f"O2:O{last}", CellIsRule(operator="equal", formula=['"Fail"'], fill=PatternFill("solid", fgColor="F8DADA")))

    # Questions
    ws = wb.create_sheet("Item analysis")
    table(ws, 1, ["Q", "Question", "Type", "Section", "Level", "Attempted", "Attempt rate %", "Correct",
                  "Partial", "Difficulty p", "Discrimination D", "Avg score", "Max score", "Flags"],
          [[f"Q{i['no']}", i["title"], i["kind"], i["section"], i["level"], i["attempted"], i["attempt_rate"],
            i["correct"], i["partial"], i["p"], i["d"] if i["d"] is not None else "", i["avg_score"], i["max_score"],
            ", ".join(f[0] for f in i["flags"])] for i in report["items"]],
          [6, 34, 9, 18, 9, 10, 13, 9, 9, 12, 15, 10, 10, 26])
    ws.freeze_panes = "C2"

    # Sections
    ws = wb.create_sheet("Sections")
    table(ws, 1, ["Section", "Average score", "Average %", "Candidates"],
          [[s["title"], s["avg_score"], s["avg_pct"], s["n"]] for s in report["sections"]], [30, 15, 12, 12])

    # Activity
    ws = wb.create_sheet("Submissions & integrity")
    end = table(ws, 1, ["Coding verdict", "Count", "Share %"],
                [[v["label"], v["count"], v["pct"]] for v in report["verdicts"]], [26, 10, 10])
    end = table(ws, end + 2, ["Language", "Submissions"], [[l["label"], l["count"]] for l in report["languages"]])
    table(ws, end + 2, ["Proctoring event", "Count"], [[v["label"], v["count"]] for v in report["violation_types"]])

    buf = BytesIO()
    wb.save(buf)
    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{slugify(assessment.name) or "assessment"}-report.xlsx"'
    return response


# ─────────────────────────── PDF export ───────────────────────────

def pdf_response(assessment, report):
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    brand = colors.HexColor("#1D8A4B")
    ink = colors.HexColor("#16201A")
    muted = colors.HexColor("#66776D")
    line = colors.HexColor("#D9DDD9")
    series = colors.HexColor("#2A78D6")

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=ink, alignment=0, fontSize=20, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=ink, fontSize=13, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], textColor=ink, fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, textColor=muted, fontSize=8.5)

    def grid(data, widths=None, align_right_from=None, align_right_to=-1):
        t = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), brand),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, line),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F7F4")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if align_right_from is not None:
            style.append(("ALIGN", (align_right_from, 1), (align_right_to, -1), "RIGHT"))
        t.setStyle(TableStyle(style))
        return t

    def bar_chart(labels, values, title, width=120 * mm, height=55 * mm):
        d = Drawing(width, height + 14)
        d.add(String(0, height + 4, title, fontName="Helvetica-Bold", fontSize=9, fillColor=ink))
        c = VerticalBarChart()
        c.x, c.y, c.width, c.height = 28, 18, width - 40, height - 24
        c.data = [values or [0]]
        c.categoryAxis.categoryNames = labels or [""]
        c.categoryAxis.labels.fontSize = 6.5
        c.categoryAxis.labels.angle = 30 if len(labels) > 6 else 0
        c.categoryAxis.labels.dy = -6 if len(labels) > 6 else 0
        c.valueAxis.valueMin = 0
        peak = max(values or [0])
        c.valueAxis.valueMax = max(1, peak)
        c.valueAxis.valueStep = max(1, -(-peak // 5))  # whole people only
        c.valueAxis.labelTextFormat = "%d"
        c.valueAxis.labels.fontSize = 7
        c.valueAxis.gridStrokeColor = line
        c.valueAxis.visibleGrid = True
        c.bars[0].fillColor = series
        c.bars[0].strokeColor = None
        c.barSpacing = 2
        d.add(c)
        return d

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=f"{assessment.name} report")
    k = report["kpis"]
    story = [
        Paragraph(f"{assessment.name} — assessment report", h1),
        Paragraph(f"Generated {timezone.localtime(report['generated_at']):%d %b %Y, %H:%M} · "
                  f"{k['signups']} signups · {k['ranked']} ranked candidates", small),
        Spacer(1, 8),
    ]
    kpi_cells = [
        ("Signups", k["signups"]), ("Completion", f"{k['completion_rate']}%"), ("Average", f"{k['avg_pct']}%"),
        ("Median", f"{k['median_pct']}%"), ("Pass rate", f"{k['pass_rate']}%"), ("Highest", f"{k['max_pct']}%"),
        ("Avg time", k["avg_time"]), ("Proctoring events", k["violations"]),
    ]
    kt = Table([[Paragraph(f"<font size=7.5 color='#66776D'>{a.upper()}</font><br/><font size=14><b>{b}</b></font>", body) for a, b in kpi_cells]],
               colWidths=[33 * mm] * 8)
    kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, line), ("INNERGRID", (0, 0), (-1, -1), 0.4, line),
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F6F7F4")),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story += [kt, Spacer(1, 10)]
    if report["insights"]:
        story.append(Paragraph("Key insights", h2))
        story += [Paragraph(f"• {i['text']}", body) for i in report["insights"]]

    charts = Table([[
        bar_chart([d["label"] for d in report["distribution"]], [d["count"] for d in report["distribution"]], "Score distribution (candidates per band)"),
        bar_chart([f["label"] for f in report["funnel"]], [f["count"] for f in report["funnel"]], "Candidate funnel"),
    ]])
    story += [Spacer(1, 6), charts]

    if report["sections"]:
        story.append(Paragraph("Section performance", h2))
        story.append(grid([["Section", "Average score", "Average %", "Candidates"]] +
                          [[s["title"], s["avg_score"], f"{s['avg_pct']}%", s["n"]] for s in report["sections"]],
                          [90 * mm, 35 * mm, 30 * mm, 30 * mm], 1))
    if report["items"]:
        story.append(Paragraph("Item analysis", h2))
        story.append(Paragraph("Difficulty p = share of ranked candidates who answered correctly. "
                               "Discrimination D = p(top 27%) − p(bottom 27%); below 0.2 suggests the question needs review.", small))
        story.append(Spacer(1, 4))
        story.append(grid([["Q", "Question", "Type", "Section", "Attempted", "Correct", "p", "D", "Avg score", "Flags"]] +
                          [[f"Q{i['no']}", Paragraph(i["title"], body), i["kind"], i["section"], i["attempted"], i["correct"],
                            i["p"], i["d"] if i["d"] is not None else "—", f"{i['avg_score']}/{i['max_score']:g}",
                            ", ".join(f[0] for f in i["flags"]) or "—"] for i in report["items"]],
                          [10 * mm, 70 * mm, 16 * mm, 34 * mm, 18 * mm, 16 * mm, 12 * mm, 12 * mm, 22 * mm, 50 * mm], 4, 8))
    if report["verdicts"] or report["violation_types"]:
        heading = Paragraph("Submissions & integrity", h2)
        left = grid([["Coding verdict", "Count", "Share"]] + [[v["label"], v["count"], f"{v['pct']}%"] for v in report["verdicts"]]) if report["verdicts"] else Paragraph("No coding submissions.", small)
        right = grid([["Proctoring event", "Count"]] + [[v["label"], v["count"]] for v in report["violation_types"]]) if report["violation_types"] else Paragraph("No proctoring events recorded.", small)
        story.append(KeepTogether([heading, Table([[left, right]], colWidths=[130 * mm, 130 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]))

    story += [PageBreak(), Paragraph("Candidate sheet", h2)]
    story.append(grid(
        [["Rank", "Name", "Email", "Status", "Score", "%", "Correct", "Incorrect", "Unanswered", "Time", "Events", "Result"]] +
        [[s["rank"] or "—", s["username"], s["email"], s["status"],
          f"{s['score']:g}/{s['max']:g}" if s["score"] is not None else "—",
          f"{s['pct']}%" if s["pct"] is not None else "—",
          s["correct"] if s["correct"] is not None else "—", s["incorrect"] if s["incorrect"] is not None else "—",
          s["unanswered"] if s["unanswered"] is not None else "—", s["time"] or "—", s["violations"], s["result"] or "—"]
         for s in report["sheet"]],
        [12 * mm, 32 * mm, 52 * mm, 26 * mm, 20 * mm, 16 * mm, 16 * mm, 18 * mm, 20 * mm, 20 * mm, 15 * mm, 16 * mm], 4, 10,
    ))

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(14 * mm, 7 * mm, f"BashaByte · {assessment.name}")
        canvas.drawRightString(landscape(A4)[0] - 14 * mm, 7 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    response = HttpResponse(buf.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{slugify(assessment.name) or "assessment"}-report.pdf"'
    return response
