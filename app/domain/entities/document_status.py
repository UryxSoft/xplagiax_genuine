"""Document lifecycle states (docs/DOMAIN_MODEL.md sect 2.4)."""

from __future__ import annotations

from enum import StrEnum


class DocumentStatus(StrEnum):
    RECEIVED = "RECEIVED"
    EXTRACTED = "EXTRACTED"
    CHUNKED = "CHUNKED"
    EMBEDDED = "EMBEDDED"
    INDEXED = "INDEXED"
    DISCARDED = "DISCARDED"
