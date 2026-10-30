import io
import warnings

from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Work

COVER_SIZE = (600, 900)
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000


def optimize_cover(upload):
    if upload.size > MAX_BYTES:
        raise HttpError(413, "A capa deve ter no máximo 10 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                if source.format not in {"JPEG", "PNG"}:
                    raise HttpError(422, "Envie uma imagem JPEG ou PNG.")
                if source.width * source.height > MAX_PIXELS:
                    raise HttpError(422, "A imagem deve ter no máximo 20 megapixels.")
                if getattr(source, "n_frames", 1) != 1:
                    raise HttpError(422, "Envie uma capa estática, sem animação.")
                # Orient first, then shrink. Metadata is never copied to the output canvas.
                image = ImageOps.exif_transpose(source)
                image.thumbnail(COVER_SIZE, Image.Resampling.LANCZOS, reducing_gap=3.0)
                image = image.convert("RGBA")
                canvas = Image.new("RGB", COVER_SIZE, "white")
                canvas.paste(image, ((600 - image.width) // 2, (900 - image.height) // 2), image)
                output = io.BytesIO()
                canvas.save(output, format="WEBP", quality=82, method=4)
                return ContentFile(output.getvalue())
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise HttpError(422, "Imagem inválida, corrompida ou grande demais.") from exc


def replace_cover(user, work_id, upload=None):
    # Check ownership before spending resources on image decoding.
    get_object_or_404(Work, pk=work_id, owner=user)
    optimized = optimize_cover(upload) if upload is not None else None
    new_name = None
    storage = Work._meta.get_field("cover").storage
    try:
        with transaction.atomic():
            work = get_object_or_404(Work.objects.select_for_update(), pk=work_id, owner=user)
            old_name = work.cover.name
            if optimized is not None:
                work.cover.save("cover.webp", optimized, save=False)
                new_name = work.cover.name
            else:
                work.cover = ""
            work.save(update_fields=["cover", "updated_at"])
            if old_name:
                transaction.on_commit(lambda: storage.delete(old_name))
    except Exception:
        if new_name:
            storage.delete(new_name)
        raise
