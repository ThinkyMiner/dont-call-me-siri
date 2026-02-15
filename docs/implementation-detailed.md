# Custom Wake Phrase Siri Trigger: Detailed Implementation Notes

This document describes what is implemented in each project file and how the runtime pipeline works end-to-end.

## 1. What this project currently does

- Runs on macOS and listens to microphone audio continuously.
- Uses WebRTC VAD to decide when speech starts/ends.
- Sends completed speech segments to Vosk with constrained grammar (`wake_phrases + [unk]`).
- Optionally validates constrained matches against an unconstrained fallback transcript.
- Triggers Siri with AppleScript keyboard simulation (or prints in test mode).

Current architecture in runtime terms:

1. `AudioCapture` streams raw PCM frames.
2. `VoiceActivityDetector` groups frames into speech segments.
3. `PhraseDetector` checks each segment for configured wake phrase matches.
4. `SiriTrigger` executes keyboard automation if detection passes threshold/cooldown.

## 2. File-by-file implementation status

### 2.1 Root-level files

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/setup.sh`
Completed tasks:
- Validates Python version (`3.10` to `3.14`).
- Creates `venv` and activates it.
- Upgrades `pip` and installs from `requirements.txt`.
- Downloads Vosk small model into `models/vosk-model-small-en-us-0.15` if missing.
- Creates default `config.json` if absent.

Behavior notes:
- Script is re-runnable; model download is skipped if directory exists.
- Default Siri shortcut in generated config is `command + space`.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/requirements.txt`
Completed tasks:
- Declares runtime dependencies:
  - `vosk`
  - `webrtcvad`
  - `sounddevice`
  - `numpy`
- Declares dev/support dependencies currently used in this repo:
  - `pytest`
  - `setuptools`

Behavior notes:
- `webrtcvad` currently emits a `pkg_resources` deprecation warning through setuptools path. It is noisy but non-blocking.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/config.json`
Completed tasks:
- Stores all runtime knobs used by the app:
  - `wake_phrases`
  - `audio`
  - `vad`
  - `detection`
  - `siri`
  - `general`

Current checked-in values (at time of this doc update):
- `wake_phrases`: `"mithi"`
- `audio.device_id`: `0`
- `detection.confidence_threshold`: `0.0`
- Siri shortcut profile:
  - `key: "command"`
  - `modifiers: []`

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/README.md`
Completed tasks:
- Documents quick start, test mode, phrase management, doctor/devices commands.
- Provides command examples used by tests and manual verification.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/.gitignore`
Completed tasks:
- Excludes local worktree/runtime artifacts:
  - `.worktrees/`
  - `venv/`
  - Python cache files
  - pytest cache
  - downloaded Vosk model folder

---

### 2.2 Source package files (`src/`)

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/__init__.py`
Completed tasks:
- Marks `src` as a Python package so `python -m src.main` works.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/config.py`
Completed tasks:
- Defines dataclasses:
  - `AudioConfig`
  - `VADConfig`
  - `DetectionConfig`
  - `SiriConfig`
  - `GeneralConfig`
- Implements `Config` class:
  - `load()` to parse JSON into typed objects.
  - `save()` to persist typed state back to JSON.
  - `add_phrase()` with case-insensitive dedupe.
  - `remove_phrase()` with case-insensitive removal.

Important behavior:
- No schema validation layer; malformed JSON raises directly (you saw this with `JSONDecodeError`).

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/audio_capture.py`
Completed tasks:
- Captures microphone input with `sounddevice.RawInputStream`.
- Uses mono `int16` PCM with configurable block size (`chunk_size`).
- Maintains rolling pre-buffer using `deque(maxlen=...)`.
- Exposes:
  - `start(callback)`
  - `stop()`
  - `get_pre_buffer()`
  - `clear_pre_buffer()`
  - `list_devices()`

Hardening done:
- Converts `PortAudioError` to actionable `RuntimeError` messages:
  - no input devices detected
  - selected device cannot be opened

Important behavior:
- `list_devices()` filters to devices with `max_input_channels > 0`.
- Callback stores every incoming chunk in pre-buffer before forwarding it.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/vad.py`
Completed tasks:
- Wraps `webrtcvad` in a segment-building state machine:
  - `IDLE`
  - `SPEAKING`
  - `TRAILING`
- Returns `VADResult` per chunk with:
  - `is_speech`
  - current `state`
  - completed `audio_segment` only when speech segment closes
- Prepends supplied pre-buffer when speech starts.

Important behavior:
- Segment finalization happens only after enough trailing silence (`silence_duration_ms`).
- Segment is dropped if shorter than configured minimum speech duration (`min_speech_duration_ms`).

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/phrase_detector.py`
Completed tasks:
- Loads Vosk model once.
- Creates constrained recognizer grammar as JSON: `phrases + ["[unk]"]`.
- Detects phrase matches from each completed speech segment.
- Returns `DetectionResult` containing:
  - `detected`
  - `phrase`
  - `confidence`
  - constrained `raw_text`
  - optional unconstrained `fallback_text`

Detection logic improvements already implemented:
- Normalizes constrained text by removing `[unk]` tokens before equality checks.
  - Example: `[unk] hello [unk]` can still map to phrase `hello`.
- Optional fallback recognizer path:
  - enabled when `debug_fallback_transcript=True` or `verify_with_fallback=True`.
- Fallback verification gate:
  - if constrained says phrase matched but fallback transcript disagrees, match is rejected.

Important behavior:
- In constrained grammar mode, word confidence is often missing; `confidence` can stay `0.0` even on valid detections.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/siri_trigger.py`
Completed tasks:
- Handles Siri trigger cooldown.
- Builds AppleScript keyboard actions based on config.
- Executes with `osascript`.
- Exposes static checks:
  - `check_siri_enabled()`
  - `check_accessibility_permissions()`

Implemented trigger modes:
1. Standard key + modifiers (example: `command + space`).
2. Modifier-only double press (example: double `command`) when:
   - `shortcut_key` is modifier key
   - `shortcut_modifiers` is empty

Important behavior:
- First trigger is never cooldown-blocked.
- Failed AppleScript execution returns `False` without crashing daemon.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/utils.py`
Completed tasks:
- `setup_logging(level)` now accepts both `str` and `int` levels.
- `show_notification()` wraps macOS notification via `osascript` and ignores failures.
- `is_macos()` platform helper.

Bugfix included:
- Prevented crash from `--verbose` path where logging level was an integer (`AttributeError: int has no attribute upper`).

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/src/main.py`
Completed tasks:
- Defines `WakePhraseDaemon` orchestration class.
- Defines CLI commands:
  - `run`
  - `test`
  - `phrases list`
  - `phrases add`
  - `phrases remove`
  - `doctor`
  - `devices`
- Wires config into all runtime components.
- Runs decoder loop on background thread.
- Handles graceful stop on Ctrl+C.

Operational improvements implemented:
- Audio startup failures are caught and logged cleanly.
- Verbose diagnostics include:
  - VAD state transitions
  - queued segment byte sizes
  - constrained detection text
  - fallback transcript (when available)
- Reads Siri shortcut from config and passes into `SiriTrigger`.

---

### 2.3 Test files (`tests/`)

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_smoke.py`
Completed task:
- Sanity test that pytest runs.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_config.py`
Completed tasks:
- Verifies config load/save behavior.
- Verifies phrase add/remove persistence and case-insensitive removal.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_audio_capture.py`
Completed tasks:
- Verifies pre-buffer roll behavior.
- Verifies callback invocation path.
- Verifies helpful error when no input devices exist.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_vad.py`
Completed tasks:
- Verifies VAD state transitions and segment emission on trailing silence.
- Verifies pre-buffer is included in emitted segment.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_phrase_detector.py`
Completed tasks:
- Verifies phrase match + confidence average when confidences are present.
- Verifies fallback transcript capture on `[unk]`.
- Verifies `[unk]`-wrapped text can still match phrase.
- Verifies fallback disagreement rejection.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_siri_trigger.py`
Completed tasks:
- Verifies cooldown behavior.
- Verifies double-command AppleScript generation.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_main_daemon.py`
Completed tasks:
- Verifies VAD segment is queued by daemon callback.
- Verifies daemon handles audio start failures.
- Verifies Siri shortcut config values are passed to `SiriTrigger`.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_utils.py`
Completed tasks:
- Verifies logging setup for string/int level inputs.
- Verifies notification helper failure tolerance.
- Verifies platform helper behavior.

#### `/Users/kartik/Developer/dont-call-me-siri/.worktrees/custom-wake-phrase/tests/test_readme.py`
Completed tasks:
- Verifies README contains critical operational commands.

## 3. End-to-end runtime flow (exact execution path)

### 3.1 Startup flow

1. User runs one of:
   - `python -m src.main run`
   - `python -m src.main test --verbose`
2. `src/main.py` parses CLI args.
3. `Config().load()` parses `config.json` into dataclass objects.
4. `setup_logging(...)` initializes logging.
5. `WakePhraseDaemon` initializes:
   - `AudioCapture`
   - `VoiceActivityDetector`
   - `PhraseDetector`
   - `SiriTrigger`
6. Decoder thread starts (`_decoder_loop`).
7. Audio stream starts (`audio.start(self._on_audio)`).

### 3.2 Real-time audio + VAD flow

For each audio chunk from callback:

1. `AudioCapture._handle_audio(...)` receives raw bytes from PortAudio.
2. Chunk is appended to pre-buffer ring.
3. Chunk is passed to daemon callback (`_on_audio`).
4. `_on_audio` calls `vad.process(chunk, pre_buffer)`.
5. VAD transitions among `idle/speaking/trailing`.
6. When trailing silence threshold is met and segment length is valid, VAD returns `audio_segment`.
7. Daemon queues that segment and clears pre-buffer.

### 3.3 Decoder and phrase verification flow

For each queued speech segment:

1. Decoder thread calls `detector.detect(segment)`.
2. Constrained recognizer returns text built from configured grammar.
3. Detector normalizes constrained text by removing `[unk]` wrappers.
4. Phrase comparison is done against configured phrases (lowercased).
5. If fallback path is enabled, unconstrained transcript is generated for debug/verification.
6. If fallback verification is enabled and fallback disagrees, detection is cancelled.
7. `DetectionResult` returns to daemon.

### 3.4 Trigger flow

If detection passes threshold:

1. In `test` mode:
   - prints `[TEST MODE] Would trigger Siri for: ...`.
2. In `run` mode:
   - `SiriTrigger.trigger()` checks cooldown.
   - Builds AppleScript for configured shortcut.
   - Executes `osascript`.
   - Updates last-trigger timestamp on success.
3. Optional notification is displayed if enabled.

### 3.5 Shutdown flow

1. User presses Ctrl+C.
2. Daemon `stop()` sets `running = False`.
3. Audio stream is stopped/closed.
4. Decoder thread exits after queue timeout checks.

## 4. Why confidence often shows `0.00`

This is expected in your current logs for constrained grammar use:

- The detector computes confidence only from `result["result"][*]["conf"]` entries.
- Constrained Vosk outputs often include only top-level text (`"text"`) without per-word `conf` tokens.
- In that case confidence stays `0.0` even when phrase text matches correctly.

That is why phrase acceptance is currently driven more by exact transcript matching plus fallback verification than by confidence.

## 5. Practical tuning knobs that matter most

### 5.1 `config.json` fields with highest impact

- `audio.device_id`
  - Pick the actual microphone index from `python -m src.main devices`.
- `vad.aggressiveness`
  - Higher values reduce false speech detections in noisy environments.
- `vad.silence_duration_ms`
  - Higher value creates longer segments, useful for multi-word phrases.
- `detection.confidence_threshold`
  - Because confidence is often `0.0`, setting this above `0.0` can block valid detections.
- `wake_phrases`
  - Pick phonetically distinct words to reduce false triggers.

### 5.2 Current working local profile (as observed)

- Device pinned to built-in mic (`device_id: 0` on your machine).
- Trigger phrase testing done with short words (`hello`, `mithi`) and verbose mode.
- Siri trigger route set to double Command press.

## 6. Validation status

Latest known suite result in this worktree:

- `./venv/bin/python -m pytest -v`
- Result: `19 passed`, `1 warning` (`webrtcvad` setuptools deprecation warning)

## 7. Known limitations (current implementation)

- Grammar-constrained STT can over-map similar-sounding words to the target phrase.
  - Mitigated by fallback verification, but not eliminated.
- No persistent calibration flow yet (noise profile, threshold learning, etc.).
- No packaging/auto-start GUI yet (still CLI-first PoC).
- `config.json` has no schema validation or migration handling.

## 8. Command reference for your current workflow

Setup and run:

```bash
./setup.sh
source venv/bin/activate
python -m src.main doctor
python -m src.main devices
python -m src.main test --verbose
python -m src.main run
```

Wake phrase management:

```bash
python -m src.main phrases list
python -m src.main phrases add "computer"
python -m src.main phrases remove "computer"
```
