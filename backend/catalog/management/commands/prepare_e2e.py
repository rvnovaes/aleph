import json
import secrets
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from PIL import Image
from pypdf import PdfWriter


class Command(BaseCommand):
    help = "Create an isolated temporary browser-test account; writes credentials to /tmp only."

    def handle(self, **options):
        password = secrets.token_urlsafe(32)
        user = get_user_model().objects.create_user(
            username="e2e-" + secrets.token_hex(6), password=password
        )
        path = Path("/tmp/aleph-e2e.json")
        path.write_text(json.dumps({"username": user.username, "password": password}))
        path.chmod(0o600)
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=400)
        writer.write("/tmp/aleph-e2e.pdf")
        Image.new("RGB", (1200, 1800), "#284c3e").save("/tmp/aleph-e2e-cover.jpg")
        self.stdout.write("Temporary test account prepared.")
