import time


class DynamicRateLimiter:
    def __init__(self, max_requests: int = 15, period_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.period = period_seconds
        self.used_requests = 0
        self.start_time = time.time()

    def wait_if_needed(self) -> None:
        elapsed = time.time() - self.start_time
        if elapsed > self.period:
            self.used_requests = 0
            self.start_time = time.time()
            return

        if self.used_requests >= self.max_requests:
            wait_time = self.period - elapsed
            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time:.3f}s")
                time.sleep(wait_time)
            self.used_requests = 0
            self.start_time = time.time()

    def record(self, count: int = 1) -> None:
        self.used_requests += count
        self.wait_if_needed()
