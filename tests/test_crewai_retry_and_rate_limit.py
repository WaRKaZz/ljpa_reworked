from unittest.mock import patch

import pytest

from ljpa_reworked.decorators import crewai_retry_handler
from ljpa_reworked.services.dynamic_rate_limiter import DynamicRateLimiter


def test_retry_handler_waits_with_bounded_backoff():
    calls = 0

    @crewai_retry_handler
    def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("gateway")
        return "ok"

    with patch("ljpa_reworked.decorators.time.sleep") as sleep:
        assert operation() == "ok"
    assert calls == 3
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


def test_retry_handler_does_not_retry_value_error():
    @crewai_retry_handler
    def operation():
        raise ValueError("invalid profile")

    with (
        pytest.raises(ValueError, match="invalid profile"),
        patch("ljpa_reworked.decorators.time.sleep") as sleep,
    ):
        operation()
    sleep.assert_not_called()


def test_rate_limiter_acquires_before_exceeding_window():
    limiter = DynamicRateLimiter(max_requests=1, period_seconds=60)
    limiter.acquire()
    with patch("ljpa_reworked.services.dynamic_rate_limiter.time.sleep") as sleep:
        limiter.acquire()
    sleep.assert_called_once()
    assert limiter.used_requests == 1
