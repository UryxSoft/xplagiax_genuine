"""Anti-corruption layer around a local GROBID service (RF-08, ADR-012).

GROBID measured F1 ~0.958 on authors and ~0.935 on abstract, but is known
to be weak on affiliation/institution parsing (docs/RESEARCH.md #6). This
adapter therefore treats `institution` as best-effort and lets the caller
apply a fallback (first-page heuristic, gazetteer normalization) when it
comes back None.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from lxml import etree

from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata

logger = logging.getLogger(__name__)

_TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


class GrobidUnavailableError(Exception):
    """Raised when the GROBID service cannot be reached or errors out."""


class GrobidAdapter:
    """Extracts title/authors/affiliation/year via GROBID's header endpoint."""

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def extract_header(self, pdf_path: Path) -> BibliographicMetadata:
        try:
            tei_xml = self._call_grobid(pdf_path)
        except (httpx.HTTPError, OSError) as exc:
            raise GrobidUnavailableError(str(exc)) from exc

        return self._parse_tei(tei_xml)

    def _call_grobid(self, pdf_path: Path) -> bytes:
        url = f"{self._base_url}/api/processHeaderDocument"
        with pdf_path.open("rb") as fh:
            files = {"input": (pdf_path.name, fh, "application/pdf")}
            response = httpx.post(url, files=files, timeout=self._timeout)
        response.raise_for_status()
        return response.content

    def _parse_tei(self, tei_xml: bytes) -> BibliographicMetadata:
        try:
            root = etree.fromstring(tei_xml)
        except etree.XMLSyntaxError:
            logger.warning("GROBID returned unparseable TEI, treating as empty metadata")
            return BibliographicMetadata()

        title = self._first_text(root, ".//tei:titleStmt/tei:title")
        authors = self._extract_authors(root)
        institution = self._first_text(root, ".//tei:affiliation//tei:orgName[@type='institution']")
        year = self._extract_year(root)

        return BibliographicMetadata(
            title=title,
            authors=tuple(authors),
            institution=institution,
            year=year,
        )

    def _first_text(self, root: etree._Element, xpath: str) -> str | None:
        nodes = root.xpath(xpath, namespaces=_TEI_NS)
        if not nodes:
            return None
        text = "".join(nodes[0].itertext()).strip()
        return text or None

    def _extract_authors(self, root: etree._Element) -> list[str]:
        authors: list[str] = []
        for pers_name in root.xpath(".//tei:sourceDesc//tei:author/tei:persName", namespaces=_TEI_NS):
            forename = pers_name.xpath("./tei:forename", namespaces=_TEI_NS)
            surname = pers_name.xpath("./tei:surname", namespaces=_TEI_NS)
            parts = [n.text.strip() for n in (*forename, *surname) if n.text]
            if parts:
                authors.append(" ".join(parts))
        return authors

    def _extract_year(self, root: etree._Element) -> int | None:
        date_nodes = root.xpath(".//tei:sourceDesc//tei:date[@when]", namespaces=_TEI_NS)
        if not date_nodes:
            return None
        when = date_nodes[0].get("when", "")
        year_str = when[:4]
        return int(year_str) if year_str.isdigit() else None
