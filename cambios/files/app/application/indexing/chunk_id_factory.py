"""Deterministic ChunkId derivation (shared uint64 key, docs/DOMAIN_MODEL.md sect 7).

ChunkId = blake2b(document_id ++ order) truncated to 63 bits. Deterministic
ids make indexing idempotent (a retried document maps onto the same TurboVec
ids instead of duplicating vectors) and need no coordination service or DB
sequence -- essential once multiple indexer processes exist (Fase 3).

63 bits, not 64: the metadata store keeps ChunkId in a signed BigInteger
(orm.py), so the sign bit must stay clear. Collision odds at the 10M-chunk
scale the ADR targets are ~5e-6 (birthday bound over 2^63); the chunks
primary key would surface a collision as an integrity error rather than
silently corrupting the index.
"""

from __future__ import annotations

import hashlib

_MASK_63_BITS = (1 << 63) - 1


def chunk_id_for(document_id: str, order: int) -> int:
    if order < 0:
        raise ValueError("order must be >= 0")
    digest = hashlib.blake2b(
        f"{document_id}\x00{order}".encode("utf-8"), digest_size=8
    ).digest()
    return int.from_bytes(digest, byteorder="big") & _MASK_63_BITS
