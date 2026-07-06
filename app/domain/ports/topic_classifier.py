"""Port for automatic academic-topic classification (RF-07)."""

from __future__ import annotations

from typing import Protocol

from app.domain.value_objects.topic import Topic


class TopicClassifier(Protocol):
    def classify(self, text: str) -> Topic:
        ...
