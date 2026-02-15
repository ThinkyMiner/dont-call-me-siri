from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    chunk_duration_ms: int = 30
    pre_buffer_duration_ms: int = 400
    device_id: Optional[int] = None


@dataclass
class VADConfig:
    aggressiveness: int = 2
    min_speech_duration_ms: int = 200
    silence_duration_ms: int = 500


@dataclass
class DetectionConfig:
    confidence_threshold: float = 0.5
    cooldown_seconds: float = 3.0
    allow_unk_wrapped_match: bool = False


@dataclass
class SiriConfig:
    trigger_method: str = "keyboard"
    keyboard_shortcut: dict = None


@dataclass
class GeneralConfig:
    log_level: str = "INFO"
    show_notifications: bool = True


class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.wake_phrases: list[str] = []
        self.audio = AudioConfig()
        self.vad = VADConfig()
        self.detection = DetectionConfig()
        self.siri = SiriConfig()
        self.general = GeneralConfig()

    def load(self) -> "Config":
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.wake_phrases = raw.get("wake_phrases", [])
        self.audio = AudioConfig(**raw.get("audio", {}))
        self.vad = VADConfig(**raw.get("vad", {}))
        self.detection = DetectionConfig(**raw.get("detection", {}))
        self.siri = SiriConfig(**raw.get("siri", {}))
        self.general = GeneralConfig(**raw.get("general", {}))
        return self

    def save(self) -> None:
        payload = {
            "wake_phrases": self.wake_phrases,
            "audio": self.audio.__dict__,
            "vad": self.vad.__dict__,
            "detection": self.detection.__dict__,
            "siri": self.siri.__dict__,
            "general": self.general.__dict__,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

    def add_phrase(self, phrase: str) -> None:
        if phrase.lower() not in [p.lower() for p in self.wake_phrases]:
            self.wake_phrases.append(phrase)
            self.save()

    def remove_phrase(self, phrase: str) -> bool:
        for existing in list(self.wake_phrases):
            if existing.lower() == phrase.lower():
                self.wake_phrases.remove(existing)
                self.save()
                return True
        return False
