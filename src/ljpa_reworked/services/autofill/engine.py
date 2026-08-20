from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import anyio
from playwright.async_api import ElementHandle, Page

from ljpa_reworked.services.autofill.profile_parser import CandidateProfile
from ljpa_reworked.services.autofill.registry import (
    CanonicalField,
    classify_control,
)

logger = logging.getLogger(__name__)


@dataclass
class FieldFillRecord:
    field: str
    canonical: str
    selector: str
    value_source: str


@dataclass
class UploadedFileRecord:
    field: str
    selector: str
    file: str


@dataclass
class UnresolvedFieldRecord:
    label: str
    kind: str
    required: bool
    reason: str


@dataclass
class AutofillResult:
    status: str = "complete"  # "complete" | "partial" | "error"
    filled_count: int = 0
    filled: list[FieldFillRecord] = field(default_factory=list)
    uploaded: list[UploadedFileRecord] = field(default_factory=list)
    unresolved: list[UnresolvedFieldRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Patterns that clearly represent required application privacy / mandatory data processing terms
REQUIRED_PRIVACY_PATTERNS = [
    r"\bprivacy\s+policy\b",
    r"\bdata\s+processing\b",
    r"\bterms\s+(?:and|&)\s+conditions\b",
    r"\bconsent\s+to\s+process\b",
    r"\bdata\s+protection\b",
    r"\bapplicant\s+privacy\b",
    r"\bterms\s+of\s+use\b",
    r"\baccept\s+terms\b",
]

# Patterns that indicate optional / marketing / promotional choices
MARKETING_OPT_PATTERNS = [
    r"\bmarketing\b",
    r"\bpromotional\b",
    r"\bnewsletter\b",
    r"\btalent\s+community\b",
    r"\btalent\s+network\b",
    r"\bjob\s+alerts\b",
    r"\bsms\s+updates\b",
    r"\bfuture\s+opportunities\b",
]


def _is_safe_required_consent(text: str, is_required: bool) -> bool:
    if not text:
        return False
    lower = text.lower()
    if any(re.search(pat, lower) for pat in MARKETING_OPT_PATTERNS):
        return False
    if is_required and any(re.search(pat, lower) for pat in REQUIRED_PRIVACY_PATTERNS):
        return True
    return False


async def _get_control_info(element: ElementHandle, page: Page) -> dict[str, Any]:
    """Extract semantic and DOM attributes from an interactive form element."""
    return await page.evaluate(
        """(el) => {
            let tag = el.tagName.toLowerCase();
            let type = (el.getAttribute('type') || '').toLowerCase();
            let autocomplete = el.getAttribute('autocomplete') || '';
            let name = el.getAttribute('name') || '';
            let id = el.getAttribute('id') || '';
            let placeholder = el.getAttribute('placeholder') || '';
            let ariaLabel = el.getAttribute('aria-label') || '';
            let ariaLabelledBy = el.getAttribute('aria-labelledby') || '';
            let required = el.hasAttribute('required') || el.getAttribute('aria-required') === 'true';
            let role = el.getAttribute('role') || '';
            let disabled = el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';
            let readonly = el.hasAttribute('readonly');

            // Find associated label text
            let labelText = '';
            if (id) {
                let lbl = document.querySelector(`label[for="${id}"]`);
                if (lbl) labelText = lbl.textContent || '';
            }
            if (!labelText) {
                let parentLabel = el.closest('label');
                if (parentLabel) labelText = parentLabel.textContent || '';
            }
            if (!labelText && ariaLabelledBy) {
                let lblEl = document.getElementById(ariaLabelledBy);
                if (lblEl) labelText = lblEl.textContent || '';
            }

            // Check if label indicates required (*)
            if (labelText && labelText.includes('*')) {
                required = true;
            }

            // Extract select options if native select
            let options = [];
            if (tag === 'select') {
                options = Array.from(el.options).map(o => ({ value: o.value, text: o.text }));
            }

            return {
                tag,
                type,
                autocomplete,
                name,
                id,
                placeholder,
                aria_label: ariaLabel,
                label: labelText.trim(),
                required,
                role,
                disabled,
                readonly,
                options
            };
        }""",
        element,
    )


async def fill_form_batch(
    page: Page,
    profile: CandidateProfile,
    resume_path: Path | str | None = None,
) -> AutofillResult:
    """Analyze form elements on active page and fill recognized fields in batch."""
    result = AutofillResult()

    resolved_resume: str | None = None
    if resume_path:
        anyio_p = anyio.Path(resume_path)
        if await anyio_p.exists():
            resolved_resume = str(await anyio_p.resolve())
        else:
            result.errors.append(f"Resume file not found at: {resume_path}")

    # Step 1: Detect custom comboboxes or non-native custom dropdowns
    custom_combos = await page.query_selector_all(
        '[role="combobox"], spl-autocomplete, div.select2-container, div.v-select'
    )
    for combo in custom_combos:
        if not await combo.is_visible():
            continue
        info = await _get_control_info(combo, page)
        lbl = (
            info.get("label")
            or info.get("aria_label")
            or info.get("name")
            or "Custom combobox"
        )
        result.unresolved.append(
            UnresolvedFieldRecord(
                label=lbl,
                kind="custom_combobox",
                required=info.get("required", True),
                reason="non-native widget",
            )
        )

    # Step 2: Query interactive form controls (input, select, textarea)
    controls = await page.query_selector_all("input, select, textarea")

    for control in controls:
        try:
            if not await control.is_visible():
                # If it's a hidden file input for resume upload (e.g. dropzone file inputs), still allow
                ctype = await control.get_attribute("type")
                if ctype != "file":
                    continue

            info = await _get_control_info(control, page)
            if info.get("disabled") or info.get("readonly"):
                continue

            tag = info["tag"]
            ctype = info["type"]
            label_text = (
                info["label"] or info["aria_label"] or info["name"] or info["id"]
            )
            is_required = info.get("required", False)

            # Skip submit / button inputs
            if ctype in ("submit", "button", "reset", "image"):
                continue

            # Checkbox handling (Safe Consent Policy)
            if ctype == "checkbox":
                full_text = f"{info['label']} {info['aria_label']}"
                if _is_safe_required_consent(full_text, is_required):
                    try:
                        input_id = info.get("id")
                        locator = (
                            page.locator(f"#{input_id}")
                            if input_id
                            else page.locator(f"input[name='{info['name']}']")
                        )
                        if not await locator.is_checked():
                            await locator.check()
                        result.filled.append(
                            FieldFillRecord(
                                field=label_text or "Required Privacy Consent",
                                canonical="privacy_consent",
                                selector=f"#{input_id}" if input_id else "checkbox",
                                value_source="policy.safe_required_consent",
                            )
                        )
                        result.filled_count += 1
                    except Exception as e:
                        logger.warning(
                            "Failed to check required consent checkbox: %s", e
                        )
                elif is_required and not any(
                    re.search(pat, full_text.lower()) for pat in MARKETING_OPT_PATTERNS
                ):
                    result.unresolved.append(
                        UnresolvedFieldRecord(
                            label=label_text or "Required Checkbox",
                            kind="checkbox",
                            required=True,
                            reason="unrecognized required checkbox",
                        )
                    )
                continue

            # Classify control against Canonical Registry
            canonical, score = classify_control(info)

            # File input handling (Resume)
            if canonical == CanonicalField.RESUME or ctype == "file":
                if resolved_resume:
                    input_id = info.get("id")
                    name_attr = info.get("name")
                    selector = (
                        f"#{input_id}"
                        if input_id
                        else (
                            f"input[name='{name_attr}']"
                            if name_attr
                            else "input[type='file']"
                        )
                    )
                    await control.set_input_files(resolved_resume)
                    result.uploaded.append(
                        UploadedFileRecord(
                            field=label_text or "Resume Attachment",
                            selector=selector,
                            file=resolved_resume,
                        )
                    )
                    result.filled_count += 1
                    continue
                if is_required:
                    result.unresolved.append(
                        UnresolvedFieldRecord(
                            label=label_text or "Resume Upload",
                            kind="file",
                            required=True,
                            reason="resume path missing or file not found",
                        )
                    )
                continue

            # If matched canonically with high confidence:
            if canonical:
                val = profile.get_canonical_value(canonical.value)
                if val is not None and str(val).strip():
                    val_str = str(val).strip()
                    input_id = info.get("id")
                    name_attr = info.get("name")
                    selector = (
                        f"#{input_id}"
                        if input_id
                        else (f"{tag}[name='{name_attr}']" if name_attr else f"{tag}")
                    )

                    if tag == "select":
                        # Match native select options
                        options = info.get("options", [])
                        selected = False
                        # 1. Try matching by exact option value
                        for opt in options:
                            if opt["value"].lower() == val_str.lower():
                                await control.select_option(value=opt["value"])
                                selected = True
                                break
                        # 2. Try matching by option text / label
                        if not selected:
                            for opt in options:
                                if (
                                    val_str.lower() in opt["text"].lower()
                                    or opt["text"].lower() in val_str.lower()
                                ):
                                    await control.select_option(value=opt["value"])
                                    selected = True
                                    break
                        if selected:
                            result.filled.append(
                                FieldFillRecord(
                                    field=label_text or canonical.value,
                                    canonical=canonical.value,
                                    selector=selector,
                                    value_source=f"profile.{canonical.value}",
                                )
                            )
                            result.filled_count += 1
                        else:
                            if is_required:
                                result.unresolved.append(
                                    UnresolvedFieldRecord(
                                        label=label_text or canonical.value,
                                        kind="select",
                                        required=True,
                                        reason=f"option for '{val_str}' not found in select dropdown",
                                    )
                                )
                    elif tag in ("input", "textarea"):
                        # Native Playwright fill
                        locator = page.locator(selector).first
                        await locator.fill(val_str)
                        result.filled.append(
                            FieldFillRecord(
                                field=label_text or canonical.value,
                                canonical=canonical.value,
                                selector=selector,
                                value_source=f"profile.{canonical.value}",
                            )
                        )
                        result.filled_count += 1
                    continue

            # If control is unclassified or no profile value:
            if is_required:
                result.unresolved.append(
                    UnresolvedFieldRecord(
                        label=label_text or "Unmatched field",
                        kind=tag if tag != "input" else ctype,
                        required=True,
                        reason="unmatched required field / semantic question",
                    )
                )

        except Exception as err:
            logger.error("Error processing form control: %s", err)
            result.errors.append(str(err))

    # Determine overall status
    if result.errors:
        result.status = "error"
    elif any(u.required for u in result.unresolved):
        result.status = "partial"
    else:
        result.status = "complete"

    return result
