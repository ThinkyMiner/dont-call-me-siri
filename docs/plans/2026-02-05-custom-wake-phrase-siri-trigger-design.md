# Custom Wake Phrase Siri Trigger - Design

## Goal
Build a macOS-only Python proof of concept that triggers Siri when a user speaks any configurable wake phrase. The system is fully offline and avoids model training by using Vosk with a constrained grammar and a VAD gate to minimize CPU use.

## Non-Goals
- No Siri conversation handling (only triggering).
- No per-phrase actions (all phrases trigger Siri).
- No cross-platform support.
- No production-grade deployment.

## High-Level Architecture
Audio is continuously captured at 16 kHz mono in 30 ms frames. A webrtcvad gate determines when speech starts and ends. When a speech segment ends, we prepend a rolling pre-buffer (to capture phrase onset) and send the full segment to Vosk. Vosk uses a constrained grammar consisting only of configured phrases plus `[unk]`. If the recognized text exactly matches a configured phrase and the confidence exceeds a threshold, Siri is triggered via AppleScript keyboard simulation. A cooldown prevents rapid retriggers.

Pipeline:
1. Audio capture (callback-based, non-blocking)
2. VAD state machine (IDLE -> SPEAKING -> TRAILING)
3. Phrase detection with constrained Vosk grammar
4. Siri trigger with cooldown

## Components
- `audio_capture.py`: Uses `sounddevice.RawInputStream` for 16-bit PCM audio. Maintains a rolling pre-buffer (`deque`) sized by `pre_buffer_duration_ms`. Calls a callback per chunk.
- `vad.py`: Wraps `webrtcvad.Vad` and tracks speech state. When trailing silence exceeds threshold, returns a complete audio segment including pre-buffer.
- `phrase_detector.py`: Loads the Vosk model once, creates a `KaldiRecognizer` with constrained grammar (`phrases + ["[unk]"]`). Extracts recognized text and average confidence, resets recognizer after each segment.
- `siri_trigger.py`: Triggers Siri using `osascript` keyboard shortcut. Enforces cooldown and handles errors (e.g., missing permissions).
- `config.py`: Typed configuration loader/saver backed by `config.json`.
- `utils.py`: Logging setup and optional macOS notifications.
- `main.py`: CLI entry point and orchestration (run, test, phrases, doctor, devices).

## Data Flow
- Audio capture callback receives 30 ms PCM chunks.
- Each chunk is appended to the pre-buffer and passed to VAD.
- When VAD ends a speech segment, it returns the combined pre-buffer + speech audio.
- The segment is pushed to a queue for a decoder thread.
- The decoder thread runs Vosk, checks for exact phrase match and confidence threshold, then triggers Siri or logs in test mode.

## Error Handling
- Microphone access errors: surface clear instructions to enable mic permissions.
- Missing Vosk model: `doctor` reports and suggests running `setup.sh`.
- Siri disabled or missing accessibility permissions: `doctor` reports with instructions.
- AppleScript errors: logged but do not crash the daemon.

## CLI Commands
- `run`: Start listening and trigger Siri on detection.
- `test`: Run detection without triggering Siri.
- `phrases list|add|remove`: Manage wake phrases in `config.json`.
- `doctor`: Check Siri enabled, accessibility permission, and model availability.
- `devices`: List available input devices.

## Testing Strategy
- Run `setup.sh` to install dependencies and download the Vosk model.
- `python -m src.main devices` to confirm mic index.
- `python -m src.main test --verbose` to observe detection and tune thresholds.
- `python -m src.main doctor` to verify system setup.

## Success Criteria
- Saying any configured wake phrase triggers Siri reliably.
- CPU usage remains low when idle (VAD gating).
- Configuration changes persist and take effect.
- Clean shutdown on Ctrl+C.
