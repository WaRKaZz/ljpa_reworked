import json
import logging
import os
import re
import tempfile
from typing import Annotated, Any

import gdown
from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from sqlalchemy import or_

from ljpa_reworked.config import CHATGPT_GDRIVE_URL
from ljpa_reworked.models.crewai_pydantic_models import VisaStatus
from ljpa_reworked.models.database_models import DataSource, Vacancy
from ljpa_reworked.models.enums import VacancyStatus

logger = logging.getLogger(__name__)

StrippedStr = Annotated[str, StringConstraints(strip_whitespace=True)]


class ChatGPTJobItem(BaseModel):
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    company: StrippedStr | None = None
    location: StrippedStr | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10)]
    submit_url: StrippedStr | None = None
    submit_email: StrippedStr | None = None
    source: str = "other"
    visa_status: VisaStatus = Field(default=VisaStatus.provided)

    @field_validator("submit_email", "submit_url", mode="before")
    @classmethod
    def empty_string_to_none(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            matches = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", v)
            if matches and "@" in v and not v.startswith(("http://", "https://")):
                return matches[0].strip()
        return v

    @field_validator("submit_email", mode="after")
    @classmethod
    def validate_email_syntax(cls, v: str | None) -> str | None:
        if v is not None:
            if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
                raise ValueError(f"Invalid email syntax: '{v}'")
        return v

    @field_validator("visa_status", mode="before")
    @classmethod
    def parse_visa_status(cls, v: Any) -> VisaStatus:
        if isinstance(v, bool):
            return VisaStatus.provided if v else VisaStatus.not_provided
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if cleaned in ("provided", "true", "yes", "sponsored"):
                return VisaStatus.provided
            if cleaned in ("not_provided", "false", "no"):
                return VisaStatus.not_provided
            if cleaned in ("not_mentioned", "none", "unknown"):
                return VisaStatus.not_mentioned
            if cleaned in ("not_required", "citizen_only"):
                return VisaStatus.not_required
            if cleaned in ("not_specified",):
                return VisaStatus.NOT_SPECIFIED
        if isinstance(v, VisaStatus):
            return v
        return VisaStatus.NOT_SPECIFIED

    @model_validator(mode="after")
    def validate_at_least_one_contact(self) -> "ChatGPTJobItem":
        email_clean = self.submit_email.strip() if self.submit_email else None
        url_clean = self.submit_url.strip() if self.submit_url else None
        if not email_clean and not url_clean:
            raise ValueError(
                "Vacancy must have at least one valid contact method (submit_url or submit_email)."
            )
        return self


class ChatGPTJobPayload(BaseModel):
    updated_at: str | None = None
    vacancies: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def support_jobs_key_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "vacancies" not in data and "jobs" in data:
                data["vacancies"] = data["jobs"]
        elif isinstance(data, list):
            data = {"vacancies": data}
        return data


def fetch_gdrive_json_data(url: str | None = None) -> Any:
    """Download Google Drive file using gdown and return parsed JSON data."""
    target_url = url or CHATGPT_GDRIVE_URL
    if not target_url or not target_url.strip():
        raise ValueError(
            "Google Drive URL is not configured. Set CHATGPT_GDRIVE_URL in .env"
        )

    logger.info("Starting download of vacancies file from Google Drive: %s", target_url)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        downloaded = gdown.download(
            url=target_url,
            output=tmp_path,
            quiet=False,
        )
        if not downloaded or not os.path.exists(tmp_path):
            raise RuntimeError(
                f"Failed to download vacancies file from Google Drive URL: {target_url}"
            )

        file_size = os.path.getsize(tmp_path)
        logger.info(
            "Successfully downloaded Google Drive file (%d bytes) to %s",
            file_size,
            tmp_path,
        )

        with open(tmp_path, encoding="utf-8") as f:
            raw_content = f.read()

        try:
            return json.loads(raw_content)
        except json.JSONDecodeError as json_err:
            logger.error(
                "Downloaded file is not valid JSON (first 200 chars): %r",
                raw_content[:200],
            )
            raise ValueError(
                f"Google Drive file content is not valid JSON: {json_err}"
            ) from json_err
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def parse_and_validate_vacancies(raw_data: Any) -> list[ChatGPTJobItem]:
    """Validate raw JSON payload against ChatGPTJobPayload and ChatGPTJobItem schema."""
    logger.info("Validating downloaded payload against vacancy schema...")

    payload = ChatGPTJobPayload.model_validate(raw_data)
    raw_vacancies = payload.vacancies
    logger.info(
        "Found %d candidate vacancy items in payload (updated_at: %s)",
        len(raw_vacancies),
        payload.updated_at or "N/A",
    )

    valid_items: list[ChatGPTJobItem] = []
    for idx, item_dict in enumerate(raw_vacancies, start=1):
        item_title = (
            item_dict.get("title", f"Item #{idx}")
            if isinstance(item_dict, dict)
            else f"Item #{idx}"
        )
        try:
            validated = ChatGPTJobItem.model_validate(item_dict)
            valid_items.append(validated)
            logger.debug(
                "Validated vacancy #%d: '%s' (Company: %s, Contacts: URL=%s, Email=%s, Visa=%s)",
                idx,
                validated.title,
                validated.company or "N/A",
                validated.submit_url or "None",
                validated.submit_email or "None",
                validated.visa_status.value,
            )
        except Exception as exc:
            logger.warning(
                "Skipping invalid vacancy #%d ('%s'): %s",
                idx,
                item_title,
                exc,
            )

    logger.info(
        "Validation complete: %d / %d vacancies passed validation.",
        len(valid_items),
        len(raw_vacancies),
    )
    return valid_items


def sync_chatgpt_vacancies_to_db(
    db,
    items: list[ChatGPTJobItem],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Sync validated ChatGPT vacancies into the SQLite database.

    Deduplicates against existing records using submit_url and submit_email + title.
    If dry_run is True, logs what records would be created without modifying the DB.
    Returns (added_count, skipped_count).
    """
    added_count = 0
    skipped_count = 0
    seen_urls_in_batch: set[str] = set()
    seen_emails_in_batch: set[tuple[str, str]] = set()

    logger.info(
        "=== Beginning database synchronization (%d items, dry_run=%s) ===",
        len(items),
        dry_run,
    )

    for idx, item in enumerate(items, start=1):
        # 1. In-batch deduplication
        if item.submit_url and item.submit_url in seen_urls_in_batch:
            logger.info(
                "[%d/%d] SKIPPED (Duplicate URL in current batch): '%s' -> %s",
                idx,
                len(items),
                item.title,
                item.submit_url,
            )
            skipped_count += 1
            continue

        email_key = (
            item.submit_email.lower() if item.submit_email else "",
            item.title.lower(),
        )
        if item.submit_email and email_key in seen_emails_in_batch:
            logger.info(
                "[%d/%d] SKIPPED (Duplicate Email+Title in current batch): '%s' -> %s",
                idx,
                len(items),
                item.title,
                item.submit_email,
            )
            skipped_count += 1
            continue

        # 2. Database deduplication
        query_filters = []
        if item.submit_url:
            query_filters.append(Vacancy.submit_url == item.submit_url)
        if item.submit_email:
            query_filters.append(
                (Vacancy.submit_email == item.submit_email)
                & (Vacancy.title == item.title)
            )

        existing = None
        if query_filters:
            existing = db.query(Vacancy).filter(or_(*query_filters)).first()

        if existing:
            contact_info = (
                f"URL={item.submit_url}"
                if item.submit_url
                else f"Email={item.submit_email}"
            )
            logger.info(
                "[%d/%d] SKIPPED (Already exists in DB with ID %d): '%s' (%s, %s)",
                idx,
                len(items),
                existing.id,
                item.title,
                item.company or "N/A",
                contact_info,
            )
            skipped_count += 1
            continue

        # 3. New record
        contact_display = []
        if item.submit_url:
            contact_display.append(f"URL: {item.submit_url}")
            seen_urls_in_batch.add(item.submit_url)
        if item.submit_email:
            contact_display.append(f"Email: {item.submit_email}")
            seen_emails_in_batch.add(email_key)

        company_info = f" [Company: {item.company}]" if item.company else ""
        location_info = f" [Location: {item.location}]" if item.location else ""

        if dry_run:
            logger.info(
                "[DRY-RUN] [WOULD CREATE] Vacancy #%d: '%s'%s%s | Contacts: %s | Visa: %s | Text length: %d chars",
                idx,
                item.title,
                company_info,
                location_info,
                ", ".join(contact_display),
                item.visa_status.value,
                len(item.text),
            )
            added_count += 1
        else:
            vacancy = Vacancy(
                title=item.title,
                text=item.text,
                submit_url=item.submit_url,
                submit_email=item.submit_email,
                source=DataSource.other,
                visa_status=item.visa_status,
                status=VacancyStatus.created,
            )
            db.add(vacancy)
            added_count += 1
            logger.info(
                "[+] [CREATED] Vacancy #%d: '%s'%s%s | Contacts: %s | Visa: %s",
                idx,
                item.title,
                company_info,
                location_info,
                ", ".join(contact_display),
                item.visa_status.value,
            )

    if not dry_run and added_count > 0:
        db.commit()
        logger.info("Successfully committed %d new vacancies to database.", added_count)

    logger.info(
        "=== ChatGPT GDrive Sync Summary: Total Valid: %d | New Added: %d | Skipped Duplicates: %d ===",
        len(items),
        added_count,
        skipped_count,
    )
    return added_count, skipped_count


class ChatGPTGDriveService:
    """High-level service orchestrating fetching, validation, and syncing of ChatGPT GDrive vacancies."""

    def __init__(self, url: str | None = None, dry_run: bool = False):
        self.url = url or CHATGPT_GDRIVE_URL
        self.dry_run = dry_run

    def run(self, db) -> tuple[int, int]:
        """Execute the ingestion pipeline."""
        raw_data = fetch_gdrive_json_data(url=self.url)
        valid_items = parse_and_validate_vacancies(raw_data)
        if not valid_items:
            logger.warning(
                "No valid vacancies found in Google Drive file. Database sync skipped."
            )
            return 0, 0
        return sync_chatgpt_vacancies_to_db(
            db=db, items=valid_items, dry_run=self.dry_run
        )
