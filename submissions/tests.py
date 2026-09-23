from django.test import TestCase

from .judge import comparable_case_text, normalize_case_text


class TestCaseTextTests(TestCase):
	def test_multiline_case_text_preserves_internal_line_breaks(self):
		value = r'11 x 1 = 11\n11 x 2 = 22\n11 x 3 = 33'
		self.assertEqual(normalize_case_text(value), '11 x 1 = 11\n11 x 2 = 22\n11 x 3 = 33')
		self.assertEqual(comparable_case_text(value), '11 x 1 = 11\n11 x 2 = 22\n11 x 3 = 33')

# Create your tests here.
