from pathlib import Path

from ljpa_reworked.services.autofill.profile_parser import (
    CandidateProfile,
    load_candidate_profile,
    parse_profile_markdown,
)


def test_parse_profile_markdown_extracts_canonical_fields():
    profile_text = """# Candidate Profile — Ivan Danilov

## General Information
- **Name:** Ivan Danilov
- **Target Title:** Controls Engineer | PLC / SCADA / DCS | Industrial Automation
- **Location:** Karaganda, Kazakhstan

## Job Search Preferences
- **Target locations:** Worldwide, excluding Kazakhstan.
- **Citizenship & Work Authorization:** Citizen of Kazakhstan. Requires Visa Sponsorship and Relocation Support for all foreign / international roles (no pre-existing US/EU/UK work authorization).
- **Visa Sponsorship Requirement:** Strict requirement — prioritize roles offering visa sponsorship / relocation support. Reject vacancies explicitly requiring pre-existing local citizenship or work authorization without sponsorship.
- **Email:** ivan.danilov.wk@gmail.com
- **Phone:** +7 701 724 25 32
- **LinkedIn:** https://www.linkedin.com/in/ivan-danilov-wk
- **GitHub:** https://github.com/ivan-danilov
- **Portfolio / Website:** https://danilov-controls.com

## Summary
Controls Engineer and Industrial Automation Specialist with over 7 years of experience...

## Experience

### Tengizchevroil — FGP PLC Engineer
**Dates:** April 2021 – Present
**Location:** Atyrau Region, Kazakhstan
"""
    profile = parse_profile_markdown(profile_text)
    assert isinstance(profile, CandidateProfile)
    assert profile.first_name == "Ivan"
    assert profile.last_name == "Danilov"
    assert profile.full_name == "Ivan Danilov"
    assert profile.email == "ivan.danilov.wk@gmail.com"
    assert profile.phone == "+7 701 724 25 32"
    assert profile.phone_country_code == "+7"
    assert profile.national_phone == "7017242532"
    assert profile.city == "Karaganda"
    assert profile.country == "Kazakhstan"
    assert profile.linkedin == "https://www.linkedin.com/in/ivan-danilov-wk"
    assert profile.github == "https://github.com/ivan-danilov"
    assert profile.portfolio == "https://danilov-controls.com"
    assert profile.current_company == "Tengizchevroil"
    assert profile.current_title == "FGP PLC Engineer"
    assert profile.experience_years == 7
    assert profile.requires_sponsorship is True
    assert profile.willing_to_relocate is True


def test_load_candidate_profile_from_file():
    real_profile_path = Path("resources/profile.md")
    assert real_profile_path.exists()
    profile = load_candidate_profile(real_profile_path)
    assert profile.first_name == "Ivan"
    assert profile.last_name == "Danilov"
    assert profile.email == "ivan.danilov.wk@gmail.com"
    assert profile.country == "Kazakhstan"
    assert profile.city == "Karaganda"
