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

    def detect(self, audio_segment: bytes) -> DetectionResult:
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

        # Try exact match first, then contains match
        for phrase in self.phrases:
            norm_phrase = self._normalize(phrase)
            if norm_phrase == normalized:
                return DetectionResult(
                    detected=True, phrase=phrase, confidence=1.0, raw_text=raw_text
                )

        for phrase in self.phrases:
            norm_phrase = self._normalize(phrase)
            if norm_phrase in normalized:
                return DetectionResult(
                    detected=True, phrase=phrase, confidence=1.0, raw_text=raw_text
                )

        return DetectionResult(
            detected=False, phrase=None, confidence=0.0, raw_text=raw_text
        )

    def update_phrases(self, phrases: list[str]) -> None:
        self.phrases = phrases

    @property
    def current_phrases(self) -> list[str]:
        return self.phrases
