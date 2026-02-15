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
    fallback_text: str = ""


class PhraseDetector:
    def __init__(
        self,
        model_path: str,
        phrases: list[str],
        sample_rate: int = 16000,
        model=None,
        recognizer_factory: Optional[Callable] = None,
        debug_fallback_transcript: bool = False,
        verify_with_fallback: bool = False,
        fallback_recognizer_factory: Optional[Callable] = None,
        allow_unk_wrapped_match: bool = False,
    ):
        self.sample_rate = sample_rate
        self.phrases = phrases
        self.model = model or Model(model_path)
        self._recognizer_factory = recognizer_factory or KaldiRecognizer
        self._fallback_recognizer_factory = fallback_recognizer_factory or KaldiRecognizer
        self.debug_fallback_transcript = debug_fallback_transcript
        self.verify_with_fallback = verify_with_fallback
        self.allow_unk_wrapped_match = allow_unk_wrapped_match
        self._create_recognizer()
        self._fallback_recognizer = None
        if self.debug_fallback_transcript or self.verify_with_fallback:
            self._fallback_recognizer = self._fallback_recognizer_factory(self.model, self.sample_rate)

    def _create_recognizer(self) -> None:
        grammar = json.dumps(self.phrases + ["[unk]"])
        self.recognizer = self._recognizer_factory(self.model, self.sample_rate, grammar)

    def detect(self, audio_segment: bytes) -> DetectionResult:
        self.recognizer.AcceptWaveform(audio_segment)
        result = json.loads(self.recognizer.FinalResult())
        text = result.get("text", "").strip().lower()
        normalized_text = " ".join(token for token in text.split() if token != "[unk]").strip()
        fallback_text = ""

        detected = False
        matched_phrase = None
        for phrase in self.phrases:
            normalized_phrase = phrase.lower().strip()
            is_exact_match = normalized_phrase == text
            is_wrapped_match = self.allow_unk_wrapped_match and normalized_phrase == normalized_text
            if is_exact_match or is_wrapped_match:
                detected = True
                matched_phrase = phrase
                break

        confidence = 0.0
        if result.get("result"):
            confidences = [w.get("conf", 0.0) for w in result["result"]]
            confidence = sum(confidences) / len(confidences)

        if self._fallback_recognizer is not None and (text == "[unk]" or (detected and self.verify_with_fallback)):
            self._fallback_recognizer.AcceptWaveform(audio_segment)
            fallback_result = json.loads(self._fallback_recognizer.FinalResult())
            fallback_text = fallback_result.get("text", "").strip().lower()
            self._fallback_recognizer.Reset()

        if detected and self.verify_with_fallback:
            normalized_fallback = " ".join(token for token in fallback_text.split() if token != "[unk]").strip()
            normalized_phrase = matched_phrase.lower().strip() if matched_phrase else ""
            if normalized_phrase not in {"", normalized_fallback}:
                detected = False
                matched_phrase = None

        self.recognizer.Reset()

        return DetectionResult(
            detected=detected,
            phrase=matched_phrase,
            confidence=confidence,
            raw_text=text,
            fallback_text=fallback_text,
        )

    def update_phrases(self, phrases: list[str]) -> None:
        self.phrases = phrases
        self._create_recognizer()

    @property
    def current_phrases(self) -> list[str]:
        return self.phrases
