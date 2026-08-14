from pathlib import Path


def test_layout_requires_3000_characters_on_each_non_final_page():
    source = Path("src/ljpa_reworked/services/rendercv_helper.py").read_text()

    assert "if i < num_pages - 1 and count < 3000:" in source
    assert "if count < 1400:" in source
