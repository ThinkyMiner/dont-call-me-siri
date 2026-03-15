import re
import string
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class DetectionResult:
    detected: bool
    phrase: Optional[str]
    confidence: float
    raw_text: str


class PhraseDetector:
    def __init__(
        self,
        phrases: list[str],
        model=None,
        tokenizer=None,
        model_name: str = "moonshine/tiny",
        sample_rate: int = 16000,
    ):
        self.phrases = phrases
        self.sample_rate = sample_rate
        self._update_normalized_phrases()

        if model is not None:
            self._model = model
        else:
            from moonshine_onnx import MoonshineOnnxModel
            self._model = MoonshineOnnxModel(model_name=model_name)

        if tokenizer is not None:
            self._tokenizer = tokenizer
        else:
            from moonshine_onnx import load_tokenizer
            self._tokenizer = load_tokenizer()

    def _normalize(self, text: str) -> str:
        """Lowercase and strip punctuation."""
        text = text.lower().strip()
        text = text.translate(str.maketrans("", "", string.punctuation))
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _update_normalized_phrases(self) -> None:
        self._norm_phrases = [(p, self._normalize(p)) for p in self.phrases]

    def detect(self, audio_segment: bytes) -> DetectionResult:
        if len(audio_segment) < 2:
            return DetectionResult(detected=False, phrase=None, confidence=0.0, raw_text="")

        audio = np.frombuffer(audio_segment, dtype=np.int16).astype(np.float32) / 32768.0
        audio = audio[np.newaxis, :]  # shape [1, num_samples]

        tokens = self._model.generate(audio)
        text_list = self._tokenizer.decode_batch(tokens)
        raw_text = text_list[0] if text_list else ""
        normalized = self._normalize(raw_text)

        if not normalized:
            return DetectionResult(
                detected=False, phrase=None, confidence=0.0, raw_text=raw_text
            )

        # Try exact match first, then word-boundary contains match
        for phrase, norm_phrase in self._norm_phrases:
            if norm_phrase == normalized:
                return DetectionResult(
                    detected=True, phrase=phrase, confidence=1.0, raw_text=raw_text
                )

        for phrase, norm_phrase in self._norm_phrases:
            pattern = r"\b" + re.escape(norm_phrase) + r"\b"
            if re.search(pattern, normalized):
                return DetectionResult(
                    detected=True, phrase=phrase, confidence=1.0, raw_text=raw_text
                )

        return DetectionResult(
            detected=False, phrase=None, confidence=0.0, raw_text=raw_text
        )

    def update_phrases(self, phrases: list[str]) -> None:
        self.phrases = phrases
        self._update_normalized_phrases()

    @property
    def current_phrases(self) -> list[str]:
        return self.phrases
