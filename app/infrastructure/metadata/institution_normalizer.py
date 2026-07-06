"""Canonicalizes free-text institution names (docs/RESEARCH.md #6/#9).

GROBID and the first-page regex fallback (Parser sprint) both produce raw,
inconsistently formatted institution strings ("Univ. Nacional", "UNIVERSIDAD
NACIONAL DE INGENIERIA", "Universidad Nacional de Ingenieria"). Without
canonicalization, `entity_match` in the plagiarism score and university
filters degrade to noise.

The embedded gazetteer below is a small starter set for demonstration and
testing. A production deployment should load a real registry (e.g. ROR --
Research Organization Registry, openly licensed and usable offline) instead
of this hardcoded list.
"""

from __future__ import annotations

import difflib
import re

_STARTER_GAZETTEER: tuple[str, ...] = (
    "Universidad Nacional de Ingenieria",
    "Universidad Nacional Mayor de San Marcos",
    "Pontificia Universidad Catolica del Peru",
    "Universidad Nacional Autonoma de Mexico",
    "Universidad de Buenos Aires",
    "Universidad Complutense de Madrid",
    "Universidad de Chile",
    "University of Cambridge",
    "University of Oxford",
    "Massachusetts Institute of Technology",
    "Stanford University",
    "Universidade de Sao Paulo",
    "Universidade Federal do Rio de Janeiro",
)

_FUZZY_MATCH_CUTOFF = 0.82
_ABBREVIATION_PATTERN = re.compile(r"\bUniv\.?\b", re.IGNORECASE)


class InstitutionNormalizer:
    """Fuzzy-matches a raw institution string against a canonical gazetteer."""

    def __init__(self, gazetteer: tuple[str, ...] = _STARTER_GAZETTEER) -> None:
        self._gazetteer = gazetteer

    def normalize(self, raw_name: str | None) -> str | None:
        if raw_name is None:
            return None

        cleaned = self._clean(raw_name)
        if not cleaned:
            return None

        match = difflib.get_close_matches(
            cleaned, self._gazetteer, n=1, cutoff=_FUZZY_MATCH_CUTOFF
        )
        return match[0] if match else cleaned

    @staticmethod
    def _clean(raw_name: str) -> str:
        expanded = _ABBREVIATION_PATTERN.sub("Universidad", raw_name)
        collapsed = " ".join(expanded.split())
        return collapsed.strip(" .,-").title() if collapsed.isupper() else collapsed.strip(" .,-")
