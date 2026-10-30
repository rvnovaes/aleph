import hashlib
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError
from pypdf import PdfReader

from .models import (
    Author,
    City,
    Contribution,
    Document,
    Identifier,
    Journal,
    LookupCache,
    Publisher,
    SourceRecord,
    Tag,
    Work,
)


def normalize_identifier(scheme, value):
    if scheme == "doi":
        value = re.sub(
            r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.IGNORECASE
        ).lower()
        if not re.fullmatch(r"10\.\d{4,9}/\S+", value):
            raise ValueError("DOI inválido.")
        return value
    value = re.sub(r"[\s-]", "", value).upper()
    if re.fullmatch(r"\d{9}[\dX]", value):
        digits = [10 if x == "X" else int(x) for x in value]
        if sum((10 - i) * n for i, n in enumerate(digits)) % 11:
            raise ValueError("ISBN inválido.")
        value = "978" + value[:9]
        value += str((-sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(value))) % 10)
    if (
        not re.fullmatch(r"97[89]\d{10}", value)
        or sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(value)) % 10
    ):
        raise ValueError("ISBN inválido.")
    return value


def work_queryset(user):
    return (
        Work.objects.filter(owner=user)
        .select_related("publisher", "city", "journal")
        .prefetch_related(
            "identifiers", "contributions__author", "items__location", "documents", "tags"
        )
    )


def serialize(work):
    data = {
        field: getattr(work, field)
        for field in [
            "id",
            "kind",
            "title",
            "subtitle",
            "year",
            "edition",
            "language",
            "pages",
            "volume",
            "issue",
            "url",
            "accessed",
            "notes",
            "abnt_reference",
            "pending",
            "subjects",
            "ddc",
            "ddc_wording",
            "lcc",
            "series",
            "original_title",
            "original_language",
            "binding",
            "publication_statement",
            "physical_description",
            "private_notes",
        ]
    }
    data.update(
        {
            field: getattr(work, field).name if getattr(work, field) else ""
            for field in ["publisher", "city", "journal"]
        }
    )
    data["publisher_id"] = work.publisher_id
    data["tags"] = list(work.tags.values_list("name", flat=True))
    data["authors"] = [
        {
            "name": c.author.name,
            "given": c.author.given,
            "family": c.author.family,
            "institutional": c.author.institutional,
            "role": c.role,
        }
        for c in work.contributions.all()
    ]
    data["identifiers"] = [{"scheme": i.scheme, "value": i.value} for i in work.identifiers.all()]
    data["items"] = [
        {
            "id": i.id,
            "code": str(i.code),
            "location_id": i.location_id,
            "location": " / ".join(
                filter(None, [i.location.room, i.location.bookcase, i.location.shelf])
            )
            if i.location
            else "Localização não informada",
            "notes": i.notes,
            **{
                key: (str(getattr(i, key)) if getattr(i, key) is not None else None)
                for key in ["purchase_price", "estimated_value", "reported_value"]
            },
            **{
                key: getattr(i, key)
                for key in [
                    "legacy_barcode",
                    "currency",
                    "acquired_on",
                    "acquired_from",
                    "condition",
                    "cataloged_on",
                ]
            },
        }
        for i in work.items.all()
    ]
    data["cover_url"] = (
        f"/api/covers/{work.pk}?v={work.cover.name.rsplit('/', 1)[-1]}" if work.cover else None
    )
    data["documents"] = [
        {"id": d.id, "name": d.original_name, "size": d.size} for d in work.documents.all()
    ]
    return data


def resolve_publisher(user, name):
    name = name.strip()
    if not name:
        return None
    return Publisher.objects.filter(
        owner=user, name__iexact=name
    ).first() or Publisher.objects.create(owner=user, name=name)


@transaction.atomic
def save_work(user, payload, work_id=None):
    values = payload.model_dump(
        exclude={"authors", "identifiers", "candidate_key", "candidate_index", "tags"}
    )
    if "abnt_reference" not in payload.model_fields_set:
        values.pop("abnt_reference", None)
    if values["url"] and not values["url"].startswith(("https://", "http://")):
        raise HttpError(422, "URL deve começar com http:// ou https://.")
    normalized = []
    for identifier in payload.identifiers:
        try:
            normalized.append(
                (identifier.scheme, normalize_identifier(identifier.scheme, identifier.value))
            )
        except ValueError as exc:
            raise HttpError(422, str(exc))
    # Serializes simultaneous creates for one account, avoiding duplicate ISBN records.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    for scheme, value in normalized:
        existing = (
            Identifier.objects.filter(work__owner=user, scheme=scheme, value=value)
            .exclude(work_id=work_id)
            .first()
        )
        if (
            existing
            and not Identifier.objects.filter(work_id=work_id, scheme=scheme, value=value).exists()
        ):
            raise HttpError(
                409,
                f"Identificador já cadastrado no registro {existing.work_id}. Abra-o para adicionar outro exemplar.",
            )
    work = get_object_or_404(Work, owner=user, pk=work_id) if work_id else Work(owner=user)
    publisher_id = values.pop("publisher_id")
    publisher_name = values.pop("publisher").strip()
    publisher = (
        get_object_or_404(Publisher, owner=user, pk=publisher_id)
        if publisher_id
        else resolve_publisher(user, publisher_name)
    )
    values["publisher"] = publisher
    if "city" not in payload.model_fields_set:
        values["city"] = (
            work.city.name
            if work.city_id
            else publisher.default_city.name
            if not work_id and publisher and publisher.default_city_id
            else ""
        )
    for name, model in [("city", City), ("journal", Journal)]:
        text = values.pop(name).strip()
        values[name] = (
            (model.objects.filter(name=text).first() or model.objects.create(name=text))
            if text
            else None
        )
    work = get_object_or_404(Work, owner=user, pk=work_id) if work_id else Work(owner=user)
    for key, value in values.items():
        setattr(work, key, value)
    work.save()
    work.tags.set(
        [
            Tag.objects.get_or_create(owner=user, name=name.strip())[0]
            for name in dict.fromkeys(payload.tags)
            if name.strip()
        ]
    )
    work.identifiers.all().delete()
    for scheme, value in set(normalized):
        Identifier.objects.create(work=work, scheme=scheme, value=value)
    previous_authors = list(Author.objects.filter(contribution__work=work))
    work.contributions.all().delete()
    # Deliberately do not merge people just because their names coincide.
    for position, author in enumerate(payload.authors):
        fields = author.model_dump(exclude={"role"})
        person = next(
            (
                a
                for a in previous_authors
                if all(getattr(a, key) == value for key, value in fields.items())
            ),
            None,
        ) or Author.objects.create(**fields)
        Contribution.objects.create(work=work, author=person, position=position, role=author.role)
    if payload.candidate_key:
        cached = LookupCache.objects.filter(key=payload.candidate_key).first()
        candidates = cached.result.get("candidates", []) if cached else []
        if 0 <= payload.candidate_index < len(candidates):
            candidate = candidates[payload.candidate_index]
            SourceRecord.objects.create(
                work=work,
                source=candidate["source"],
                query=payload.candidate_key,
                raw=candidate["raw"],
            )
    return work


def save_pdf(work, upload):
    if upload.size > settings.MAX_PDF_BYTES:
        raise HttpError(413, "PDF excede o limite de 100 MB.")
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    if upload.read(5) != b"%PDF-":
        raise HttpError(422, "O arquivo não é um PDF válido.")
    upload.seek(0)
    try:
        reader = PdfReader(upload)
        if reader.is_encrypted:
            raise ValueError("encrypted")
        if len(reader.pages) == 0:
            raise ValueError("empty")
    except Exception:
        raise HttpError(422, "PDF inválido, vazio ou protegido por senha.")
    upload.seek(0)
    sha = digest.hexdigest()
    existing = Document.objects.filter(work=work, sha256=sha).first()
    if existing:
        return existing
    document = Document(work=work, original_name=upload.name[:255], size=upload.size, sha256=sha)
    document.file.save("document.pdf", upload, save=False)
    try:
        document.save()
    except Exception:
        document.file.delete(save=False)
        raise
    return document


def csl(work):
    return csl_data(serialize(work), str(work.pk))


def csl_data(data, record_id="preview"):
    result = {
        "id": record_id,
        "type": data["kind"],
        "title": data["title"] + (": " + data["subtitle"] if data["subtitle"] else ""),
    }
    for role in ["author", "editor", "translator"]:
        names = []
        for author in data["authors"]:
            if author["role"] != role:
                continue
            names.append(
                {"family": author["family"], "given": author["given"]}
                if author["family"] and not author["institutional"]
                else {"literal": author["name"]}
            )
        if names:
            result[role] = names
    if data["year"]:
        result["issued"] = {"date-parts": [[data["year"]]]}
    for key, value in {
        "edition": data["edition"],
        "language": data["language"],
        "publisher": data["publisher"],
        "publisher-place": data["city"],
        "container-title": data["journal"],
        "volume": data["volume"],
        "issue": data["issue"],
        "URL": data["url"],
        "number-of-pages" if data["kind"] == "book" else "page": data["pages"],
    }.items():
        if value:
            result[key] = value
    if data["accessed"]:
        accessed = data["accessed"]
        result["accessed"] = {"date-parts": [[accessed.year, accessed.month, accessed.day]]}
    for identifier in data["identifiers"]:
        result[identifier["scheme"].upper()] = identifier["value"]
    return result
