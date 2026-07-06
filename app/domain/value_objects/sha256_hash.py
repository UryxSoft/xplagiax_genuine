"""Exact-duplicate fingerprint of a document's normalized text (RF-10)."""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class Sha256Hash(BaseModel):
    model_config = {"frozen": True}

    hex: str

    @field_validator("hex")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        value = value.lower()
        if not _HEX_64.match(value):
            raise ValueError("hex must be a 64-character lowercase SHA-256 digest")
        return value

    @classmethod
    def of(cls, text: str) -> "Sha256Hash":
        import hashlib

        return cls(hex=hashlib.sha256(text.encode("utf-8")).hexdigest())
