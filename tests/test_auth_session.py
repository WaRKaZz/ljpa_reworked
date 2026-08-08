import json
import pytest
from pathlib import Path
from ljpa_reworked.auth.session import verify_auth_state, load_auth_state

def test_verify_auth_state_missing_file(tmp_path):
    missing_file = tmp_path / "state.json"
    assert verify_auth_state(missing_file) is False

def test_verify_auth_state_invalid_json(tmp_path):
    bad_file = tmp_path / "state.json"
    bad_file.write_text("invalid json", encoding="utf-8")
    assert verify_auth_state(bad_file) is False

def test_verify_auth_state_valid(tmp_path):
    valid_file = tmp_path / "state.json"
    valid_data = {
        "cookies": [
            {"name": "li_at", "value": "secret_cookie_value", "domain": ".linkedin.com", "path": "/"}
        ],
        "origins": []
    }
    valid_file.write_text(json.dumps(valid_data), encoding="utf-8")
    assert verify_auth_state(valid_file) is True
    loaded = load_auth_state(valid_file)
    assert loaded["cookies"][0]["name"] == "li_at"

def test_load_auth_state_invalid_raises_value_error(tmp_path):
    missing_file = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="Invalid or missing auth state file"):
        load_auth_state(missing_file)
