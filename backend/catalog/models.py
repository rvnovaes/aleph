import uuid

from django.conf import settings
from django.db import models


class Named(models.Model):
    name = models.CharField(max_length=300)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Author(Named):
    given = models.CharField(max_length=200, blank=True)
    family = models.CharField(max_length=200, blank=True)
    institutional = models.BooleanField(default=False)


class Publisher(Named):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    default_city = models.ForeignKey("City", null=True, blank=True, on_delete=models.SET_NULL)


class City(Named):
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)


class Journal(Named):
    issn = models.CharField(max_length=20, blank=True)


class Language(models.Model):
    """Languages offered in the work form. Works store `code` (or the name when no code)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_owner_language")
        ]

    @property
    def value(self):
        return self.code or self.name

    def __str__(self):
        return self.name


class Tag(Named):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="unique_owner_tag")]


def cover_path(instance, filename):
    return f"covers/{instance.owner_id}/{uuid.uuid4()}.webp"


class Work(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(
        max_length=20, choices=[("book", "Livro"), ("article-journal", "Artigo")]
    )
    title = models.CharField(max_length=1000)
    subtitle = models.CharField(max_length=1000, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    edition = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=100, blank=True)
    pages = models.CharField(max_length=100, blank=True)
    publisher = models.ForeignKey(Publisher, null=True, blank=True, on_delete=models.SET_NULL)
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL)
    journal = models.ForeignKey(Journal, null=True, blank=True, on_delete=models.SET_NULL)
    volume = models.CharField(max_length=100, blank=True)
    issue = models.CharField(max_length=100, blank=True)
    url = models.URLField(max_length=2000, blank=True)
    accessed = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    abnt_reference = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="works")
    subjects = models.JSONField(default=list, blank=True)
    ddc = models.JSONField(default=list, blank=True)
    ddc_wording = models.JSONField(default=list, blank=True)
    lcc = models.JSONField(default=list, blank=True)
    original_title = models.CharField(max_length=1000, blank=True)
    original_language = models.CharField(max_length=300, blank=True)
    series = models.JSONField(default=list, blank=True)
    binding = models.CharField(max_length=300, blank=True)
    publication_statement = models.TextField(blank=True)
    physical_description = models.TextField(blank=True)
    private_notes = models.TextField(blank=True)
    cover = models.FileField(upload_to=cover_path, blank=True)
    pending = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["owner", "title"])]


class Contribution(models.Model):
    work = models.ForeignKey(Work, related_name="contributions", on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.PROTECT)
    position = models.PositiveSmallIntegerField(default=0)
    role = models.CharField(
        max_length=30,
        choices=[("author", "Autor"), ("editor", "Organizador"), ("translator", "Tradutor")],
        default="author",
    )

    class Meta:
        ordering = ["position", "id"]


class Identifier(models.Model):
    work = models.ForeignKey(Work, related_name="identifiers", on_delete=models.CASCADE)
    scheme = models.CharField(max_length=10, choices=[("isbn", "ISBN"), ("doi", "DOI")])
    value = models.CharField(max_length=300, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["work", "scheme", "value"], name="unique_work_identifier"
            )
        ]


class Location(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    room = models.CharField(max_length=150)
    bookcase = models.CharField(max_length=100, blank=True)
    shelf = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "room", "bookcase", "shelf"], name="unique_location"
            )
        ]


class Item(models.Model):
    work = models.ForeignKey(Work, related_name="items", on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True)
    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    notes = models.TextField(blank=True)
    legacy_barcode = models.CharField(max_length=150, blank=True, db_index=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reported_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="BRL")
    acquired_on = models.DateField(null=True, blank=True)
    acquired_from = models.CharField(max_length=300, blank=True)
    condition = models.CharField(max_length=150, blank=True)
    cataloged_on = models.DateField(null=True, blank=True)


class ImportRecord(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=100)
    external_id = models.CharField(max_length=150)
    work = models.ForeignKey(Work, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.SET_NULL, null=True, blank=True)
    raw = models.JSONField()
    checksum = models.CharField(max_length=64)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "source", "external_id"], name="unique_import_record"
            )
        ]


def pdf_path(instance, filename):
    return f"{instance.work.owner_id}/{uuid.uuid4()}.pdf"


class Document(models.Model):
    work = models.ForeignKey(Work, related_name="documents", on_delete=models.CASCADE)
    file = models.FileField(upload_to=pdf_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["work", "sha256"], name="unique_work_pdf")]


class SourceRecord(models.Model):
    work = models.ForeignKey(Work, related_name="sources", on_delete=models.CASCADE)
    source = models.CharField(max_length=100)
    query = models.CharField(max_length=300)
    raw = models.JSONField(default=dict)
    retrieved_at = models.DateTimeField(auto_now_add=True)


class LookupCache(models.Model):
    key = models.CharField(max_length=350, unique=True)
    result = models.JSONField(default=dict)
    expires_at = models.DateTimeField()


class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField()
