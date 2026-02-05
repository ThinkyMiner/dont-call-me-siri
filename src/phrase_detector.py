from dataclasses import dataclass
from typing import Optional, Callable
import json
from vosk import Model, KaldiRecognizer


@dataclass
class DetectionResult:
    detected: bool
    phrase: Optional[str]
    confidence: float
    raw_text: str


class PhraseDetector:
    def __init__(
        self,
        model_path: str,
        phrases: list[str],
        sample_rate: int = 16000,
        model=None,
        recognizer_factory: Optional[Callable] = None,
    ):
        self.sample_rate = sample_rate
        self.phrases = phrases
        self.model = model or Model(model_path)
        self._recognizer_factory = recognizer_factory or KaldiRecognizer
        self._create_recognizer()

    def _create_recognizer(self) -> None:
        grammar = json.dumps(self.phrases + ["[unk]"])
        self.recognizer = self._recognizer_factory(self.model, self.sample_rate, grammar)

    def detect(self, audio_segment: bytes) -> DetectionResult:
        self.recognizer.AcceptWaveform(audio_segment)
        result = json.loads(self.recognizer.FinalResult())
        text = result.get("text", "").strip().lower()

        detected = False
        matched_phrase = None
        for phrase in self.phrases:
            if phrase.lower() == text:
                detected = True
                matched_phrase = phrase
                break

        confidence = 0.0
        if result.get("result"):
            confidences = [w.get("conf", 0.0) for w in result["result"]]
            confidence = sum(confidences) / len(confidences)

        self.recognizer.Reset()

        return DetectionResult(
            detected=detected,
            phrase=matched_phrase,
            confidence=confidence,
            raw_text=text,
        )

    def update_phrases(self, phrases: list[str]) -> None:
        self.phrases = phrases
        self._create_recognizer()

    @property
    def current_phrases(self) -> list[str]:
        return self.phrases
