import json
from src.config import Config, DetectionConfig


def test_load_and_save_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "wake_phrases": ["alpha"],
                "audio": {
                    "sample_rate": 16000,
                    "chunk_duration_ms": 30,
                    "pre_buffer_duration_ms": 400,
                    "device_id": None,
                },
                "vad": {
                    "aggressiveness": 2,
                    "min_speech_duration_ms": 200,
                    "silence_duration_ms": 500,
                },
                "detection": {"confidence_threshold": 0.5, "cooldown_seconds": 3.0},
                "siri": {
                    "trigger_method": "keyboard",
                    "keyboard_shortcut": {"key": "space", "modifiers": ["command"]},
                },
                "general": {"log_level": "INFO", "show_notifications": True},
            }
        )
    )

    config = Config(config_path=str(path)).load()
    assert config.wake_phrases == ["alpha"]

    config.add_phrase("beta")
    reloaded = Config(config_path=str(path)).load()
    assert "beta" in reloaded.wake_phrases

    assert reloaded.remove_phrase("alpha") is True
    assert reloaded.remove_phrase("missing") is False


def test_detection_config_has_no_allow_unk_wrapped_match():
    """allow_unk_wrapped_match was a Vosk-specific option and should be removed."""
    dc = DetectionConfig()
    assert not hasattr(dc, "allow_unk_wrapped_match")
    assert dc.confidence_threshold == 0.5
