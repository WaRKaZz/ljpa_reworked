import argparse
import json
import logging
import sys
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def run_linkedin_harness(
    prompt_file: str = "/app/prompts/harness_scraper.md",
    timeout: str = "8h",
    api_url: str = "http://antigravity-cli:8080/run-harness",
) -> int:
    """Run the LinkedIn harness by sending a request to the Antigravity CLI container's API."""
    payload = json.dumps({
        "prompt_file": prompt_file,
        "timeout": timeout,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    logger.info(f"Sending harness execution request to {api_url}")

    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                # Streaming the logs line-by-line as they come from the server
                sys.stdout.write(line.decode("utf-8"))
                sys.stdout.flush()
        return 0
    except urllib.error.URLError as error:
        logger.error(f"Failed to connect to Antigravity API: {error}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Harness AGY HTTP Runner")
    parser.add_argument("--prompt-file", default="/app/prompts/harness_scraper.md")
    parser.add_argument("--timeout", default="8h")
    parser.add_argument("--api-url", default="http://antigravity-cli:8080/run-harness")
    args = parser.parse_args()
    sys.exit(
        run_linkedin_harness(
            prompt_file=args.prompt_file,
            timeout=args.timeout,
            api_url=args.api_url,
        )
    )
