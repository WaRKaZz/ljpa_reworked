import json


def parse_terminal_result(line: str) -> tuple[bool, bool]:
    """Return (is_terminal, is_success) for one AGY NDJSON line."""
    try:
        data = json.loads(line)
        if not isinstance(data, dict):
            return False, False
        if data.get("event") == "result":
            result_obj = data.get("result")
            is_success = isinstance(result_obj, dict) and result_obj.get("status") == "SUCCESS"
            return True, is_success
        return False, False
    except (json.JSONDecodeError, TypeError):
        return False, False
