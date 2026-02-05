from enum import Enum
from typing import Optional
import webrtcvad


class VADState(Enum):
    IDLE = "idle"
    SPEAKING = "speaking"
    TRAILING = "trailing"


class VADResult:
    def __init__(self, is_speech: bool, state: VADState, audio_segment: Optional[bytes] = None):
        self.is_speech = is_speech
        self.state = state
        self.audio_segment = audio_segment


class VoiceActivityDetector:
    def __init__(
        self,
        sample_rate: int = 16000,
        aggressiveness: int = 2,
        min_speech_duration_ms: int = 200,
        silence_duration_ms: int = 500,
        vad_impl=None,
        chunk_duration_ms: int = 30,
    ):
        self.sample_rate = sample_rate
        self.vad = vad_impl or webrtcvad.Vad(aggressiveness)
        self.min_speech_frames = max(1, int(min_speech_duration_ms / chunk_duration_ms))
        self.silence_frames = max(1, int(silence_duration_ms / chunk_duration_ms))
        self.state = VADState.IDLE
        self._speech_frames = []
        self._trailing_count = 0

    def process(self, audio_chunk: bytes, pre_buffer: bytes = b"") -> VADResult:
        is_speech = self.vad.is_speech(audio_chunk, self.sample_rate)

        if self.state == VADState.IDLE:
            if is_speech:
                self.state = VADState.SPEAKING
                self._speech_frames = [pre_buffer, audio_chunk]
            return VADResult(is_speech, self.state)

        if self.state == VADState.SPEAKING:
            self._speech_frames.append(audio_chunk)
            if not is_speech:
                self.state = VADState.TRAILING
                self._trailing_count = 1
            return VADResult(is_speech, self.state)

        if self.state == VADState.TRAILING:
            self._speech_frames.append(audio_chunk)
            if is_speech:
                self.state = VADState.SPEAKING
                self._trailing_count = 0
                return VADResult(True, self.state)
            self._trailing_count += 1
            if self._trailing_count >= self.silence_frames:
                segment = b"".join(self._speech_frames)
                self.reset()
                if len(segment) >= self.min_speech_frames * len(audio_chunk):
                    return VADResult(False, VADState.IDLE, segment)
            return VADResult(False, self.state)

        return VADResult(is_speech, self.state)

    def reset(self) -> None:
        self.state = VADState.IDLE
        self._speech_frames = []
        self._trailing_count = 0
