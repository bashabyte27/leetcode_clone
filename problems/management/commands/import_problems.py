# problems/management/commands/import_problems.py

import pandas as pd
from django.core.management.base import BaseCommand
from problems.models import Problem, TestCase
import os


class Command(BaseCommand):
    help = 'Import problems and test cases from Excel file'

    def handle(self, *args, **kwargs):

        # ── File Path ──
        file_path = os.path.join(
            'data', 'problems', 'import_data.xlsx'
        )

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        self.stdout.write('Reading Excel file...')

        # ── Read Both Sheets ──
        problems_df = pd.read_excel(file_path, sheet_name='Problems')
        testcases_df = pd.read_excel(file_path, sheet_name='TestCases')

        self.stdout.write(f'Found {len(problems_df)} problems and {len(testcases_df)} test cases')

        # ── Import Problems ──
        self.stdout.write('Importing problems...')

        for _, row in problems_df.iterrows():
            description = str(row['description']).replace('\\n', '\n') if pd.notna(row['description']) else ''
            problem, created = Problem.objects.update_or_create(
                order_num=int(row['order_num']),
                defaults={
                    'title': row['title'],
                    'description': description,
                    'difficulty': row['difficulty'].lower(),
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created problem #{problem.order_num} - {problem.title}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  Updated problem #{problem.order_num} - {problem.title}'))

        # ── Import Test Cases ──
        self.stdout.write('Importing test cases...')

        for _, row in testcases_df.iterrows():
            # Find the problem using problem_order_num
            try:
                problem = Problem.objects.get(order_num=int(row['problem_order_num']))
            except Problem.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'  Problem with order_num {row["problem_order_num"]} not found! Skipping...'))
                continue

            # Handle \n replacement
            input_data = str(row['input_data']).replace('\\n', '\n') if pd.notna(row['input_data']) else ''
            expected_output = str(row['expected_output']).replace('\\n', '\n') if pd.notna(row['expected_output']) else ''

            # Handle is_sample — Excel stores TRUE/FALSE as bool
            is_sample = bool(row['is_sample']) if pd.notna(row['is_sample']) else False

            # Handle explanation — it can be empty
            explanation = str(row['explanation']).replace('\\n', '\n') if pd.notna(row['explanation']) else None

            testcase, created = TestCase.objects.update_or_create(
                problem=problem,
                order_num=int(row['order_num']),
                defaults={
                    'input_data': input_data,
                    'expected_output': expected_output,
                    'is_sample': is_sample,
                    'explanation': explanation,
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created test case #{testcase.order_num} for {problem.title}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  Updated test case #{testcase.order_num} for {problem.title}'))

        self.stdout.write(self.style.SUCCESS('Import completed successfully!'))