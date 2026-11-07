"""Safe Markdown → HTML for authored course text, and step preparation for read-only lesson views."""

import hashlib
import random

import bleach
import markdown

ALLOWED_TAGS = [
    "p", "br", "hr", "h2", "h3", "h4", "h5", "strong", "em", "code", "pre", "blockquote",
    "ul", "ol", "li", "a", "table", "thead", "tbody", "tr", "th", "td", "span", "del",
]
ALLOWED_ATTRS = {"a": ["href", "title", "rel", "target"], "code": ["class"], "span": ["class"], "th": ["align"], "td": ["align"]}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_markdown(text):
    """Render staff-authored Markdown and strip anything outside the allow-list (scripts, styles, iframes)."""
    html = markdown.markdown(text or "", extensions=["fenced_code", "tables", "sane_lists"], output_format="html")
    clean = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, protocols=ALLOWED_PROTOCOLS, strip=True)
    return bleach.linkify(clean, callbacks=[bleach.callbacks.nofollow, bleach.callbacks.target_blank])


def _clock(seconds):
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def prepare_steps(steps, reveal_answers):
    """
    Attach render-ready attributes to each step for the read-only lesson views.

    `reveal_answers=True` is the staff preview (correct options, explanations, hints and
    Parsons lines in order). `False` is the public preview: nothing that gives an answer away.
    Steps need `questions__mcq__options` and `coding_question__supported_languages__language`
    prefetched.
    """
    for step in steps:
        content = step.content or {}
        if step.step_type == "TEXT":
            step.html = render_markdown(content.get("markdown", ""))
            step.callout_html = [(c["kind"], render_markdown(c["markdown"])) for c in content.get("callouts", [])]
        elif step.step_type == "VIDEO":
            step.chapter_rows = [(_clock(ch["t"]), ch["title"]) for ch in content.get("chapters", [])]
            step.duration_label = _clock(content.get("duration_s")) if content.get("duration_s") else ""
        elif step.step_type == "PARSONS":
            lines = [dict(line, distractor=False) for line in content.get("lines", [])]
            lines += [{"text": d, "indent": 0, "distractor": True} for d in content.get("distractors", [])]
            if not reveal_answers:  # same shuffle on every load, so the page is stable and cacheable
                seed = int(hashlib.sha256(f"parsons:{step.pk}".encode()).hexdigest()[:8], 16)
                random.Random(seed).shuffle(lines)
            step.parsons_lines = lines
        elif step.spec.uses_mcqs:
            step.mcq_items = [(sq, render_markdown(sq.mcq.statement)) for sq in step.questions.all()]
        if step.spec.uses_coding_question and step.coding_question_id:
            question = step.coding_question
            step.statement_html = render_markdown(question.statement)
            fix = question.coding_mode == "fix"
            step.code_variants = [(v.language.name, v.buggy_code if fix else v.starter_code)
                                  for v in question.supported_languages.all()]
        step.reveal = reveal_answers
    return steps


STEP_PREFETCH = ("questions__mcq__options", "coding_question__supported_languages__language")
