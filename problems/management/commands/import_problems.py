# problems/management/commands/import_problems.py

import os

from django.core.management.base import BaseCommand

from problems.services import import_problems


class Command(BaseCommand):
    help = 'Import problems and test cases from Excel file'

    def handle(self, *args, **kwargs):
        file_path = os.path.join(
            'data', 'problems', 'import_data.xlsx'
        )

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        result = import_problems(file_path)
        for error in result['errors']:
            self.stdout.write(self.style.ERROR(error))
        self.stdout.write(self.style.SUCCESS(
            f"Import completed: {result['created']} created, {result['updated']} updated, "
            f"{len(result['errors'])} errors"
        ))