from pathlib import Path


def test_layout_validation_uses_readability_and_page_limit_not_density():
    source = Path("src/ljpa_reworked/services/rendercv_helper.py").read_text()
    assert "count < 3300 or count > 3475" not in source
    assert "count < 3000" not in source
    assert "1 <= page_count <= 2" in source
    assert "insufficient readable text" in source
