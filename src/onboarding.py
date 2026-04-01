"""
Resume onboarding interview.

Runs a structured section-by-section interview when resume.yaml does not exist.
Each user answer (typed or pasted) is sent to parser_model for extraction and
validated with Pydantic. The user confirms each section before it is saved.
After all 6 sections, resume.yaml is written and the dict is returned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import ProviderSuite

import yaml

from src import ui
from src.llm import _call_with_retry
from src.resume_models import SECTION_MODEL_MAP
from src.prompts import ONBOARDING_SECTION_PROMPTS


SECTION_ORDER = ["basics", "work", "education", "skills", "projects", "certificates"]

_OPENING_PROMPTS: dict[str, str] = {
    "basics": (
        "Let's start with your basic info. What's your name, email, phone, location, "
        "and any LinkedIn or GitHub profiles? You can type it out or paste from your profile."
    ),
    "work": (
        "Tell me about your work history. Start with your most recent role — "
        "or paste multiple jobs at once."
    ),
    "education": (
        "What's your educational background? Include your degree, field of study, "
        "institution, and years."
    ),
    "skills": (
        "What are your key skills? List them freely, by category, or paste from your resume."
    ),
    "projects": (
        "Do you have any personal or portfolio projects to include? "
        "(Type 'skip' to leave this section empty)"
    ),
    "certificates": (
        "Any certifications or completed courses? "
        "(Type 'skip' to leave this section empty)"
    ),
}


def extract_section(
    section: str,
    raw_input: str,
    provider_suite: "ProviderSuite",
    llm_cfg: dict,
    correction: str | None = None,
) -> Any:
    """Send raw user input to parser_model and return a validated Pydantic section model."""
    if correction:
        user_text = (
            f"Original input:\n{raw_input}\n\n"
            f"User correction:\n{correction}\n\n"
            "Apply the correction and return updated JSON."
        )
    else:
        user_text = raw_input

    system_prompt = ONBOARDING_SECTION_PROMPTS[section]
    model_class = SECTION_MODEL_MAP[section]
    return _call_with_retry(
        model_class, provider_suite.provider, llm_cfg,
        system_prompt, user_text, provider_suite.parser_models
    )


def _section_to_dict(section: str, extracted: Any) -> Any:
    """Convert a Pydantic section model to a plain dict or list for YAML output."""
    data = extracted.model_dump()
    if section == "basics":
        return data
    return data[section]  # e.g. WorkSection.model_dump() -> {"work": [...]} -> [...]


def _empty_section(section: str) -> Any:
    """Return an appropriate empty value for the section (dict for basics, list for others)."""
    if section == "basics":
        return {}
    return []


def _format_extracted(section: str, extracted: Any) -> str:
    """Format a Pydantic section model as readable YAML text for the confirmation prompt."""
    data = _section_to_dict(section, extracted)
    return yaml.dump(data, allow_unicode=True, default_flow_style=False).rstrip()


def _interview_section(
    section: str,
    provider_suite: "ProviderSuite",
    llm_cfg: dict,
) -> Any:
    """Run the interactive loop for one section. Returns the confirmed plain dict or list."""
    ui.print_section_header(section)
    ui.print_onboarding_question(_OPENING_PROMPTS[section])

    while True:
        raw = input(ui.onboarding_input_prompt()).strip()
        if not raw:
            continue
        if raw.lower() == "skip":
            ui.print_step(f"Skipping {section}.")
            return _empty_section(section)

        try:
            with ui.thinking_spinner("Parsing your input\u2026"):
                extracted = extract_section(section, raw, provider_suite, llm_cfg)
        except RuntimeError as exc:
            ui.print_error(f"Extraction failed: {exc}. Please try again.")
            continue

        ui.print_extracted_preview(section, _format_extracted(section, extracted))

        while True:
            answer = input(ui.onboarding_confirm_prompt()).strip().lower()
            if answer == "yes":
                return _section_to_dict(section, extracted)
            if answer == "skip":
                ui.print_step(f"Skipping {section}.")
                return _empty_section(section)
            if answer == "edit":
                correction = input(ui.onboarding_edit_prompt()).strip()
                if not correction:
                    continue
                try:
                    with ui.thinking_spinner("Applying correction\u2026"):
                        extracted = extract_section(
                            section, raw, provider_suite, llm_cfg, correction=correction
                        )
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    ui.print_error(f"Re-extraction failed: {exc}. Keeping previous result.")
                else:
                    ui.print_extracted_preview(section, _format_extracted(section, extracted))
            else:
                ui.print_step("Please type 'yes', 'edit', or 'skip'.")


def run_onboarding(config: dict, provider_name: str) -> dict:
    """Run the full resume onboarding interview. Returns the completed resume dict.

    Writes resume.yaml to config["paths"]["resume_yaml"] before returning.
    """
    from src.providers import get_provider, resolve_models  # pylint: disable=import-outside-toplevel
    from src.models import ProviderSuite  # pylint: disable=import-outside-toplevel

    provider = get_provider(provider_name, config["llm"])
    models, parser_models = resolve_models(provider_name, config["llm"])
    ps = ProviderSuite(
        provider=provider,
        models=models,
        parser_models=parser_models,
        name=provider_name
    )
    llm_cfg = config["llm"]

    ui.print_onboarding_intro()

    sections: dict[str, Any] = {}
    for section in SECTION_ORDER:
        sections[section] = _interview_section(section, ps, llm_cfg)

    resume = {section: sections[section] for section in SECTION_ORDER}

    resume_path = config["paths"]["resume_yaml"]
    Path(resume_path).parent.mkdir(parents=True, exist_ok=True)
    with open(resume_path, "w", encoding="utf-8") as f:
        yaml.dump(resume, f, allow_unicode=True, default_flow_style=False)

    ui.print_success("resume.yaml created. Let's find you some jobs!")
    return resume
