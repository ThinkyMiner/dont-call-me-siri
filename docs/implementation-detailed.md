# Custom Wake Phrase Siri Trigger: Detailed Implementation Notes

This document describes what is implemented in each project file and how the runtime pipeline works end-to-end.

## 1. What this project currently does

- Runs on macOS and listens to microphone audio continuously.
- Uses WebRTC VAD to decide when speech starts/ends.
- Sends completed speech segments to Moonshine Tiny for full-vocabulary transcription.
- Matches transcription against configured wake phrases using word-boundary matching.
- Triggers Siri with `open -a Siri` or AppleScript keyboard simulation (or prints in test mode).

Current architecture in runtime terms:

1. `AudioCapture` streams raw PCM frames.
2. `VoiceActivityDetector` groups frames into speech segments.
3. `PhraseDetector` transcribes each segment with Moonshine Tiny and checks for phrase matches.
4. `SiriTrigger` triggers Siri if detection passes threshold/cooldown.

## 2. File-by-file implementation status

### 2.1 Root-level files

#### `setup.sh`
- Validates Python version (`3.10` to `3.14`).
- Creates `venv` and activates it.
- Upgrades `pip` and installs from `requirements.txt`.
- Verifies Moonshine Tiny model is accessible (auto-downloads from HuggingFace if needed).
- Creates default `config.json` if absent.

#### `requirements.txt`
- Runtime: `useful-moonshine-onnx`, `webrtcvad`, `sounddevice`, `numpy`
- Dev: `pytest`, `setuptools`

#### `config.json`
Stores all runtime knobs: `wake_phrases`, `audio`, `vad`, `detection`, `siri`, `general`.

### 2.2 Source package files (`src/`)

#### `src/config.py`
- Typed dataclasses: `AudioConfig`, `VADConfig`, `DetectionConfig`, `SiriConfig`, `GeneralConfig`
- `Config` class: `load()`, `save()`, `add_phrase()`, `remove_phrase()`

#### `src/audio_capture.py`
- Captures microphone input with `sounddevice.RawInputStream` (mono int16 PCM, 16kHz).
- Rolling pre-buffer using `deque(maxlen=...)` to capture phrase onset.
- Actionable error messages for missing/inaccessible audio devices.

#### `src/vad.py`
- Wraps `webrtcvad` in a three-state machine: `IDLE` -> `SPEAKING` -> `TRAILING`.
- Returns completed `audio_segment` when trailing silence threshold is met.
- Prepends pre-buffer when speech starts.

#### `src/phrase_detector.py`
- Loads Moonshine Tiny model (ONNX, ~60 MB, auto-downloaded from HuggingFace).
- Converts int16 audio bytes to float32 numpy array for Moonshine.
- Full-vocabulary transcription — any English word works as a wake phrase.
- Phrase matching: normalize text (lowercase, strip punctuation), exact match first, then word-boundary contains match.
- Returns `DetectionResult(detected, phrase, confidence, raw_text)`.

#### `src/siri_trigger.py`
- Trigger methods: `open_app` (`open -a Siri`) or `keyboard` (AppleScript).
- Cooldown prevents rapid re-triggering.
- Static checks: `check_siri_enabled()`, `check_accessibility_permissions()`, `check_voice_mode()`, `set_voice_mode()`.

#### `src/utils.py`
- `setup_logging(level)` — accepts str or int levels.
- `show_notification()` — macOS notification via osascript.
- `is_macos()` — platform helper.

#### `src/main.py`
- `WakePhraseDaemon` orchestrator wiring all components.
- CLI: `run`, `test`, `phrases list|add|remove`, `doctor`, `devices`.
- Decoder loop on background thread, graceful Ctrl+C shutdown.

### 2.3 Test files (`tests/`)

39 tests across 10 files covering all components with mocked dependencies.

## 3. End-to-end runtime flow

### 3.1 Startup
1. CLI parses args, loads `config.json` into typed dataclasses.
2. `WakePhraseDaemon` initializes all components.
3. Moonshine model loads (first run downloads from HuggingFace).
4. Decoder thread starts, audio stream starts.

### 3.2 Audio + VAD
1. Audio callback receives 30ms chunks from microphone.
2. Chunks stored in pre-buffer ring and forwarded to VAD.
3. VAD state machine: IDLE -> SPEAKING -> TRAILING -> segment emitted.
4. Completed segment queued for decoder thread.

### 3.3 Decoder and phrase matching
1. Decoder thread dequeues speech segment.
2. Audio bytes converted to float32 numpy array.
3. Moonshine Tiny transcribes the segment.
4. Transcription normalized (lowercase, strip punctuation).
5. Exact match check against wake phrases, then word-boundary contains match.
6. `DetectionResult` returned to daemon.

### 3.4 Trigger
- Test mode: prints detection to stdout.
- Run mode: checks cooldown, triggers Siri, optional notification.

### 3.5 Shutdown
Ctrl+C -> `stop()` -> audio stream closed -> decoder thread exits.

## 4. Practical tuning knobs

- `audio.device_id` — pin the correct microphone.
- `vad.aggressiveness` (1-3) — higher reduces false speech detection in noise.
- `vad.silence_duration_ms` — higher creates longer segments for multi-word phrases.
- `detection.confidence_threshold` (0.0-1.0) — filter low-confidence detections.
- `wake_phrases` — any English words work; phonetically distinct words reduce false triggers.

## 5. Known limitations

- No persistent calibration (noise profile, threshold learning).
- No packaging/auto-start GUI (CLI-first).
- No schema validation for `config.json`.
