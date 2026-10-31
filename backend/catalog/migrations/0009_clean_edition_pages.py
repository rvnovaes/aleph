"""Edition and pages hold numbers only, since the ABNT style adds "ed." and "p."."""

import re

from django.db import migrations


def clean_edition(value):
    for number in re.findall(r"\d+", value or ""):
        if int(number) < 1000:
            return str(int(number))
    return ""


def clean_pages(value, kind="book"):
    value = value or ""
    if kind == "article-journal":
        span = re.search(r"(\d+)\s*[-–—]+\s*(\d+)", value)
        if span:
            return f"{int(span[1])}-{int(span[2])}"
    before_p = re.search(r"(\d+)\s*(?:p\b|pp\b|pág|pag|f\.)", value, re.IGNORECASE)
    if before_p:
        return str(int(before_p[1]))
    numbers = [int(n) for n in re.findall(r"\d+", value)]
    return str(max(numbers)) if numbers else ""


def clean(apps, schema_editor):
    Work = apps.get_model("catalog", "Work")
    changed = []
    for work in Work.objects.exclude(edition="", pages="").only("id", "kind", "edition", "pages"):
        edition = clean_edition(work.edition)
        pages = clean_pages(work.pages, work.kind)
        if (edition, pages) != (work.edition, work.pages):
            work.edition, work.pages = edition, pages
            changed.append(work)
    Work.objects.bulk_update(changed, ["edition", "pages"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0008_language")]
    operations = [migrations.RunPython(clean, migrations.RunPython.noop)]
