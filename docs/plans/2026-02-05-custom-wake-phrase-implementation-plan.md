# Custom Wake Phrase Siri Trigger Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a macOS-only Python app that triggers Siri when a configurable wake phrase is detected using VAD-gated constrained Vosk recognition.

**Architecture:** Audio capture streams 16 kHz mono chunks into a pre-buffer, VAD segments speech, Vosk recognizes only configured phrases, and Siri is triggered via AppleScript with a cooldown. A CLI orchestrates components and provides health checks.

**Tech Stack:** Python 3.10+, vosk, webrtcvad, sounddevice, numpy, pytest.

---

### Task 1: Scaffold project and test harness

**Files:**
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `requirements.txt`
- Create: `config.json`
- Create: `setup.sh`
- Create: `models/.gitkeep`
- Create: `README.md`

**Step 1: Write a failing test (smoke test for pytest)**

```python
# tests/test_smoke.py

def test_pytest_runs():
    assert True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL because pytest not installed yet.

**Step 3: Write minimal implementation**

- Add `pytest` to `requirements.txt` (alongside runtime deps).
- Create empty `src/__init__.py` and `tests/__init__.py`.
- Add default `config.json` and `models/.gitkeep`.
- Add `setup.sh` from the spec.
- Add `README.md` with quickstart commands.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS after installing dependencies.

**Step 5: Commit**

```bash
git add requirements.txt config.json setup.sh README.md src/__init__.py tests/__init__.py models/.gitkeep tests/test_smoke.py
git commit -m "feat: scaffold project structure and test harness"
```

---

### Task 2: Config loader/saver (TDD)

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
import json
from src.config import Config

def test_load_and_save_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "wake_phrases": ["alpha"],
        "audio": {"sample_rate": 16000, "chunk_duration_ms": 30, "pre_buffer_duration_ms": 400, "device_id": None},
        "vad": {"aggressiveness": 2, "min_speech_duration_ms": 200, "silence_duration_ms": 500},
        "detection": {"confidence_threshold": 0.5, "cooldown_seconds": 3.0},
        "siri": {"trigger_method": "keyboard", "keyboard_shortcut": {"key": "space", "modifiers": ["command"]}},
        "general": {"log_level": "INFO", "show_notifications": True}
    }))

    config = Config(config_path=str(path)).load()
    assert config.wake_phrases == ["alpha"]

    config.add_phrase("beta")
    reloaded = Config(config_path=str(path)).load()
    assert "beta" in reloaded.wake_phrases

    assert reloaded.remove_phrase("alpha") is True
    assert reloaded.remove_phrase("missing") is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`.

**Step 3: Write minimal implementation**

```python
# src/config.py
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config loader and editor"
```

---

### Task 3: Utilities (TDD)

**Files:**
- Create: `src/utils.py`
- Create: `tests/test_utils.py`

**Step 1: Write the failing test**

```python
# tests/test_utils.py
import subprocess
import logging
import types
from src.utils import setup_logging, show_notification, is_macos

def test_setup_logging_sets_level():
    logging.getLogger().handlers.clear()
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG

def test_show_notification_ignores_failure(monkeypatch):
    def runner(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["osascript"])
    show_notification("Title", "Message", runner=runner)


def test_is_macos_false(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    assert is_macos() is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.utils'`.

**Step 3: Write minimal implementation**

```python
# src/utils.py
import logging
import subprocess
import sys
from typing import Callable

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def show_notification(title: str, message: str, runner: Callable = subprocess.run):
    script = f'display notification "{message}" with title "{title}"'
    try:
        runner(["osascript", "-e", script], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass


def is_macos() -> bool:
    return sys.platform == "darwin"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_utils.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/utils.py tests/test_utils.py
git commit -m "feat: add logging and notification utilities"
```

---

### Task 4: Audio capture with pre-buffer (TDD)

**Files:**
- Create: `src/audio_capture.py`
- Create: `tests/test_audio_capture.py`

**Step 1: Write the failing test**

```python
# tests/test_audio_capture.py
from src.audio_capture import AudioCapture

def test_pre_buffer_rolls_and_callback_called():
    chunks = []
    capture = AudioCapture(sample_rate=16000, chunk_duration_ms=10, pre_buffer_duration_ms=20)

    def cb(data):
        chunks.append(data)

    capture.start(cb)

    chunk_bytes = b"\x00\x00" * capture.chunk_size
    capture._handle_audio(chunk_bytes, capture.chunk_size, None, None)
    capture._handle_audio(chunk_bytes, capture.chunk_size, None, None)
    capture._handle_audio(chunk_bytes, capture.chunk_size, None, None)

    assert len(chunks) == 3
    assert len(capture.pre_buffer) == 2
    assert len(capture.get_pre_buffer()) == len(chunk_bytes) * 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_audio_capture.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.audio_capture'`.

**Step 3: Write minimal implementation**

```python
# src/audio_capture.py
from collections import deque
from typing import Callable, Optional
import sounddevice as sd

class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 30,
        pre_buffer_duration_ms: int = 400,
        device_id: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self.pre_buffer_chunks = int(pre_buffer_duration_ms / chunk_duration_ms)
        self.pre_buffer: deque[bytes] = deque(maxlen=self.pre_buffer_chunks)
        self.device_id = device_id
        self._stream = None
        self._callback: Optional[Callable[[bytes], None]] = None

    def _handle_audio(self, indata, frames, time_info, status):
        data = bytes(indata)
        self.pre_buffer.append(data)
        if self._callback:
            self._callback(data)

    def start(self, callback: Callable[[bytes], None]) -> None:
        self._callback = callback
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self.chunk_size,
            device=self.device_id,
            callback=self._handle_audio,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_pre_buffer(self) -> bytes:
        return b"".join(self.pre_buffer)

    def clear_pre_buffer(self) -> None:
        self.pre_buffer.clear()

    @staticmethod
    def list_devices() -> list[dict]:
        devices = sd.query_devices()
        return [
            {"index": i, "name": d["name"]}
            for i, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        ]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_audio_capture.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/audio_capture.py tests/test_audio_capture.py
git commit -m "feat: add audio capture with rolling pre-buffer"
```

---

### Task 5: VAD state machine (TDD)

**Files:**
- Create: `src/vad.py`
- Create: `tests/test_vad.py`

**Step 1: Write the failing test**

```python
# tests/test_vad.py
from src.vad import VoiceActivityDetector, VADState

class FakeVad:
    def __init__(self, sequence):
        self._seq = list(sequence)

    def is_speech(self, _chunk, _rate):
        return self._seq.pop(0) if self._seq else False


def test_vad_emits_segment_after_trailing_silence():
    vad = VoiceActivityDetector(
        sample_rate=16000,
        aggressiveness=2,
        min_speech_duration_ms=60,
        silence_duration_ms=60,
        vad_impl=FakeVad([False, True, True, False, False]),
        chunk_duration_ms=30,
    )

    pre = b"pre"
    chunk = b"\x00\x00" * 480

    assert vad.process(chunk, pre).state == VADState.IDLE
    assert vad.process(chunk, pre).state == VADState.SPEAKING
    assert vad.process(chunk, pre).state == VADState.SPEAKING
    result = vad.process(chunk, pre)
    assert result.state == VADState.TRAILING
    final = vad.process(chunk, pre)

    assert final.state == VADState.IDLE
    assert final.audio_segment is not None
    assert final.audio_segment.startswith(pre)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_vad.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.vad'`.

**Step 3: Write minimal implementation**

```python
# src/vad.py
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_vad.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/vad.py tests/test_vad.py
git commit -m "feat: add VAD state machine"
```

---

### Task 6: Phrase detector with constrained grammar (TDD)

**Files:**
- Create: `src/phrase_detector.py`
- Create: `tests/test_phrase_detector.py`

**Step 1: Write the failing test**

```python
# tests/test_phrase_detector.py
import json
from src.phrase_detector import PhraseDetector

class FakeRecognizer:
    def __init__(self, result_json):
        self._result_json = result_json
    def AcceptWaveform(self, _audio):
        return True
    def FinalResult(self):
        return self._result_json
    def Reset(self):
        pass


def test_detect_matches_phrase_and_confidence():
    results = json.dumps({
        "text": "hello",
        "result": [{"conf": 0.6}, {"conf": 0.8}],
    })

    def factory(_model, _rate, grammar):
        assert "[unk]" in grammar
        return FakeRecognizer(results)

    detector = PhraseDetector(
        model_path="/tmp/does-not-matter",
        phrases=["hello"],
        sample_rate=16000,
        model=object(),
        recognizer_factory=factory,
    )

    res = detector.detect(b"audio")
    assert res.detected is True
    assert res.phrase == "hello"
    assert abs(res.confidence - 0.7) < 0.001
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_phrase_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.phrase_detector'`.

**Step 3: Write minimal implementation**

```python
# src/phrase_detector.py
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_phrase_detector.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/phrase_detector.py tests/test_phrase_detector.py
git commit -m "feat: add Vosk phrase detector"
```

---

### Task 7: Siri trigger with cooldown (TDD)

**Files:**
- Create: `src/siri_trigger.py`
- Create: `tests/test_siri_trigger.py`

**Step 1: Write the failing test**

```python
# tests/test_siri_trigger.py
from src.siri_trigger import SiriTrigger


def test_trigger_respects_cooldown():
    calls = []
    def runner(*args, **kwargs):
        calls.append(args)
        return None

    times = [0.0, 0.1, 5.0]
    def time_fn():
        return times.pop(0)

    trigger = SiriTrigger(cooldown_seconds=1.0, runner=runner, time_fn=time_fn)

    assert trigger.trigger() is True
    assert trigger.trigger() is False
    assert trigger.trigger() is True
    assert len(calls) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_siri_trigger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.siri_trigger'`.

**Step 3: Write minimal implementation**

```python
# src/siri_trigger.py
import time
import subprocess
from typing import Callable, Optional

class SiriTrigger:
    def __init__(
        self,
        cooldown_seconds: float = 3.0,
        shortcut_key: str = "space",
        shortcut_modifiers: Optional[list[str]] = None,
        runner: Callable = subprocess.run,
        time_fn: Callable = time.time,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.shortcut_key = shortcut_key
        self.shortcut_modifiers = shortcut_modifiers or ["command"]
        self._last_trigger_time = 0.0
        self._runner = runner
        self._time_fn = time_fn

    def trigger(self) -> bool:
        if self.is_in_cooldown():
            return False

        key = self.shortcut_key
        modifier = self.shortcut_modifiers[0]
        script = (
            'tell application "System Events"\n'
            f'    key down {modifier}\n'
            f'    keystroke "{key}"\n'
            '    delay 0.3\n'
            f'    key up {modifier}\n'
            'end tell\n'
        )

        try:
            self._runner(["osascript", "-e", script], check=True, capture_output=True)
            self._last_trigger_time = self._time_fn()
            return True
        except subprocess.CalledProcessError:
            return False

    def is_in_cooldown(self) -> bool:
        return (self._time_fn() - self._last_trigger_time) < self.cooldown_seconds

    @staticmethod
    def check_siri_enabled(runner: Callable = subprocess.run) -> bool:
        try:
            result = runner(
                ["defaults", "read", "com.apple.assistant.support", "Assistant Enabled"],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() == "1"
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def check_accessibility_permissions(runner: Callable = subprocess.run) -> bool:
        try:
            result = runner(
                ["osascript", "-e", "tell application \"System Events\" to return UI elements enabled"],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip().lower() == "true"
        except subprocess.CalledProcessError:
            return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_siri_trigger.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/siri_trigger.py tests/test_siri_trigger.py
git commit -m "feat: add Siri trigger with cooldown"
```

---

### Task 8: Daemon orchestration and CLI (TDD)

**Files:**
- Create: `src/main.py`
- Create: `tests/test_main_daemon.py`

**Step 1: Write the failing test**

```python
# tests/test_main_daemon.py
import queue
from src.main import WakePhraseDaemon
from src.phrase_detector import DetectionResult

class FakeAudio:
    def __init__(self):
        self._cb = None
    def start(self, cb):
        self._cb = cb
    def stop(self):
        pass
    def get_pre_buffer(self):
        return b""
    def clear_pre_buffer(self):
        pass

class FakeVAD:
    def __init__(self):
        self.called = False
    def process(self, chunk, pre):
        if not self.called:
            self.called = True
            class Result:
                audio_segment = b"segment"
            return Result()
        class Result:
            audio_segment = None
        return Result()

class FakeDetector:
    def detect(self, _segment):
        return DetectionResult(True, "hello", 0.9, "hello")

class FakeTrigger:
    def __init__(self):
        self.count = 0
    def trigger(self):
        self.count += 1
        return True

class FakeConfig:
    class detection:
        confidence_threshold = 0.5
    class general:
        show_notifications = False


def test_daemon_triggers_on_detected_phrase():
    daemon = WakePhraseDaemon(
        config=FakeConfig(),
        test_mode=False,
        audio=FakeAudio(),
        vad=FakeVAD(),
        detector=FakeDetector(),
        trigger=FakeTrigger(),
    )

    daemon.running = True
    daemon._on_audio(b"chunk")
    segment = daemon.audio_queue.get(timeout=0.1)
    assert segment == b"segment"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_main_daemon.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.main'`.

**Step 3: Write minimal implementation**

```python
# src/main.py
import argparse
import logging
import queue
import threading

from .config import Config
from .audio_capture import AudioCapture
from .vad import VoiceActivityDetector
from .phrase_detector import PhraseDetector
from .siri_trigger import SiriTrigger
from .utils import setup_logging, show_notification

class WakePhraseDaemon:
    def __init__(self, config: Config, test_mode: bool = False, audio=None, vad=None, detector=None, trigger=None):
        self.config = config
        self.test_mode = test_mode
        self.running = False
        self.audio_queue: queue.Queue[bytes] = queue.Queue()

        self.audio = audio or AudioCapture(
            sample_rate=config.audio.sample_rate,
            chunk_duration_ms=config.audio.chunk_duration_ms,
            pre_buffer_duration_ms=config.audio.pre_buffer_duration_ms,
            device_id=config.audio.device_id,
        )
        self.vad = vad or VoiceActivityDetector(
            sample_rate=config.audio.sample_rate,
            aggressiveness=config.vad.aggressiveness,
            min_speech_duration_ms=config.vad.min_speech_duration_ms,
            silence_duration_ms=config.vad.silence_duration_ms,
        )
        self.detector = detector or PhraseDetector(
            model_path="models/vosk-model-small-en-us-0.15",
            phrases=config.wake_phrases,
            sample_rate=config.audio.sample_rate,
        )
        self.trigger = trigger or SiriTrigger(
            cooldown_seconds=config.detection.cooldown_seconds
        )

    def start(self):
        self.running = True
        decoder_thread = threading.Thread(target=self._decoder_loop, daemon=True)
        decoder_thread.start()
        logging.info("Listening for: %s", ", ".join(self.config.wake_phrases))
        self.audio.start(self._on_audio)

        try:
            while self.running:
                threading.Event().wait(0.1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logging.info("Shutting down...")
        self.running = False
        self.audio.stop()

    def _on_audio(self, chunk: bytes):
        result = self.vad.process(chunk, self.audio.get_pre_buffer())
        if getattr(result, "audio_segment", None) is not None:
            self.audio_queue.put(result.audio_segment)
            self.audio.clear_pre_buffer()

    def _decoder_loop(self):
        while self.running:
            try:
                segment = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            result = self.detector.detect(segment)
            logging.debug("Detected: '%s' (conf: %.2f)", result.raw_text, result.confidence)
            if result.detected and result.confidence >= self.config.detection.confidence_threshold:
                if self.test_mode:
                    print(f"[TEST MODE] Would trigger Siri for: '{result.phrase}'")
                else:
                    if self.trigger.trigger() and self.config.general.show_notifications:
                        show_notification("Wake Phrase Detected", f"Triggered Siri with '{result.phrase}'")


def main():
    parser = argparse.ArgumentParser(description="Custom Wake Phrase Siri Trigger")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    run_parser = subparsers.add_parser("run", help="Start listening")
    run_parser.add_argument("--verbose", "-v", action="store_true")

    test_parser = subparsers.add_parser("test", help="Test mode")
    test_parser.add_argument("--verbose", "-v", action="store_true")

    phrases_parser = subparsers.add_parser("phrases", help="Manage phrases")
    phrases_sub = phrases_parser.add_subparsers(dest="phrases_command")
    phrases_sub.add_parser("list")
    add_parser = phrases_sub.add_parser("add")
    add_parser.add_argument("phrase")
    remove_parser = phrases_sub.add_parser("remove")
    remove_parser.add_argument("phrase")

    subparsers.add_parser("doctor")
    subparsers.add_parser("devices")

    args = parser.parse_args()
    config = Config().load()
    log_level = logging.DEBUG if getattr(args, "verbose", False) else config.general.log_level
    setup_logging(log_level)

    if args.command == "run":
        WakePhraseDaemon(config, test_mode=False).start()
    elif args.command == "test":
        WakePhraseDaemon(config, test_mode=True).start()
    elif args.command == "phrases":
        if args.phrases_command == "list":
            print("Current wake phrases:")
            for phrase in config.wake_phrases:
                print(f"  • {phrase}")
        elif args.phrases_command == "add":
            config.add_phrase(args.phrase)
            print(f"Added: {args.phrase}")
        elif args.phrases_command == "remove":
            if config.remove_phrase(args.phrase):
                print(f"Removed: {args.phrase}")
            else:
                print(f"Phrase not found: {args.phrase}")
    elif args.command == "doctor":
        print("System Check")
        print(f"Phrases: {', '.join(config.wake_phrases)}")
        if SiriTrigger.check_siri_enabled():
            print("Siri enabled")
        else:
            print("Siri not enabled")
        if SiriTrigger.check_accessibility_permissions():
            print("Accessibility permissions granted")
        else:
            print("Accessibility permissions needed")
    elif args.command == "devices":
        for d in AudioCapture.list_devices():
            print(f"[{d['index']}] {d['name']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_main_daemon.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/main.py tests/test_main_daemon.py
git commit -m "feat: add daemon orchestration and CLI"
```

---

### Task 9: Documentation and final verification

**Files:**
- Modify: `README.md`

**Step 1: Write the failing test**

```python
# tests/test_readme.py
from pathlib import Path

def test_readme_mentions_setup_and_run():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "setup.sh" in text
    assert "python -m src.main run" in text
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_readme.py -v`
Expected: FAIL if README is missing these commands.

**Step 3: Write minimal implementation**

Update `README.md` to include setup, venv activation, running, test mode, and phrases commands.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_readme.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add README.md tests/test_readme.py
git commit -m "docs: add usage instructions"
```

---

### Task 10: Full test run

**Files:**
- None

**Step 1: Run full test suite**

Run: `pytest -v`
Expected: PASS.

**Step 2: Commit**

```bash
git commit --allow-empty -m "chore: verify test suite"
```
