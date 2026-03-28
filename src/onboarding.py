"""
Resume onboarding interview.

Runs a structured section-by-section interview when resume.yaml does not exist.
Each user answer (typed or pasted) is sent to parser_model for extraction and
validated with Pydantic. The user confirms each section before it is saved.
After all 6 sections, resume.yaml is written and the dict is returned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

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
    provider,
    parser_models: list[str],
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
    return _call_with_retry(model_class, provider, llm_cfg, system_prompt, user_text, parser_models)


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
    provider: Any,
    parser_models: list[str],
    llm_cfg: dict,
) -> Any:
    """Run the interactive loop for one section. Returns the confirmed plain dict or list."""
    print(f"\n{_OPENING_PROMPTS[section]}\n")

    while True:
        raw = input("> ").strip()
        if not raw:
            continue
        if raw.lower() == "skip":
            print(f"  Skipping {section}.\n")
            return _empty_section(section)

        try:
            extracted = extract_section(section, raw, provider, parser_models, llm_cfg)
        except Exception as exc:
            print(f"  Extraction failed: {exc}. Please try again.\n")
            continue

        print(f"\nHere's what I captured for {section}:\n")
        print(_format_extracted(section, extracted))
        print()

        while True:
            answer = input("Does this look right? (yes / edit / skip) > ").strip().lower()
            if answer == "yes":
                return _section_to_dict(section, extracted)
            elif answer == "skip":
                print(f"  Skipping {section}.\n")
                return _empty_section(section)
            elif answer == "edit":
                correction = input("What should be changed? > ").strip()
                if not correction:
                    continue
                try:
                    extracted = extract_section(
                        section, raw, provider, parser_models, llm_cfg, correction=correction
                    )
                except Exception as exc:
                    print(f"  Re-extraction failed: {exc}. Keeping previous result.\n")
                print(f"\nUpdated {section}:\n")
                print(_format_extracted(section, extracted))
                print()
            else:
                print("  Please type 'yes', 'edit', or 'skip'.")


def run_onboarding(config: dict, provider_name: str) -> dict:
    """Run the full resume onboarding interview. Returns the completed resume dict.

    Writes resume.yaml to config["paths"]["resume_yaml"] before returning.
    """
    from src.providers import get_provider, resolve_models

    provider = get_provider(provider_name, config["llm"])
    _, parser_models = resolve_models(provider_name, config["llm"])
    llm_cfg = config["llm"]

    print("\nWelcome! No resume.yaml found. Let's build it together.")
    print("You can type short answers or paste text from your existing resume or LinkedIn.\n")

    sections: dict[str, Any] = {}
    for section in SECTION_ORDER:
        sections[section] = _interview_section(section, provider, parser_models, llm_cfg)

    resume = {section: sections[section] for section in SECTION_ORDER}

    resume_path = config["paths"]["resume_yaml"]
    Path(resume_path).parent.mkdir(parents=True, exist_ok=True)
    with open(resume_path, "w", encoding="utf-8") as f:
        yaml.dump(resume, f, allow_unicode=True, default_flow_style=False)

    print(f"\nresume.yaml created. Let's find you some jobs!\n")
    return resume
