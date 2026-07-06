from app.domain.value_objects.embedding_vector import EmbeddingVector
from app.infrastructure.embeddings.batch_encoder import BatchEncoder
from app.infrastructure.embeddings.embedding_cache import EmbeddingCache


class _FakeEmbeddingModel:
    """Deterministic fake: embeds text as its length, records batch calls."""

    def __init__(self) -> None:
        self.passage_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    @property
    def dimension(self) -> int:
        return 1

    @property
    def name(self) -> str:
        return "fake-model"

    def embed_passages(self, texts: list[str]) -> list[EmbeddingVector]:
        self.passage_calls.append(list(texts))
        return [EmbeddingVector(values=(float(len(t)),)) for t in texts]

    def embed_query(self, text: str) -> EmbeddingVector:
        self.query_calls.append(text)
        return EmbeddingVector(values=(float(len(text)),))


def test_encode_passages_without_cache_calls_model_once_per_batch() -> None:
    model = _FakeEmbeddingModel()
    encoder = BatchEncoder(model, cache=None, batch_size=2)

    result = encoder.encode_passages(["a", "bb", "ccc", "dddd", "e"])

    assert [v.values[0] for v in result] == [1.0, 2.0, 3.0, 4.0, 1.0]
    assert len(model.passage_calls) == 3  # batches of 2,2,1
    assert model.passage_calls == [["a", "bb"], ["ccc", "dddd"], ["e"]]


def test_encode_passages_skips_cached_entries() -> None:
    model = _FakeEmbeddingModel()
    cache = EmbeddingCache(max_size=10)
    encoder = BatchEncoder(model, cache=cache, batch_size=10)

    encoder.encode_passages(["a", "bb"])
    assert len(model.passage_calls) == 1

    result = encoder.encode_passages(["a", "bb", "ccc"])

    # "a" and "bb" were cached -> model only called for "ccc"
    assert model.passage_calls[-1] == ["ccc"]
    assert [v.values[0] for v in result] == [1.0, 2.0, 3.0]


def test_encode_passages_preserves_original_order_with_partial_cache_hits() -> None:
    model = _FakeEmbeddingModel()
    cache = EmbeddingCache(max_size=10)
    encoder = BatchEncoder(model, cache=cache, batch_size=10)

    encoder.encode_passages(["bb"])  # pre-cache "bb"
    result = encoder.encode_passages(["a", "bb", "ccc"])

    assert [v.values[0] for v in result] == [1.0, 2.0, 3.0]


def test_encode_query_uses_query_method_and_caches_separately_from_passages() -> None:
    model = _FakeEmbeddingModel()
    cache = EmbeddingCache(max_size=10)
    encoder = BatchEncoder(model, cache=cache, batch_size=10)

    encoder.encode_passages(["ab"])  # passage namespace
    encoder.encode_query("ab")  # query namespace, must not reuse passage cache entry

    assert model.query_calls == ["ab"]  # model.embed_query was actually called, no false cache hit


def test_encode_query_hits_cache_on_second_call() -> None:
    model = _FakeEmbeddingModel()
    cache = EmbeddingCache(max_size=10)
    encoder = BatchEncoder(model, cache=cache, batch_size=10)

    encoder.encode_query("hola")
    encoder.encode_query("hola")

    assert model.query_calls == ["hola"]  # only called once


def test_rejects_non_positive_batch_size() -> None:
    import pytest

    with pytest.raises(ValueError):
        BatchEncoder(_FakeEmbeddingModel(), batch_size=0)
