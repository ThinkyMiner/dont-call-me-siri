import logging
import subprocess
from src.siri_trigger import SiriTrigger


def test_trigger_respects_cooldown():
    calls = []

    def runner(*args, **kwargs):
        calls.append(args)
        return None

    times = [0.0, 0.1, 5.0]

    def time_fn():
        return times.pop(0)

    trigger = SiriTrigger(cooldown_seconds=1.0, runner=runner, time_fn=time_fn)

    assert trigger.trigger() is True
    assert trigger.trigger() is False
    assert trigger.trigger() is True
    assert len(calls) == 2


def test_trigger_supports_double_command_shortcut():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return None

    trigger = SiriTrigger(
        cooldown_seconds=0.0,
        shortcut_key="command",
        shortcut_modifiers=[],
        runner=runner,
        time_fn=lambda: 0.0,
    )

    assert trigger.trigger() is True
    script = calls[0][2]
    assert script.count("key down command") == 2
    assert script.count("key up command") == 2
    assert "keystroke" not in script


def test_trigger_logs_error_when_subprocess_fails(caplog):
    def failing_runner(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr=b"Siri not available")

    trigger = SiriTrigger(
        cooldown_seconds=0.0,
        trigger_method="open_app",
        runner=failing_runner,
        time_fn=lambda: 0.0,
    )

    with caplog.at_level(logging.ERROR):
        result = trigger.trigger()

    assert result is False
    assert len(caplog.records) > 0
    assert caplog.records[0].levelno == logging.ERROR


def test_trigger_open_app_method_uses_open_command():
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return None

    trigger = SiriTrigger(
        cooldown_seconds=0.0,
        trigger_method="open_app",
        runner=runner,
        time_fn=lambda: 0.0,
    )

    assert trigger.trigger() is True
    assert calls == [["open", "-a", "Siri"]]


def test_check_voice_mode_returns_true_when_type_to_siri_disabled():
    """Voice mode is active when TypeToSiriEnabled is 0."""
    received = []

    def runner(cmd, **kwargs):
        received.append(cmd)
        class R:
            stdout = "0\n"
        return R()

    assert SiriTrigger.check_voice_mode(runner=runner) is True
    assert received == [["defaults", "read", "com.apple.Accessibility", "TypeToSiriEnabled"]]


def test_check_voice_mode_returns_false_when_type_to_siri_enabled():
    """Voice mode is inactive when TypeToSiriEnabled is 1."""
    received = []

    def runner(cmd, **kwargs):
        received.append(cmd)
        class R:
            stdout = "1\n"
        return R()

    assert SiriTrigger.check_voice_mode(runner=runner) is False
    assert received == [["defaults", "read", "com.apple.Accessibility", "TypeToSiriEnabled"]]


def test_check_voice_mode_returns_false_when_key_missing():
    """Key absent means macOS default — still text mode on Apple Intelligence systems."""
    def runner(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)
    assert SiriTrigger.check_voice_mode(runner=runner) is False


def test_set_voice_mode_writes_correct_defaults_key():
    """set_voice_mode() writes TypeToSiriEnabled=false and kills the accessibility agent."""
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)

    SiriTrigger.set_voice_mode(runner=runner)

    write_calls = [c for c in calls if "defaults" in c and "write" in c]
    assert len(write_calls) == 1, "Expected exactly one defaults write call"
    write_cmd = write_calls[0]
    assert "TypeToSiriEnabled" in write_cmd
    assert "-bool" in write_cmd and "false" in write_cmd, \
        "Expected TypeToSiriEnabled to be set to false"
    assert any("killall" in " ".join(c) for c in calls), \
        "Expected killall to restart the accessibility agent"
