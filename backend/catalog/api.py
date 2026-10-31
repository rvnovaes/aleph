from typing import Literal

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from ninja import File, NinjaAPI, Query
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.security import django_auth

from .connectors import lookup
from .covers import replace_cover
from .models import City, Item, Language, Location, Publisher, SourceRecord, Tag, Work
from .schemas import ItemIn, LanguageIn, LocationIn, PublisherIn, WorkIn
from .services import (
    csl,
    csl_data,
    normalize_identifier,
    save_pdf,
    save_work,
    serialize,
    work_queryset,
)

api = NinjaAPI(
    title="Aleph · Catálogo pessoal",
    version="1.0",
    auth=django_auth,
    docs_decorator=login_required(login_url="/"),
)


@api.get("/works")
def list_works(
    request,
    q: str = "",
    page: int = 1,
    location: int | None = None,
    kind: str = "",
    pending: bool = False,
    tag: list[str] = Query([]),
    unlocated: bool = False,
    room: str | None = None,
    bookcase: str | None = None,
):
    queryset = work_queryset(request.user)
    total_count = queryset.count()
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(contributions__author__name__icontains=q)
            | Q(identifiers__value__icontains=q)
            | Q(publisher__name__icontains=q)
            | Q(tags__name__icontains=q)
            | Q(items__legacy_barcode__icontains=q)
        ).distinct()
    if location is not None or room is not None or bookcase is not None:
        places = Location.objects.filter(owner=request.user)
        if location is not None:
            places = places.filter(pk=location)
        if room is not None:
            places = places.filter(room=room)
        if bookcase is not None:
            places = places.filter(bookcase=bookcase)
        queryset = queryset.filter(items__location__in=places).distinct()
    # Several tags narrow the list: a work must carry every selected tag.
    for name in {t for t in tag if t}:
        queryset = queryset.filter(
            pk__in=Work.objects.filter(tags__owner=request.user, tags__name=name).values("pk")
        )
    if unlocated:
        queryset = queryset.filter(items__isnull=False, items__location__isnull=True).distinct()
    if kind:
        queryset = queryset.filter(kind=kind)
    if pending:
        queryset = queryset.filter(pending=True)
    page = max(1, page)
    return {
        "count": queryset.count(),
        "total_count": total_count,
        "page": page,
        "results": [
            serialize(w) for w in queryset.order_by("title", "pk")[(page - 1) * 30 : page * 30]
        ],
    }


@api.get("/works/{work_id}")
def detail(request, work_id: int):
    return serialize(get_object_or_404(work_queryset(request.user), pk=work_id))


@api.post("/works")
def create(request, payload: WorkIn):
    return {"id": save_work(request.user, payload).id}


@api.put("/works/{work_id}")
def update(request, work_id: int, payload: WorkIn):
    return {"id": save_work(request.user, payload, work_id).id}


@api.get("/locations")
def locations(request):
    return list(
        Location.objects.filter(owner=request.user)
        .annotate(
            item_count=Count("item", filter=Q(item__work__owner=request.user)),
            work_count=Count("item__work", distinct=True, filter=Q(item__work__owner=request.user)),
        )
        .order_by("room", "bookcase", "shelf")
        .values("id", "room", "bookcase", "shelf", "item_count", "work_count")
    )


@api.post("/locations")
def create_location(request, payload: LocationIn):
    obj, _ = Location.objects.get_or_create(owner=request.user, **payload.model_dump())
    return {"id": obj.id}


@api.post("/works/{work_id}/items")
def add_item(request, work_id: int, payload: ItemIn):
    work = get_object_or_404(Work, owner=request.user, pk=work_id)
    location = (
        get_object_or_404(Location, owner=request.user, pk=payload.location_id)
        if payload.location_id
        else None
    )
    item = Item.objects.create(
        work=work, location=location, **payload.model_dump(exclude={"location_id"})
    )
    return {"id": item.id, "code": str(item.code)}


@api.put("/items/{item_id}")
def move_item(request, item_id: int, payload: ItemIn):
    item = get_object_or_404(Item, work__owner=request.user, pk=item_id)
    if "location_id" in payload.model_fields_set:
        item.location = (
            get_object_or_404(Location, owner=request.user, pk=payload.location_id)
            if payload.location_id
            else None
        )
    for key, value in payload.model_dump(exclude={"location_id"}, exclude_unset=True).items():
        setattr(item, key, value)
    item.save()
    return {"id": item.id}


@api.delete("/items/{item_id}")
def delete_item(request, item_id: int):
    get_object_or_404(Item, work__owner=request.user, pk=item_id).delete()
    return {"ok": True}


@api.post("/works/{work_id}/pdfs")
def upload(request, work_id: int, file: File[UploadedFile]):
    document = save_pdf(get_object_or_404(Work, owner=request.user, pk=work_id), file)
    return {"id": document.id}


@api.get("/lookup")
def search_external(request, scheme: Literal["isbn", "doi"], value: str, enrich: bool = False):
    try:
        value = normalize_identifier(scheme, value)
    except ValueError as exc:
        raise HttpError(422, str(exc))
    existing = (
        work_queryset(request.user)
        .filter(identifiers__scheme=scheme, identifiers__value=value)
        .first()
    )
    if existing and not enrich:
        return {"existing_id": existing.id, "candidates": [], "warnings": []}
    result = lookup(scheme, value)
    # Raw source responses stay server-side until a candidate is selected.
    return {
        **result,
        "candidates": [{"source": c["source"], "data": c["data"]} for c in result["candidates"]],
    }


@api.post("/works/{work_id}/cover")
def upload_cover(request, work_id: int, file: File[UploadedFile]):
    replace_cover(request.user, work_id, file)
    return {"ok": True}


@api.delete("/works/{work_id}/cover")
def delete_cover(request, work_id: int):
    replace_cover(request.user, work_id)
    return {"ok": True}


@api.get("/works/{work_id}/csl")
def export_csl(request, work_id: int):
    return csl(get_object_or_404(work_queryset(request.user), pk=work_id))


@api.get("/tags")
def tags(request):
    return list(
        Tag.objects.filter(owner=request.user, works__isnull=False)
        .distinct()
        .order_by("name")
        .values_list("name", flat=True)
    )


DEFAULT_LANGUAGES = [
    ("Português", "por"),
    ("Inglês", "eng"),
    ("Espanhol", "spa"),
    ("Francês", "fre"),
    ("Alemão", "ger"),
    ("Italiano", "ita"),
    ("Latim", "lat"),
    ("Grego antigo", "grc"),
]


@api.get("/languages")
def languages(request):
    rows = Language.objects.filter(owner=request.user)
    if not rows.exists():
        Language.objects.bulk_create(
            [Language(owner=request.user, name=n, code=c) for n, c in DEFAULT_LANGUAGES],
            ignore_conflicts=True,
        )
    result = [{"value": row.value, "name": row.name} for row in rows.order_by("name")]
    known = {row["value"] for row in result}
    used = (
        Work.objects.filter(owner=request.user)
        .exclude(language="")
        .values_list("language", flat=True)
        .distinct()
    )
    result += [{"value": v, "name": v} for v in sorted(set(used) - known)]
    return result


@api.post("/languages")
def create_language(request, payload: LanguageIn):
    name, code = payload.name.strip(), payload.code.strip()
    if not name:
        raise HttpError(422, "Informe o nome do idioma.")
    existing = Language.objects.filter(owner=request.user, name__iexact=name).first()
    if existing:
        return {"value": existing.value, "name": existing.name}
    if code and Language.objects.filter(owner=request.user, code__iexact=code).exists():
        raise HttpError(409, "Já existe um idioma com esse código.")
    row = Language.objects.create(owner=request.user, name=name, code=code)
    return {"value": row.value, "name": row.name}


def publisher_data(obj):
    return {
        "id": obj.id,
        "name": obj.name,
        "default_city": obj.default_city.name if obj.default_city else "",
        "work_count": obj.work_count
        if hasattr(obj, "work_count")
        else obj.work_set.filter(owner=obj.owner).count(),
    }


@api.get("/publishers")
def publishers(request, q: str = ""):
    rows = (
        Publisher.objects.filter(owner=request.user)
        .select_related("default_city")
        .annotate(work_count=Count("work", filter=Q(work__owner=request.user)))
    )
    if q:
        rows = rows.filter(Q(name__icontains=q) | Q(default_city__name__icontains=q))
    return [publisher_data(row) for row in rows.order_by("name", "id")]


def write_publisher(user, payload, publisher_id=None):
    name = payload.name.strip()
    city = payload.default_city.strip()
    if not name:
        raise HttpError(422, "Informe o nome da editora.")
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        obj = (
            get_object_or_404(Publisher, owner=user, pk=publisher_id)
            if publisher_id
            else Publisher(owner=user)
        )
        if Publisher.objects.filter(owner=user, name__iexact=name).exclude(pk=obj.pk).exists():
            raise HttpError(409, "Já existe uma editora com esse nome.")
        obj.name = name
        obj.default_city = (
            (City.objects.filter(name=city).first() or City.objects.create(name=city))
            if city
            else None
        )
        obj.save()
    return publisher_data(obj)


@api.post("/publishers")
def create_publisher(request, payload: PublisherIn):
    return write_publisher(request.user, payload)


@api.put("/publishers/{publisher_id}")
def update_publisher(request, publisher_id: int, payload: PublisherIn):
    return write_publisher(request.user, payload, publisher_id)


@api.post("/publishers/{target_id}/merge/{source_id}")
def merge_publishers(request, target_id: int, source_id: int):
    if target_id == source_id:
        raise HttpError(422, "Selecione duas editoras diferentes.")
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        rows = Publisher.objects.select_for_update().filter(owner=request.user)
        target = get_object_or_404(rows, pk=target_id)
        source = get_object_or_404(rows, pk=source_id)
        if Work.objects.filter(publisher=source).exclude(owner=request.user).exists():
            raise HttpError(409, "Editora vinculada a registros de outro usuário.")
        works = Work.objects.filter(owner=request.user, publisher=source)
        count = works.count()
        SourceRecord.objects.bulk_create([
            SourceRecord(work=work, source="Fusão de editoras", query=str(source.pk), raw={
                "source_id": source.pk, "source_name": source.name,
                "source_city": source.default_city.name if source.default_city_id else "",
                "target_id": target.pk, "target_name": target.name,
            }) for work in works
        ])
        works.update(publisher=target)
        source.delete()
    return {"moved": count, "publisher": publisher_data(target)}


@api.post("/citation-preview")
def citation_preview(request, payload: WorkIn):
    data = payload.model_dump()
    if payload.publisher_id:
        data["publisher"] = get_object_or_404(
            Publisher, pk=payload.publisher_id, owner=request.user
        ).name
    return csl_data(data)
