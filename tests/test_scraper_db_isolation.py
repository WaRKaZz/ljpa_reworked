import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from ljpa_reworked.services.harness_runner import (
    prepare_scraper_database,
    publish_scraper_database,
    run_linkedin_harness,
    validate_scraper_completion,
)


def _create_database(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES (?)", (value,))


def _marker(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT value FROM marker").fetchone()[0]


def test_scraper_database_copy_round_trip(tmp_path: Path):
    canonical = tmp_path / "canonical" / "app.db"
    scraper = tmp_path / "scraper" / "app.db"
    canonical.parent.mkdir()
    _create_database(canonical, "before")

    prepare_scraper_database(canonical, scraper)
    assert _marker(scraper) == "before"

    with sqlite3.connect(scraper) as connection:
        connection.execute("UPDATE marker SET value = 'after'")
    publish_scraper_database(canonical, scraper)
    assert _marker(canonical) == "after"


def test_submit_never_uses_scraper_database_lifecycle():
    from ljpa_reworked.services import harness_runner

    assert "prepare_scraper_database" not in harness_runner.harness_submit.__code__.co_names
    assert "publish_scraper_database" not in harness_runner.harness_submit.__code__.co_names


def test_validate_scraper_completion(tmp_path: Path):
    scraper_db = tmp_path / "scraper" / "app.db"
    scraper_db.parent.mkdir(parents=True, exist_ok=True)
    _create_database(scraper_db, "test")
    artifact_path = tmp_path / "scraper" / "scraper-result.json"

    # Missing artifact
    assert not validate_scraper_completion(scraper_db)

    # Invalid status artifact
    artifact_path.write_text(json.dumps({"status": "failed", "integrity_check": "ok", "foreign_key_check": "ok"}))
    assert not validate_scraper_completion(scraper_db)

    # Valid artifact
    artifact_path.write_text(json.dumps({
        "status": "completed",
        "workspace_db": "/app/data/app.db",
        "integrity_check": "ok",
        "foreign_key_check": "ok",
        "final_valid_vacancy_count": 5
    }))
    assert validate_scraper_completion(scraper_db)


def test_harness_no_artifact_deletes_scraper_db_and_retains_canonical(tmp_path: Path):
    canonical = tmp_path / "canonical" / "app.db"
    scraper = tmp_path / "scraper" / "app.db"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _create_database(canonical, "before")

    mock_response = MagicMock()
    mock_response.__enter__.return_value = [b'{"event":"result","result":{"status":"SUCCESS"}}\n']

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = run_linkedin_harness(
            api_url="http://localhost:8080/run-harness",
            canonical_db_path=canonical,
            scraper_db_path=scraper,
        )

    assert result == 1
    assert _marker(canonical) == "before"
    assert not scraper.exists()


def test_harness_valid_artifact_publishes_canonical_and_cleans_scraper_db(tmp_path: Path):
    canonical = tmp_path / "canonical" / "app.db"
    scraper = tmp_path / "scraper" / "app.db"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _create_database(canonical, "before")

    mock_response = MagicMock()
    mock_response.__enter__.return_value = [b'{"event":"result","result":{"status":"SUCCESS"}}\n']

    def side_effect_urlopen(*args, **kwargs):
        # Simulate scraper creating updated DB and completion artifact
        with sqlite3.connect(scraper) as connection:
            connection.execute("UPDATE marker SET value = 'published_after_artifact'")
        artifact = scraper.with_name("scraper-result.json")
        artifact.write_text(json.dumps({
            "status": "completed",
            "workspace_db": "/app/data/app.db",
            "integrity_check": "ok",
            "foreign_key_check": "ok",
            "final_valid_vacancy_count": 1
        }))
        return mock_response

    with patch("urllib.request.urlopen", side_effect=side_effect_urlopen):
        result = run_linkedin_harness(
            api_url="http://localhost:8080/run-harness",
            canonical_db_path=canonical,
            scraper_db_path=scraper,
        )

    assert result == 0
    assert _marker(canonical) == "published_after_artifact"
    assert not scraper.exists()
    assert not scraper.with_name("scraper-result.json").exists()
