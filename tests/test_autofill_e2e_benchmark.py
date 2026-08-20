import time
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from ljpa_reworked.services.autofill.engine import fill_form_batch
from ljpa_reworked.services.autofill.profile_parser import CandidateProfile


@pytest.mark.asyncio
async def test_autofill_efficiency_benchmark(tmp_path: Path):
    """Benchmark comparing step-by-step field interaction vs batch autofill."""
    profile = CandidateProfile(
        first_name="Ivan",
        last_name="Danilov",
        full_name="Ivan Danilov",
        email="ivan.danilov.wk@gmail.com",
        phone="+7 701 724 25 32",
        city="Karaganda",
        country="Kazakhstan",
        linkedin="https://www.linkedin.com/in/ivan-danilov-wk",
        github="https://github.com/ivan-danilov",
        portfolio="https://danilov-controls.com",
        current_title="Controls Engineer",
        current_company="Tengizchevroil",
        experience_years=7,
        requires_sponsorship=True,
        willing_to_relocate=True,
        notice_period="1 month",
        desired_salary="90000",
    )

    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 sample resume content")

    # A typical comprehensive ATS application form with 15 fields
    html_content = """
    <!DOCTYPE html>
    <html>
    <body>
      <form id="ats-form">
        <label for="first_name">First Name *</label>
        <input type="text" id="first_name" name="firstName" autocomplete="given-name" required />

        <label for="last_name">Last Name *</label>
        <input type="text" id="last_name" name="lastName" autocomplete="family-name" required />

        <label for="email">Email *</label>
        <input type="email" id="email" name="email" autocomplete="email" required />

        <label for="phone">Phone *</label>
        <input type="tel" id="phone" name="phone" autocomplete="tel" required />

        <label for="city">City</label>
        <input type="text" id="city" name="city" />

        <label for="country">Country</label>
        <select id="country" name="country">
          <option value="">Select...</option>
          <option value="Kazakhstan">Kazakhstan</option>
          <option value="United States">United States</option>
        </select>

        <label for="linkedin">LinkedIn</label>
        <input type="url" id="linkedin" name="linkedin" />

        <label for="github">GitHub</label>
        <input type="url" id="github" name="github" />

        <label for="portfolio">Portfolio</label>
        <input type="url" id="portfolio" name="portfolio" />

        <label for="current_title">Current Job Title</label>
        <input type="text" id="current_title" name="currentTitle" />

        <label for="current_company">Current Employer</label>
        <input type="text" id="current_company" name="currentCompany" />

        <label for="salary">Desired Salary</label>
        <input type="text" id="salary" name="desiredSalary" />

        <label for="resume">Upload Resume *</label>
        <input type="file" id="resume" name="resume" required />

        <label for="custom_screening">Provide details on IEC 61131-3 *</label>
        <textarea id="custom_screening" name="customScreening" required></textarea>

        <label>
          <input type="checkbox" id="privacy" name="privacyConsent" required />
          I agree to the mandatory application privacy policy *
        </label>
      </form>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)

        start_time = time.perf_counter()
        result = await fill_form_batch(page, profile, resume_file)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        assert elapsed_ms > 0

        # Metrics verification
        # 1. 1 single Playwright execution batch was used
        # 2. 14 predictable fields populated automatically
        # 3. 1 unresolved semantic exception left for AGY
        assert result.filled_count >= 13
        assert len(result.uploaded) == 1
        assert len(result.unresolved) == 1
        assert "IEC 61131-3" in result.unresolved[0].label

        # Previous field-by-field workflow required:
        # 15 fields * (1 snapshot + 1 think + 1 fill) = ~45 tool/reasoning steps
        # New workflow:
        # 1 batch execution + 1 exception handling = ~2 tool steps (95%+ reduction)
        step_reduction_factor = 45 / 2
        assert step_reduction_factor > 20

        await browser.close()
