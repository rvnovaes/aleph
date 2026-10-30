import os
import re
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import httpx
from django.db import transaction
from django.utils import timezone
from pymarc import MARCReader

from .models import LookupCache
from .services import normalize_identifier


def author_name(name):
    name = name.strip(" /;,")
    parts = name.split(",", 1)
    return {
        "name": name,
        "family": parts[0] if len(parts) == 2 else "",
        "given": parts[1].strip() if len(parts) == 2 else "",
        "role": "author",
    }


def marc_candidate(record):
    def sub(tag, code):
        field = record.get(tag)
        return (field.get(code, "") if field else "").strip(" /:;,.")

    publication = "264" if record.get("264") else "260"
    match = re.search(r"\d{4}", sub(publication, "c"))
    identifiers = []
    for field in record.get_fields("020"):
        for value in field.get_subfields("a"):
            value = re.split(r"[ (]", value.strip())[0]
            try:
                identifiers.append({"scheme": "isbn", "value": normalize_identifier("isbn", value)})
            except ValueError:
                pass
    authors = []
    for tag in ["100", "110", "700", "710"]:
        for field in record.get_fields(tag):
            if field.get("a"):
                person = author_name(field["a"])
                person["institutional"] = tag in ["110", "710"]
                relator = " ".join(field.get_subfields("e", "4")).lower()
                person["role"] = (
                    "translator"
                    if "trad" in relator or "trl" in relator
                    else "editor"
                    if any(x in relator for x in ["org", "edt", "editor"])
                    else "author"
                )
                authors.append(person)
    return {
        "source": "UFSC",
        "raw": record.as_dict(),
        "data": {
            "title": sub("245", "a") or "Sem título",
            "subtitle": sub("245", "b"),
            "kind": "book",
            "year": int(match[0]) if match else None,
            "edition": sub("250", "a"),
            "publisher": sub(publication, "b"),
            "city": sub(publication, "a"),
            "pages": sub("300", "a"),
            "authors": authors,
            "identifiers": identifiers,
        },
    }


def ufsc(isbn):
    isbn = normalize_identifier("isbn", isbn)
    query = f"@attr 1=7 {isbn}"
    if isbn.startswith("978"):
        stem = isbn[3:12]
        check = (-sum((10 - i) * int(n) for i, n in enumerate(stem))) % 11
        isbn10 = stem + ("X" if check == 10 else str(check))
        query = f"@or @attr 1=7 {isbn} @attr 1=7 {isbn10}"
    prefix = f"open z3950.ufsc.br:210/Default\nformat usmarc\nfind {query}\n"
    probe = subprocess.run(
        ["yaz-client"],
        input=prefix + "quit\n",
        text=True,
        capture_output=True,
        timeout=12,
        check=True,
    )
    hits = re.search(r"Number of hits: (\d+)", probe.stdout)
    if not hits:
        raise ValueError("UFSC não confirmou o resultado da consulta.")
    count = min(int(hits[1]), 5)
    if not count:
        return []
    with tempfile.TemporaryDirectory(prefix="aleph-marc-") as directory:
        output = Path(directory) / "records.mrc"
        commands = prefix + f"show 1+{count}\nquit\n"
        subprocess.run(
            ["yaz-client", "-m", str(output)],
            input=commands,
            text=True,
            capture_output=True,
            timeout=18,
            check=True,
        )
        if not output.exists() or not output.stat().st_size:
            raise ValueError("UFSC encontrou registros, mas não devolveu MARC.")
        candidates = []
        with output.open("rb") as stream:
            for record in MARCReader(stream, to_unicode=True, force_utf8=True):
                if record:
                    candidates.append(marc_candidate(record))
        if not candidates:
            raise ValueError("MARC retornado pela UFSC não pôde ser lido.")
        return candidates


def json_get(url):
    contact = os.getenv("CONTACT_EMAIL", "")
    response = httpx.get(
        url,
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": f"AlephPersonalCatalog/0.1 ({contact})"},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def openlibrary(isbn):
    # One request returns resolved author names as well as publication details.
    raw = json_get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data")
    data = (raw or {}).get(f"ISBN:{isbn}")
    if not data:
        return []
    match = re.search(r"\d{4}", data.get("publish_date", ""))

    def first_name(field):
        return next((x.get("name", "") for x in data.get(field, [])), "")

    return [
        {
            "source": "Open Library",
            "raw": data,
            "data": {
                "kind": "book",
                "title": data["title"],
                "subtitle": data.get("subtitle", ""),
                "year": int(match[0]) if match else None,
                "publisher": first_name("publishers"),
                "city": first_name("publish_places"),
                "pages": str(data.get("number_of_pages", "")),
                "authors": [author_name(a["name"]) for a in data.get("authors", [])],
                "identifiers": [{"scheme": "isbn", "value": isbn}],
            },
        }
    ]


def crossref(doi):
    raw = json_get("https://api.crossref.org/works/" + quote(doi, safe=""))
    if not raw:
        return []
    data = raw["message"]
    dates = data.get("issued", {}).get("date-parts", [[]])[0]
    authors = [
        {
            "name": " ".join(filter(None, [a.get("given"), a.get("family")]))
            or a.get("name", "Autor"),
            "given": a.get("given", ""),
            "family": a.get("family", ""),
            "role": "author",
        }
        for a in data.get("author", [])
    ]
    return [
        {
            "source": "Crossref",
            "raw": data,
            "data": {
                "kind": "article-journal",
                "title": next(iter(data.get("title", [])), "Sem título"),
                "year": dates[0] if dates else None,
                "journal": next(iter(data.get("container-title", [])), ""),
                "volume": data.get("volume", ""),
                "issue": data.get("issue", ""),
                "pages": data.get("page", ""),
                "url": data.get("URL", ""),
                "authors": authors,
                "identifiers": [{"scheme": "doi", "value": doi}],
            },
        }
    ]


def lookup(scheme, value):
    key = f"{scheme}:{value}"
    cached = LookupCache.objects.filter(key=key, expires_at__gt=timezone.now()).first()
    if cached:
        return {**cached.result, "key": key}
    candidates, warnings = [], []
    for name, connector in (
        [("UFSC", ufsc), ("Open Library", openlibrary)]
        if scheme == "isbn"
        else [("Crossref", crossref)]
    ):
        # Persistent source cooldown, shared by gunicorn workers.
        with transaction.atomic():
            gate, _ = LookupCache.objects.get_or_create(
                key=f"rate:{name}", defaults={"expires_at": timezone.now()}
            )
            gate = LookupCache.objects.select_for_update().get(pk=gate.pk)
            if gate.expires_at > timezone.now():
                warnings.append(f"{name}: aguarde alguns segundos antes de consultar novamente.")
                continue
            gate.expires_at = timezone.now() + timedelta(seconds=2)
            gate.save()
        try:
            candidates = connector(value)
        except (httpx.HTTPError, subprocess.SubprocessError, OSError, ValueError, KeyError):
            warnings.append(f"{name}: serviço indisponível ou resposta não reconhecida.")
        if candidates:
            break
    result = {"candidates": candidates, "warnings": warnings}
    if candidates or not warnings:
        LookupCache.objects.update_or_create(
            key=key,
            defaults={
                "result": result,
                "expires_at": timezone.now() + timedelta(days=7 if candidates else 1),
            },
        )
    return {**result, "key": key}
