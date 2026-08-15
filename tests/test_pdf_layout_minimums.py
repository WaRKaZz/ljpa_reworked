from pathlib import Path


def test_layout_no_longer_requires_density_padding():
    """Readable pages are accepted without arbitrary character-density targets."""
    source = Path("src/ljpa_reworked/services/rendercv_helper.py").read_text()
    assert "count < 3000" not in source
    assert "count < 1400" not in source
    assert "insufficient readable text" in source
