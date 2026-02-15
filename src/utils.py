import logging
import subprocess
import sys
from typing import Callable


def setup_logging(level: str | int = "INFO"):
    resolved_level = level if isinstance(level, int) else getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def show_notification(title: str, message: str, runner: Callable = subprocess.run):
    script = f'display notification "{message}" with title "{title}"'
    try:
        runner(["osascript", "-e", script], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass


def is_macos() -> bool:
    return sys.platform == "darwin"
