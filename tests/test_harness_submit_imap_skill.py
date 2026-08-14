from pathlib import Path


def test_submit_prompt_uses_imap_mcp_credentials_from_env_file():
    prompt = Path("prompts/harness_submit.md").read_text(encoding="utf-8")
    assert "LJPA Gmail" in prompt
    assert "MCP server `imap`" in prompt
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_USERNAME" in prompt
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_PASSWORD" in prompt
    assert "Do not read `.env`" in prompt
    assert "profile-only contact-data rule" in prompt


def test_imap_registration_skill_prohibits_secret_handling_and_writes():
    skill = Path(".gemini/skills/imap-email-registration/SKILL.md").read_text(encoding="utf-8")
    assert "Read-only tools are intentional" in skill
    assert "Do not ask for, read, print, write, or store mailbox credentials" in skill
    assert "imap_search_emails" in skill
    assert "imap_get_email" in skill
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_USERNAME" in skill
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_PASSWORD" in skill
