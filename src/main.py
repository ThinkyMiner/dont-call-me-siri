import argparse
import logging
import os
import queue
import threading

from .config import Config
from .audio_capture import AudioCapture
from .vad import VoiceActivityDetector
from .phrase_detector import PhraseDetector
from .siri_trigger import SiriTrigger
from .utils import setup_logging, show_notification


class WakePhraseDaemon:
    def __init__(self, config: Config, test_mode: bool = False, audio=None, vad=None, detector=None, trigger=None):
        self.config = config
        self.test_mode = test_mode
        self.running = False
        self.audio_queue: queue.Queue[bytes] = queue.Queue()

        self.audio = audio or AudioCapture(
            sample_rate=config.audio.sample_rate,
            chunk_duration_ms=config.audio.chunk_duration_ms,
            pre_buffer_duration_ms=config.audio.pre_buffer_duration_ms,
            device_id=config.audio.device_id,
        )
        self.vad = vad or VoiceActivityDetector(
            sample_rate=config.audio.sample_rate,
            aggressiveness=config.vad.aggressiveness,
            min_speech_duration_ms=config.vad.min_speech_duration_ms,
            silence_duration_ms=config.vad.silence_duration_ms,
        )
        self.detector = detector or PhraseDetector(
            model_path="models/vosk-model-small-en-us-0.15",
            phrases=config.wake_phrases,
            sample_rate=config.audio.sample_rate,
            debug_fallback_transcript=test_mode,
            verify_with_fallback=True,
            allow_unk_wrapped_match=getattr(config.detection, "allow_unk_wrapped_match", False),
        )
        if trigger is not None:
            self.trigger = trigger
        else:
            shortcut_key = "space"
            shortcut_modifiers = ["command"]
            trigger_method = "keyboard"
            siri_cfg = getattr(config, "siri", None)
            shortcut_cfg = getattr(siri_cfg, "keyboard_shortcut", None) if siri_cfg else None
            if siri_cfg:
                trigger_method = getattr(siri_cfg, "trigger_method", trigger_method)
            if isinstance(shortcut_cfg, dict):
                shortcut_key = shortcut_cfg.get("key", shortcut_key)
                shortcut_modifiers = shortcut_cfg.get("modifiers", shortcut_modifiers)
                if shortcut_modifiers is None:
                    shortcut_modifiers = []
            self.trigger = SiriTrigger(
                cooldown_seconds=config.detection.cooldown_seconds,
                shortcut_key=shortcut_key,
                shortcut_modifiers=shortcut_modifiers,
                trigger_method=trigger_method,
            )
        self._last_vad_state = None

    def start(self):
        self.running = True
        decoder_thread = threading.Thread(target=self._decoder_loop, daemon=True)
        decoder_thread.start()
        logging.info("Listening for: %s", ", ".join(self.config.wake_phrases))
        try:
            self.audio.start(self._on_audio)
        except RuntimeError as exc:
            logging.error("%s", exc)
            self.running = False
            return

        try:
            while self.running:
                threading.Event().wait(0.1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        logging.info("Shutting down...")
        self.running = False
        self.audio.stop()

    def _on_audio(self, chunk: bytes):
        result = self.vad.process(chunk, self.audio.get_pre_buffer())
        state = getattr(result, "state", None)
        if state is not None and state != self._last_vad_state:
            label = state.value if hasattr(state, "value") else str(state)
            logging.debug("VAD state: %s", label)
            self._last_vad_state = state
        if getattr(result, "audio_segment", None) is not None:
            logging.debug("Queued speech segment: %d bytes", len(result.audio_segment))
            self.audio_queue.put(result.audio_segment)
            self.audio.clear_pre_buffer()

    def _decoder_loop(self):
        while self.running:
            try:
                segment = self.audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            result = self.detector.detect(segment)
            logging.debug("Detected: '%s' (conf: %.2f)", result.raw_text, result.confidence)
            if result.fallback_text:
                logging.debug("Fallback transcript: '%s'", result.fallback_text)

            if result.detected and result.confidence >= self.config.detection.confidence_threshold:
                if self.test_mode:
                    print(f"[TEST MODE] Would trigger Siri for: '{result.phrase}'")
                else:
                    if self.trigger.trigger():
                        logging.info("Siri triggered")
                        if self.config.general.show_notifications:
                            show_notification("Wake Phrase Detected", f"Triggered Siri with '{result.phrase}'")


def main():
    parser = argparse.ArgumentParser(description="Custom Wake Phrase Siri Trigger")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    run_parser = subparsers.add_parser("run", help="Start listening for wake phrases")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    test_parser = subparsers.add_parser("test", help="Test mode (no Siri trigger)")
    test_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    phrases_parser = subparsers.add_parser("phrases", help="Manage wake phrases")
    phrases_sub = phrases_parser.add_subparsers(dest="phrases_command")
    phrases_sub.add_parser("list", help="List wake phrases")
    add_parser = phrases_sub.add_parser("add", help="Add a wake phrase")
    add_parser.add_argument("phrase", help="Phrase to add")
    remove_parser = phrases_sub.add_parser("remove", help="Remove a wake phrase")
    remove_parser.add_argument("phrase", help="Phrase to remove")

    subparsers.add_parser("doctor", help="Check system status")
    subparsers.add_parser("devices", help="List audio devices")

    args = parser.parse_args()

    config = Config().load()
    log_level = logging.DEBUG if getattr(args, "verbose", False) else config.general.log_level
    setup_logging(log_level)

    if args.command == "run":
        WakePhraseDaemon(config, test_mode=False).start()
    elif args.command == "test":
        WakePhraseDaemon(config, test_mode=True).start()
    elif args.command == "phrases":
        if args.phrases_command == "list":
            print("Current wake phrases:")
            for phrase in config.wake_phrases:
                print(f"  • {phrase}")
        elif args.phrases_command == "add":
            config.add_phrase(args.phrase)
            print(f"Added: {args.phrase}")
        elif args.phrases_command == "remove":
            if config.remove_phrase(args.phrase):
                print(f"Removed: {args.phrase}")
            else:
                print(f"Phrase not found: {args.phrase}")
    elif args.command == "doctor":
        print("System Check")
        print("=" * 40)
        print(f"Config loaded: {len(config.wake_phrases)} phrases")
        print(f"Phrases: {', '.join(config.wake_phrases)}")
        if SiriTrigger.check_siri_enabled():
            print("Siri enabled")
        else:
            print("Siri not enabled - enable in System Settings")
        trigger_method = getattr(config.siri, "trigger_method", "keyboard")
        if trigger_method == "open_app":
            print("Accessibility permissions not required for open_app trigger")
        else:
            if SiriTrigger.check_accessibility_permissions():
                print("Accessibility permissions granted")
            else:
                print("Accessibility permissions needed - add Terminal in System Settings")
        if os.path.exists("models/vosk-model-small-en-us-0.15"):
            print("Vosk model found")
        else:
            print("Vosk model not found - run setup.sh")
    elif args.command == "devices":
        devices = AudioCapture.list_devices()
        print("Available input devices:")
        for d in devices:
            print(f"  [{d['index']}] {d['name']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
