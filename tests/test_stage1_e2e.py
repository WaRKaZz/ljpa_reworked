import json
import pytest
from pathlib import Path
from ljpa_reworked.auth.session import verify_auth_state, load_auth_state
from ljpa_reworked.auth.login_linkedin import get_cdp_endpoint

def test_cdp_endpoint_formatting():
    endpoint = get_cdp_endpoint()
    assert endpoint.startswith("ws://") or endpoint.startswith("http://")

def test_full_auth_state_lifecycle(tmp_path):
    state_file = tmp_path / "auth" / "state.json"
    
    # 1. State before login
    assert verify_auth_state(state_file) is False
    
    # 2. Simulate login harness saving state
    state_file.parent.mkdir(parents=True, exist_ok=True)
    sample_state = {
        "cookies": [
            {
                "name": "li_at",
                "value": "AQEDATTESTTOKEN",
                "domain": ".linkedin.com",
                "path": "/",
                "expires": -1,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None"
            }
        ],
        "origins": []
    }
    state_file.write_text(json.dumps(sample_state), encoding="utf-8")
    
    # 3. Verify state after saving
    assert verify_auth_state(state_file) is True
    data = load_auth_state(state_file)
    assert data["cookies"][0]["value"] == "AQEDATTESTTOKEN"
