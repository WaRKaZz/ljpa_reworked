import logging
import time

logger = logging.getLogger(__name__)


class DynamicRateLimiter:
    """Fixed-window request permit limiter for CrewAI kickoff calls."""

    def __init__(self, max_requests: int = 14, period_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.period = period_seconds
        self.used_requests = 0
        self.start_time = time.monotonic()
        self.successful_requests = 0

    def acquire(self) -> None:
        elapsed = time.monotonic() - self.start_time
        if elapsed >= self.period:
            self.used_requests = 0
            self.start_time = time.monotonic()
        if self.used_requests >= self.max_requests:
            wait_time = self.period - elapsed
            if wait_time > 0:
                logger.info("Rate limit reached. Waiting %.3fs", wait_time)
                time.sleep(wait_time)
            self.used_requests = 0
            self.start_time = time.monotonic()
        self.used_requests += 1

    def record(self, count: int = 0) -> None:
        """Record output metrics after a completed kickoff without granting a permit."""
        if isinstance(count, int):
            self.successful_requests += max(0, count)
