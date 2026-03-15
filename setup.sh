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
