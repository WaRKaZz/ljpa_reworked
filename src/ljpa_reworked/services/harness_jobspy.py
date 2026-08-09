"""Backward-compatibility module forwarding to ljpa_reworked.services.jobspy."""
import ljpa_reworked.services.jobspy as _impl

scrape_jobs = _impl.scrape_jobs
save_vacancy = _impl.save_vacancy

def fetch_and_store_jobs(*args, **kwargs):
    # Dynamically bind patched globals to the implementation module
    _impl.scrape_jobs = scrape_jobs
    _impl.save_vacancy = save_vacancy
    return _impl.fetch_and_store_jobs(*args, **kwargs)

run_jobspy_harness = fetch_and_store_jobs

__all__ = ["fetch_and_store_jobs", "run_jobspy_harness", "scrape_jobs", "save_vacancy"]
