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

echo "Downloading Vosk model (small)..."
MODEL_DIR="models/vosk-model-small-en-us-0.15"
if [ ! -d "$MODEL_DIR" ]; then
    mkdir -p models
    cd models
    curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    unzip vosk-model-small-en-us-0.15.zip
    rm vosk-model-small-en-us-0.15.zip
    cd ..
fi

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
        "confidence_threshold": 0.0,
        "cooldown_seconds": 3.0,
        "allow_unk_wrapped_match": false
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
