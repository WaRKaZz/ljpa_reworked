from pathlib import Path


def test_submit_prompt_uses_imap_mcp_credentials_from_env_file():
    prompt = Path("prompts/harness_submit.md").read_text(encoding="utf-8")
    assert "LJPA Gmail" in prompt
    assert "MCP server `imap`" in prompt
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_USERNAME" in prompt
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_PASSWORD" in prompt
    assert "Do not read `.env`" in prompt
    assert "profile-only contact-data rule" in prompt
    assert "/runtime/workspace/credentials.json" in prompt
    assert "/inputs/resources/profile.md" in prompt


def test_imap_registration_skill_prohibits_secret_handling_and_writes():
    skill = Path("runtime/gemini/skills/imap-email-registration/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Read-only tools are intentional" in skill
    assert "Do not ask for, read, print, write, or store mailbox credentials" in skill
    assert "imap_search_emails" in skill
    assert "imap_get_email" in skill
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_USERNAME" in skill
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_PASSWORD" in skill


def test_antigravity_entrypoint_bootstraps_env_managed_ljpa_gmail_account():
    entrypoint = Path(
        "src/ljpa_reworked/services/docker/antigravity-entrypoint.sh"
    ).read_text(encoding="utf-8")

    assert "LJPA Gmail" in entrypoint
    assert '"host": "imap.gmail.com"' in entrypoint
    assert '"password": ""' in entrypoint
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_USERNAME" not in entrypoint
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_PASSWORD" not in entrypoint


def test_harness_submit_prompt_has_no_final_skill_authoring_task():
    prompt = Path("prompts/harness_submit.md").read_text(encoding="utf-8")
    assert "/runtime/workspace/credentials.json" in prompt
    assert "SKILL.md Documentation" not in prompt
    assert "README.md Registry" not in prompt
    assert "updated with the final application flow details" not in prompt


def test_harness_save_site_skill_prompt_contracts():
    prompt = Path("prompts/harness_save_site_skill.md").read_text(encoding="utf-8")
    assert "/runtime/workspace/<site-or-vacancy-name>/SKILL.md" in prompt
    assert "/runtime/workspace/README.md" in prompt
    assert "Technical selector strategies" in prompt or "selector strategies" in prompt
    assert "No Personal Data" in prompt
    assert "credentials.json" in prompt
    assert "No Raw Logs" in prompt or "raw transcript" in prompt
    assert "Do not access or query SQLite database" in prompt or "database" in prompt


def test_harness_save_scraper_skill_prompt_contracts():
    prompt_path = Path("prompts/harness_save_scraper_skill.md")
    assert prompt_path.exists(), "prompts/harness_save_scraper_skill.md must exist"
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "AUTOMATED REUSABLE LINKEDIN SCRAPER SKILL SAVING HARNESS" in prompt
    assert "/runtime/workspace/linkedin_posts_scraper/SKILL.md" in prompt
    assert "/runtime/workspace/README.md" in prompt
    assert "search quer" in prompt.lower() or "keyword pattern" in prompt.lower()
    assert "see more" in prompt.lower()
    assert "redirect" in prompt.lower() or "unwrapping" in prompt.lower()
    assert "pagination" in prompt.lower() or "scrolling" in prompt.lower()
    assert "personal data" in prompt.lower() or "candidate" in prompt.lower()
    assert "password" in prompt.lower() or "otp" in prompt.lower()
    assert "database" in prompt.lower() or "app.db" in prompt.lower()
