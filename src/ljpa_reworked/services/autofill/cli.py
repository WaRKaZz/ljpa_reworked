from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from ljpa_reworked.services.autofill.engine import fill_form_batch
from ljpa_reworked.services.autofill.profile_parser import load_candidate_profile


def _resolve_default_paths() -> tuple[str, str]:
    # Profile candidates
    for p in ["/inputs/resources/profile.md", "resources/profile.md"]:
        if Path(p).exists():
            profile_path = p
            break
    else:
        profile_path = "resources/profile.md"

    # Resume candidates
    for r in [
        "/inputs/resources/Danilov_Latest_CV.pdf",
        "resources/Danilov_Latest_CV.pdf",
    ]:
        if Path(r).exists():
            resume_path = r
            break
    else:
        resume_path = "resources/Danilov_Latest_CV.pdf"

    return profile_path, resume_path


async def run_autofill_cli(
    profile_path: str,
    resume_path: str | None = None,
    cdp_url: str = "http://cloak-browser:9222",
) -> int:
    """Connect to active browser over CDP, execute batch autofill, and print JSON report."""
    try:
        profile = load_candidate_profile(profile_path)
    except Exception as e:
        print(
            json.dumps(
                {
                    "status": "error",
                    "filled_count": 0,
                    "filled": [],
                    "uploaded": [],
                    "unresolved": [],
                    "errors": [f"Failed to load profile: {e}"],
                }
            )
        )
        return 1

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            if not browser.contexts:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "filled_count": 0,
                            "filled": [],
                            "uploaded": [],
                            "unresolved": [],
                            "errors": ["No browser context found on CDP endpoint"],
                        }
                    )
                )
                return 1

            context = browser.contexts[0]
            if not context.pages:
                print(
                    json.dumps(
                        {
                            "status": "error",
                            "filled_count": 0,
                            "filled": [],
                            "uploaded": [],
                            "unresolved": [],
                            "errors": ["No active page found in browser context"],
                        }
                    )
                )
                return 1

            page = context.pages[-1]
            await page.bring_to_front()

            result = await fill_form_batch(page, profile, resume_path)
            print(json.dumps(result.to_dict(), indent=2))
            return 0 if result.status in ("complete", "partial") else 1
    except Exception as e:
        print(
            json.dumps(
                {
                    "status": "error",
                    "filled_count": 0,
                    "filled": [],
                    "uploaded": [],
                    "unresolved": [],
                    "errors": [f"Autofill execution failed: {e}"],
                }
            )
        )
        return 1


def main() -> None:
    default_profile, default_resume = _resolve_default_paths()
    default_cdp = os.environ.get("CDP_URL", "http://cloak-browser:9222")

    parser = argparse.ArgumentParser(
        description="Generic Deterministic Form Autofill Engine"
    )
    parser.add_argument(
        "--profile",
        default=default_profile,
        help="Path to candidate profile markdown file",
    )
    parser.add_argument(
        "--resume",
        default=default_resume,
        help="Path to candidate resume PDF file",
    )
    parser.add_argument(
        "--cdp",
        default=default_cdp,
        help="CDP URL for CloakBrowser/Chromium instance",
    )

    args = parser.parse_args()
    exit_code = asyncio.run(
        run_autofill_cli(
            profile_path=args.profile,
            resume_path=args.resume,
            cdp_url=args.cdp,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
