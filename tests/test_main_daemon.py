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
