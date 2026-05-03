from django.core.management.base import BaseCommand
from courses.models import Courses


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        all_courses = [
            ('Python Programming',      'A beginner friendly course where you can learn everything about Python from scratch.',            '120 hrs',"courses/thumbnails/6069ec7c-2364-440b-ad89-81fcfd673cc7.png"),
            ('Django Web Development',  'Learn how to build full stack web applications using Django and PostgreSQL.',                     '80 hrs',"courses/thumbnails/images (1).jpeg"),
            ('Data Structures & Algorithms', 'Master DSA concepts with hands-on problem solving in Python.',                             '100 hrs',"courses/thumbnails/images (3).png"),
            ('SQL & Database Design',   'Learn SQL from basics to advanced — joins, indexing, normalization and best practices.',          '60 hrs',"courses/thumbnails/download (2).png"),
            ('React for Beginners',     'Build modern user interfaces using React, hooks, and component-based architecture.',             '70 hrs',"courses/thumbnails/images (4).png"),
            ('System Design',           'Understand how large scale systems are designed — load balancing, caching, and more.',           '50 hrs',"courses/thumbnails/download.jpeg"),
        ]

        for course in all_courses:
            instance, created = Courses.objects.get_or_create(
                title=course[0],
                description=course[1],
                duration=course[2],
            )
            print(f"{course[0]} is created: {created}")

        self.stdout.write(self.style.SUCCESS('Seeding completed successfully.'))