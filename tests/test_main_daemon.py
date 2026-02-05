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
    class detection:
        confidence_threshold = 0.5

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
