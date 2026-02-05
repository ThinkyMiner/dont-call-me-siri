import subprocess
import logging
from src.utils import setup_logging, show_notification, is_macos


def test_setup_logging_sets_level():
    logging.getLogger().handlers.clear()
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_show_notification_ignores_failure():
    def runner(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["osascript"])
    show_notification("Title", "Message", runner=runner)


def test_is_macos_false(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    assert is_macos() is False
