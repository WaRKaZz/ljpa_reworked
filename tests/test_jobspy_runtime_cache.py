def test_default_jobspy_cache_is_in_writable_data_directory():
    from ljpa_reworked.services.jobspy import DEFAULT_CACHE_PATH, PROJECT_ROOT

    assert DEFAULT_CACHE_PATH == PROJECT_ROOT / "data" / "profile_search_query.json"
