"""Hybrid segmentation strategy (RF-05, ADR §11):
double newline -> sentence-final period -> hard token-length cutoff,
target 300-500 tokens per segment with 20% overlap, preserving context.

docs/RESEARCH.md #4: evidence does not show semantic/adaptive chunking
reliably beating paragraph-respecting splits, so this hybrid approach
(the "zero-cost" middle ground) is the only chunking strategy implemented;
adaptive chunking stays a documented future option pending an internal
benchmark.
"""

from __future__ import annotations

import re

from app.domain.ports.token_counter import TokenCounter
from app.domain.value_objects.text_segment import TextSegment
from app.domain.value_objects.token_span import TokenSpan

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PUNCT_ONLY = re.compile(r"^[^\w\s]$", re.UNICODE)


class HybridChunker:
    """Splits normalized Markdown into overlapping, context-preserving segments."""

    def __init__(
        self,
        token_counter: TokenCounter,
        min_tokens: int = 300,
        max_tokens: int = 500,
        overlap_ratio: float = 0.2,
    ) -> None:
        if min_tokens <= 0 or max_tokens <= min_tokens:
            raise ValueError("require 0 < min_tokens < max_tokens")
        if not 0 <= overlap_ratio < 1:
            raise ValueError("overlap_ratio must be in [0, 1)")

        self._counter = token_counter
        self._min_tokens = min_tokens
        self._max_tokens = max_tokens
        self._overlap_ratio = overlap_ratio

    def chunk(self, text: str) -> list[TextSegment]:
        units = self._build_units(text)
        if not units:
            return []
        return self._assemble_segments(units)

    # -- unit construction: paragraph -> sentence -> hard token cutoff ------

    def _build_units(self, text: str) -> list[str]:
        units: list[str] = []
        for paragraph in _PARAGRAPH_SPLIT.split(text.strip()):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            units.extend(self._split_paragraph(paragraph))
        return units

    def _split_paragraph(self, paragraph: str) -> list[str]:
        if self._counter.count(paragraph) <= self._max_tokens:
            return [paragraph]

        units: list[str] = []
        for sentence in _SENTENCE_SPLIT.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if self._counter.count(sentence) <= self._max_tokens:
                units.append(sentence)
            else:
                units.extend(self._hard_split(sentence))
        return units

    def _hard_split(self, text: str) -> list[str]:
        """Last resort: a single sentence exceeds max_tokens with no further
        natural boundary. Slices at the token level and re-joins tokens.
        """
        tokens = self._counter.tokenize(text)
        pieces = []
        for start in range(0, len(tokens), self._max_tokens):
            piece_tokens = tokens[start : start + self._max_tokens]
            pieces.append(self._detokenize(piece_tokens))
        return pieces

    @staticmethod
    def _detokenize(tokens: list[str]) -> str:
        parts: list[str] = []
        for token in tokens:
            if parts and _PUNCT_ONLY.match(token):
                parts[-1] = parts[-1] + token
            else:
                parts.append(token)
        return " ".join(parts)

    # -- assembly: greedy pack units into [min_tokens, max_tokens] windows --

    def _assemble_segments(self, units: list[str]) -> list[TextSegment]:
        segments: list[TextSegment] = []
        order = 0
        global_cursor = 0
        overlap_units: list[str] = []
        overlap_tokens = 0

        index = 0
        total = len(units)
        while index < total:
            current_units = list(overlap_units)
            current_tokens = overlap_tokens
            start_index = global_cursor - overlap_tokens

            first_addition = True
            while index < total:
                unit = units[index]
                unit_tokens = self._counter.count(unit)
                would_overflow = current_tokens + unit_tokens > self._max_tokens
                already_enough = current_tokens >= self._min_tokens
                if not first_addition and would_overflow and already_enough:
                    break

                current_units.append(unit)
                current_tokens += unit_tokens
                global_cursor += unit_tokens
                index += 1
                first_addition = False

                if current_tokens >= self._max_tokens:
                    break

            end_index = start_index + current_tokens
            segments.append(
                TextSegment(
                    text=" ".join(current_units),
                    span=TokenSpan(start=start_index, end=end_index),
                    order=order,
                )
            )
            order += 1

            overlap_units, overlap_tokens = self._trailing_overlap(current_units, current_tokens)

        return segments

    def _trailing_overlap(self, chunk_units: list[str], chunk_tokens: int) -> tuple[list[str], int]:
        target = round(chunk_tokens * self._overlap_ratio)
        if target <= 0:
            return [], 0

        trailing: list[str] = []
        trailing_tokens = 0
        for unit in reversed(chunk_units):
            if trailing_tokens >= target:
                break
            trailing.insert(0, unit)
            trailing_tokens += self._counter.count(unit)
        return trailing, trailing_tokens
