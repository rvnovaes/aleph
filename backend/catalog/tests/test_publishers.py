import importlib
import json

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from catalog.models import City, Publisher, Work
from catalog.schemas import WorkIn
from catalog.services import save_work

pytestmark = pytest.mark.django_db


def test_defaults_are_snapshots_and_city_can_be_overridden(user):
    city = City.objects.create(name="São Paulo")
    pub = Publisher.objects.create(owner=user, name="Editora", default_city=city)
    first = save_work(user, WorkIn(title="Primeiro", publisher_id=pub.id))
    assert first.city == city and first.publisher == pub
    pub.default_city = City.objects.create(name="Campinas")
    pub.save()
    first.refresh_from_db()
    assert first.city == city
    second = save_work(user, WorkIn(title="Segundo", publisher_id=pub.id, city="Recife"))
    assert second.city.name == "Recife"
    blank = save_work(user, WorkIn(title="Sem cidade", publisher_id=pub.id, city=""))
    assert blank.city is None
    edited = save_work(user, WorkIn(title="Editado", publisher_id=pub.id), first.id)
    assert edited.city == city
    assert save_work(user, WorkIn(title="Terceiro", publisher="editora")).publisher_id == pub.id


def test_management_permissions_and_duplicate_names(authenticated, user):
    def send(method, path, payload):
        return getattr(authenticated, method)(
            path, data=json.dumps(payload), content_type="application/json"
        )

    created = send(
        "post", "/api/v1/publishers", {"name": "Minha editora", "default_city": "São Paulo"}
    )
    assert created.status_code == 200
    publisher_id = created.json()["id"]
    work = save_work(user, WorkIn(title="Livro", publisher_id=publisher_id))
    assert send("post", "/api/v1/publishers", {"name": " MINHA EDITORA "}).status_code == 409
    changed = send(
        "put",
        f"/api/v1/publishers/{publisher_id}",
        {"name": "Minha editora", "default_city": "Recife"},
    )
    assert changed.status_code == 200
    work.refresh_from_db()
    assert work.city.name == "São Paulo"
    other = get_user_model().objects.create_user(username="another")
    secret = Publisher.objects.create(owner=other, name="Privada")
    assert send("put", f"/api/v1/publishers/{secret.id}", {"name": "Tentativa"}).status_code == 404
    assert (
        send("post", "/api/v1/works", {"title": "Teste", "publisher_id": secret.id}).status_code
        == 404
    )
    rows = authenticated.get("/api/v1/publishers").json()
    assert [p["id"] for p in rows] == [publisher_id]
    assert rows[0]["work_count"] == 1


def test_migration_splits_shared_publishers_without_changing_book_cities(user):
    other = get_user_model().objects.create_user(username="other")
    city1 = City.objects.create(name="São Paulo")
    city2 = City.objects.create(name="Recife")
    pub = Publisher.objects.create(name="Compartilhada")
    first = Work.objects.create(owner=user, kind="book", title="A", publisher=pub, city=city1)
    second = Work.objects.create(owner=other, kind="book", title="B", publisher=pub, city=city2)
    migration = importlib.import_module("catalog.migrations.0006_publisher_ownership_and_defaults")
    migration.populate(apps, None)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.publisher.owner == user and second.publisher.owner == other
    assert first.publisher_id != second.publisher_id
    assert first.city == first.publisher.default_city == city1
    assert second.city == second.publisher.default_city == city2


def test_migration_leaves_ambiguous_default_empty(user):
    pub = Publisher.objects.create(name="Duas cidades")
    for name in ["São Paulo", "Rio de Janeiro"]:
        Work.objects.create(
            owner=user, kind="book", title=name, publisher=pub, city=City.objects.create(name=name)
        )
    importlib.import_module("catalog.migrations.0006_publisher_ownership_and_defaults").populate(
        apps, None
    )
    pub.refresh_from_db()
    assert pub.owner == user and pub.default_city is None
