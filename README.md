# Custom Wake Phrase Siri Trigger

A macOS-only proof of concept that triggers Siri when any configured wake phrase is detected. It uses VAD-gated, constrained Vosk recognition to stay lightweight and offline.

## Requirements

- macOS 12+
- Python 3.10+
- Siri enabled
- Microphone + Accessibility permissions

## Quickstart

```bash
./setup.sh
source venv/bin/activate
python -m src.main run
```

Test mode (no Siri trigger):

```bash
python -m src.main test --verbose
```

Manage phrases:

```bash
python -m src.main phrases list
python -m src.main phrases add "computer"
python -m src.main phrases remove "bhature"
```
