"""Hash any passwords that were saved as plain text through the old admin form."""

from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations

UNUSABLE_PREFIX = "!"


def hash_plaintext_passwords(apps, schema_editor):
    Users = apps.get_model("users", "Users")
    for user in Users.objects.exclude(password="").only("pk", "password").iterator():
        raw = user.password
        if raw.startswith(UNUSABLE_PREFIX):
            continue
        try:
            identify_hasher(raw)
        except ValueError:
            Users.objects.filter(pk=user.pk).update(password=make_password(raw))


class Migration(migrations.Migration):
    dependencies = [("users", "0002_users_is_faculty")]

    operations = [migrations.RunPython(hash_plaintext_passwords, migrations.RunPython.noop)]
