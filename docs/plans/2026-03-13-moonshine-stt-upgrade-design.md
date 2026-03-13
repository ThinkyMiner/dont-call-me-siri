# Moonshine Tiny STT Upgrade Design

**Date:** 2026-03-13
**Goal:** Replace Vosk with Moonshine Tiny for dramatically better accuracy and real confidence scores.

## Problem

Vosk's constrained grammar approach has fundamental accuracy issues:
- Confidence is always 0.0 in constrained mode — `confidence_threshold` is useless
- Constrained grammar forces output to configured phrases or `[unk]` — over-matches similar-sounding words
- Fallback verification (second recognition pass) doubles compute for marginal benefit
- Kaldi-based engine has inherently lower accuracy than modern transformer models

## Solution

Replace Vosk with Moonshine Tiny — a 27M parameter transformer model purpose-built for edge/on-device speech recognition.

### Architecture

Same pipeline shape, better engine:

```
Mic → AudioCapture (pre-buffer) → webrtcvad → Queue → Moonshine Tiny → Phrase Match → Siri
```

### What Changes

| Component | Current | New |
|-----------|---------|-----|
| STT Engine | Vosk (constrained grammar + [unk]) | Moonshine Tiny (full transcription) |
| Phrase Matching | Exact text match after constrained decode | Substring match on real transcription |
| Confidence | Always 0.0, useless | Real scores, threshold filtering works |
| Fallback verifier | Second Vosk pass (unconstrained) | Not needed |
| Dependencies | `vosk` | `moonshine-onnx` (+ `onnxruntime`) |
| VAD | webrtcvad (unchanged) | No change |
| AudioCapture | unchanged | No change |
| SiriTrigger | unchanged | No change |

### PhraseDetector Rewrite

New `detect()` flow:
1. Convert audio_segment (int16 bytes) → float32 numpy array
2. `moonshine.transcribe(audio)` → full text transcription
3. Normalize text (lowercase, strip punctuation)
4. Match against wake phrases:
   - Exact match first: `"jarvis" == "jarvis"`
   - Contains match second: `"jarvis"` in `"hey jarvis"`
5. Return DetectionResult with real confidence

### Config Changes

- Remove `allow_unk_wrapped_match` (no longer relevant)
- `confidence_threshold` becomes meaningful (default 0.5)
- Model path changes from Vosk to Moonshine
- Remove `verify_with_fallback` and `debug_fallback_transcript`

### Dependency Changes

**requirements.txt:**
- Remove: `vosk>=0.3.44`
- Add: `moonshine-onnx`

### Setup Changes

- `setup.sh` no longer downloads Vosk model
- Moonshine ONNX model is bundled with the pip package (no separate download)

### Doctor Command Updates

- Check for moonshine-onnx import instead of Vosk model directory
- Remove Vosk model path check

### Testing

- Update `test_phrase_detector.py` for new Moonshine-based API
- Mock `moonshine_onnx.MoonshineOnnxModel` instead of `KaldiRecognizer`
- Test: exact match, contains match, no match, empty audio, confidence filtering
- All VAD/audio/trigger tests unchanged

### Moonshine Tiny Stats

- Parameters: 27.1M
- Model size: ~60 MB (ONNX, bundled with pip package)
- RAM for transcription: <8 MB target
- Speed: 5x faster than Whisper Tiny
- Variable-length encoder (no 30s padding waste)
- License: MIT
