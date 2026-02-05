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
