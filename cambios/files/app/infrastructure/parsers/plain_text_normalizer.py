"""Whitespace normalization for inline plain-text ingestion (POST /index).

Deliberately NOT TextNormalizer (text_normalizer.py): that one strips lines
repeated across PDF pages (running headers/footers), a heuristic that is
meaningless -- and destructive -- for single-blob plain text, where a
legitimately repeated line would be deleted as a "header".

Paragraph boundaries (blank lines) are preserved because HybridChunker's
first-level split is the double newline (RF-05); collapsing them here would
silently disable paragraph-respecting segmentation.
"""

from __future__ import annotations

import re

_TRAILING_SPACES = re.compile(r"[ \t]+\n")
_MULTI_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_plain_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_SPACES.sub("\n", text)
    text = _MULTI_BLANK_LINES.sub("\n\n", text)
    return text.strip()
