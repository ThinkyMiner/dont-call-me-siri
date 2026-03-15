from src.phrase_detector import PhraseDetector


class FakeTokenizer:
    def __init__(self, text=""):
        self._text = text

    def decode_batch(self, token_batches):
        return [self._text for _ in token_batches]


class FakeModel:
    """Fake MoonshineOnnxModel that returns preset tokens."""

    def generate(self, audio, max_len=None):
        return [[1, 100, 2]]  # start, token, eos


def _make_detector(text, phrases):
    model = FakeModel()
    tokenizer = FakeTokenizer(text)
    return PhraseDetector(phrases=phrases, model=model, tokenizer=tokenizer)


def test_detect_exact_match():
    detector = _make_detector("hello", ["hello"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True
    assert res.phrase == "hello"
    assert res.raw_text == "hello"


def test_detect_contains_match():
    detector = _make_detector("hey jarvis how are you", ["jarvis"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True
    assert res.phrase == "jarvis"


def test_detect_no_match():
    detector = _make_detector("the weather is nice today", ["hello", "jarvis"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is False
    assert res.phrase is None


def test_detect_empty_transcription():
    detector = _make_detector("", ["hello"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is False
    assert res.raw_text == ""


def test_detect_case_insensitive():
    detector = _make_detector("Hello", ["hello"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True
    assert res.phrase == "hello"


def test_detect_strips_punctuation():
    detector = _make_detector("hello!", ["hello"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True


def test_detect_word_boundary_prevents_partial_match():
    """'hi' should NOT match inside 'this' or 'thinking'."""
    detector = _make_detector("this is thinking", ["hi"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is False


def test_detect_word_boundary_allows_real_word():
    """'hi' should match when it appears as a standalone word."""
    detector = _make_detector("say hi there", ["hi"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True


def test_detect_empty_audio():
    detector = _make_detector("hello", ["hello"])
    res = detector.detect(b"")
    assert res.detected is False
    assert res.raw_text == ""


def test_update_phrases():
    detector = _make_detector("computer", ["hello"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is False

    detector.update_phrases(["computer"])
    res = detector.detect(b"\x00\x00" * 8000)
    assert res.detected is True


def test_current_phrases():
    detector = _make_detector("", ["hello", "jarvis"])
    assert detector.current_phrases == ["hello", "jarvis"]
