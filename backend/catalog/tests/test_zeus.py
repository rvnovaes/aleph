import json
from unittest.mock import patch

import pytest

from catalog.connectors import ZEUS_LIBRARIES, parse_zeus, zeus_candidates

pytestmark = pytest.mark.django_db


def record(year, edition, control):
    return f"""<record xmlns="http://www.loc.gov/MARC21/slim">
  <leader>00696nam a2200241 a 4500</leader>
  <controlfield tag="001">{control}</controlfield>
  <datafield tag="020" ind1=" " ind2=" "><subfield code="a">9788577534098</subfield></datafield>
  <datafield tag="100" ind1="1" ind2=" "><subfield code="a">Freire, Paulo,</subfield></datafield>
  <datafield tag="245" ind1="1" ind2="0"><subfield code="a">Pedagogia da autonomia :</subfield>
    <subfield code="b">saberes necessários à prática educativa /</subfield></datafield>
  <datafield tag="250" ind1=" " ind2=" "><subfield code="a">{edition}</subfield></datafield>
  <datafield tag="260" ind1=" " ind2=" "><subfield code="a">Rio de Janeiro :</subfield>
    <subfield code="b">Paz e Terra,</subfield><subfield code="c">{year}.</subfield></datafield>
</record>"""


def page(idx, *records):
    items = "".join(f'<li><div class="marc">{r}</div></li>' for r in records)
    return f'<div data-z39-target-idx="{idx}"><ul>{items}</ul></div>'


PAGE = (
    "<html><body>"
    + page(9, record(2024, "78. ed.", 1))
    + page(
        0,
        record(2019, "60. ed.", 2),
        record(2024, "78. ed.", 3),
        '<record xmlns="http://www.loc.gov/MARC21/slim">broken</record>',
    )
    + "</body></html>"
)


def test_zeus_page_becomes_candidates_newest_first():
    found = zeus_candidates(PAGE)
    assert [(c["source"], c["data"]["year"]) for c in found] == [
        ("Zeus · Biblioteca Nacional", 2024),
        ("Zeus · Biblioteca Nacional", 2019),
    ]
    data = found[0]["data"]
    assert data["title"] == "Pedagogia da autonomia"
    assert data["subtitle"] == "saberes necessários à prática educativa"
    assert data["publisher"] == "Paz e Terra" and data["city"] == "Rio de Janeiro"
    assert data["authors"][0]["family"] == "Freire"
    assert data["identifiers"] == [{"scheme": "isbn", "value": "9788577534098"}]


def fake_library(isbn, idx):
    if idx == 9:
        return parse_zeus(page(9, record(2024, "78. ed.", 1)))
    if idx == 3:
        raise OSError("timeout")
    return []


def events(response):
    text = b"".join(response.streaming_content).decode()
    return [json.loads(line[6:]) for line in text.split("\n\n") if line.startswith("data: ")]


def test_stream_reports_each_library_and_skips_open_library(authenticated):
    with (
        patch("catalog.connectors.ufsc", return_value=[]),
        patch("catalog.connectors.zeus_library", side_effect=fake_library),
        patch("catalog.connectors.openlibrary") as openlibrary,
    ):
        response = authenticated.get("/api/v1/lookup/stream?scheme=isbn&value=9788577534098")
        assert response["Content-Type"].startswith("text/event-stream")
        got = events(response)
    assert openlibrary.call_count == 0
    assert got[0] == {
        "type": "plan",
        "steps": ["UFSC", *ZEUS_LIBRARIES, "Open Library", "Library of Congress"],
    }
    final = {}
    for e in got:
        if e["type"] == "step":
            final[e["source"]] = (e["status"], e.get("count"))
    assert final["UFSC"] == ("done", 0)
    assert final["UFMG"] == ("done", 1)
    assert final["Senado Federal (Folio)"] == ("error", None)
    assert final["Biblioteca Nacional"] == ("done", 0)
    assert final["Open Library"] == ("skipped", None)
    assert final["Library of Congress"] == ("skipped", None)
    assert any(e["type"] == "candidates" for e in got)
    result = got[-1]
    assert result["type"] == "result"
    assert result["candidates"][0]["source"] == "Zeus · UFMG"
    assert "raw" not in result["candidates"][0]

    # Second time comes from the cache, without asking anyone.
    with patch("catalog.connectors.zeus_library") as again:
        cached = events(authenticated.get("/api/v1/lookup/stream?scheme=isbn&value=9788577534098"))
    assert again.call_count == 0 and cached[-1]["cached"] is True


def test_stream_points_to_existing_work(authenticated):
    from catalog.tests.test_catalog import create

    work = create(authenticated, identifiers=[{"scheme": "isbn", "value": "9788577534098"}])
    got = events(authenticated.get("/api/v1/lookup/stream?scheme=isbn&value=9788577534098"))
    assert got[-1]["existing_id"] == work.json()["id"]


def test_library_of_congress_is_the_last_fallback(authenticated):
    from types import SimpleNamespace

    from catalog.connectors import library_of_congress

    sru = (
        '<zs:searchRetrieveResponse xmlns:zs="http://www.loc.gov/zing/srw/"><zs:records>'
        f"<zs:record><zs:recordData>{record(2009, '3rd ed.', 9)}</zs:recordData></zs:record>"
        "</zs:records></zs:searchRetrieveResponse>"
    )
    reply = SimpleNamespace(text=sru, raise_for_status=lambda: None)
    with patch("catalog.connectors.httpx.get", return_value=reply) as get:
        found = library_of_congress("9780262033848")
    assert get.call_args.kwargs["params"]["query"] == (
        "bath.isbn=9780262033848 or bath.isbn=0262033844"
    )
    assert found[0]["source"] == "Library of Congress"
    assert found[0]["data"]["edition"] == "3rd ed"

    with (
        patch("catalog.connectors.ufsc", return_value=[]),
        patch("catalog.connectors.zeus_library", return_value=[]),
        patch("catalog.connectors.openlibrary", return_value=[]),
        patch("catalog.connectors.library_of_congress", return_value=found) as loc,
    ):
        body = authenticated.get("/api/v1/lookup?scheme=isbn&value=9780262033848").json()
    assert loc.call_count == 1
    assert body["candidates"][0]["source"] == "Library of Congress"
