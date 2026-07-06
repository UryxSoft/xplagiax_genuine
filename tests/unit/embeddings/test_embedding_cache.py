from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.infrastructure.embeddings.embedding_cache import EmbeddingCache


def test_put_then_get_returns_same_vector() -> None:
    cache = EmbeddingCache(max_size=10)
    vector = EmbeddingVector(values=(0.1, 0.2, 0.3))

    cache.put("hola mundo", vector)

    assert cache.get("hola mundo") == vector


def test_miss_returns_none() -> None:
    cache = EmbeddingCache(max_size=10)
    assert cache.get("no existe") is None


def test_query_and_passage_namespaces_do_not_collide() -> None:
    cache = EmbeddingCache(max_size=10)
    passage_vec = EmbeddingVector(values=(1.0, 0.0))
    query_vec = EmbeddingVector(values=(0.0, 1.0))

    cache.put("mismo texto", passage_vec, namespace="passage")
    cache.put("mismo texto", query_vec, namespace="query")

    assert cache.get("mismo texto", namespace="passage") == passage_vec
    assert cache.get("mismo texto", namespace="query") == query_vec


def test_evicts_least_recently_used_when_over_capacity() -> None:
    cache = EmbeddingCache(max_size=2)
    v1, v2, v3 = (EmbeddingVector(values=(float(i),)) for i in range(3))

    cache.put("a", v1)
    cache.put("b", v2)
    cache.put("c", v3)  # evicts "a"

    assert cache.get("a") is None
    assert cache.get("b") == v2
    assert cache.get("c") == v3


def test_get_refreshes_recency() -> None:
    cache = EmbeddingCache(max_size=2)
    v1, v2, v3 = (EmbeddingVector(values=(float(i),)) for i in range(3))

    cache.put("a", v1)
    cache.put("b", v2)
    cache.get("a")  # "a" is now most recently used
    cache.put("c", v3)  # should evict "b", not "a"

    assert cache.get("a") == v1
    assert cache.get("b") is None
    assert cache.get("c") == v3


def test_rejects_non_positive_max_size() -> None:
    import pytest

    with pytest.raises(ValueError):
        EmbeddingCache(max_size=0)
