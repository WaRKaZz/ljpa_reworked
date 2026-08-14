import functools
import logging
import time

logger = logging.getLogger(__name__)


def crewai_retry_handler(func):
    """Retry transient CrewAI gateway failures with bounded backoff."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except ValueError:
                raise
            except Exception:
                if attempt == 2:
                    raise
                delay = 2**attempt
                logger.warning(
                    "CrewAI attempt %d/3 failed; retrying in %ss", attempt + 1, delay
                )
                time.sleep(delay)

    return wrapper
