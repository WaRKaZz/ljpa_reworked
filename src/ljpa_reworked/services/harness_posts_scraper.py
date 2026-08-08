"""Backward-compatibility module forwarding to ljpa_reworked.services.harness.posts_scraper."""
from ljpa_reworked.services.harness.posts_scraper import run_agy_harness_1, run_agy_harness_sdk, run_linkedin_posts_agent

__all__ = ["run_agy_harness_1", "run_agy_harness_sdk", "run_linkedin_posts_agent"]

