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
