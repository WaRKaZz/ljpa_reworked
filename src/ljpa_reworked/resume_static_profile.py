import re


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)",
        text,
        re.MULTILINE,
    )
    return match.group(1) if match else ""


def _field(text: str, name: str) -> str:
    match = re.search(
        rf"^[-*]?\s*\*\*{re.escape(name)}:\*\*\s*(.+)$", text, re.MULTILINE
    )
    return match.group(1).strip() if match else ""


def _dates(value: str) -> tuple[str, str]:
    parts = re.split(r"\s+[–-]\s+", value, maxsplit=1)
    return (
        (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (value.strip(), "")
    )


def _entries(section: str, fields: dict[str, str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    chunks = re.split(r"^###\s+", section, flags=re.MULTILINE)[1:]
    for chunk in chunks:
        lines = chunk.splitlines()
        heading = lines[0].strip()
        data = dict.fromkeys(fields, "")
        for key, label in fields.items():
            data[key] = _field(chunk, label)
        data["_heading"] = heading
        data["_bullets"] = [
            line[2:].strip() for line in lines[1:] if line.startswith("- ")
        ]
        entries.append(data)
    return entries


def parse_static_resume_profile(profile_text: str) -> dict:
    """Extract immutable resume facts from the canonical profile markdown."""
    general = _section(profile_text, "General Information")
    preferences = _section(profile_text, "Job Search Preferences")
    personal_info = {
        "name": _field(general, "Name"),
        "email": _field(preferences, "Email"),
        "phone": _field(preferences, "Phone"),
        "address": "",  # Profile has no street address; RenderCV does not use it.
        "location": _field(general, "Location"),
        "linkedin_url": _field(preferences, "LinkedIn") or None,
        "target_title": _field(general, "Target Title") or None,
    }

    experience = []
    for entry in _entries(
        _section(profile_text, "Experience"), {"dates": "Dates", "location": "Location"}
    ):
        company, title = (
            part.strip() for part in entry.pop("_heading").split(" — ", maxsplit=1)
        )
        start_date, end_date = _dates(entry.pop("dates"))
        experience.append(
            {
                "company": company,
                "title": title,
                "location": entry["location"],
                "start_date": start_date,
                "end_date": end_date,
                "description": entry["_bullets"],
            }
        )

    education = []
    for entry in _entries(
        _section(profile_text, "Education"), {"course": "Degree", "dates": "Dates"}
    ):
        start_date, end_date = _dates(entry.pop("dates"))
        education.append(
            {
                "institution": entry.pop("_heading"),
                "course": entry["course"],
                "location": personal_info["location"],
                "start_date": start_date,
                "end_date": end_date,
            }
        )

    return {
        "personal_info": personal_info,
        "experience": experience,
        "education": education,
    }


def merge_static_resume_profile(dynamic: dict, static: dict) -> dict:
    """Overlay LLM wording onto profile-derived immutable resume facts."""
    result = dict(dynamic)
    result["personal_info"] = static["personal_info"]
    result["education"] = static["education"]
    dynamic_experience = dynamic.get("experience", [])
    dynamic_descriptions = {
        (item.get("company"), item.get("title"), item.get("start_date")): item.get(
            "description"
        )
        for item in dynamic_experience
        if isinstance(item, dict)
    }
    result["experience"] = []
    for static_entry in static["experience"]:
        key = (
            static_entry["company"],
            static_entry["title"],
            static_entry["start_date"],
        )
        description = dynamic_descriptions.get(key)
        if not isinstance(description, list) or len(description) < 3:
            description = static_entry["description"]
        result["experience"].append(static_entry | {"description": description})
    return result
