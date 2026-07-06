"""Exact n-gram overlap: the "coincidencia exacta" score component (ADR sect 12).

Measures what fraction of the query's word n-grams appear verbatim in the
candidate text -- a cheap, high-precision signal for copy-pasted spans that
survive even when embedding similarity is diluted by paraphrasing elsewhere
in the document.
"""

from __future__ import annotations

from app.infrastructure.dedup.shingles import word_shingles

DEFAULT_NGRAM_SIZE = 8


def exact_ngram_overlap(query_text: str, candidate_text: str, ngram_size: int = DEFAULT_NGRAM_SIZE) -> float:
    query_shingles = word_shingles(query_text, ngram_size)
    if not query_shingles:
        return 0.0
    candidate_shingles = word_shingles(candidate_text, ngram_size)
    overlap = len(query_shingles & candidate_shingles)
    return overlap / len(query_shingles)
