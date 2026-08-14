from ljpa_reworked.resume_static_profile import parse_static_resume_profile


def test_static_profile_parser_preserves_identity_experience_and_education():
    profile = """# Candidate
## General Information
- **Name:** Ivan Danilov
- **Target Title:** Controls Engineer
- **Location:** Karaganda, Kazakhstan
## Job Search Preferences
- **Email:** ivan@example.com
- **Phone:** +7 701 724 25 32
- **LinkedIn:** https://linkedin.com/in/ivan
## Summary
Summary
## Experience
### TCO — PLC Engineer
**Dates:** April 2021 – Present
**Location:** Atyrau, Kazakhstan
- Verified PLC systems.
## Education
### Technical University
**Degree:** Master's Degree, Automation and Control
**Dates:** 2013 – 2019
## Skills
- PLC
"""

    base = parse_static_resume_profile(profile)

    assert base["personal_info"] == {
        "name": "Ivan Danilov",
        "email": "ivan@example.com",
        "phone": "+7 701 724 25 32",
        "address": "",
        "location": "Karaganda, Kazakhstan",
        "linkedin_url": "https://linkedin.com/in/ivan",
        "target_title": "Controls Engineer",
    }
    assert base["experience"] == [
        {
            "company": "TCO",
            "title": "PLC Engineer",
            "location": "Atyrau, Kazakhstan",
            "start_date": "April 2021",
            "end_date": "Present",
            "description": ["Verified PLC systems."],
        }
    ]
    assert base["education"] == [
        {
            "institution": "Technical University",
            "course": "Master's Degree, Automation and Control",
            "location": "Karaganda, Kazakhstan",
            "start_date": "2013",
            "end_date": "2019",
        }
    ]


def test_static_profile_overlay_rejects_llm_static_fact_omissions():
    from ljpa_reworked.resume_static_profile import merge_static_resume_profile

    base = {
        "personal_info": {
            "name": "Ivan",
            "email": "i@example.com",
            "phone": "1",
            "location": "A",
        },
        "experience": [
            {
                "company": "TCO",
                "title": "PLC Engineer",
                "location": "A",
                "start_date": "2021",
                "end_date": "Present",
            }
        ],
        "education": [
            {
                "institution": "University",
                "course": "MSc",
                "start_date": "2013",
                "end_date": "2019",
            }
        ],
    }
    llm = {
        "summary": "Tailored summary",
        "skills": [],
        "experience": [{"description": ["One", "Two", "Three"]}],
        "education": [],
        "projects": [],
        "certifications": [],
    }

    merged = merge_static_resume_profile(llm, base)

    assert merged["personal_info"]["name"] == "Ivan"
    assert merged["experience"][0]["title"] == "PLC Engineer"
    assert merged["education"][0]["course"] == "MSc"
    assert merged["experience"][0]["description"] == ["One", "Two", "Three"]


def test_static_profile_overlay_uses_profile_bullets_when_llm_omits_experience():
    from ljpa_reworked.resume_static_profile import merge_static_resume_profile

    static = {
        "personal_info": {},
        "education": [],
        "experience": [
            {
                "company": "TCO",
                "title": "PLC Engineer",
                "location": "A",
                "start_date": "2021",
                "end_date": "Present",
                "description": ["One", "Two", "Three"],
            }
        ],
    }
    assert merge_static_resume_profile({"experience": []}, static)["experience"][0][
        "description"
    ] == ["One", "Two", "Three"]
