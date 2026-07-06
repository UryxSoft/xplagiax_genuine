"""Best-effort institution extraction when GROBID yields no affiliation.

docs/RESEARCH.md #6/#9: GROBID is weak on affiliation parsing, and Latin
American theses (non-standard cover pages) fall outside GROBID's training
distribution. As a cheap fallback, academic cover pages almost always name
the institution near the top of page one. Full gazetteer/fuzzy-matching
normalization (e.g. against ROR) is deferred to the Metadata sprint; this
is only a last-resort text match, not canonicalization.
"""

from __future__ import annotations

import re

_WS = r"[^\S\n]"  # whitespace but not newline: keeps the match on a single line

_INSTITUTION_PATTERN = re.compile(
    r"^.{0,20}\b("
    rf"universidad(?:{_WS}+\S+){{0,6}}"
    rf"|university(?:{_WS}+of)?(?:{_WS}+\S+){{0,6}}"
    rf"|instituto(?:{_WS}+\S+){{0,6}}"
    rf"|institut(?:o|e)(?:{_WS}+of)?(?:{_WS}+\S+){{0,6}}"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

_FIRST_PAGE_CHAR_BUDGET = 2000


def guess_institution(markdown: str) -> str | None:
    """Returns the first plausible institution mention near the document start."""
    window = markdown[:_FIRST_PAGE_CHAR_BUDGET]
    match = _INSTITUTION_PATTERN.search(window)
    if not match:
        return None
    return " ".join(match.group(0).split()).strip(" .,-")
