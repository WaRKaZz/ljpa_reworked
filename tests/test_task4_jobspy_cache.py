import hashlib
from unittest.mock import MagicMock

import pytest

from ljpa_reworked.models.crewai_pydantic_models import (
    JobSearchQuery,
    JobSearchQuerySet,
)
from ljpa_reworked.services.jobspy import (
    JobSpyIntegrationService,
    compute_profile_sha256,
    get_or_generate_job_search_queries,
    normalize_and_deduplicate_queries,
)


@pytest.fixture
def temp_resource_dir(tmp_path):
    res_dir = tmp_path / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)
    return res_dir


def test_compute_profile_sha256(temp_resource_dir):
    profile_path = temp_resource_dir / "profile.md"
    content = "Senior Python & AI Engineer"
    profile_path.write_text(content, encoding="utf-8")

    text, sha = compute_profile_sha256(profile_path)
    expected_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()

    assert text == content
    assert sha == expected_sha


def test_unchanged_profile_reuses_valid_cache(temp_resource_dir):
    profile_path = temp_resource_dir / "profile.md"
    cache_path = temp_resource_dir / "profile_search_query.json"

    profile_text = "Senior Python Developer"
    profile_path.write_text(profile_text, encoding="utf-8")
    _, expected_sha = compute_profile_sha256(profile_path)

    query1 = JobSearchQuery(search_term="Python Engineer", location="Remote", site_name="linkedin")
    cached_query_set = JobSearchQuerySet(profile_sha256=expected_sha, queries=[query1])
    cache_path.write_text(cached_query_set.model_dump_json(indent=2), encoding="utf-8")

    mock_crew_runner = MagicMock()

    result = get_or_generate_job_search_queries(
        profile_path=profile_path,
        cache_path=cache_path,
        crew_runner=mock_crew_runner,
    )

    mock_crew_runner.assert_not_called()
    assert result.profile_sha256 == expected_sha
    assert len(result.queries) == 1
    assert result.queries[0].search_term == "Python Engineer"


def test_changed_profile_retriggers_crewai_generation_and_updates_cache(temp_resource_dir):
    profile_path = temp_resource_dir / "profile.md"
    cache_path = temp_resource_dir / "profile_search_query.json"

    # Initial profile and cache
    profile_path.write_text("Old Profile Text", encoding="utf-8")
    _, old_sha = compute_profile_sha256(profile_path)
    old_query = JobSearchQuery(search_term="Old Role", location="Remote", site_name="linkedin")
    cache_path.write_text(
        JobSearchQuerySet(profile_sha256=old_sha, queries=[old_query]).model_dump_json(),
        encoding="utf-8",
    )

    # Change profile
    new_profile_text = "New Profile: Lead AI Architect"
    profile_path.write_text(new_profile_text, encoding="utf-8")
    _, new_sha = compute_profile_sha256(profile_path)

    new_query = JobSearchQuery(search_term="AI Architect", location="Remote", site_name="linkedin")
    mock_new_query_set = JobSearchQuerySet(profile_sha256=new_sha, queries=[new_query])

    mock_crew_runner = MagicMock(return_value=mock_new_query_set)

    result = get_or_generate_job_search_queries(
        profile_path=profile_path,
        cache_path=cache_path,
        crew_runner=mock_crew_runner,
    )

    mock_crew_runner.assert_called_once_with(
        profile_text=new_profile_text,
        profile_sha256=new_sha,
    )
    assert result.profile_sha256 == new_sha
    assert result.queries[0].search_term == "AI Architect"

    # Check updated cache file on disk
    saved_data = JobSearchQuerySet.model_validate_json(cache_path.read_text(encoding="utf-8"))
    assert saved_data.profile_sha256 == new_sha
    assert saved_data.queries[0].search_term == "AI Architect"


def test_corrupt_cache_file_forces_regeneration(temp_resource_dir):
    profile_path = temp_resource_dir / "profile.md"
    cache_path = temp_resource_dir / "profile_search_query.json"

    profile_text = "Python Dev"
    profile_path.write_text(profile_text, encoding="utf-8")
    _, current_sha = compute_profile_sha256(profile_path)

    # Write corrupted JSON
    cache_path.write_text("{ corrupt json data ...", encoding="utf-8")

    new_query = JobSearchQuery(search_term="Backend Engineer", location="Remote", site_name="linkedin")
    generated_query_set = JobSearchQuerySet(profile_sha256=current_sha, queries=[new_query])
    mock_crew_runner = MagicMock(return_value=generated_query_set)

    result = get_or_generate_job_search_queries(
        profile_path=profile_path,
        cache_path=cache_path,
        crew_runner=mock_crew_runner,
    )

    mock_crew_runner.assert_called_once_with(
        profile_text=profile_text,
        profile_sha256=current_sha,
    )
    assert result.profile_sha256 == current_sha

    # Verify cache file is now valid JSON
    saved_data = JobSearchQuerySet.model_validate_json(cache_path.read_text(encoding="utf-8"))
    assert saved_data.profile_sha256 == current_sha


def test_crewai_failure_raises_exception_and_preserves_previous_valid_cache_file(temp_resource_dir):
    profile_path = temp_resource_dir / "profile.md"
    cache_path = temp_resource_dir / "profile_search_query.json"

    # Write old profile and valid cache
    profile_path.write_text("Old Profile", encoding="utf-8")
    _, old_sha = compute_profile_sha256(profile_path)
    old_query = JobSearchQuery(search_term="Old Role", location="Remote", site_name="linkedin")
    cache_content = JobSearchQuerySet(profile_sha256=old_sha, queries=[old_query]).model_dump_json(indent=2)
    cache_path.write_text(cache_content, encoding="utf-8")

    # Update profile to trigger generation
    profile_path.write_text("Changed Profile Text", encoding="utf-8")
    _, new_sha = compute_profile_sha256(profile_path)

    mock_crew_runner = MagicMock(side_effect=Exception("LLM API Timeout"))

    with pytest.raises(RuntimeError, match="CrewAI query generation failed"):
        get_or_generate_job_search_queries(
            profile_path=profile_path,
            cache_path=cache_path,
            crew_runner=mock_crew_runner,
        )

    # Previous cache file MUST be preserved intact
    assert cache_path.exists()
    assert cache_path.read_text(encoding="utf-8") == cache_content


def test_duplicate_queries_deduplication():
    queries = [
        JobSearchQuery(search_term=" Python Engineer ", location="Remote ", site_name="linkedin"),
        JobSearchQuery(search_term="python engineer", location="remote", site_name="linkedin"),
        JobSearchQuery(search_term="PYTHON ENGINEER", location="REMOTE", site_name="linkedin"),
        JobSearchQuery(search_term="Python Engineer", location="Remote", site_name="indeed"),
    ]

    deduped = normalize_and_deduplicate_queries(queries)

    assert len(deduped) == 2
    assert deduped[0].site_name == "linkedin"
    assert deduped[1].site_name == "indeed"


def test_jobspy_integration_service_queries(temp_resource_dir):
    profile_path = temp_resource_dir / "profile.md"
    cache_path = temp_resource_dir / "profile_search_query.json"

    profile_text = "Software Engineer"
    profile_path.write_text(profile_text, encoding="utf-8")
    _, current_sha = compute_profile_sha256(profile_path)

    query1 = JobSearchQuery(search_term="Software Engineer", location="Remote", site_name="linkedin")
    query_set = JobSearchQuerySet(profile_sha256=current_sha, queries=[query1])

    mock_crew_runner = MagicMock(return_value=query_set)

    service = JobSpyIntegrationService(
        profile_path=profile_path,
        cache_path=cache_path,
        crew_runner=mock_crew_runner,
    )

    queries = service.get_queries()
    assert len(queries) == 1
    assert queries[0].search_term == "Software Engineer"


def test_generation_rejects_mismatched_profile_hash_and_preserves_cache(tmp_path):
    from ljpa_reworked.services.jobspy import get_or_generate_job_search_queries

    profile_path = tmp_path / "profile.md"
    cache_path = tmp_path / "profile_search_query.json"
    profile_path.write_text("Candidate profile", encoding="utf-8")
    cache_path.write_text("known-good-cache", encoding="utf-8")

    def crew_runner(**_):
        return {
            "profile_sha256": "0" * 64,
            "queries": [{"search_term": "Python Engineer", "location": "Remote", "site_name": "linkedin", "results_wanted": 10}],
        }

    with pytest.raises(RuntimeError, match="profile_sha256 does not match"):
        get_or_generate_job_search_queries(profile_path, cache_path, crew_runner)

    assert cache_path.read_text(encoding="utf-8") == "known-good-cache"
