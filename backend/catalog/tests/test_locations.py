import pytest
from django.contrib.auth import get_user_model

from catalog.models import Item, Location, Work

pytestmark = pytest.mark.django_db


def test_location_counts_and_hierarchy(authenticated, user):
    a = Location.objects.create(owner=user, room="Sala", bookcase="A", shelf="1")
    b = Location.objects.create(owner=user, room="Sala", bookcase="A", shelf="2")
    c = Location.objects.create(owner=user, room="Quarto", bookcase="B", shelf="1")
    empty = Location.objects.create(owner=user, room="Sala", bookcase="Vazia")
    book = Work.objects.create(owner=user, title="Livro compartilhado", kind="book")
    second = Work.objects.create(owner=user, title="Segundo", kind="book")
    Item.objects.create(work=book, location=a)
    Item.objects.create(work=book, location=a)
    Item.objects.create(work=book, location=b)
    Item.objects.create(work=book, location=c)
    Item.objects.create(work=second, location=b)
    data = {v["id"]: v for v in authenticated.get("/api/v1/locations").json()}
    assert data[a.id]["item_count"] == 2
    assert data[a.id]["work_count"] == 1
    assert data[empty.id]["item_count"] == 0
    assert authenticated.get("/api/v1/works?room=Sala&bookcase=A").json()["count"] == 2
    assert authenticated.get(f"/api/v1/works?location={a.id}").json()["count"] == 1
    # Both conditions must refer to the same physical location, not two different copies.
    assert authenticated.get("/api/v1/works?room=Sala&bookcase=B").json()["count"] == 0
    assert authenticated.get("/api/v1/works?room=Sala&bookcase=").json()["count"] == 0
    assert authenticated.get("/api/v1/works?room=Sala&q=Segundo").json()["count"] == 1
    other = get_user_model().objects.create_user(username="location-other")
    secret = Location.objects.create(owner=other, room="Sala", bookcase="A")
    private = Work.objects.create(owner=other, title="Segredo", kind="book")
    Item.objects.create(work=private, location=secret)
    assert authenticated.get(f"/api/v1/works?location={secret.id}").json()["count"] == 0
    assert len(authenticated.get("/api/v1/locations").json()) == 4
    Item.objects.filter(work=second).update(location=c)
    assert authenticated.get("/api/v1/works?room=Sala&bookcase=A").json()["count"] == 1
