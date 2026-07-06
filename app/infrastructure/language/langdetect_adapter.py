"""Language detection via `langdetect` (RF-06, ADR-012 fallback option).

`langdetect` ships its n-gram language profiles as package data, so
detection works fully offline with no model download -- unlike fastText,
which needs a separately downloaded .bin model. This satisfies the
air-gapped constraint without extra deployment steps; fastText remains a
documented, swappable alternative behind the same LanguageDetector port.
"""

from __future__ import annotations

from app.domain.value_objects.language import Language

_DEFAULT_LANGUAGE = "en"
_MIN_TEXT_LENGTH = 3


class LangDetectAdapter:
    def detect(self, text: str) -> Language:
        from langdetect import DetectorFactory, detect_langs  # deferred import
        from langdetect.lang_detect_exception import LangDetectException

        DetectorFactory.seed = 0  # deterministic results across runs

        stripped = text.strip()
        if len(stripped) < _MIN_TEXT_LENGTH:
            return Language(code=_DEFAULT_LANGUAGE, confidence=0.0)

        try:
            candidates = detect_langs(stripped)
        except LangDetectException:
            return Language(code=_DEFAULT_LANGUAGE, confidence=0.0)

        best = candidates[0]
        code = best.lang[:2]
        return Language(code=code, confidence=round(best.prob, 4))
