import os

from django.conf import settings
from django.test import TestCase

from problems.models import TestCase as ProblemTestCase
from problems.services import import_problems
from staff.services import _truthy


class ImportSampleFlagTests(TestCase):
    def test_truthy_handles_excel_values(self):
        for value in (1, 1.0, '1', '1.0', True, 'TRUE', 'yes', 'Y'):
            self.assertTrue(_truthy(value), value)
        for value in (0, 0.0, '0', '', None, float('nan'), False, 'no'):
            self.assertFalse(_truthy(value), value)

    def test_bundled_import_file_keeps_sample_cases(self):
        path = os.path.join(settings.BASE_DIR, 'data', 'problems', 'import_data.xlsx')
        if not os.path.exists(path):
            self.skipTest('import_data.xlsx not present')
        result = import_problems(path)
        self.assertEqual(result['errors'], [])
        self.assertGreater(ProblemTestCase.objects.filter(is_sample=True).count(), 0)
        self.assertGreater(ProblemTestCase.objects.filter(is_sample=False).count(), 0)
