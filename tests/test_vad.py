from src.vad import VoiceActivityDetector, VADState


class FakeVad:
    def __init__(self, sequence):
        self._seq = list(sequence)

    def is_speech(self, _chunk, _rate):
        return self._seq.pop(0) if self._seq else False


def test_vad_emits_segment_after_trailing_silence():
    vad = VoiceActivityDetector(
        sample_rate=16000,
        aggressiveness=2,
        min_speech_duration_ms=60,
        silence_duration_ms=60,
        vad_impl=FakeVad([False, True, True, False, False]),
        chunk_duration_ms=30,
    )

    pre = b"pre"
    chunk = b"\x00\x00" * 480

    assert vad.process(chunk, pre).state == VADState.IDLE
    assert vad.process(chunk, pre).state == VADState.SPEAKING
    assert vad.process(chunk, pre).state == VADState.SPEAKING
    result = vad.process(chunk, pre)
    assert result.state == VADState.TRAILING
    final = vad.process(chunk, pre)

    assert final.state == VADState.IDLE
    assert final.audio_segment is not None
    assert final.audio_segment.startswith(pre)
