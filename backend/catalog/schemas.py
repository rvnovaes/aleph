from datetime import date
from decimal import Decimal
from typing import Literal

from ninja import Schema
from pydantic import Field


class AuthorIn(Schema):
    name: str = Field(min_length=1, max_length=300)
    given: str = ""
    family: str = ""
    institutional: bool = False
    role: str = Field(default="author", max_length=30)


class IdentifierIn(Schema):
    scheme: Literal["isbn", "doi"]
    value: str = Field(max_length=300)


class WorkIn(Schema):
    kind: Literal["book", "article-journal"] = "book"
    title: str = Field(min_length=1, max_length=1000)
    subtitle: str = Field(default="", max_length=1000)
    year: int | None = Field(default=None, ge=1, le=9999)
    edition: str = Field(default="", max_length=100)
    language: str = Field(default="", max_length=100)
    pages: str = Field(default="", max_length=100)
    publisher_id: int | None = None
    publisher: str = Field(default="", max_length=300)
    city: str = Field(default="", max_length=300)
    journal: str = Field(default="", max_length=300)
    volume: str = Field(default="", max_length=100)
    issue: str = Field(default="", max_length=100)
    url: str = Field(default="", max_length=2000)
    accessed: date | None = None
    notes: str = Field(default="", max_length=20000)
    abnt_reference: str = Field(default="", max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=200)
    subjects: list[str] = Field(default_factory=list, max_length=200)
    ddc: list[str] = Field(default_factory=list, max_length=50)
    ddc_wording: list[str] = Field(default_factory=list, max_length=200)
    lcc: list[str] = Field(default_factory=list, max_length=50)
    series: list[str] = Field(default_factory=list, max_length=100)
    original_title: str = Field(default="", max_length=1000)
    original_language: str = Field(default="", max_length=300)
    binding: str = Field(default="", max_length=300)
    publication_statement: str = Field(default="", max_length=20000)
    physical_description: str = Field(default="", max_length=20000)
    private_notes: str = Field(default="", max_length=20000)
    pending: bool = False
    authors: list[AuthorIn] = Field(default_factory=list, max_length=100)
    identifiers: list[IdentifierIn] = Field(default_factory=list, max_length=30)
    candidate_key: str = ""
    candidate_index: int = 0


class LocationIn(Schema):
    room: str = Field(min_length=1, max_length=150)
    bookcase: str = Field(default="", max_length=100)
    shelf: str = Field(default="", max_length=100)


class ItemIn(Schema):
    location_id: int | None = None
    notes: str = Field(default="", max_length=20000)
    legacy_barcode: str = Field(default="", max_length=150)
    purchase_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    reported_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    acquired_on: date | None = None
    acquired_from: str = Field(default="", max_length=300)
    condition: str = Field(default="", max_length=150)
    cataloged_on: date | None = None


class Credentials(Schema):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=300)


class LanguageIn(Schema):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(default="", max_length=100)


class PublisherIn(Schema):
    name: str = Field(min_length=1, max_length=300)
    default_city: str = Field(default="", max_length=300)
