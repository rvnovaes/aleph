import json
from decimal import Decimal

import pytest

from catalog.librarything import import_librarything
from catalog.models import (
    Author,
    Contribution,
    Identifier,
    ImportRecord,
    Item,
    Location,
    Publisher,
    Tag,
    Work,
)

pytestmark = pytest.mark.django_db


def sample(tmp_path, extra=None):
    record = {
        "books_id": "42",
        "title": "Livro exemplo",
        "date": "2020",
        "publication": "Zahar",
        "authors": [{"lf": "Silva, Ana", "role": "Author"}],
        "isbn": {"0": "0140328726"},
        "tags": ["História", "Política"],
        "subject": {"0": ["Brasil", "História"]},
        "ddc": {"code": ["900"], "wording": ["History"]},
        "lcc": {"code": "D1"},
        "price": "42,47",
        "price_value": "89",
        "barcode": {"1": "299"},
        "dateacquired": "2025-06-18",
        "originallanguage_codeA": {"0": "por"},
        "privatecomment": "Nota privada",
    }
    records = {"42": record}
    if extra:
        records.update(extra)
    path = tmp_path / "export.json"
    path.write_text(json.dumps(records))
    return path


def test_dry_run_and_idempotency(user, tmp_path):
    path = sample(tmp_path)
    report = import_librarything(user, path, True)
    assert report["created"] == 1
    assert Work.objects.count() == 0
    assert Tag.objects.count() == 0
    first = import_librarything(user, path)
    assert first["created"] == 1
    work = Work.objects.get()
    item = Item.objects.get()
    assert item.reported_value == Decimal("42.47")
    assert item.purchase_price is None
    assert item.estimated_value == Decimal("89.00")
    assert item.location is None and item.legacy_barcode == "299"
    assert work.subjects == ["Brasil — História"]
    assert work.ddc == ["900"]
    assert work.private_notes == "Nota privada"
    assert set(work.tags.values_list("name", flat=True)) == {"História", "Política"}
    assert ImportRecord.objects.get().raw["price"] == "42,47"
    work.title = "Correção manual"
    work.save()
    second = import_librarything(user, path)
    assert second["skipped"] == 1
    assert Work.objects.count() == Item.objects.count() == ImportRecord.objects.count() == 1
    assert Work.objects.get().title == "Correção manual"


def test_matches_existing_preserves_location_and_edits(user, tmp_path):
    pub = Publisher.objects.create(name="Zahar")
    work = Work.objects.create(
        owner=user,
        title="LIVRO EXEMPLO",
        kind="book",
        year=2020,
        publisher=pub,
        notes="Minha correção",
    )
    person = Author.objects.create(name="Silva, Ana")
    Contribution.objects.create(work=work, author=person)
    Identifier.objects.create(work=work, scheme="isbn", value="9780140328721")
    location = Location.objects.create(owner=user, room="Escritório")
    item = Item.objects.create(work=work, location=location)
    report = import_librarything(user, sample(tmp_path))
    assert report["matched_existing"] == 1 and report["created"] == 0
    work.refresh_from_db()
    item.refresh_from_db()
    assert work.notes == "Minha correção" and work.title == "LIVRO EXEMPLO"
    assert item.location_id == location.id and item.legacy_barcode == "299"
    assert Item.objects.count() == 1


def test_duplicate_isbn_and_barcodes_preserved(user, tmp_path):
    path = sample(tmp_path)
    data = json.loads(path.read_text())
    data["43"] = {**data["42"], "books_id": "43", "title": "Outro volume"}
    path.write_text(json.dumps(data))
    report = import_librarything(user, path)
    assert report["created"] == 2
    assert Work.objects.count() == 2
    assert Item.objects.filter(legacy_barcode="299").count() == 2
    assert report["warnings"]


def test_failed_import_is_atomic(user, tmp_path):
    path = sample(tmp_path, {"43": {"books_id": "43", "title": "X" * 2000}})
    with pytest.raises(Exception):
        import_librarything(user, path)
    assert not ImportRecord.objects.exists() and not Work.objects.exists()


def test_tags_and_item_update_preserve_unmentioned_fields(authenticated, user, tmp_path):
    import_librarything(user, sample(tmp_path))
    work = Work.objects.get()
    item = Item.objects.get()
    assert authenticated.get("/api/v1/works?tag=História").json()["count"] == 1
    assert authenticated.get("/api/v1/works?unlocated=true").json()["count"] == 1
    assert authenticated.get("/api/v1/works?q=299").json()["count"] == 1
    response = authenticated.put(
        f"/api/v1/items/{item.id}",
        data=json.dumps({"purchase_price": "50.25"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.purchase_price == Decimal("50.25") and item.reported_value == Decimal("42.47")
    data = authenticated.get(f"/api/v1/works/{work.id}").json()
    data["title"] = "Editado"
    assert (
        authenticated.put(
            f"/api/v1/works/{work.id}", data=json.dumps(data), content_type="application/json"
        ).status_code
        == 200
    )
    work.refresh_from_db()
    assert work.ddc == ["900"] and work.tags.count() == 2


@pytest.mark.parametrize(
    "statement,expected",
    [
        ("São Paulo:Expressão Popular", ("São Paulo", "Expressão Popular")),
        ("Campinas, SP: Unicamp", ("Campinas, SP", "Unicamp")),
        ("Rio de Janeiro: Elsevier, 2023", ("Rio de Janeiro", "Elsevier")),
        ("Paris: L'échappée", ("Paris", "L'échappée")),
        ("Ícone (2017), Edição: Religião", ("", "Ícone")),
        ("Editora, Edition: 1", ("", "Editora")),
    ],
)
def test_publication_parser(statement, expected):
    from catalog.librarything import parse_publication

    assert parse_publication(statement) == expected


def test_repair_publication_preserves_existing_and_is_repeatable(user, tmp_path):
    from catalog.models import City

    path = sample(tmp_path)
    data = json.loads(path.read_text())
    data["42"]["publication"] = "Campinas, SP: Unicamp"
    path.write_text(json.dumps(data))
    import_librarything(user, path)
    work = Work.objects.get()
    assert work.publisher.name == "Unicamp"
    assert work.city.name == "Campinas, SP"
    work.publisher = None
    work.city = None
    work.title = "Título corrigido"
    work.save()
    assert import_librarything(user, path, True, True)["updated"] == 1
    work.refresh_from_db()
    assert work.publisher is None and work.city is None
    assert import_librarything(user, path, repair_publication=True)["updated"] == 1
    assert import_librarything(user, path, repair_publication=True)["updated"] == 0
    work.refresh_from_db()
    assert work.title == "Título corrigido"
    work.city = City.objects.create(name="Cidade corrigida")
    work.save()
    assert import_librarything(user, path, repair_publication=True)["updated"] == 0
    work.refresh_from_db()
    assert work.city.name == "Cidade corrigida"
    assert Work.objects.count() == Item.objects.count() == 1
    assert ImportRecord.objects.get().raw == data["42"]
