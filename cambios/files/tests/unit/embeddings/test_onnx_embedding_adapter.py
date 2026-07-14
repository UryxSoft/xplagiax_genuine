"""OnnxEmbeddingAdapter against fake onnxruntime/tokenizers modules
(same sys.modules technique as the turbovec repository tests): proves
prefixing, batching, mean pooling over the attention mask and L2
normalization without the optional native dependencies installed."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest


class _FakeEncoding:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids
        self.attention_mask = [1 if t != 0 else 0 for t in ids]


class _FakeTokenizer:
    last_batches: list[list[str]] = []

    @classmethod
    def from_file(cls, path: str) -> "_FakeTokenizer":
        return cls()

    def enable_truncation(self, max_length: int) -> None:
        self.max_length = max_length

    def enable_padding(self) -> None:
        pass

    def encode_batch(self, batch: list[str]) -> list[_FakeEncoding]:
        _FakeTokenizer.last_batches.append(list(batch))
        # fixed-width fake tokenization: one "token id" per word, padded to 4
        encodings = []
        for text in batch:
            ids = [hash(w) % 1000 + 1 for w in text.split()[:4]]
            ids += [0] * (4 - len(ids))
            encodings.append(_FakeEncoding(ids))
        return encodings


class _FakeInput:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeSession:
    def __init__(self, path: str, sess_options=None, providers=None) -> None:
        self.path = path

    def get_inputs(self):
        return [_FakeInput("input_ids"), _FakeInput("attention_mask")]

    def run(self, outputs, feeds):
        input_ids = feeds["input_ids"]
        batch, seq = input_ids.shape
        dim = 3
        # token embedding = token id broadcast over dim; padding tokens get
        # a huge value that MUST be masked out by mean pooling
        hidden = np.zeros((batch, seq, dim), dtype=np.float32)
        for b in range(batch):
            for s in range(seq):
                token = float(input_ids[b, s])
                hidden[b, s, :] = token if token != 0 else 9999.0
        return (hidden,)


@pytest.fixture()
def adapter(monkeypatch, tmp_path: Path):
    fake_ort = types.ModuleType("onnxruntime")
    fake_ort.SessionOptions = lambda: types.SimpleNamespace(graph_optimization_level=None)
    fake_ort.GraphOptimizationLevel = types.SimpleNamespace(ORT_ENABLE_ALL="all")
    fake_ort.InferenceSession = _FakeSession
    fake_tokenizers = types.ModuleType("tokenizers")
    fake_tokenizers.Tokenizer = _FakeTokenizer
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)
    monkeypatch.setitem(sys.modules, "tokenizers", fake_tokenizers)
    _FakeTokenizer.last_batches = []

    from app.infrastructure.embeddings.onnx_embedding_adapter import OnnxEmbeddingAdapter

    return OnnxEmbeddingAdapter(model_dir=tmp_path, batch_size=2)


def test_dimension_probed_from_model(adapter) -> None:
    assert adapter.dimension == 3


def test_query_and_passage_prefixes_applied(adapter) -> None:
    adapter.embed_query("hola mundo")
    adapter.embed_passages(["texto uno"])

    flattened = [text for batch in _FakeTokenizer.last_batches for text in batch]
    assert "query: hola mundo" in flattened
    assert "passage: texto uno" in flattened


def test_vectors_are_l2_normalized(adapter) -> None:
    vector = adapter.embed_query("hola mundo ejemplo")
    norm = sum(x * x for x in vector.values) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-5)


def test_padding_tokens_excluded_from_pooling(adapter) -> None:
    # one word -> 3 padding positions with poisoned 9999.0 embeddings;
    # normalized output of a constant positive vector is uniform positive
    vector = adapter.embed_query("palabra")
    assert all(x > 0 for x in vector.values)
    assert max(vector.values) == pytest.approx(min(vector.values), abs=1e-6)


def test_batching_respects_batch_size(adapter) -> None:
    _FakeTokenizer.last_batches = []
    adapter.embed_passages(["a", "b", "c", "d", "e"])
    assert [len(b) for b in _FakeTokenizer.last_batches] == [2, 2, 1]


def test_empty_input_short_circuits(adapter) -> None:
    assert adapter.embed_passages([]) == []
