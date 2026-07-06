"""Port for counting/tokenizing text into discrete token units."""

from __future__ import annotations

from typing import Protocol


class TokenCounter(Protocol):
    """Splits text into token strings and counts them.

    Implementations must be deterministic and side-effect free so the
    chunker can rely on stable offsets across repeated calls.
    """

    def tokenize(self, text: str) -> list[str]:
        ...

    def count(self, text: str) -> int:
        ...
