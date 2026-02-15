from src.audio_capture import AudioCapture
import pytest
import sounddevice as sd


def test_pre_buffer_rolls_and_callback_called(monkeypatch):
    chunks = []

    class FakeStream:
        def __init__(self, *args, **kwargs):
            self.callback = kwargs["callback"]
            self.started = False

        def start(self):
            self.started = True

        def stop(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("sounddevice.RawInputStream", FakeStream)

    capture = AudioCapture(sample_rate=16000, chunk_duration_ms=10, pre_buffer_duration_ms=20)

    def cb(data):
        chunks.append(data)

    capture.start(cb)

    chunk_bytes = b"\x00\x00" * capture.chunk_size
    capture._handle_audio(chunk_bytes, capture.chunk_size, None, None)
    capture._handle_audio(chunk_bytes, capture.chunk_size, None, None)
    capture._handle_audio(chunk_bytes, capture.chunk_size, None, None)

    assert len(chunks) == 3
    assert len(capture.pre_buffer) == 2
    assert len(capture.get_pre_buffer()) == len(chunk_bytes) * 2


def test_start_raises_helpful_error_when_no_input_device(monkeypatch):
    class BrokenStream:
        def __init__(self, *args, **kwargs):
            raise sd.PortAudioError("Error querying device -1")

    monkeypatch.setattr("sounddevice.RawInputStream", BrokenStream)
    monkeypatch.setattr("sounddevice.query_devices", lambda: [])

    capture = AudioCapture()

    with pytest.raises(RuntimeError, match="No input audio devices"):
        capture.start(lambda _data: None)
