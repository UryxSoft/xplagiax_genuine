"""SimHash fingerprint and Hamming-distance similarity (docs/RESEARCH.md #5).

SimHash is the practically favored fingerprint for whole-document/whole-text
near-duplicate comparison via a single compact fingerprint (64 bits of
SimHash perform comparably to ~24 bytes of MinHash for this use case);
MinHash remains the choice for set-Jaccard-style shingle overlap
(minhash_similarity.py). Both are used here as independent signals in the
composite plagiarism score, not as substitutes for one another.
"""

from __future__ import annotations

import hashlib

from app.infrastructure.dedup.shingles import word_shingles

DEFAULT_SHINGLE_SIZE = 4
BITS = 64
_MASK = (1 << BITS) - 1


def simhash(text: str, shingle_size: int = DEFAULT_SHINGLE_SIZE) -> int:
    shingles = word_shingles(text, shingle_size)
    if not shingles:
        return 0

    weights = [0] * BITS
    for shingle in shingles:
        digest = hashlib.md5(shingle.encode("utf-8")).digest()
        shingle_hash = int.from_bytes(digest, byteorder="big") & _MASK
        for bit in range(BITS):
            weights[bit] += 1 if (shingle_hash >> bit) & 1 else -1

    fingerprint = 0
    for bit in range(BITS):
        if weights[bit] > 0:
            fingerprint |= 1 << bit
    return fingerprint


def simhash_similarity(text_a: str, text_b: str, shingle_size: int = DEFAULT_SHINGLE_SIZE) -> float:
    hash_a = simhash(text_a, shingle_size)
    hash_b = simhash(text_b, shingle_size)
    hamming_distance = bin(hash_a ^ hash_b).count("1")
    return 1.0 - hamming_distance / BITS
