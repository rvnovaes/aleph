import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from pypdf import PdfWriter

from catalog.models import Document, ImportRecord, Work


class RepositoryImportTests(TestCase):
    def test_duplicate_pdf_and_rerun_keep_one_pending_record(self):
        user = get_user_model().objects.create_user(username="repository-test")
        with (
            tempfile.TemporaryDirectory() as folder,
            override_settings(MEDIA_ROOT=folder + "/media"),
        ):
            root = Path(folder)
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.write(str(root / "book.pdf"))
            digest = hashlib.sha256((root / "book.pdf").read_bytes()).hexdigest()
            (root / "copy.pdf").write_bytes((root / "book.pdf").read_bytes())
            rows = [
                {"path": name, "title": "Livro", "author": "Autora", "sha256": digest}
                for name in ["book.pdf", "copy.pdf"]
            ]
            manifest = root / "inventory.jsonl"
            manifest.write_text("\n".join(json.dumps(r) for r in rows))
            for _ in range(2):
                call_command(
                    "import_pdf_repository",
                    str(manifest),
                    str(root),
                    username=user.username,
                    report=root / "report.json",
                )
            self.assertEqual(Work.objects.filter(owner=user, pending=True).count(), 1)
            self.assertEqual(Document.objects.count(), 1)
            self.assertEqual(ImportRecord.objects.count(), 1)
            self.assertEqual(Document.objects.get().sha256, digest)
            self.assertEqual(
                Path(Document.objects.get().file.path).read_bytes(),
                (root / "book.pdf").read_bytes(),
            )
