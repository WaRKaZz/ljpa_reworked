from pathlib import Path


def test_resume_prompt_forbids_unsupported_credentials_and_claims():
    text = Path("src/ljpa_reworked/crews/resume_generation_crew/config/tasks.yaml").read_text()

    assert "omit unsupported tools, responsibilities, metrics, dates, credentials, and outcomes" in text
    assert "Freely use the candidate profile, vacancy, and general domain information" not in text


def test_email_prompt_uses_neutral_salutation_without_explicit_name():
    text = Path("src/ljpa_reworked/crews/email_generation_crew/config/tasks.yaml").read_text()

    assert "Dear Hiring Manager" in text
    assert "infer gender" not in text


def test_resume_prompt_leaves_page_measurement_to_render_and_retry():
    text = Path("src/ljpa_reworked/crews/resume_generation_crew/config/tasks.yaml").read_text()

    assert "Count every visible character you generate" not in text
    assert "Retry feedback is produced after deterministic RenderCV validation" in text
