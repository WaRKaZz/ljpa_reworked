import functools
import logging
import time

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def crewai_retry_handler(func):
    """CrewAI retry decorator.

    A decorator to handle errors and retry a function call up to 3 times
    with a 60-second delay between retries.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        retries = 3
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error(f"Attempt {i + 1} of {retries} failed with error: {e}")
                if i < retries - 1:
                    logging.info("Retrying in 60 seconds...")
                    time.sleep(60)
                else:
                    logging.error("All retries failed.")
                    raise

    return wrapper
