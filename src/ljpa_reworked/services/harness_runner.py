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
    payload = json.dumps(
        {
            "prompt_file": prompt_file,
            "timeout": timeout,
        }
    ).encode("utf-8")

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


def harness_submit(
    vacancy_url: str,
    resume_path: str,
    prompt_file: str = "/app/prompts/harness_submit.md",
    timeout: str = "8h",
    api_url: str = "http://antigravity-cli:8080/run-harness",
) -> int:
    """Submit a vacancy application via URL harness API request."""
    payload = json.dumps(
        {
            "prompt_file": prompt_file,
            "timeout": timeout,
            "vacancy_url": vacancy_url,
            "resume_path": resume_path,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    logger.info(f"Sending submission harness request to {api_url} for URL {vacancy_url}")

    confirmed = False
    success_status = False

    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                decoded_line = line.decode("utf-8")
                sys.stdout.write(decoded_line)
                sys.stdout.flush()

                try:
                    data = json.loads(decoded_line)
                    if data.get("status") == "confirmed_submitted":
                        confirmed = True
                    elif data.get("status") == "success":
                        success_status = True
                except Exception:
                    pass

        return 0 if (confirmed or success_status) else 1
    except urllib.error.URLError as error:
        logger.error(f"Failed to connect to Antigravity API: {error}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Harness AGY HTTP Runner")
    parser.add_argument("--prompt-file", default="/app/prompts/harness_scraper.md")
    parser.add_argument("--timeout", default="8h")
    parser.add_argument("--api-url", default="http://antigravity-cli:8080/run-harness")
    parser.add_argument("--url", help="Target vacancy URL for manual one-vacancy submission")
    parser.add_argument("--pdf-path", help="Path to rendered PDF resume for manual one-vacancy submission")
    args = parser.parse_args()

    if args.url and args.pdf_path:
        prompt = (
            args.prompt_file
            if args.prompt_file != "/app/prompts/harness_scraper.md"
            else "/app/prompts/harness_submit.md"
        )
        sys.exit(
            harness_submit(
                vacancy_url=args.url,
                resume_path=args.pdf_path,
                prompt_file=prompt,
                timeout=args.timeout,
                api_url=args.api_url,
            )
        )
    else:
        sys.exit(
            run_linkedin_harness(
                prompt_file=args.prompt_file,
                timeout=args.timeout,
                api_url=args.api_url,
            )
        )


if __name__ == "__main__":
    main()
