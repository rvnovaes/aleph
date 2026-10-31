import io
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import httpx
from django.db import transaction
from django.utils import timezone
from pymarc import MARCReader, parse_xml_to_array

from .models import LookupCache
from .services import clean_edition, clean_pages, normalize_identifier


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
            "edition": clean_edition(sub("250", "a")),
            "publisher": sub(publication, "b"),
            "city": sub(publication, "a"),
            "pages": clean_pages(sub("300", "a")),
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


# Zeus (UFSC) queries these libraries over Z39.50 and returns MARCXML in its page.
# The position is Zeus' target index; names are shown in the search progress.
ZEUS_URL = "https://catalogo.bu.ufsc.br/zeus/"
ZEUS_LIBRARIES = [
    "Biblioteca Nacional",
    "Fundacentro",
    "Senado Federal (Aleph)",
    "Senado Federal (Folio)",
    "USP",
    "UERJ",
    "UNICAMP",
    "UNESP",
    "UFG",
    "UFMG",
    "UFPE",
    "UFSC (Zeus)",
    "UFSCar",
    "UNIFESP",
    "UFU",
    "UFPR",
    "UFRGS",
    "UFF",
    "UTFPR",
]
ZEUS_SECTION = re.compile(r'data-z39-target-idx="(\d+)"')
ZEUS_RECORD = re.compile(r"<record xmlns=\"http://www.loc.gov/MARC21/slim\">.*?</record>", re.S)
ZEUS_PARALLEL = 10


def parse_zeus(page):
    """(target index, candidate) pairs found in a Zeus result page."""
    parts = ZEUS_SECTION.split(page)
    found = []
    for idx, chunk in zip(parts[1::2], parts[2::2]):
        idx = int(idx)
        library = ZEUS_LIBRARIES[idx] if idx < len(ZEUS_LIBRARIES) else "Zeus"
        for xml in ZEUS_RECORD.findall(chunk):
            try:
                records = parse_xml_to_array(io.BytesIO(xml.encode("utf-8")))
            except Exception:
                continue
            for record in records:
                if record and record.get("245"):
                    candidate = marc_candidate(record)
                    candidate["source"] = f"Zeus · {library}"
                    found.append((idx, candidate))
    return found


def rank_zeus(found, limit=10):
    """Newest printing first, then Biblioteca Nacional first; one entry per year/edition.

    Publishers often reuse one ISBN across reprints, so several editions may be listed.
    """
    found = sorted(found, key=lambda pair: (-(pair[1]["data"]["year"] or 0), pair[0]))
    result, seen = [], set()
    for _, candidate in found:
        data = candidate["data"]
        key = (data["title"].casefold(), data["year"], data["edition"].casefold())
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result[:limit]


def zeus_candidates(page, limit=10):
    return rank_zeus(parse_zeus(page), limit)


def zeus_library(isbn, idx):
    """Ask Zeus about one library, so progress can be shown library by library."""
    response = httpx.get(
        ZEUS_URL,
        params={
            "searchString": isbn,
            "searchType": "7",
            "operator": "and",
            f"targets[{idx}]": "on",
        },
        timeout=httpx.Timeout(25, connect=10),
        headers={"User-Agent": "Aleph catalogo pessoal (consulta por ISBN)"},
    )
    response.raise_for_status()
    return parse_zeus(response.text)


LOC_SRU = "http://lx2.loc.gov:210/lcdb"  # official SRU service (no HTTPS on this port)


def isbn10(isbn):
    if not isbn.startswith("978") or len(isbn) != 13:
        return None
    stem = isbn[3:12]
    check = (-sum((10 - i) * int(n) for i, n in enumerate(stem))) % 11
    return stem + ("X" if check == 10 else str(check))


def library_of_congress(isbn):
    isbn = normalize_identifier("isbn", isbn)
    query = f"bath.isbn={isbn}"
    if isbn10(isbn):
        query += f" or bath.isbn={isbn10(isbn)}"
    response = httpx.get(
        LOC_SRU,
        params={
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": query,
            "maximumRecords": "5",
            "recordSchema": "marcxml",
        },
        timeout=httpx.Timeout(20, connect=10),
    )
    response.raise_for_status()
    candidates = []
    for xml in ZEUS_RECORD.findall(response.text):
        for record in parse_xml_to_array(io.BytesIO(xml.encode("utf-8"))):
            if record and record.get("245"):
                candidate = marc_candidate(record)
                candidate["source"] = "Library of Congress"
                candidates.append(candidate)
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
                "pages": clean_pages(str(data.get("number_of_pages", ""))),
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
                "pages": clean_pages(data.get("page", ""), "article-journal"),
                "url": data.get("URL", ""),
                "authors": authors,
                "identifiers": [{"scheme": "doi", "value": doi}],
            },
        }
    ]


SOURCE_ERRORS = (httpx.HTTPError, subprocess.SubprocessError, OSError, ValueError, KeyError)


def take_turn(name):
    """Persistent source cooldown, shared by gunicorn workers. False when too soon."""
    with transaction.atomic():
        gate, _ = LookupCache.objects.get_or_create(
            key=f"rate:{name}", defaults={"expires_at": timezone.now()}
        )
        gate = LookupCache.objects.select_for_update().get(pk=gate.pk)
        if gate.expires_at > timezone.now():
            return False
        gate.expires_at = timezone.now() + timedelta(seconds=2)
        gate.save()
    return True


def lookup_steps(scheme):
    if scheme == "isbn":
        return ["UFSC", *ZEUS_LIBRARIES, "Open Library", "Library of Congress"]
    return ["Crossref"]


def lookup_events(scheme, value):
    """Search the sources in order, yielding progress events; the last one is the result.

    Events: {"type": "plan", "steps": [...]}, {"type": "step", "source", "status",
    "count"?}, {"type": "candidates", "items"} and finally {"type": "result", ...}.
    Sources after the first one that finds something are reported as skipped.
    """
    key = f"{scheme}:{value}"
    steps = lookup_steps(scheme)
    yield {"type": "plan", "steps": steps}
    cached = LookupCache.objects.filter(key=key, expires_at__gt=timezone.now()).first()
    if cached:
        for name in steps:
            yield {"type": "step", "source": name, "status": "cached"}
        yield {"type": "result", **cached.result, "key": key, "cached": True}
        return
    candidates, warnings = [], []

    def single(name, connector):
        nonlocal candidates
        if not take_turn(name):
            warnings.append(f"{name}: aguarde alguns segundos antes de consultar novamente.")
            yield {"type": "step", "source": name, "status": "busy"}
            return
        yield {"type": "step", "source": name, "status": "running"}
        try:
            candidates = connector(value)
        except SOURCE_ERRORS:
            warnings.append(f"{name}: serviço indisponível ou resposta não reconhecida.")
            yield {"type": "step", "source": name, "status": "error"}
            return
        yield {"type": "step", "source": name, "status": "done", "count": len(candidates)}
        if candidates:
            yield {"type": "candidates", "items": candidates}

    def zeus_all():
        nonlocal candidates
        if not take_turn("Zeus"):
            warnings.append("Zeus: aguarde alguns segundos antes de consultar novamente.")
            for name in ZEUS_LIBRARIES:
                yield {"type": "step", "source": name, "status": "busy"}
            return
        isbn = normalize_identifier("isbn", value)
        for name in ZEUS_LIBRARIES:
            yield {"type": "step", "source": name, "status": "running"}
        found, failed = [], 0
        with ThreadPoolExecutor(max_workers=ZEUS_PARALLEL) as pool:
            jobs = {pool.submit(zeus_library, isbn, i): i for i in range(len(ZEUS_LIBRARIES))}
            for job in as_completed(jobs):
                name = ZEUS_LIBRARIES[jobs[job]]
                try:
                    pairs = job.result()
                except SOURCE_ERRORS:
                    failed += 1
                    yield {"type": "step", "source": name, "status": "error"}
                    continue
                found += pairs
                yield {"type": "step", "source": name, "status": "done", "count": len(pairs)}
                if pairs:
                    yield {"type": "candidates", "items": rank_zeus(found)}
        candidates = rank_zeus(found)
        if failed and not candidates:
            warnings.append(f"Zeus: {failed} biblioteca(s) não responderam.")

    plan = (
        [
            ("UFSC", lambda: single("UFSC", ufsc)),
            ("Zeus", zeus_all),
            ("Open Library", lambda: single("Open Library", openlibrary)),
            ("Library of Congress", lambda: single("Library of Congress", library_of_congress)),
        ]
        if scheme == "isbn"
        else [("Crossref", lambda: single("Crossref", crossref))]
    )
    for position, (name, run) in enumerate(plan):
        yield from run()
        if candidates:
            for later, _ in plan[position + 1 :]:
                names = ZEUS_LIBRARIES if later == "Zeus" else [later]
                for skipped in names:
                    yield {"type": "step", "source": skipped, "status": "skipped"}
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
    yield {"type": "result", **result, "key": key}


def lookup(scheme, value):
    result = None
    for event in lookup_events(scheme, value):
        result = event
    result.pop("type")
    result.pop("cached", None)
    return result
