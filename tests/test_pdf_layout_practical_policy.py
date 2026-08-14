from pathlib import Path


def test_layout_validation_does_not_reject_a_readable_non_final_page_for_density():
    source = Path("src/ljpa_reworked/services/rendercv_helper.py").read_text()

    assert "count < 3300 or count > 3475" not in source
    assert "count < 3000" in source


def test_pdfium_compatibility_warning_is_silenced_at_the_render_boundary():
    source = Path("src/ljpa_reworked/services/rendercv_helper.py").read_text()

    assert "implicitly redirected to get_text_bounded" in source
    assert "filterwarnings" in source
