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


def test_detect_unknown_phrase_includes_fallback_transcript():
    constrained = json.dumps({
        "text": "[unk]",
        "result": [],
    })
    fallback = json.dumps({
        "text": "hey nervous",
        "result": [],
    })

    def constrained_factory(_model, _rate, _grammar):
        return FakeRecognizer(constrained)

    def fallback_factory(_model, _rate):
        return FakeRecognizer(fallback)

    detector = PhraseDetector(
        model_path="/tmp/does-not-matter",
        phrases=["hey jarvis"],
        sample_rate=16000,
        model=object(),
        recognizer_factory=constrained_factory,
        debug_fallback_transcript=True,
        fallback_recognizer_factory=fallback_factory,
    )

    res = detector.detect(b"audio")
    assert res.detected is False
    assert res.raw_text == "[unk]"
    assert res.fallback_text == "hey nervous"


def test_detect_matches_when_phrase_is_wrapped_by_unk_tokens():
    wrapped = json.dumps({
        "text": "[unk] hello [unk]",
        "result": [],
    })

    def factory(_model, _rate, _grammar):
        return FakeRecognizer(wrapped)

    detector = PhraseDetector(
        model_path="/tmp/does-not-matter",
        phrases=["hello"],
        sample_rate=16000,
        model=object(),
        recognizer_factory=factory,
        allow_unk_wrapped_match=True,
    )

    res = detector.detect(b"audio")
    assert res.detected is True
    assert res.phrase == "hello"


def test_detect_rejects_wrapped_unk_by_default_for_strictness():
    wrapped = json.dumps({
        "text": "[unk] hello [unk]",
        "result": [],
    })

    def factory(_model, _rate, _grammar):
        return FakeRecognizer(wrapped)

    detector = PhraseDetector(
        model_path="/tmp/does-not-matter",
        phrases=["hello"],
        sample_rate=16000,
        model=object(),
        recognizer_factory=factory,
    )

    res = detector.detect(b"audio")
    assert res.detected is False
    assert res.phrase is None


def test_detect_rejected_when_fallback_disagrees():
    constrained = json.dumps({
        "text": "hello",
        "result": [],
    })
    fallback = json.dumps({
        "text": "yellow",
        "result": [],
    })

    def constrained_factory(_model, _rate, _grammar):
        return FakeRecognizer(constrained)

    def fallback_factory(_model, _rate):
        return FakeRecognizer(fallback)

    detector = PhraseDetector(
        model_path="/tmp/does-not-matter",
        phrases=["hello"],
        sample_rate=16000,
        model=object(),
        recognizer_factory=constrained_factory,
        verify_with_fallback=True,
        fallback_recognizer_factory=fallback_factory,
    )

    res = detector.detect(b"audio")
    assert res.detected is False
    assert res.phrase is None
    assert res.fallback_text == "yellow"
