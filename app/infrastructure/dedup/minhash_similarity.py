"""MinHash-estimated Jaccard similarity (docs/RESEARCH.md #5, #8).

MinHash is the practically and theoretically favored estimator for set
(shingle) Jaccard similarity at scale (In Defense of MinHash Over SimHash,
arXiv:1407.4416); num_perm=128 and 5-word shingles match the reference
values docs/RESEARCH.md settled on. `datasketch` also backs the
LSH-based bulk near-duplicate detection at indexing time (future
dedup-at-ingest sprint); here it is reused directly for two-text
similarity during reranking.
"""

from __future__ import annotations

from app.infrastructure.dedup.shingles import word_shingles

DEFAULT_NUM_PERM = 128
DEFAULT_SHINGLE_SIZE = 5


def minhash_similarity(
    text_a: str,
    text_b: str,
    num_perm: int = DEFAULT_NUM_PERM,
    shingle_size: int = DEFAULT_SHINGLE_SIZE,
) -> float:
    shingles_a = word_shingles(text_a, shingle_size)
    shingles_b = word_shingles(text_b, shingle_size)
    if not shingles_a or not shingles_b:
        return 0.0

    from datasketch import MinHash  # deferred import

    minhash_a = MinHash(num_perm=num_perm)
    for shingle in shingles_a:
        minhash_a.update(shingle.encode("utf-8"))

    minhash_b = MinHash(num_perm=num_perm)
    for shingle in shingles_b:
        minhash_b.update(shingle.encode("utf-8"))

    return float(minhash_a.jaccard(minhash_b))
