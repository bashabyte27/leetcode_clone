"""
Load the 100-problem beginner curriculum into the database.

    python manage.py seed_curriculum                 # create / update, starting at order_num 15
    python manage.py seed_curriculum --dry-run       # validate only, write nothing
    python manage.py seed_curriculum --export data/problems/curriculum_100.xlsx

Safe to run on every deploy:
  * problems are matched by slug, test cases by (problem, order_num), so rows are
    updated in place and submission history attached to them is kept;
  * if an order number is already taken by a different problem, nothing is written.
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from problems.curriculum import CURRICULUM, STAGES, build_cases
from problems.models import Editorial, Problem, ProblemHint, ProblemTag, Tag, TestCase

DEFAULT_START = 15  # problems 1-14 are the original hand-written set


def stage_for(position):
    for lo, hi, name in STAGES:
        if lo <= position <= hi:
            return name
    return ""


class Command(BaseCommand):
    help = "Create or update the 100-problem beginner DSA curriculum (problems, test cases, tags, hints, editorials)."

    def add_arguments(self, parser):
        parser.add_argument("--start", type=int, default=DEFAULT_START, help="order_num of the first curriculum problem")
        parser.add_argument("--dry-run", action="store_true", help="build and validate everything without writing")
        parser.add_argument("--export", metavar="PATH", help="also write the curriculum to an .xlsx file")

    def handle(self, *args, **options):
        start = options["start"]
        built = []
        for index, spec in enumerate(CURRICULUM):
            try:
                cases = build_cases(spec, index)
            except Exception as exc:  # surface which problem broke
                raise CommandError(f"{spec.slug}: {exc}") from exc
            built.append((start + index, spec, cases))
        total_cases = sum(len(c) for _, _, c in built)
        self.stdout.write(f"Built {len(built)} problems with {total_cases} test cases.")

        if options["export"]:
            self.export(options["export"], built, start)

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run: nothing written."))
            return

        self.check_conflicts(built)
        created = updated = 0
        with transaction.atomic():
            tag_cache = {}
            for order_num, spec, cases in built:
                was_created = self.save_problem(order_num, spec, cases, tag_cache)
                created += int(was_created)
                updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(
            f"Curriculum ready: {created} created, {updated} updated "
            f"(order {start}-{start + len(built) - 1})."
        ))

    # ── Safety ───────────────────────────────────────────────
    def check_conflicts(self, built):
        wanted = {order_num: spec.slug for order_num, spec, _ in built}
        clashes = [
            f"#{p.order_num} is '{p.slug}', curriculum wants '{wanted[p.order_num]}'"
            for p in Problem.objects.filter(order_num__in=wanted).only("order_num", "slug")
            if p.slug != wanted[p.order_num]
        ]
        if clashes:
            raise CommandError(
                "Order numbers already used by other problems (nothing was written):\n  "
                + "\n  ".join(clashes)
                + "\nRe-run with --start <free number>."
            )

    # ── Writing ──────────────────────────────────────────────
    def save_problem(self, order_num, spec, cases, tag_cache):
        problem, was_created = Problem.objects.update_or_create(
            slug=spec.slug,
            defaults={
                "order_num": order_num,
                "title": spec.title,
                "description": spec.description(),
                "difficulty": spec.difficulty,
                "is_active": True,
            },
        )

        # Test cases: update in place by order_num (keeps SubmissionResult rows intact).
        existing = {tc.order_num: tc for tc in problem.test_cases.all()}
        to_create, to_update = [], []
        for case in cases:
            tc = existing.pop(case["order_num"], None)
            if tc is None:
                to_create.append(TestCase(problem=problem, **case))
                continue
            changed = False
            for field in ("input_data", "expected_output", "is_sample", "explanation"):
                if getattr(tc, field) != case[field]:
                    setattr(tc, field, case[field])
                    changed = True
            if changed:
                to_update.append(tc)
        if to_create:
            TestCase.objects.bulk_create(to_create)
        if to_update:
            TestCase.objects.bulk_update(to_update, ["input_data", "expected_output", "is_sample", "explanation"])
        if existing:  # curriculum shrank for this problem
            TestCase.objects.filter(pk__in=[tc.pk for tc in existing.values()]).delete()

        # Tags
        tag_ids = []
        for name in spec.tags:
            if name not in tag_cache:
                tag_cache[name], _ = Tag.objects.get_or_create(slug=slugify(name), defaults={"name": name})
            tag_ids.append(tag_cache[name].id)
        ProblemTag.objects.filter(problem=problem).exclude(tag_id__in=tag_ids).delete()
        have = set(ProblemTag.objects.filter(problem=problem).values_list("tag_id", flat=True))
        ProblemTag.objects.bulk_create([ProblemTag(problem=problem, tag_id=t) for t in tag_ids if t not in have])

        # Hints (no other table points at hints, so replace them wholesale)
        current_hints = list(problem.hints.values_list("hint_text", flat=True))
        if current_hints != spec.hints:
            problem.hints.all().delete()
            ProblemHint.objects.bulk_create(
                [ProblemHint(problem=problem, hint_text=text, order_num=i) for i, text in enumerate(spec.hints, 1)]
            )

        # Editorial
        Editorial.objects.update_or_create(
            problem=problem,
            defaults={
                "content": spec.editorial_html(),
                "time_complexity": spec.time,
                "space_complexity": spec.space,
                "is_published": True,
            },
        )
        return was_created

    # ── Export ───────────────────────────────────────────────
    def export(self, path, built, start):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        wb = Workbook()
        problems = wb.active
        problems.title = "Problems"
        problems.append(["order_num", "title", "description", "difficulty", "stage", "tags", "hints",
                         "time_complexity", "space_complexity", "slug"])
        tests = wb.create_sheet("TestCases")
        tests.append(["problem_order_num", "order_num", "input_data", "expected_output", "is_sample", "explanation"])

        for order_num, spec, cases in built:
            problems.append([
                order_num, spec.title, spec.description(), spec.difficulty.capitalize(),
                stage_for(order_num - start + 1), ", ".join(spec.tags), "\n".join(spec.hints),
                spec.time, spec.space, spec.slug,
            ])
            for case in cases:
                tests.append([
                    order_num, case["order_num"], case["input_data"], case["expected_output"],
                    1 if case["is_sample"] else 0, case["explanation"] or "",
                ])

        head_fill = PatternFill("solid", fgColor="1F4E79")
        for sheet, widths in ((problems, [10, 34, 80, 11, 28, 30, 60, 16, 16, 30]), (tests, [18, 10, 40, 40, 10, 60])):
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = head_fill
            for col, width in zip("ABCDEFGHIJ", widths):
                sheet.column_dimensions[col].width = width
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions

        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        wb.save(path)
        self.stdout.write(self.style.SUCCESS(f"Exported to {path}"))
