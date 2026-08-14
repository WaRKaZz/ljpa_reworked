import argparse
import json
import logging
import os
import shutil
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ljpa_reworked.services.harness.protocol import parse_terminal_result

logger = logging.getLogger(__name__)

SCRAPER_CONTAINER_DB = Path("/runtime/harness-scraper/app.db")
HARNESS_MODEL = "gemini-3.6-flash-medium"


def get_gemini_quota_remaining(api_url: str) -> float:
    """Read Antigravity's Gemini five-hour quota fraction through the harness."""
    usage_url = f"{api_url.rsplit('/', 1)[0]}/usage"
    request = urllib.request.Request(usage_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            remaining = float(json.loads(response.read())["remaining_fraction"])
    except (
        KeyError,
        TypeError,
        ValueError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(
            "Could not read Antigravity Gemini five-hour quota."
        ) from error
    if not 0 <= remaining <= 1:
        raise RuntimeError("Antigravity returned an invalid Gemini quota fraction.")
    return remaining


def _validate_sqlite(database_path: Path) -> None:
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise RuntimeError(f"SQLite integrity check failed for {database_path}")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError(f"SQLite foreign key check failed for {database_path}")


def prepare_scraper_database(canonical_path: Path, scraper_path: Path) -> None:
    """Copy a validated canonical database into the scraper-only mount."""
    _validate_sqlite(canonical_path)
    scraper_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(canonical_path, scraper_path)
    _validate_sqlite(scraper_path)


def publish_scraper_database(canonical_path: Path, scraper_path: Path) -> None:
    """Atomically publish a validated scraper result to the canonical database."""
    _validate_sqlite(scraper_path)
    next_path = canonical_path.with_suffix(".db.next")
    try:
        shutil.copy2(scraper_path, next_path)
        _validate_sqlite(next_path)
        os.replace(next_path, canonical_path)
    finally:
        next_path.unlink(missing_ok=True)
        scraper_path.unlink(missing_ok=True)


def run_linkedin_harness(
    prompt_file: str = "/app/prompts/harness_scraper.md",
    timeout: str = "8h",
    api_url: str = "http://antigravity-cli:8080/run-harness",
    canonical_db_path: Path | None = None,
    scraper_db_path: Path | None = None,
) -> int:
    """Run scraper against an isolated DB copy, then publish only on success."""
    if canonical_db_path is None:
        canonical_db_path = Path("data/app.db")
    if scraper_db_path is None:
        scraper_db_path = Path("runtime/harness-scraper/app.db")

    try:
        prepare_scraper_database(canonical_db_path, scraper_db_path)
    except (OSError, RuntimeError, sqlite3.Error) as error:
        logger.error("Could not prepare scraper database: %s", error)
        return 1

    payload = json.dumps(
        {"prompt_file": prompt_file, "timeout": timeout, "model": HARNESS_MODEL}
    ).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    logger.info("Sending scraper harness request to %s", api_url)
    agy_success = False
    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                decoded_line = line.decode("utf-8")
                sys.stdout.write(decoded_line)
                sys.stdout.flush()
                is_terminal, is_success = parse_terminal_result(decoded_line)
                if is_terminal:
                    if is_success:
                        agy_success = True
                        break
                    else:
                        raise RuntimeError("AGY process returned terminal error result")
        if not agy_success:
            logger.warning("Stream ended without terminal AGY result event")
            scraper_db_path.unlink(missing_ok=True)
            return 1

        publish_scraper_database(canonical_db_path, scraper_db_path)
        return 0
    except (urllib.error.URLError, OSError, RuntimeError, sqlite3.Error) as error:
        logger.error(
            "Scraper harness failed; canonical database was retained: %s", error
        )
        scraper_db_path.unlink(missing_ok=True)
        return 1


def harness_submit(
    vacancy_url: str,
    resume_path: str,
    prompt_file: str = "/app/prompts/harness_submit.md",
    timeout: str = "1h",
    api_url: str = "http://antigravity-cli:8080/run-harness",
) -> int:
    """Submit exactly one vacancy; normal harness completion counts as submitted."""
    payload = json.dumps(
        {
            "prompt_file": prompt_file,
            "timeout": timeout,
            "vacancy_url": vacancy_url,
            "resume_path": resume_path,
            "model": HARNESS_MODEL,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    logger.info(
        "Sending submission harness request to %s for URL %s", api_url, vacancy_url
    )
    completed = False
    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                decoded_line = line.decode("utf-8")
                sys.stdout.write(decoded_line)
                sys.stdout.flush()
                try:
                    completed |= json.loads(decoded_line).get("status") == "success"
                except json.JSONDecodeError:
                    pass
        return 0 if completed else 1
    except urllib.error.URLError as error:
        logger.error("Failed to connect to Antigravity API: %s", error)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Harness AGY HTTP Runner")
    parser.add_argument("--prompt-file", default="/app/prompts/harness_scraper.md")
    parser.add_argument("--timeout", default="1h")
    parser.add_argument("--api-url", default="http://antigravity-cli:8080/run-harness")
    parser.add_argument(
        "--url", help="Target vacancy URL for manual one-vacancy submission"
    )
    parser.add_argument(
        "--pdf-path",
        help="Path to rendered PDF resume for manual one-vacancy submission",
    )
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
    sys.exit(
        run_linkedin_harness(
            prompt_file=args.prompt_file,
            timeout=args.timeout,
            api_url=args.api_url,
        )
    )


if __name__ == "__main__":
    main()
