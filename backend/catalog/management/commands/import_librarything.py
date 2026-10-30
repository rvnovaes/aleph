import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from catalog.librarything import import_librarything


class Command(BaseCommand):
    help = "Importa LibraryThing de forma transacional, preservando originais e ignorando IDs já importados."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--username", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--repair-publication", action="store_true")
        parser.add_argument("--report", required=True)

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options["username"])
            report = import_librarything(
                user, options["path"], options["dry_run"], options["repair_publication"]
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        Path(options["report"]).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.stdout.write(
            json.dumps(
                {k: v for k, v in report.items() if k not in ["records", "warnings"]},
                ensure_ascii=False,
            )
        )
        self.stdout.write(
            f"Registros com avisos: {len(report['warnings'])}. Relatório: {options['report']}"
        )
