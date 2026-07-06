import httpx
import pytest

from app.infrastructure.parsers.grobid_adapter import GrobidAdapter, GrobidUnavailableError

_TEI_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title level="a" type="main">Deteccion de Plagio Semantico</title>
      </titleStmt>
      <sourceDesc>
        <biblStruct>
          <analytic>
            <author>
              <persName><forename type="first">Juan</forename><surname>Perez</surname></persName>
            </author>
          </analytic>
          <monogr>
            <imprint>
              <date type="published" when="2024-05-01" />
            </imprint>
          </monogr>
        </biblStruct>
      </sourceDesc>
    </fileDesc>
  </teiHeader>
</TEI>
"""


def test_parses_title_authors_and_year(tmp_path, monkeypatch) -> None:
    adapter = GrobidAdapter(base_url="http://localhost:8070")
    monkeypatch.setattr(adapter, "_call_grobid", lambda pdf_path: _TEI_SAMPLE)

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    metadata = adapter.extract_header(pdf_path)

    assert metadata.title == "Deteccion de Plagio Semantico"
    assert metadata.authors == ("Juan Perez",)
    assert metadata.year == 2024
    assert metadata.institution is None  # not present in this sample -> null-safe


def test_raises_grobid_unavailable_on_connection_error(tmp_path, monkeypatch) -> None:
    adapter = GrobidAdapter(base_url="http://localhost:8070")

    def _raise(pdf_path):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(adapter, "_call_grobid", _raise)
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    with pytest.raises(GrobidUnavailableError):
        adapter.extract_header(pdf_path)


def test_malformed_tei_returns_empty_metadata(tmp_path, monkeypatch) -> None:
    adapter = GrobidAdapter(base_url="http://localhost:8070")
    monkeypatch.setattr(adapter, "_call_grobid", lambda pdf_path: b"not xml at all")

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    metadata = adapter.extract_header(pdf_path)

    assert metadata.title is None
    assert metadata.authors == ()
