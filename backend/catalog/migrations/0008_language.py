from django.conf import settings
from django.db import migrations, models

NAMES = {
    "por": "Português",
    "eng": "Inglês",
    "spa": "Espanhol",
    "fre": "Francês",
    "ger": "Alemão",
    "ita": "Italiano",
    "lat": "Latim",
    "grc": "Grego antigo",
    "gre": "Grego moderno",
    "rus": "Russo",
    "cat": "Catalão",
    "chi": "Chinês",
    "jpn": "Japonês",
    "heb": "Hebraico",
    "ara": "Árabe",
    "ind": "Indonésio",
}
COMMON = ["por", "eng", "spa", "fre", "ger", "ita", "lat", "grc"]


def label(code):
    parts = [p.strip() for p in code.split(";") if p.strip()]
    return " e ".join(NAMES.get(p, p) for p in parts) or code


def seed(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Work = apps.get_model("catalog", "Work")
    Language = apps.get_model("catalog", "Language")
    for user in User.objects.all():
        used = set(
            Work.objects.filter(owner=user).exclude(language="").values_list("language", flat=True)
        )
        if not used:
            continue
        for code in sorted(used | set(COMMON)):
            Language.objects.get_or_create(owner=user, name=label(code), defaults={"code": code})


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_work_abnt_reference"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Language",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("code", models.CharField(blank=True, max_length=100)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="language",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"), name="unique_owner_language"
            ),
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
