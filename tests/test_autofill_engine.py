from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from ljpa_reworked.services.autofill.engine import (
    AutofillResult,
    fill_form_batch,
)
from ljpa_reworked.services.autofill.profile_parser import CandidateProfile


@pytest.fixture
def sample_profile() -> CandidateProfile:
    return CandidateProfile(
        first_name="Ivan",
        last_name="Danilov",
        full_name="Ivan Danilov",
        email="ivan.danilov.wk@gmail.com",
        phone="+7 701 724 25 32",
        phone_country_code="+7",
        national_phone="7017242532",
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
    )


@pytest.mark.asyncio
async def test_autofill_standard_html_form(
    tmp_path: Path, sample_profile: CandidateProfile
):
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 dummy pdf content")

    html_content = """
    <!DOCTYPE html>
    <html>
    <body>
      <form id="job-app">
        <label for="fname">First Name *</label>
        <input type="text" id="fname" name="firstName" autocomplete="given-name" required />

        <label for="lname">Last Name *</label>
        <input type="text" id="lname" name="lastName" autocomplete="family-name" required />

        <label for="email">Email Address *</label>
        <input type="email" id="email" name="email" autocomplete="email" required />

        <label for="phone">Phone Number *</label>
        <input type="tel" id="phone" name="phone" autocomplete="tel" required />

        <label for="city">City</label>
        <input type="text" id="city" name="city" />

        <label for="country">Country</label>
        <select id="country" name="country">
          <option value="">Select country...</option>
          <option value="KZ">Kazakhstan</option>
          <option value="US">United States</option>
          <option value="DE">Germany</option>
        </select>

        <label for="linkedin">LinkedIn Profile URL</label>
        <input type="url" id="linkedin" name="linkedin" />

        <label for="resume">Attach Resume / CV *</label>
        <input type="file" id="resume" name="resume" required />

        <label for="custom_q">Describe your experience with IEC 61131-3 *</label>
        <textarea id="custom_q" name="q_iec" required></textarea>

        <label>
          <input type="checkbox" id="marketing_opt" name="marketing" />
          I would like to receive promotional job alerts and marketing emails.
        </label>

        <label>
          <input type="checkbox" id="privacy_agree" name="privacy_consent" required />
          I agree to the application privacy policy and mandatory data processing terms *
        </label>

        <button type="submit" id="submit-btn">Submit Application</button>
      </form>
    </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)

        result = await fill_form_batch(page, sample_profile, resume_file)

        assert isinstance(result, AutofillResult)
        assert result.filled_count >= 7

        # Check filled values on the page
        assert await page.locator("#fname").input_value() == "Ivan"
        assert await page.locator("#lname").input_value() == "Danilov"
        assert await page.locator("#email").input_value() == "ivan.danilov.wk@gmail.com"
        assert await page.locator("#phone").input_value() == "+7 701 724 25 32"
        assert await page.locator("#city").input_value() == "Karaganda"
        assert await page.locator("#country").input_value() == "KZ"
        assert (
            await page.locator("#linkedin").input_value()
            == "https://www.linkedin.com/in/ivan-danilov-wk"
        )

        # Check resume upload
        assert len(result.uploaded) == 1
        assert result.uploaded[0].file == str(resume_file)

        # Check consent safety: marketing MUST NOT be checked, required privacy MUST be checked
        assert not await page.locator("#marketing_opt").is_checked()
        assert await page.locator("#privacy_agree").is_checked()

        # Check unresolved: custom question remains unresolved
        assert any("IEC 61131-3" in item.label for item in result.unresolved)

        # Form must NOT have been submitted
        assert await page.locator("#submit-btn").is_visible()

        await browser.close()


@pytest.mark.asyncio
async def test_autofill_detects_custom_combobox(sample_profile: CandidateProfile):
    html_content = """
    <!DOCTYPE html>
    <html>
    <body>
      <form>
        <label for="fn">First Name</label>
        <input type="text" id="fn" name="firstName" />

        <div role="combobox" aria-label="Target Work Location" aria-required="true" id="custom-combo">
          <input type="text" placeholder="Search locations..." />
        </div>
      </form>
    </body>
    </html>
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_content)

        result = await fill_form_batch(page, sample_profile)

        assert await page.locator("#fn").input_value() == "Ivan"
        assert any(item.kind == "custom_combobox" for item in result.unresolved)

        await browser.close()
