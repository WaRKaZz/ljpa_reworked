from ljpa_reworked.services.autofill.registry import (
    CanonicalField,
    classify_control,
)


def test_classify_standard_positive_signals():
    # 1. Autocomplete signal
    res, score = classify_control({"autocomplete": "given-name", "tag": "input"})
    assert res == CanonicalField.FIRST_NAME
    assert score >= 0.9

    # 2. Label signal
    res, score = classify_control(
        {"label": "Email Address", "tag": "input", "type": "email"}
    )
    assert res == CanonicalField.EMAIL
    assert score >= 0.8

    # 3. Name & Placeholder signal
    res, score = classify_control(
        {
            "name": "candidate.lastName",
            "placeholder": "Enter your surname",
            "tag": "input",
        }
    )
    assert res == CanonicalField.LAST_NAME
    assert score >= 0.7

    # 4. LinkedIn profile URL
    res, score = classify_control(
        {"label": "LinkedIn Profile URL", "name": "linkedin_link", "tag": "input"}
    )
    assert res == CanonicalField.LINKEDIN
    assert score >= 0.75

    # 5. File input for resume
    res, score = classify_control(
        {"label": "Upload Resume / CV", "type": "file", "tag": "input"}
    )
    assert res == CanonicalField.RESUME
    assert score >= 0.8


def test_negative_anti_false_positive_signals():
    # "Manager first name" must NOT match candidate first name
    res, score = classify_control(
        {
            "label": "Hiring Manager First Name",
            "name": "managerFirstName",
            "tag": "input",
        }
    )
    assert res is None or res != CanonicalField.FIRST_NAME

    # "Emergency contact email" must NOT match candidate email
    res, score = classify_control(
        {
            "label": "Emergency Contact Email Address",
            "name": "emergency_email",
            "tag": "input",
        }
    )
    assert res is None or res != CanonicalField.EMAIL

    # "Referral Name" must NOT match full name
    res, score = classify_control(
        {
            "label": "Employee Referral Full Name",
            "name": "referral_name",
            "tag": "input",
        }
    )
    assert res is None or res != CanonicalField.FULL_NAME


def test_unknown_custom_question_not_matched():
    res, score = classify_control(
        {
            "label": "Describe your experience with IEC 61131-3 standard logic.",
            "name": "q_iec_61131_3",
            "tag": "textarea",
        }
    )
    assert res is None or score < 0.7
