import pytest
from pydantic import ValidationError

from ljpa_reworked.models.crewai_pydantic_models import (
    JobSearchQuery,
    JobSearchQuerySet,
)


def test_job_search_query_valid():
    query = JobSearchQuery(
        search_term="Python Engineer",
        location="Remote",
        site_name="linkedin",
    )
    assert query.search_term == "Python Engineer"
    assert query.location == "Remote"
    assert query.site_name == "linkedin"
    assert query.results_wanted == 25  # default value

    query_custom = JobSearchQuery(
        search_term="Backend Developer",
        location="New York, NY",
        site_name="indeed",
        results_wanted=10,
    )
    assert query_custom.results_wanted == 10


def test_job_search_query_invalid_site_name():
    with pytest.raises(ValidationError):
        JobSearchQuery(
            search_term="Python Engineer",
            location="Remote",
            site_name="monster",  # Not in allowed Literal
        )


def test_job_search_query_invalid_results_wanted():
    with pytest.raises(ValidationError):
        JobSearchQuery(
            search_term="Python Engineer",
            location="Remote",
            site_name="linkedin",
            results_wanted=0,  # ge=1 constraint
        )

    with pytest.raises(ValidationError):
        JobSearchQuery(
            search_term="Python Engineer",
            location="Remote",
            site_name="linkedin",
            results_wanted=51,  # le=50 constraint
        )


def test_job_search_query_invalid_str_constraints():
    with pytest.raises(ValidationError):
        JobSearchQuery(
            search_term="a",  # min_length=2
            location="Remote",
            site_name="linkedin",
        )

    with pytest.raises(ValidationError):
        JobSearchQuery(
            search_term="Python Engineer",
            location="a" * 161,  # max_length=160
            site_name="linkedin",
        )


def test_job_search_query_set_valid():
    valid_sha256 = "a" * 64
    valid_query = JobSearchQuery(
        search_term="Python Engineer",
        location="Remote",
        site_name="linkedin",
    )
    query_set = JobSearchQuerySet(
        profile_sha256=valid_sha256,
        queries=[valid_query],
    )
    assert query_set.profile_sha256 == valid_sha256
    assert len(query_set.queries) == 1


def test_job_search_query_set_invalid_sha256():
    valid_query = JobSearchQuery(
        search_term="Python Engineer",
        location="Remote",
        site_name="linkedin",
    )

    # Upper case letters not allowed by pattern r"^[0-9a-f]{64}$"
    with pytest.raises(ValidationError):
        JobSearchQuerySet(
            profile_sha256="A" * 64,
            queries=[valid_query],
        )

    # Invalid length (63 chars)
    with pytest.raises(ValidationError):
        JobSearchQuerySet(
            profile_sha256="a" * 63,
            queries=[valid_query],
        )

    # Non-hex characters
    with pytest.raises(ValidationError):
        JobSearchQuerySet(
            profile_sha256="z" * 64,
            queries=[valid_query],
        )


def test_job_search_query_set_invalid_queries_count():
    valid_sha256 = "b" * 64
    valid_query = JobSearchQuery(
        search_term="Python Engineer",
        location="Remote",
        site_name="linkedin",
    )

    # Empty list (min_length=1)
    with pytest.raises(ValidationError):
        JobSearchQuerySet(
            profile_sha256=valid_sha256,
            queries=[],
        )

    # More than 12 queries (max_length=12)
    with pytest.raises(ValidationError):
        JobSearchQuerySet(
            profile_sha256=valid_sha256,
            queries=[valid_query] * 16,
        )


def test_query_generation_crew_structure():
    from ljpa_reworked.crews.query_generation_crew.query_generation_crew import (
        QueryGenerationCrew,
    )

    crew_inst = QueryGenerationCrew()
    agent_obj = crew_inst.query_strategist()
    assert agent_obj.role.strip() == "Job Search Strategist and Query Planner"

    task_obj = crew_inst.generate_job_search_queries_task()
    assert task_obj.output_pydantic == JobSearchQuerySet
    assert (
        "JobSearchQuerySet" in task_obj.description
        or "JobSearchQuerySet" in task_obj.expected_output
    )


def test_job_search_query_set_rejects_normalized_duplicates():
    with pytest.raises(ValidationError, match="duplicate"):
        JobSearchQuerySet(
            profile_sha256="c" * 64,
            queries=[
                JobSearchQuery(
                    search_term="Python Engineer",
                    location="Remote",
                    site_name="linkedin",
                ),
                JobSearchQuery(
                    search_term=" python engineer ",
                    location="remote",
                    site_name="linkedin",
                ),
            ],
        )


def test_job_search_query_set_allows_up_to_15_queries():
    queries = [
        JobSearchQuery(
            search_term=f"Python Engineer {index}",
            location="Remote",
            site_name="linkedin",
        )
        for index in range(15)
    ]
    JobSearchQuerySet(profile_sha256="d" * 64, queries=queries)

    with pytest.raises(ValidationError):
        JobSearchQuerySet(
            profile_sha256="d" * 64,
            queries=queries
            + [
                JobSearchQuery(
                    search_term="Python Engineer 16",
                    location="Remote",
                    site_name="linkedin",
                )
            ],
        )


def test_query_generation_prompt_uses_job_search_preferences_not_candidate_history():
    from pathlib import Path

    task_config = (
        Path(__file__).parents[1]
        / "src/ljpa_reworked/crews/query_generation_crew/config/tasks.yaml"
    ).read_text(encoding="utf-8")

    assert "Job Search Preferences" in task_config
    assert "current or past residence" in task_config
    assert "10 to 15" in task_config


def test_query_generation_prompt_preserves_explicit_worldwide_preference():
    from pathlib import Path

    task_config = (
        Path(__file__).parents[1]
        / "src/ljpa_reworked/crews/query_generation_crew/config/tasks.yaml"
    ).read_text(encoding="utf-8")

    assert "location `worldwide`" in task_config


def test_query_generation_prompt_source_aware_worldwide_contract():
    from pathlib import Path

    task_config = (
        Path(__file__).parents[1]
        / "src/ljpa_reworked/crews/query_generation_crew/config/tasks.yaml"
    ).read_text(encoding="utf-8")

    assert "Require at least one LinkedIn query with location `worldwide`." in task_config
    assert (
        "Require Indeed and Google queries to use individual country locations"
        in task_config
    )
    assert "Never use `worldwide` for Indeed or Google queries." in task_config
    assert (
        "not their current or past residence unless profile preferences explicitly choose them"
        in task_config
    )


def test_query_generation_prompt_has_no_fixed_hardcoded_markets():
    from pathlib import Path

    task_config = (
        Path(__file__).parents[1]
        / "src/ljpa_reworked/crews/query_generation_crew/config/tasks.yaml"
    ).read_text(encoding="utf-8")

    for prohibited in ["Saudi Arabia", "UAE", "United Arab Emirates", "USA", "United States"]:
        assert prohibited not in task_config


def test_query_generation_prompt_restricts_site_names_to_working_sources():
    from pathlib import Path

    task_config = (
        Path(__file__).parents[1]
        / "src/ljpa_reworked/crews/query_generation_crew/config/tasks.yaml"
    ).read_text(encoding="utf-8")

    assert "Allowed site_name values only: linkedin, indeed, google." in task_config
    assert "zip_recruiter" not in task_config


def test_job_search_query_google_search_term_field():
    query_google = JobSearchQuery(
        search_term="Python Engineer",
        location="Munich, Germany",
        site_name="google",
        google_search_term="Python Engineer jobs near Munich, Germany",
    )
    assert query_google.google_search_term == "Python Engineer jobs near Munich, Germany"

    query_linkedin = JobSearchQuery(
        search_term="Python Engineer",
        location="Remote",
        site_name="linkedin",
    )
    assert query_linkedin.google_search_term is None


def test_query_generation_prompt_keyword_query_rules():
    from pathlib import Path

    task_config = (
        Path(__file__).parents[1]
        / "src/ljpa_reworked/crews/query_generation_crew/config/tasks.yaml"
    ).read_text(encoding="utf-8")

    assert "1–3 short" in task_config or "1-3 short" in task_config
    assert "no sentence" in task_config or "full sentences" in task_config
    assert "google_search_term" in task_config
    assert "jobs near <location>" in task_config
