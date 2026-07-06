import sys
import types

import numpy as np
import pytest


class _FakeSentenceTransformer:
    """Stands in for sentence_transformers.SentenceTransformer without
    downloading any model weights."""

    last_instance: "_FakeSentenceTransformer | None" = None

    def __init__(self, model_name: str, device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self.encode_calls: list[dict] = []
        _FakeSentenceTransformer.last_instance = self

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, texts, batch_size, normalize_embeddings, convert_to_numpy):
        self.encode_calls.append(
            {
                "texts": list(texts),
                "batch_size": batch_size,
                "normalize_embeddings": normalize_embeddings,
            }
        )
        # deterministic fake vector: length-based, dimension 4
        return np.array([[float(len(t))] * 4 for t in texts])


@pytest.fixture(autouse=True)
def _stub_sentence_transformers(monkeypatch):
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = _FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    yield
    _FakeSentenceTransformer.last_instance = None


def test_embed_passages_applies_passage_prefix() -> None:
    from app.infrastructure.embeddings.e5_large_adapter import E5LargeAdapter

    adapter = E5LargeAdapter()
    adapter.embed_passages(["hola", "mundo"])

    calls = _FakeSentenceTransformer.last_instance.encode_calls
    assert calls[0]["texts"] == ["passage: hola", "passage: mundo"]
    assert calls[0]["normalize_embeddings"] is True


def test_embed_query_applies_query_prefix() -> None:
    from app.infrastructure.embeddings.e5_large_adapter import E5LargeAdapter

    adapter = E5LargeAdapter()
    vector = adapter.embed_query("busqueda de plagio")

    calls = _FakeSentenceTransformer.last_instance.encode_calls
    assert calls[0]["texts"] == ["query: busqueda de plagio"]
    assert vector.dimension == 4


def test_dimension_and_name_exposed() -> None:
    from app.infrastructure.embeddings.e5_large_adapter import E5LargeAdapter

    adapter = E5LargeAdapter(model_name="intfloat/multilingual-e5-large")
    assert adapter.dimension == 4
    assert adapter.name == "intfloat/multilingual-e5-large"


def test_embed_passages_empty_list_does_not_call_model() -> None:
    from app.infrastructure.embeddings.e5_large_adapter import E5LargeAdapter

    adapter = E5LargeAdapter()
    result = adapter.embed_passages([])

    assert result == []
    assert _FakeSentenceTransformer.last_instance.encode_calls == []
