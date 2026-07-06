"""Removes repeated headers/footers and page numbering from extracted Markdown (RF-04)."""

from __future__ import annotations

import re
from collections import Counter

_PAGE_NUMBER_LINE = re.compile(r"^\s*(?:page\s+)?\d{1,4}\s*(?:/\s*\d{1,4})?\s*$", re.IGNORECASE)
_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+\n")

# A line repeated across at least this fraction of pages is treated as a
# running header/footer rather than body content.
_REPETITION_RATIO_THRESHOLD = 0.4


class TextNormalizer:
    """Strips running headers/footers, page numbers and excess whitespace."""

    def normalize(self, markdown: str, page_count: int) -> str:
        lines = markdown.split("\n")
        cleaned = self._strip_repeated_lines(lines, page_count)
        cleaned = [line for line in cleaned if not _PAGE_NUMBER_LINE.match(line)]
        text = "\n".join(cleaned)
        text = _TRAILING_SPACES.sub("\n", text)
        text = _MULTI_BLANK_LINES.sub("\n\n", text)
        return text.strip()

    def _strip_repeated_lines(self, lines: list[str], page_count: int) -> list[str]:
        if page_count <= 1:
            return lines

        candidates = [line.strip() for line in lines if line.strip()]
        counts = Counter(candidates)
        min_repeats = max(2, int(page_count * _REPETITION_RATIO_THRESHOLD))
        repeated = {line for line, count in counts.items() if count >= min_repeats}

        return [line for line in lines if line.strip() not in repeated]
