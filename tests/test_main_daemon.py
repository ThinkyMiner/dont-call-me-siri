import logging
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

    def is_in_cooldown(self, now=None):
        return False


class FakeConfig:
    wake_phrases = ["hello"]

    class detection:
        confidence_threshold = 0.5
        cooldown_seconds = 3.0

    class siri:
        trigger_method = "keyboard"
        keyboard_shortcut = {"key": "space", "modifiers": ["command"]}

    class general:
        show_notifications = False



class FailingTrigger:
    def trigger(self):
        return False

    def is_in_cooldown(self, now=None):
        return False


def test_daemon_logs_warning_when_trigger_fails(caplog):
    daemon = WakePhraseDaemon(
        config=FakeConfig(),
        test_mode=False,
        audio=FakeAudio(),
        vad=FakeVAD(),
        detector=FakeDetector(),
        trigger=FailingTrigger(),
    )

    detection = DetectionResult(detected=True, phrase="hello", confidence=0.9, raw_text="hello")

    with caplog.at_level(logging.WARNING):
        daemon._handle_detection(detection)

    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_daemon_logs_debug_when_trigger_in_cooldown(caplog):
    class CooldownTrigger:
        def trigger(self):
            return False

        def is_in_cooldown(self, now=None):
            return True

    daemon = WakePhraseDaemon(
        config=FakeConfig(),
        test_mode=False,
        audio=FakeAudio(),
        vad=FakeVAD(),
        detector=FakeDetector(),
        trigger=CooldownTrigger(),
    )

    detection = DetectionResult(detected=True, phrase="hello", confidence=0.9, raw_text="hello")

    with caplog.at_level(logging.DEBUG):
        daemon._handle_detection(detection)

    assert any("cooldown" in r.message.lower() for r in caplog.records)


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


def test_daemon_handles_audio_start_failure():
    class FailingAudio(FakeAudio):
        def start(self, cb):
            raise RuntimeError("No input audio devices were found")

    daemon = WakePhraseDaemon(
        config=FakeConfig(),
        test_mode=False,
        audio=FailingAudio(),
        vad=FakeVAD(),
        detector=FakeDetector(),
        trigger=FakeTrigger(),
    )

    daemon.start()
    assert daemon.running is False


def test_daemon_reads_siri_shortcut_from_config(monkeypatch):
    captured = {}

    class CaptureTrigger:
        def __init__(self, cooldown_seconds, shortcut_key, shortcut_modifiers, trigger_method):
            captured["cooldown_seconds"] = cooldown_seconds
            captured["shortcut_key"] = shortcut_key
            captured["shortcut_modifiers"] = shortcut_modifiers
            captured["trigger_method"] = trigger_method

        def trigger(self):
            return True

    class ConfigWithDoubleCommand(FakeConfig):
        class detection:
            confidence_threshold = 0.5
            cooldown_seconds = 2.0

        class siri:
            trigger_method = "open_app"
            keyboard_shortcut = {"key": "command", "modifiers": []}

    monkeypatch.setattr("src.main.SiriTrigger", CaptureTrigger)

    WakePhraseDaemon(
        config=ConfigWithDoubleCommand(),
        test_mode=True,
        audio=FakeAudio(),
        vad=FakeVAD(),
        detector=FakeDetector(),
        trigger=None,
    )

    assert captured["cooldown_seconds"] == 2.0
    assert captured["shortcut_key"] == "command"
    assert captured["shortcut_modifiers"] == []
    assert captured["trigger_method"] == "open_app"


def test_doctor_reports_voice_mode_inactive(monkeypatch, capsys):
    """doctor command prints voice mode status when Type to Siri is ON."""
    import sys
    import types
    fake_moonshine = types.ModuleType("moonshine_onnx")
    fake_moonshine.version = "test"
    monkeypatch.setitem(sys.modules, "moonshine_onnx", fake_moonshine)
    monkeypatch.setattr("src.main.SiriTrigger.check_siri_enabled", lambda: True)
    monkeypatch.setattr("src.main.SiriTrigger.check_voice_mode", lambda: False)
    monkeypatch.setattr("src.main.SiriTrigger.check_accessibility_permissions", lambda: True)

    from unittest.mock import patch
    with patch("sys.argv", ["src.main", "doctor"]):
        from src.main import main
        try:
            main()
        except SystemExit:
            pass

    out = capsys.readouterr().out
    assert "voice mode" in out.lower() or "type to siri" in out.lower()


def test_doctor_reports_voice_mode_active(monkeypatch, capsys):
    """doctor command prints active status when Type to Siri is OFF."""
    import sys
    import types
    fake_moonshine = types.ModuleType("moonshine_onnx")
    fake_moonshine.version = "test"
    monkeypatch.setitem(sys.modules, "moonshine_onnx", fake_moonshine)
    monkeypatch.setattr("src.main.SiriTrigger.check_siri_enabled", lambda: True)
    monkeypatch.setattr("src.main.SiriTrigger.check_voice_mode", lambda: True)
    monkeypatch.setattr("src.main.SiriTrigger.check_accessibility_permissions", lambda: True)

    from unittest.mock import patch
    with patch("sys.argv", ["src.main", "doctor"]):
        from src.main import main
        try:
            main()
        except SystemExit:
            pass

    out = capsys.readouterr().out
    assert "voice mode: active" in out.lower()


def test_doctor_fix_voice_mode_calls_set_voice_mode(monkeypatch, capsys):
    """doctor --fix-voice-mode calls SiriTrigger.set_voice_mode."""
    import sys
    import types
    fake_moonshine = types.ModuleType("moonshine_onnx")
    fake_moonshine.version = "test"
    monkeypatch.setitem(sys.modules, "moonshine_onnx", fake_moonshine)
    called = []
    monkeypatch.setattr("src.main.SiriTrigger.set_voice_mode", lambda: called.append(True))
    monkeypatch.setattr("src.main.SiriTrigger.check_siri_enabled", lambda: True)
    monkeypatch.setattr("src.main.SiriTrigger.check_voice_mode", lambda: False)
    monkeypatch.setattr("src.main.SiriTrigger.check_accessibility_permissions", lambda: True)

    from unittest.mock import patch
    with patch("sys.argv", ["src.main", "doctor", "--fix-voice-mode"]):
        from src.main import main
        try:
            main()
        except SystemExit:
            pass

    assert called, "Expected set_voice_mode to be called"


def test_doctor_fix_voice_mode_prints_error_on_failure(monkeypatch, capsys):
    """doctor --fix-voice-mode prints an error message if set_voice_mode raises."""
    import sys
    import types
    import subprocess as _subprocess
    fake_moonshine = types.ModuleType("moonshine_onnx")
    fake_moonshine.version = "test"
    monkeypatch.setitem(sys.modules, "moonshine_onnx", fake_moonshine)

    def failing_set_voice_mode():
        raise _subprocess.CalledProcessError(1, ["defaults", "write"])

    monkeypatch.setattr("src.main.SiriTrigger.set_voice_mode", failing_set_voice_mode)
    monkeypatch.setattr("src.main.SiriTrigger.check_siri_enabled", lambda: True)
    monkeypatch.setattr("src.main.SiriTrigger.check_voice_mode", lambda: False)
    monkeypatch.setattr("src.main.SiriTrigger.check_accessibility_permissions", lambda: True)

    from unittest.mock import patch
    with patch("sys.argv", ["src.main", "doctor", "--fix-voice-mode"]):
        from src.main import main
        try:
            main()
        except SystemExit:
            pass

    out = capsys.readouterr().out
    assert "failed" in out.lower() or "error" in out.lower()
