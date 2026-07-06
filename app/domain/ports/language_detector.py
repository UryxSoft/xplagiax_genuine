"""Port for automatic language detection (RF-06)."""

from __future__ import annotations

from typing import Protocol

from app.domain.value_objects.language import Language


class LanguageDetector(Protocol):
    def detect(self, text: str) -> Language:
        ...
