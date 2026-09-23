import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial Django superuser from environment variables."

    def handle(self, *args, **options):
        User = get_user_model()

        user_name = os.getenv("ADMIN_USERNAME")
        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")

        if not user_name or not email or not password:
            raise CommandError(
                "ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD "
                "environment variables are required."
            )

        if User.objects.filter(user_name=user_name).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"User '{user_name}' already exists. No new user created."
                )
            )
            return

        User.objects.create_superuser(
            user_name=user_name,
            email=email,
            password=password,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Superuser '{user_name}' created successfully."
            )
        )