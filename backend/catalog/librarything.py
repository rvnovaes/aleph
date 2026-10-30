"""Conservative, repeatable LibraryThing import. Originals are retained verbatim."""

import hashlib
import html
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from .models import Author, City, Contribution, Identifier, ImportRecord, Item, Publisher, Tag, Work
from .services import normalize_identifier, resolve_publisher


def text(value):
    return html.unescape(str(value)).strip() if value is not None else ""


def values(value):
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, list):
        return value
    return [value] if value not in (None, "") else []


def strings(value):
    return list(
        dict.fromkeys(
            text(v) for v in values(value) if isinstance(v, (str, int, float)) and text(v)
        )
    )


def key(value):
    return re.sub(
        r"[^a-z0-9]",
        "",
        unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore").decode().lower(),
    )


def parse_publication(value):
    """Split the publication statement without confusing Edition: with a place."""
    statement = re.split(r"\s*\(\d{4}\)|,\s*(?:Edition|Edição):", text(value), flags=re.I)[
        0
    ].strip()
    city = ""
    if ":" in statement:
        city, statement = (part.strip() for part in statement.split(":", 1))
        if not city or not statement:
            return "", ""
    publisher = re.sub(r",\s*\d{4}\.?$", "", statement).strip()
    return city, publisher


def fill_publication(work, raw):
    """Only fill empty relations; preserve existing cataloging and source text."""
    city, publisher = parse_publication(raw.get("publication"))
    changed = {}
    for field, value, model in [("city", city, City), ("publisher", publisher, Publisher)]:
        if value and not getattr(work, field + "_id"):
            obj = (
                resolve_publisher(work.owner, value)
                if field == "publisher"
                else model.objects.filter(name=value).first() or model.objects.create(name=value)
            )
            setattr(work, field, obj)
            changed[field] = value
    if changed:
        work.save(update_fields=[*changed, "updated_at"])
    return changed


def parse_record(raw, warnings):
    def money(field):
        if raw.get(field) in (None, ""):
            return None
        try:
            value = text(raw[field])
            if "," in value:
                value = value.replace(".", "").replace(",", ".")
            amount = Decimal(value)
            if (
                not amount.is_finite()
                or amount < 0
                or amount >= Decimal("10000000000")
                or amount != amount.quantize(Decimal(".01"))
            ):
                raise ValueError()
            return amount.quantize(Decimal(".01"))
        except (InvalidOperation, ValueError):
            warnings.append(f"{field}: valor não reconhecido; preservado no original")
            return None

    def day(field):
        if not raw.get(field):
            return None
        try:
            return date.fromisoformat(raw[field])
        except ValueError:
            warnings.append(f"{field}: data não reconhecida; preservada no original")
            return None

    publication = text(raw.get("publication"))
    _, publisher = parse_publication(publication)
    year = text(raw.get("date"))
    identifiers = []
    for isbn in strings(raw.get("isbn")) + strings(raw.get("originalisbn")):
        try:
            identifiers.append(normalize_identifier("isbn", isbn))
        except ValueError:
            warnings.append(f"ISBN não válido: {isbn}")
    roles = {
        "author": "author",
        "autor": "author",
        "auteur": "author",
        "autore": "author",
        "editor": "editor",
        "organizador": "editor",
        "org.": "editor",
        "compilador": "editor",
        "coordenador": "editor",
        "translator": "translator",
        "traduction": "translator",
        "illustrator": "illustrator",
        "introduction": "introduction",
        "foreword": "foreword",
        "afterword": "afterword",
        "adapter": "adapter",
        "cartógrafo": "cartographer",
    }
    authors = []
    for author in values(raw.get("authors")):
        if not isinstance(author, dict):
            continue
        name = text(author.get("lf") or author.get("fl"))
        if not name:
            continue
        parts = name.split(",", 1)
        role = roles.get(
            text(author.get("role") or raw.get("primaryauthorrole") or "Author").lower(),
            "contributor",
        )
        authors.append(
            {
                "name": name,
                "family": parts[0] if len(parts) == 2 else "",
                "given": parts[1].strip() if len(parts) == 2 else "",
                "role": role,
            }
        )
    if not authors and raw.get("primaryauthor"):
        authors = [
            {"name": text(raw["primaryauthor"]), "family": "", "given": "", "role": "author"}
        ]
    subjects = []
    for heading in values(raw.get("subject")):
        parts = strings(heading)
        if parts:
            subjects.append(" — ".join(parts))
    ddc = raw.get("ddc") or {}
    lcc = raw.get("lcc") or {}
    fields = {
        "kind": "book",
        "title": text(raw.get("title")) or "Sem título",
        "year": int(year) if re.fullmatch(r"\d{4}", year) and int(year) > 0 else None,
        "language": "; ".join(strings(raw.get("language_codeA")) or strings(raw.get("language"))),
        "pages": text(raw.get("pages")),
        "notes": text(raw.get("comment")),
        "private_notes": text(raw.get("privatecomment")),
        "subjects": list(dict.fromkeys(subjects)),
        "ddc": strings(ddc.get("code")),
        "ddc_wording": strings(ddc.get("wording")),
        "lcc": strings(lcc.get("code")),
        "original_title": text(raw.get("originaltitle")),
        "original_language": "; ".join(
            strings(raw.get("originallanguage_codeA")) or strings(raw.get("originallanguage"))
        ),
        "series": strings(raw.get("series")),
        "binding": "; ".join(
            text(v.get("text")) for v in values(raw.get("format")) if isinstance(v, dict)
        ),
        "publication_statement": publication,
        "physical_description": text(raw.get("physical_description")),
        "pending": not bool(authors) or not bool(raw.get("title")),
    }
    item = {
        "legacy_barcode": "; ".join(strings(raw.get("barcode"))),
        "purchase_price": money("price_purchase"),
        "estimated_value": money("price_value"),
        "reported_value": money("price"),
        "acquired_on": day("dateacquired"),
        "acquired_from": text(raw.get("fromwhere")),
        "condition": text(raw.get("condition")),
        "cataloged_on": day("entrydate"),
    }
    return (
        fields,
        publisher,
        authors,
        list(dict.fromkeys(identifiers)),
        strings(raw.get("tags")),
        item,
    )


@transaction.atomic
def import_librarything(user, path, dry_run=False, repair_publication=False):
    raw_file = Path(path).read_bytes()
    data = json.loads(raw_file.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Esperado um objeto com os registros do LibraryThing.")
    type(user).objects.select_for_update().get(pk=user.pk)
    report = {
        "file_sha256": hashlib.sha256(raw_file).hexdigest(),
        "dry_run": dry_run,
        "total": len(data),
        "created": 0,
        "matched_existing": 0,
        "skipped": 0,
        "updated": 0,
        "repair_publication": repair_publication,
        "warnings": [],
        "records": [],
        "currency": "BRL (assumida conforme solicitação; arquivo não declara moeda)",
    }
    baseline = set(
        Work.objects.filter(owner=user)
        .exclude(importrecord__source="LibraryThing")
        .values_list("id", flat=True)
    )
    for source_key, raw in data.items():
        external_id = text(raw.get("books_id") or source_key)
        digest = hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        prior = ImportRecord.objects.filter(
            owner=user, source="LibraryThing", external_id=external_id
        ).first()
        if prior:
            if repair_publication and prior.checksum == digest:
                changed = fill_publication(prior.work, raw)
                if changed:
                    report["updated"] += 1
                    report["records"].append(
                        {"source_id": external_id, "work_id": prior.work_id, "filled": changed}
                    )
                    continue
            report["skipped"] += 1
            if prior.checksum != digest:
                report["warnings"].append(
                    {
                        "id": external_id,
                        "messages": [
                            "Registro mudou na origem; mantido o cadastro local sem sobrescrever."
                        ],
                    }
                )
            continue
        warnings = []
        fields, publisher, authors, isbns, tags, item_fields = parse_record(raw, warnings)
        matches = []
        for candidate in (
            Work.objects.filter(
                owner=user,
                id__in=baseline,
                identifiers__scheme="isbn",
                identifiers__value__in=isbns,
            )
            .distinct()
            .select_related("publisher")
        ):
            if (
                key(candidate.title) == key(fields["title"])
                and candidate.year == fields["year"]
                and candidate.publisher
                and key(candidate.publisher.name) == key(publisher)
                and authors
                and candidate.contributions.filter(author__name__iexact=authors[0]["name"]).exists()
            ):
                matches.append(candidate)
        if len(matches) == 1:
            work = matches[0]
            baseline.discard(work.id)
            for name, value in fields.items():
                if name != "pending" and not getattr(work, name):
                    setattr(work, name, value)
            work.save()
            report["matched_existing"] += 1
            # One existing copy is reconciled without losing its location or annotations.
            existing_items = list(work.items.all())
            item = existing_items[0] if len(existing_items) == 1 else Item(work=work)
            for name, value in item_fields.items():
                if getattr(item, name) in (None, ""):
                    setattr(item, name, value)
            item.save()
        else:
            if Identifier.objects.filter(work__owner=user, scheme="isbn", value__in=isbns).exists():
                warnings.append(
                    "ISBN compartilhado com outro cadastro; mantidos registros separados para revisão."
                )
                fields["pending"] = True
            work = Work(owner=user, **fields)
            if publisher:
                work.publisher = resolve_publisher(user, publisher)
            work.full_clean(exclude=["tags"])
            work.save()
            for position, author in enumerate(authors):
                role = author.pop("role")
                person = Author.objects.create(**author)
                Contribution.objects.create(work=work, author=person, position=position, role=role)
            item = Item.objects.create(work=work, **item_fields)
            report["created"] += 1
        fill_publication(work, raw)
        for isbn in isbns:
            Identifier.objects.get_or_create(work=work, scheme="isbn", value=isbn)
        for name in tags:
            work.tags.add(Tag.objects.get_or_create(owner=user, name=name)[0])
        ImportRecord.objects.create(
            owner=user,
            source="LibraryThing",
            external_id=external_id,
            work=work,
            item=item,
            raw=raw,
            checksum=digest,
        )
        if warnings:
            report["warnings"].append({"id": external_id, "messages": warnings})
        report["records"].append({"source_id": external_id, "work_id": work.id, "item_id": item.id})
    if dry_run:
        transaction.set_rollback(True)
    return report
