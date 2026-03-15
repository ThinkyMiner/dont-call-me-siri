# dont-call-me-siri

Offline custom wake-phrase trigger for Siri on macOS.

Uses a lightweight pipeline with Moonshine Tiny (transformer-based STT):

`Microphone -> VAD -> Moonshine Tiny STT -> Siri trigger`

## What It Does

- Runs fully offline on-device.
- Lets you define one or many wake phrases in `config.json`.
- Uses VAD gating to avoid constant speech decoding.
- Full-vocabulary transcription — any English word works as a wake phrase.
- Supports test mode (`no Siri trigger`) and run mode (`trigger Siri`).
- Supports two Siri trigger methods:
  - `open_app` (recommended reliability)
  - `keyboard` (shortcut simulation)

## Requirements

- macOS 12+
- Python 3.10+
- Siri enabled on your Mac
- Microphone permission for the terminal app you run from
- Accessibility permission only if using `keyboard` trigger method

## Quick Start

```bash
./setup.sh
source venv/bin/activate
python -m src.main doctor
python -m src.main run
```

The Moonshine Tiny model (~60 MB) downloads automatically on first run.

## Core Commands

Run normally (triggers Siri):

```bash
python -m src.main run
```

Run in test mode (no Siri trigger):

```bash
python -m src.main test --verbose
```

Wake phrase management:

```bash
python -m src.main phrases list
python -m src.main phrases add "computer"
python -m src.main phrases remove "bhature"
```

Diagnostics:

```bash
python -m src.main doctor
python -m src.main devices
```

## Configuration

All runtime configuration is in `config.json`.

### 1) Wake phrases

```json
"wake_phrases": ["hello", "jarvis"]
```

Any English word or short phrase works — Moonshine does full-vocabulary transcription.

### 2) Audio input

```json
"audio": {
  "sample_rate": 16000,
  "chunk_duration_ms": 30,
  "pre_buffer_duration_ms": 400,
  "device_id": null
}
```

- Use `python -m src.main devices` to list microphone device IDs.
- Set `device_id` explicitly if the wrong input is being used.

### 3) Sensitivity tuning

```json
"vad": {
  "aggressiveness": 3,
  "min_speech_duration_ms": 240,
  "silence_duration_ms": 650
},
"detection": {
  "confidence_threshold": 0.5,
  "cooldown_seconds": 3.0
}
```

- Higher `aggressiveness` reduces false speech activation in noisy rooms.
- `confidence_threshold` filters low-confidence detections (0.0-1.0).

### 4) Siri trigger mode

#### Recommended (`open_app`)

```json
"siri": {
  "trigger_method": "open_app",
  "keyboard_shortcut": {
    "key": "command",
    "modifiers": []
  }
}
```

- Uses `open -a Siri`
- Does not require Accessibility permissions

#### Keyboard simulation (`keyboard`)

```json
"siri": {
  "trigger_method": "keyboard",
  "keyboard_shortcut": {
    "key": "space",
    "modifiers": ["command"]
  }
}
```

- Requires Accessibility permissions for terminal/Python process
- Can also simulate double-modifier presses (for systems using that Siri shortcut)

## First-Time Validation Flow

1. Confirm health:

```bash
python -m src.main doctor
```

2. Confirm input device list:

```bash
python -m src.main devices
```

3. Verify phrase detection without Siri trigger:

```bash
python -m src.main test --verbose
```

Look for lines like:

`[TEST MODE] Would trigger Siri for: 'hello'`

4. Start real mode:

```bash
python -m src.main run
```

## Troubleshooting

### No detections at all

- Check microphone route and `audio.device_id`.
- Run `python -m src.main devices` and pin a valid input device.
- Run `python -m src.main test --verbose` and verify VAD state changes.

### Phrase not recognized

- Speak clearly and close to the microphone.
- Try common words first (`hello`, `jarvis`, `computer`).
- Lower `vad.aggressiveness` if speech segments aren't being captured.

### Too many false triggers

- Increase `vad.aggressiveness`.
- Increase `vad.min_speech_duration_ms`.
- Increase `vad.silence_duration_ms`.

### Siri says triggered but Siri UI does not open

- Switch to:

```json
"trigger_method": "open_app"
```

- If using `keyboard`, verify Accessibility and the exact Siri shortcut mapping.

## Development

Run tests:

```bash
./venv/bin/python -m pytest -q
```

Detailed implementation notes are in:

`docs/implementation-detailed.md`
