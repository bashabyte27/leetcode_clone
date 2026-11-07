"""
Import one course tab from the content workbook (docs/courses/SHEET_FORMAT.md).

    python manage.py import_course_sheet courses.xlsx --tab "Core Python"            # dry run
    python manage.py import_course_sheet courses.xlsx --tab "Core Python" --apply    # write

Dry run is the default. Bank items (MCQs, coding questions) are owned by
--owner (an email), or by the first superuser when it is left out.
"""

from django.core.management.base import BaseCommand, CommandError

from courses.sheet_importer import import_sheet
from users.models import Users


class Command(BaseCommand):
    help = "Check (and with --apply, import) one course tab from the content workbook."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Workbook (.xlsx) or a single tab saved as .csv")
        parser.add_argument("--tab", help="Tab name, e.g. 'Core Python' (not needed for .csv)")
        parser.add_argument("--apply", action="store_true", help="Write the changes (default: dry run)")
        parser.add_argument("--owner", help="Email of the staff user who owns imported bank items")

    def handle(self, *args, **opts):
        path = opts["path"]
        if not path.lower().endswith(".csv") and not opts["tab"]:
            raise CommandError("Pass --tab for a workbook, e.g. --tab \"Core Python\".")
        owner = self._owner(opts["owner"])
        with open(path, "rb") as handle:
            report = import_sheet(handle, tab=opts["tab"], owner=owner, dry_run=not opts["apply"])

        for label, created, updated in report.rows():
            if created or updated:
                self.stdout.write(f"  {label:<11} {created:>4} new  {updated:>4} updated")
        for warning in report.warnings:
            self.stdout.write(self.style.WARNING(f"  warning: {warning}"))
        for error in report.errors:
            self.stdout.write(self.style.ERROR(f"  error: {error}"))

        if report.errors:
            raise CommandError(f"{len(report.errors)} problem(s); nothing was saved.")
        if report.dry_run:
            self.stdout.write(self.style.SUCCESS("Check passed. Run again with --apply to import."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Imported {report.course.title} (course id {report.course.pk})."))

    def _owner(self, email):
        if email:
            user = Users.objects.filter(email__iexact=email).first()
            if user is None:
                raise CommandError(f"No user with email {email}.")
            return user
        user = Users.objects.filter(is_superuser=True).order_by("created_at").first()
        if user is None:
            raise CommandError("No superuser found; pass --owner <email>.")
        return user
