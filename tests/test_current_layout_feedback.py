from ljpa_reworked.crew_workflow import _format_numeric_layout_feedback


def test_non_final_3000_minimum_error_returns_expansion_instruction():
    feedback = _format_numeric_layout_feedback(
        "RenderCV output failed page layout validation: "
        "Page 1 (non-final) character count (2990) is less than minimum 3000 characters"
    )

    assert "SHORT of 3000" in feedback
    assert "expand the resume text" in feedback
    assert "approximately 110 characters" in feedback
