"""Word n-gram shingling shared by MinHash, SimHash and exact-match scoring."""

from __future__ import annotations


def word_shingles(text: str, size: int) -> set[str]:
    words = text.split()
    if not words:
        return set()
    if len(words) < size:
        return {" ".join(words)}
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}
