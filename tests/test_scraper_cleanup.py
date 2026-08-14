import sqlite3
from pathlib import Path


def test_scraper_database_is_removed_after_publish(tmp_path: Path):
    from ljpa_reworked.services.harness_runner import (
        prepare_scraper_database,
        publish_scraper_database,
    )

    canonical = tmp_path / "canonical" / "app.db"
    scraper = tmp_path / "scraper" / "app.db"
    canonical.parent.mkdir()
    with sqlite3.connect(canonical) as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")

    prepare_scraper_database(canonical, scraper)
    assert scraper.exists()

    publish_scraper_database(canonical, scraper)
    assert not scraper.exists()
