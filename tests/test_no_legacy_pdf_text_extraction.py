from pathlib import Path


def test_render_helper_uses_bounded_pdf_text_extraction():
    source = Path("src/ljpa_reworked/services/rendercv_helper.py").read_text()

    assert ".get_text_bounded()" in source
    assert ".get_text_range()" not in source
