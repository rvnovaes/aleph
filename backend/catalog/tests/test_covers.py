import io
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image

from catalog.models import Work
from catalog.tests.test_catalog import create

pytestmark = pytest.mark.django_db


def image_upload(format="JPEG", size=(1200, 1800), mode="RGB"):
    stream = io.BytesIO()
    image = Image.new(mode, size, "red")
    exif = Image.Exif()
    exif[315] = "PRIVATE_METADATA"
    image.save(stream, format=format, exif=exif)
    return SimpleUploadedFile("original." + format.lower(), stream.getvalue())


@pytest.mark.parametrize("format,mode", [("JPEG", "RGB"), ("PNG", "RGBA"), ("JPEG", "CMYK")])
def test_only_optimized_cover_persisted(authenticated, settings, tmp_path, format, mode):
    settings.MEDIA_ROOT = tmp_path
    work_id = create(authenticated).json()["id"]
    response = authenticated.post(
        f"/api/v1/works/{work_id}/cover", {"file": image_upload(format, mode=mode)}
    )
    assert response.status_code == 200, response.content
    work = Work.objects.get(pk=work_id)
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert files == [Path(work.cover.path)]
    assert files[0].suffix == ".webp"
    with Image.open(files[0]) as image:
        assert image.size == (600, 900)
        assert image.format == "WEBP"
        assert not image.getexif()
    response = authenticated.get(f"/api/covers/{work_id}")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert b"PRIVATE_METADATA" not in b"".join(response.streaming_content)
    assert authenticated.get(f"/api/v1/works/{work_id}").json()["cover_url"]


def test_small_cover_enlarged_without_white_frame():
    from catalog.covers import optimize_cover

    stream = io.BytesIO()
    image = Image.new("RGB", (240, 400), "white")
    image.paste(Image.new("RGB", (200, 320), "navy"), (20, 40))
    image.save(stream, format="JPEG", quality=95)
    result = optimize_cover(SimpleUploadedFile("small.jpg", stream.getvalue()))
    with Image.open(io.BytesIO(result.read())) as cover:
        assert cover.size == (562, 900)
        r, g, b = cover.convert("RGB").getpixel((3, 3))
        assert r < 60 and g < 60 and b > 80


def test_replacement_removes_old_file(
    authenticated, settings, tmp_path, django_capture_on_commit_callbacks
):
    settings.MEDIA_ROOT = tmp_path
    work_id = create(authenticated).json()["id"]
    authenticated.post(f"/api/v1/works/{work_id}/cover", {"file": image_upload()})
    old = Work.objects.get(pk=work_id).cover.path
    with django_capture_on_commit_callbacks(execute=True):
        assert (
            authenticated.post(
                f"/api/v1/works/{work_id}/cover", {"file": image_upload("PNG")}
            ).status_code
            == 200
        )
    assert not Path(old).exists()
    current = Work.objects.get(pk=work_id).cover.path
    with django_capture_on_commit_callbacks(execute=True):
        assert authenticated.delete(f"/api/v1/works/{work_id}/cover").status_code == 200
    assert not Path(current).exists()
    assert authenticated.get(f"/api/covers/{work_id}").status_code == 404


def test_invalid_upload_preserves_cover(authenticated, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    work_id = create(authenticated).json()["id"]
    authenticated.post(f"/api/v1/works/{work_id}/cover", {"file": image_upload()})
    old = Work.objects.get(pk=work_id).cover.name
    for upload in [SimpleUploadedFile("fake.png", b"not a picture"), image_upload("GIF")]:
        assert (
            authenticated.post(f"/api/v1/works/{work_id}/cover", {"file": upload}).status_code
            == 422
        )
    assert Work.objects.get(pk=work_id).cover.name == old


def test_cover_privacy(authenticated, user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from django.contrib.auth import get_user_model

    owner = get_user_model().objects.create_user(username="other")
    work = Work.objects.create(owner=owner, title="Private", kind="book")
    assert (
        authenticated.post(f"/api/v1/works/{work.id}/cover", {"file": image_upload()}).status_code
        == 404
    )
    assert authenticated.delete(f"/api/v1/works/{work.id}/cover").status_code == 404
    assert authenticated.get(f"/api/covers/{work.id}").status_code == 404
    assert Client().get(f"/api/covers/{work.id}").status_code == 401


def test_orientation_and_no_crop(authenticated, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    work_id = create(authenticated).json()["id"]
    image = Image.new("RGB", (900, 600), "red")
    exif = Image.Exif()
    exif[274] = 6
    buf = io.BytesIO()
    image.save(buf, format="JPEG", exif=exif)
    authenticated.post(
        f"/api/v1/works/{work_id}/cover",
        {"file": SimpleUploadedFile("rotated.jpg", buf.getvalue())},
    )
    with Image.open(Work.objects.get(pk=work_id).cover.path) as result:
        assert result.size == (600, 900)
        assert result.getpixel((5, 5))[0] > 200
        assert result.getpixel((5, 5))[1] < 40


def test_limits(authenticated, settings, tmp_path):
    from unittest.mock import patch

    settings.MEDIA_ROOT = tmp_path
    work_id = create(authenticated).json()["id"]
    with patch("catalog.covers.MAX_BYTES", 10):
        assert (
            authenticated.post(
                f"/api/v1/works/{work_id}/cover", {"file": image_upload()}
            ).status_code
            == 413
        )
    with patch("catalog.covers.MAX_PIXELS", 10):
        assert (
            authenticated.post(
                f"/api/v1/works/{work_id}/cover", {"file": image_upload()}
            ).status_code
            == 422
        )
    assert not Work.objects.get(pk=work_id).cover
