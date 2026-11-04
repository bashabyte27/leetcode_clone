from django.db import migrations


def seed_programming_languages(apps, schema_editor):
    database = schema_editor.connection.alias
    ProgrammingLanguage = apps.get_model("assessment", "ProgrammingLanguage")
    CatalogLanguage = apps.get_model("problems", "Language")

    for language in CatalogLanguage.objects.using(database).filter(is_active=True):
        try:
            judge0_language_id = int(language.judge_id)
        except (TypeError, ValueError):
            continue
        if judge0_language_id < 1:
            continue

        ProgrammingLanguage.objects.using(database).get_or_create(
            slug=language.slug,
            defaults={
                "name": language.name,
                "is_active": True,
                "is_judge0_executable": True,
                "judge0_language_id": judge0_language_id,
                "problems_language_id": language.pk,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("assessment", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_programming_languages, migrations.RunPython.noop),
    ]
