def test_harness_subpackage_exports():
    from ljpa_reworked.services.harness import run_linkedin_posts_agent
    from ljpa_reworked.services.jobspy import fetch_and_store_jobs
    assert callable(run_linkedin_posts_agent)
    assert callable(fetch_and_store_jobs)
