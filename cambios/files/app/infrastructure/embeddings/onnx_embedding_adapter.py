"""ONNX Runtime embedding adapter (NFR-03/04: the RAM/CPU diet lever).

The embedding model -- not TurboVec -- dominates the service's memory
footprint: multilingual-e5-large in float32 costs ~2.2 GB per process,
while a small multilingual model exported to ONNX int8 runs in ~120 MB and
2-4x faster on CPU, with no torch in the image. This adapter implements
the same EmbeddingModel port as E5LargeAdapter (ADR-003: interchangeable
behind the interface), so switching is a config change, not a code change.

Expects a directory produced by an offline export step, e.g.:

    optimum-cli export onnx --model intfloat/multilingual-e5-small \
        --optimize O2 <model_dir>
    # optional int8: optimum-cli onnxruntime quantize --avx2 ...

containing model.onnx (or the quantized variant) and tokenizer.json.
Mean pooling over the attention mask + L2 normalization reproduces the
sentence-transformers behavior for the e5 family; the query/passage
prefixes follow the same convention as E5LargeAdapter.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.value_objects.embedding_vector import EmbeddingVector

DEFAULT_MAX_TOKENS = 512


class OnnxEmbeddingAdapter:
    def __init__(
        self,
        model_dir: Path,
        model_filename: str = "model.onnx",
        batch_size: int = 32,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        import onnxruntime  # deferred: optional dependency (pip install xplagiax[onnx])
        from tokenizers import Tokenizer

        self._model_dir = model_dir
        self._batch_size = batch_size

        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tokenizer.enable_truncation(max_length=max_tokens)
        self._tokenizer.enable_padding()

        session_options = onnxruntime.SessionOptions()
        session_options.graph_optimization_level = (
            onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        self._session = onnxruntime.InferenceSession(
            str(model_dir / model_filename),
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {i.name for i in self._session.get_inputs()}
        self._dimension = self._probe_dimension()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return f"onnx:{self._model_dir.name}"

    def embed_passages(self, texts: list[str]) -> list[EmbeddingVector]:
        return self._encode([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> EmbeddingVector:
        return self._encode([f"query: {text}"])[0]

    def _encode(self, prefixed_texts: list[str]) -> list[EmbeddingVector]:
        if not prefixed_texts:
            return []
        vectors: list[EmbeddingVector] = []
        for start in range(0, len(prefixed_texts), self._batch_size):
            batch = prefixed_texts[start : start + self._batch_size]
            vectors.extend(self._encode_batch(batch))
        return vectors

    def _encode_batch(self, batch: list[str]) -> list[EmbeddingVector]:
        import numpy as np

        encodings = self._tokenizer.encode_batch(batch)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

        feeds: dict[str, object] = {"input_ids": input_ids, "attention_mask": attention_mask}
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.zeros_like(input_ids)

        (token_embeddings,) = self._session.run(["last_hidden_state"], feeds)

        mask = attention_mask[:, :, np.newaxis].astype(token_embeddings.dtype)
        summed = (token_embeddings * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
        pooled = summed / counts

        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        normalized = pooled / np.clip(norms, a_min=1e-12, a_max=None)

        return [EmbeddingVector(values=tuple(float(x) for x in row)) for row in normalized]

    def _probe_dimension(self) -> int:
        return len(self._encode_batch(["probe"])[0].values)
