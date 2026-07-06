"""Regex-based approximate token counter.

Air-gapped constraint: no network calls to fetch a real tokenizer's
vocabulary/encoding files at runtime. This word/punctuation-level
approximation is deterministic and offline. The `TokenCounter` port lets
the Embeddings sprint swap in the real e5/BGE tokenizer (HuggingFace
`tokenizers`, loaded from a local model bundle) without touching the
chunker.
"""

from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class WordTokenCounter:
    """Approximates tokenization by splitting on word and punctuation boundaries."""

    def tokenize(self, text: str) -> list[str]:
        return _TOKEN_PATTERN.findall(text)

    def count(self, text: str) -> int:
        return len(self.tokenize(text))
