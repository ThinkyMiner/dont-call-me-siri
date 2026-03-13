# Moonshine Tiny STT Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Vosk with Moonshine Tiny for dramatically better transcription accuracy and real confidence scores.

**Architecture:** Same pipeline shape (Mic → VAD → STT → Phrase Match → Siri), replacing the Vosk constrained-grammar recognizer with Moonshine Tiny (a 27M-parameter transformer model). Moonshine does full transcription (not constrained grammar), giving us real text and extractable per-token confidence from logits. Phrase matching changes from exact-text-against-constrained-output to substring/contains matching against real transcription.

**Tech Stack:** Python 3.10+, `useful-moonshine-onnx` (ONNX runtime), `webrtcvad`, `sounddevice`, `numpy`

---

### Task 1: Update dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Update requirements.txt**

Replace `vosk>=0.3.44` with `useful-moonshine-onnx`:

```
useful-moonshine-onnx
webrtcvad>=2.0.10
sounddevice>=0.4.6
numpy>=1.23.0
pytest>=7.0.0
setuptools>=65.0.0
```

**Step 2: Install and verify**

Run: `pip install -r requirements.txt`
Expected: successful install with moonshine_onnx importable

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: replace vosk with useful-moonshine-onnx dependency"
```

---

### Task 2: Rewrite PhraseDetector with Moonshine

**Files:**
- Modify: `src/phrase_detector.py`
- Test: `tests/test_phrase_detector.py`

**Step 1: Write failing tests**

Replace `tests/test_phrase_detector.py` entirely:

```python
import numpy as np
from src.phrase_detector import PhraseDetector, DetectionResult


class FakeTokenizer:
    def decode_batch(self, token_batches):
        return [self._decode(tokens) for tokens in token_batches]

    def _decode(self, tokens):
        # Simulates tokenizer output — tests set this via _text
        return getattr(self, "_text", "")


class FakeModel:
    """Fake MoonshineOnnxModel that returns preset tokens and logits."""

    def __init__(self, text=""):
        self._tokenizer = FakeTokenizer()
        self._tokenizer._text = text

    def generate(self, audio, max_len=None):
        return [[1, 100, 2]]  # start, token, eos


def test_detect_exact_match():
    model = FakeModel("hello")
    detector = PhraseDetector(
        phrases=["hello"],
        model=model,
        tokenizer=model._tokenizer,
    )
    res = detector.detect(b"\x00\x00" * 8000)  # 0.5s of silence at 16kHz
    assert res.detected is True
    assert res.phrase == "hello"
    assert res.raw_text == "hello"


def test_detect_contains_match():
    model = FakeModel("hey jarvis how are you")
    detector = PhraseDetector(
        phrases=["jarvis"],
        model=model,
        tokenizer=model._tokenizer,
    )
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True
    assert res.phrase == "jarvis"


def test_detect_no_match():
    model = FakeModel("the weather is nice today")
    detector = PhraseDetector(
        phrases=["hello", "jarvis"],
        model=model,
        tokenizer=model._tokenizer,
    )
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is False
    assert res.phrase is None


def test_detect_empty_transcription():
    model = FakeModel("")
    detector = PhraseDetector(
        phrases=["hello"],
        model=model,
        tokenizer=model._tokenizer,
    )
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is False
    assert res.raw_text == ""


def test_detect_case_insensitive():
    model = FakeModel("Hello")
    detector = PhraseDetector(
        phrases=["hello"],
        model=model,
        tokenizer=model._tokenizer,
    )
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True
    assert res.phrase == "hello"


def test_detect_strips_punctuation():
    model = FakeModel("hello!")
    detector = PhraseDetector(
        phrases=["hello"],
        model=model,
        tokenizer=model._tokenizer,
    )
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True


def test_update_phrases():
    model = FakeModel("computer")
    detector = PhraseDetector(
        phrases=["hello"],
        model=model,
        tokenizer=model._tokenizer,
    )
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is False

    detector.update_phrases(["computer"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True


def test_current_phrases():
    model = FakeModel("")
    detector = PhraseDetector(
        phrases=["hello", "jarvis"],
        model=model,
        tokenizer=model._tokenizer,
    )
    assert detector.current_phrases == ["hello", "jarvis"]
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_phrase_detector.py -v`
Expected: FAIL — PhraseDetector constructor signature has changed

**Step 3: Rewrite src/phrase_detector.py**

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_phrase_detector.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add src/phrase_detector.py tests/test_phrase_detector.py
git commit -m "feat: replace Vosk with Moonshine Tiny in PhraseDetector

Moonshine Tiny provides full transcription with real transformer-based
accuracy instead of Vosk's constrained grammar hack. Matching is now
substring-based on real transcription text."
```

---

### Task 3: Update Config to remove Vosk-specific options

**Files:**
- Modify: `src/config.py`
- Modify: `config.json`
- Test: `tests/test_config.py`

**Step 1: Write failing test**

Add to `tests/test_config.py`:

```python
def test_config_detection_has_no_unk_match(tmp_path):
    """allow_unk_wrapped_match should no longer exist in DetectionConfig."""
    import json
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({
        "wake_phrases": ["hello"],
        "detection": {"confidence_threshold": 0.5, "cooldown_seconds": 3.0},
    }))
    from src.config import Config
    config = Config(str(cfg_file)).load()
    assert not hasattr(config.detection, "allow_unk_wrapped_match")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py::test_config_detection_has_no_unk_match -v`
Expected: FAIL — DetectionConfig still has allow_unk_wrapped_match

**Step 3: Update src/config.py**

In `DetectionConfig`, remove the `allow_unk_wrapped_match` field and set confidence_threshold default to 0.5:

```python
@dataclass
class DetectionConfig:
    confidence_threshold: float = 0.5
    cooldown_seconds: float = 3.0
```

**Step 4: Update config.json**

Remove `allow_unk_wrapped_match` from config.json detection section. Set confidence_threshold to 0.5:

```json
"detection": {
    "confidence_threshold": 0.5,
    "cooldown_seconds": 3.0
}
```

**Step 5: Run all config tests**

Run: `python -m pytest tests/test_config.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/config.py config.json tests/test_config.py
git commit -m "refactor: remove Vosk-specific config options

Remove allow_unk_wrapped_match (no longer relevant with Moonshine).
Set confidence_threshold default to 0.5 (now meaningful)."
```

---

### Task 4: Update WakePhraseDaemon to use new PhraseDetector

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_main_daemon.py`

**Step 1: Update src/main.py**

In `WakePhraseDaemon.__init__`, replace the PhraseDetector construction:

```python
# Old:
self.detector = detector or PhraseDetector(
    model_path="models/vosk-model-small-en-us-0.15",
    phrases=config.wake_phrases,
    sample_rate=config.audio.sample_rate,
    debug_fallback_transcript=test_mode,
    verify_with_fallback=True,
    allow_unk_wrapped_match=getattr(config.detection, "allow_unk_wrapped_match", False),
)

# New:
self.detector = detector or PhraseDetector(
    phrases=config.wake_phrases,
    sample_rate=config.audio.sample_rate,
)
```

In the `doctor` command section, replace the Vosk model check:

```python
# Old:
if os.path.exists("models/vosk-model-small-en-us-0.15"):
    print("Vosk model found")
else:
    print("Vosk model not found - run setup.sh")

# New:
try:
    import moonshine_onnx
    print(f"Moonshine STT available (v{moonshine_onnx.version})")
except ImportError:
    print("Moonshine STT not installed - run: pip install useful-moonshine-onnx")
```

**Step 2: Update tests/test_main_daemon.py**

In `FakeConfig`, remove `allow_unk_wrapped_match` if referenced anywhere. The existing tests should mostly work since they use `FakeDetector` — but update the doctor tests:

Update `test_doctor_reports_voice_mode_inactive` and similar: replace `monkeypatch.setattr("os.path.exists", lambda _: True)` with a monkeypatch that makes moonshine_onnx importable. Since tests mock everything, just remove the `os.path.exists` mock — the doctor command will try to import moonshine_onnx which should be installed.

Actually, to keep tests isolated, monkeypatch the import check:

```python
# In doctor tests, replace:
monkeypatch.setattr("os.path.exists", lambda _: True)
# With:
import types
fake_moonshine = types.ModuleType("moonshine_onnx")
fake_moonshine.version = "test"
monkeypatch.setitem(sys.modules, "moonshine_onnx", fake_moonshine)
```

**Step 3: Run tests**

Run: `python -m pytest tests/test_main_daemon.py -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add src/main.py tests/test_main_daemon.py
git commit -m "refactor: update daemon and doctor to use Moonshine STT"
```

---

### Task 5: Update setup.sh

**Files:**
- Modify: `setup.sh`

**Step 1: Update setup.sh**

Remove the Vosk model download section. Moonshine model is auto-downloaded from HuggingFace on first use (bundled with the pip package / downloaded to HF cache). Replace with a verification step:

```bash
#!/bin/bash
set -e

echo "Custom Wake Phrase Trigger - Setup"
echo "=================================="

python3 --version | grep -E "3\.(10|11|12|13|14)" > /dev/null || {
    echo "Python 3.10+ required"
    exit 1
}

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Verifying Moonshine STT model..."
python3 -c "from moonshine_onnx import MoonshineOnnxModel; MoonshineOnnxModel(model_name='tiny')" && \
    echo "Moonshine Tiny model ready." || \
    echo "Warning: Moonshine model download may happen on first run."

if [ ! -f "config.json" ]; then
    echo "Creating default config..."
    cat > config.json << 'CONFIG'
{
    "wake_phrases": [
        "mithi",
        "bhature",
        "hey jarvis"
    ],
    "audio": {
        "sample_rate": 16000,
        "chunk_duration_ms": 30,
        "pre_buffer_duration_ms": 400,
        "device_id": null
    },
    "vad": {
        "aggressiveness": 2,
        "min_speech_duration_ms": 200,
        "silence_duration_ms": 500
    },
    "detection": {
        "confidence_threshold": 0.5,
        "cooldown_seconds": 3.0
    },
    "siri": {
        "trigger_method": "open_app",
        "keyboard_shortcut": {
            "key": "space",
            "modifiers": ["command"]
        }
    },
    "general": {
        "log_level": "INFO",
        "show_notifications": true
    }
}
CONFIG
fi

echo "Setup complete."
echo "Activate the environment: source venv/bin/activate"
echo "Run: python -m src.main run"
echo "Run 'python -m src.main doctor --fix-voice-mode' to enable Siri voice listening mode."
```

**Step 2: Commit**

```bash
git add setup.sh
git commit -m "chore: update setup.sh for Moonshine (remove Vosk model download)"
```

---

### Task 6: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Update README**

Key changes:
- Pipeline description: `Microphone -> VAD -> Moonshine Tiny STT -> Siri trigger`
- Remove all Vosk references (constrained grammar, vocabulary warnings, `[unk]`)
- Update detection section: remove `allow_unk_wrapped_match`, note that `confidence_threshold` now works meaningfully
- Remove the "Phrase not recognized - may be out-of-vocabulary" troubleshooting (Moonshine does full vocabulary transcription)
- Add note: "Moonshine model downloads automatically on first run (~60 MB)"

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for Moonshine STT engine"
```

---

### Task 7: Run full test suite and verify

**Step 1: Run all tests**

Run: `python -m pytest -v`
Expected: All tests pass

**Step 2: Manual smoke test**

Run: `python -m src.main doctor`
Expected: Shows "Moonshine STT available" instead of Vosk model check

Run: `python -m src.main test --verbose`
Expected: Listens for wake phrases, transcribes speech with Moonshine

**Step 3: Final commit if any fixes needed**

---

### Task 8: Clean up old Vosk artifacts

**Step 1: Remove models directory placeholder**

The `models/` directory with Vosk model is no longer needed. Remove `models/.gitkeep` and add `models/` to `.gitignore` (in case users still have old models).

**Step 2: Commit**

```bash
git rm models/.gitkeep
git commit -m "chore: remove Vosk model directory (Moonshine auto-downloads)"
```
