"""Backward-compatibility module forwarding to ljpa_reworked.services.harness.jobspy."""
import ljpa_reworked.services.harness.jobspy as _impl

scrape_jobs = _impl.scrape_jobs
save_vacancy = _impl.save_vacancy
run_jobspy_harness = _impl.run_jobspy_harness

def fetch_and_store_jobs(*args, **kwargs):
    # Dynamically bind patched globals to the implementation module
    _impl.scrape_jobs = scrape_jobs
    _impl.save_vacancy = save_vacancy
    return _impl.fetch_and_store_jobs(*args, **kwargs)

__all__ = ["fetch_and_store_jobs", "run_jobspy_harness", "scrape_jobs", "save_vacancy"]
