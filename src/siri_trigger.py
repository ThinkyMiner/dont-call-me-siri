import time
import subprocess
from typing import Callable, Optional


class SiriTrigger:
    def __init__(
        self,
        cooldown_seconds: float = 3.0,
        shortcut_key: str = "space",
        shortcut_modifiers: Optional[list[str]] = None,
        runner: Callable = subprocess.run,
        time_fn: Callable = time.time,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.shortcut_key = shortcut_key
        self.shortcut_modifiers = shortcut_modifiers or ["command"]
        self._last_trigger_time = None
        self._runner = runner
        self._time_fn = time_fn

    def trigger(self) -> bool:
        now = self._time_fn()
        if self.is_in_cooldown(now):
            return False

        key = self.shortcut_key
        modifier = self.shortcut_modifiers[0]
        script = (
            'tell application "System Events"\n'
            f'    key down {modifier}\n'
            f'    keystroke "{key}"\n'
            '    delay 0.3\n'
            f'    key up {modifier}\n'
            'end tell\n'
        )

        try:
            self._runner(["osascript", "-e", script], check=True, capture_output=True)
            self._last_trigger_time = now
            return True
        except subprocess.CalledProcessError:
            return False

    def is_in_cooldown(self, now: Optional[float] = None) -> bool:
        if self._last_trigger_time is None:
            return False
        if now is None:
            now = self._time_fn()
        return (now - self._last_trigger_time) < self.cooldown_seconds

    @staticmethod
    def check_siri_enabled(runner: Callable = subprocess.run) -> bool:
        try:
            result = runner(
                ["defaults", "read", "com.apple.assistant.support", "Assistant Enabled"],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() == "1"
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def check_accessibility_permissions(runner: Callable = subprocess.run) -> bool:
        try:
            result = runner(
                ["osascript", "-e", "tell application \"System Events\" to return UI elements enabled"],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip().lower() == "true"
        except subprocess.CalledProcessError:
            return False
