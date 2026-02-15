import time
import subprocess
from typing import Callable, Optional


class SiriTrigger:
    def __init__(
        self,
        cooldown_seconds: float = 3.0,
        shortcut_key: str = "space",
        shortcut_modifiers: Optional[list[str]] = None,
        trigger_method: str = "keyboard",
        runner: Callable = subprocess.run,
        time_fn: Callable = time.time,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.shortcut_key = shortcut_key
        self.shortcut_modifiers = ["command"] if shortcut_modifiers is None else shortcut_modifiers
        self.trigger_method = trigger_method
        self._last_trigger_time = None
        self._runner = runner
        self._time_fn = time_fn

    def trigger(self) -> bool:
        now = self._time_fn()
        if self.is_in_cooldown(now):
            return False

        try:
            if self.trigger_method == "open_app":
                self._runner(["open", "-a", "Siri"], check=True, capture_output=True)
            else:
                script = self._build_script()
                self._runner(["osascript", "-e", script], check=True, capture_output=True)
            self._last_trigger_time = now
            return True
        except subprocess.CalledProcessError:
            return False

    def _build_script(self) -> str:
        modifier_keys = {"command", "option", "control", "shift", "fn"}
        key_name = self.shortcut_key.lower().strip()
        if key_name in modifier_keys and not self.shortcut_modifiers:
            return (
                'tell application "System Events"\n'
                f'    key down {key_name}\n'
                f'    key up {key_name}\n'
                '    delay 0.12\n'
                f'    key down {key_name}\n'
                f'    key up {key_name}\n'
                'end tell\n'
            )

        key_literal = " " if key_name == "space" else self.shortcut_key
        key_literal = key_literal.replace("\\", "\\\\").replace('"', '\\"')

        if self.shortcut_modifiers:
            down = "".join(f"    key down {modifier}\n" for modifier in self.shortcut_modifiers)
            up = "".join(f"    key up {modifier}\n" for modifier in reversed(self.shortcut_modifiers))
            return (
                'tell application "System Events"\n'
                f"{down}"
                f'    keystroke "{key_literal}"\n'
                '    delay 0.12\n'
                f"{up}"
                'end tell\n'
            )

        return (
            'tell application "System Events"\n'
            f'    keystroke "{key_literal}"\n'
            'end tell\n'
        )

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
