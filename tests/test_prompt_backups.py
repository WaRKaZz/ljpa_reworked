from pathlib import Path


def test_prompt_backups_exist_and_preserve_original_files():
    backup_dir = Path("prompts/backups/generic-form-autofill-migration")
    assert backup_dir.exists() and backup_dir.is_dir()

    files = ["harness_scraper.md", "harness_submit.md", "harness_save_site_skill.md"]
    for filename in files:
        bkp = backup_dir / filename
        assert bkp.exists(), f"Backup file {bkp} does not exist"
        assert bkp.stat().st_size > 100, f"Backup {bkp} is unexpectedly empty"

    # Verify scraper backup contains expected markers
    scraper_bkp = (backup_dir / "harness_scraper.md").read_text(encoding="utf-8")
    assert "LINKEDIN DIRECT VACANCY DISCOVERY" in scraper_bkp

    # Verify submit and save backups contain expected pre-migration markers
    submit_bkp = (backup_dir / "harness_submit.md").read_text(encoding="utf-8")
    assert "AUTOMATED SINGLE-VACANCY APPLICATION SUBMISSION HARNESS" in submit_bkp
    assert "UNTRUSTED_VACANCY_URL" in submit_bkp

    save_bkp = (backup_dir / "harness_save_site_skill.md").read_text(encoding="utf-8")
    assert "AUTOMATED REUSABLE SITE SKILL SAVING HARNESS" in save_bkp
