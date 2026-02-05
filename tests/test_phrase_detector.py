import json
from src.phrase_detector import PhraseDetector


class FakeRecognizer:
    def __init__(self, result_json):
        self._result_json = result_json

    def AcceptWaveform(self, _audio):
        return True

    def FinalResult(self):
        return self._result_json

    def Reset(self):
        pass


def test_detect_matches_phrase_and_confidence():
    results = json.dumps({
        "text": "hello",
        "result": [{"conf": 0.6}, {"conf": 0.8}],
    })

    def factory(_model, _rate, grammar):
        assert "[unk]" in grammar
        return FakeRecognizer(results)

    detector = PhraseDetector(
        model_path="/tmp/does-not-matter",
        phrases=["hello"],
        sample_rate=16000,
        model=object(),
        recognizer_factory=factory,
    )

    res = detector.detect(b"audio")
    assert res.detected is True
    assert res.phrase == "hello"
    assert abs(res.confidence - 0.7) < 0.001
