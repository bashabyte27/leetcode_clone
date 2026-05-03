from django.core.management.base import BaseCommand
from courses.models import Courses


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        updates = [
            ('Python Programming',      'courses/thumbnails/python.png'),
            ('Django Web Development',  'courses/thumbnails/django.jpeg'),
            ('Data Structures & Algorithms', 'courses/thumbnails/dsa.png'),
            ('SQL & Database Design',   'courses/thumbnails/sql.png'),
            ('React for Beginners',     'courses/thumbnails/react.png'),
            ('System Design',           'courses/thumbnails/system_design.jpeg'),
        ]

        for title, thumbnail_path in updates:
            updated = Courses.objects.filter(title=title).update(thumbnail=thumbnail_path)
            if updated:
                print(f"{title} — thumbnail updated")
            else:
                print(f"{title} — not found")

        self.stdout.write(self.style.SUCCESS('Update completed.'))