"""Idempotent PDF import. Input manifest is private; external matches remain reviewable."""

import hashlib
import json
import time
from difflib import SequenceMatcher
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from pypdf import PdfReader

from catalog.connectors import lookup
from catalog.models import Document, ImportRecord, SourceRecord
from catalog.schemas import WorkIn
from catalog.services import save_work


class Command(BaseCommand):
    help = "Import private PDF inventory; mark all affected records pending review."

    def add_arguments(self, parser):
        parser.add_argument("manifest", type=Path)
        parser.add_argument("root", type=Path)
        parser.add_argument("--username", required=True)
        parser.add_argument("--report", type=Path, required=True)
        parser.add_argument("--enrich", action="store_true")

    def handle(self, **options):
        user = get_user_model().objects.get(username=options["username"])
        root = options["root"].resolve()
        results = []
        # PostgreSQL text/JSONB rejects NUL characters found in some old PDF metadata.
        rows = [json.loads(line.replace("\\u0000", "")) for line in options["manifest"].read_text().splitlines()]
        for index, row in enumerate(rows, 1):
            result = {"path": row["path"], "sha256": row["sha256"]}
            try:
                path = (root / row["path"]).resolve()
                if not path.is_relative_to(root):
                    raise ValueError("Path outside import root")
                with path.open("rb") as file:
                    digest = hashlib.file_digest(file, "sha256").hexdigest()
                if digest != row["sha256"]:
                    raise ValueError("Checksum mismatch")
                previous = ImportRecord.objects.filter(
                    owner=user, source="obsidian-pdf", external_id=digest
                ).first()
                if previous:
                    result.update(status="already-imported", work_id=previous.work_id)
                else:
                    reader = PdfReader(str(path))
                    if reader.is_encrypted and not reader.decrypt(""):
                        raise ValueError("Password-protected PDF")
                    if not len(reader.pages):
                        raise ValueError("Empty PDF")
                    existing = Document.objects.filter(work__owner=user, sha256=digest).first()
                    if existing:
                        work = existing.work
                        work.pending = True
                        work.save(update_fields=["pending"])
                    else:
                        payload = {
                            "title": row["title"],
                            "authors": [{"name": row["author"]}] if row.get("author") else [],
                            "pending": True,
                            "pages": str(len(reader.pages)),
                            "private_notes": "Importado do repositório pessoal: "
                            + row["path"]
                            + "\nMetadados extraídos automaticamente; revisar título, autoria, tipo e edição.",
                        }
                        candidates = []
                        extracted = {"ISBN": row.get("isbns", []), "DOI": row.get("dois", [])}
                        payload["private_notes"] += (
                            "\nIdentificadores candidatos, a confirmar: "
                            + json.dumps(extracted, ensure_ascii=False)
                        )
                        identifiers = row.get("isbns", [])
                        scheme = "isbn"
                        if not identifiers and len(row.get("dois", [])) == 1:
                            identifiers = row["dois"]
                            scheme = "doi"
                        if options["enrich"] and len(identifiers) == 1:
                            found = lookup(scheme, identifiers[0])
                            candidates = found.get("candidates", [])
                            for candidate in candidates:
                                data = candidate["data"]
                                similarity = SequenceMatcher(
                                    None, row["title"].casefold(), data["title"].casefold()
                                ).ratio()
                                if similarity >= 0.72:
                                    # Store the proposal, without asserting edition identity or overwriting the PDF description.
                                    payload.update(
                                        {
                                            k: v
                                            for k, v in data.items()
                                            if k
                                            in [
                                                "subtitle",
                                                "year",
                                                "publisher",
                                                "city",
                                                "edition",
                                                "journal",
                                                "volume",
                                                "issue",
                                                "kind",
                                            ]
                                            and v
                                        }
                                    )
                                    if data.get("authors"):
                                        payload["authors"] = data["authors"]
                                    break
                            time.sleep(2)
                        # A separate digital record avoids silently merging editions with physical holdings.
                        with transaction.atomic():
                            prior = SourceRecord.objects.filter(
                                work__owner=user, source="Obsidian PDF", raw__sha256=digest
                            ).first()
                            work = prior.work if prior else save_work(user, WorkIn(**payload))
                            SourceRecord.objects.create(
                                work=work, source="Obsidian PDF", query=row["path"], raw=row
                            )
                            for candidate in candidates:
                                SourceRecord.objects.create(
                                    work=work,
                                    source=candidate["source"],
                                    query=scheme + ":" + identifiers[0],
                                    raw={"candidate": candidate, "requires_edition_review": True},
                                )
                        document = Document(
                            work=work,
                            original_name=path.name[:255],
                            size=path.stat().st_size,
                            sha256=digest,
                        )
                        with path.open("rb") as file:
                            document.file.save("document.pdf", File(file), save=False)
                        try:
                            document.save()
                        except Exception:
                            document.file.delete(save=False)
                            raise
                    ImportRecord.objects.create(
                        owner=user,
                        source="obsidian-pdf",
                        external_id=digest,
                        work=work,
                        item=None,
                        raw={
                            "path": row["path"],
                            "isbns": row.get("isbns", []),
                            "dois": row.get("dois", []),
                        },
                        checksum=digest,
                    )
                    result.update(status="imported", work_id=work.pk)
            except Exception as exc:
                result.update(status="error", error=str(exc)[:500])
            results.append(result)
            options["report"].write_text(json.dumps(results, ensure_ascii=False, indent=2))
            if index % 20 == 0:
                self.stdout.write(f"{index}/{len(rows)} processed", ending="\n")
                self.stdout.flush()
        self.stdout.write(
            str(
                {
                    s: sum(r["status"] == s for r in results)
                    for s in ["imported", "already-imported", "error"]
                }
            )
        )
