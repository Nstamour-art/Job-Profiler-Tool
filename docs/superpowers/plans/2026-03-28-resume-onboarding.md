# Resume Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `resume.yaml` is missing, automatically run a structured section-by-section interview before the job search loop — accepting typed answers or pasted text, extracting structured YAML via `parser_model`, validating with Pydantic, confirming with the user, then writing `resume.yaml` and continuing seamlessly into the agent chat.

**Architecture:** A new `src/onboarding.py` module owns the full interview loop; `src/resume_models.py` defines Pydantic v2 wrapper models for each of the 6 resume sections; `src/prompts.py` gets 6 extraction system prompts; `src/agent.py`'s `run_agent_chat` checks for missing `resume.yaml` and calls `run_onboarding` before starting the job search. The extraction path reuses the existing `_call_with_retry` + `json-repair` + Pydantic pattern from `src/llm.py`.

**Tech Stack:** Python 3.11+, Pydantic v2, `json-repair`, `PyYAML`, existing `LLMProvider` / `_call_with_retry` from `src/llm.py`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/resume_models.py` | Create | Pydantic v2 section wrapper models + `SECTION_MODEL_MAP` |
| `src/prompts.py` | Modify | Add 6 `ONBOARDING_EXTRACT_*` prompts + `ONBOARDING_SECTION_PROMPTS` dict |
| `src/onboarding.py` | Create | Interview loop, extraction, display, confirmation, YAML write |
| `src/agent.py` | Modify | `run_agent_chat` signature drops `resume` param; adds missing-file check |
| `main.py` | Modify | Move `load_resume` inside `--url` branch; drop `resume=` from agent call |
| `tests/test_resume_models.py` | Create | Tests for Pydantic model parsing |
| `tests/test_onboarding.py` | Create | Tests for extraction, display, interview loop, full run |
| `tests/test_agent.py` | Modify | Add test for missing-file → onboarding path |

---

## Task 1: Pydantic Section Models

**Files:**
- Create: `src/resume_models.py`
- Create: `tests/test_resume_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resume_models.py
from src.resume_models import (
    BasicsSection, WorkSection, EducationSection,
    SkillsSection, ProjectsSection, CertificatesSection,
    SECTION_MODEL_MAP,
)


def test_basics_section_parses_full():
    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "summary": "Engineer",
        "location": {"city": "Montreal", "region": "QC", "countryCode": "CA"},
        "profiles": [{"network": "LinkedIn", "username": "janedoe", "url": "https://linkedin.com/in/janedoe"}],
    }
    result = BasicsSection.model_validate(data)
    assert result.name == "Jane Doe"
    assert result.profiles[0].network == "LinkedIn"
    assert result.location.city == "Montreal"


def test_basics_section_accepts_partial_input():
    result = BasicsSection.model_validate({"name": "Jane Doe"})
    assert result.name == "Jane Doe"
    assert result.email == ""
    assert result.profiles == []


def test_work_section_parses_multiple_entries():
    data = {"work": [
        {"name": "Acme", "position": "Engineer", "startDate": "2022", "highlights": ["Built API"]},
        {"name": "Startup", "position": "Lead", "startDate": "2020", "endDate": "2022"},
    ]}
    result = WorkSection.model_validate(data)
    assert len(result.work) == 2
    assert result.work[0].name == "Acme"
    assert result.work[0].highlights == ["Built API"]


def test_work_section_empty():
    result = WorkSection.model_validate({"work": []})
    assert result.work == []


def test_education_section_parses():
    data = {"education": [{"institution": "McGill", "area": "CS", "studyType": "BSc", "degree": "Bachelor of Science", "startDate": "2018", "endDate": "2022"}]}
    result = EducationSection.model_validate(data)
    assert result.education[0].institution == "McGill"


def test_skills_section_parses_groups():
    data = {"skills": [{"name": "Languages", "keywords": ["Python", "TypeScript"]}]}
    result = SkillsSection.model_validate(data)
    assert result.skills[0].keywords == ["Python", "TypeScript"]


def test_projects_section_parses():
    data = {"projects": [{"name": "My App", "description": "Cool thing", "url": "https://github.com/x", "highlights": ["Did stuff"]}]}
    result = ProjectsSection.model_validate(data)
    assert result.projects[0].name == "My App"


def test_certificates_section_parses():
    data = {"certificates": [{"name": "AWS SAA", "issuer": "Amazon"}]}
    result = CertificatesSection.model_validate(data)
    assert result.certificates[0].name == "AWS SAA"


def test_section_model_map_has_all_six_sections():
    for section in ("basics", "work", "education", "skills", "projects", "certificates"):
        assert section in SECTION_MODEL_MAP
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest tests/test_resume_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.resume_models'`

- [ ] **Step 3: Create `src/resume_models.py`**

```python
"""
Pydantic v2 models for each resume section.

Used by the onboarding extractor to validate LLM-extracted JSON.
All fields have defaults so partial extraction never raises ValidationError.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Profile(BaseModel):
    network: str = ""
    username: str = ""
    url: str = ""


class Location(BaseModel):
    city: str = ""
    region: str = ""
    countryCode: str = ""


class BasicsSection(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    location: Location = Field(default_factory=Location)
    profiles: list[Profile] = Field(default_factory=list)


class WorkEntry(BaseModel):
    name: str = ""
    location: str = ""
    position: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""
    highlights: list[str] = Field(default_factory=list)


class WorkSection(BaseModel):
    work: list[WorkEntry] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str = ""
    area: str = ""
    studyType: str = ""
    degree: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""


class EducationSection(BaseModel):
    education: list[EducationEntry] = Field(default_factory=list)


class SkillGroup(BaseModel):
    name: str = ""
    keywords: list[str] = Field(default_factory=list)


class SkillsSection(BaseModel):
    skills: list[SkillGroup] = Field(default_factory=list)


class Project(BaseModel):
    name: str = ""
    description: str = ""
    url: str = ""
    highlights: list[str] = Field(default_factory=list)


class ProjectsSection(BaseModel):
    projects: list[Project] = Field(default_factory=list)


class Certificate(BaseModel):
    name: str = ""
    issuer: str = ""


class CertificatesSection(BaseModel):
    certificates: list[Certificate] = Field(default_factory=list)


SECTION_MODEL_MAP: dict[str, type] = {
    "basics": BasicsSection,
    "work": WorkSection,
    "education": EducationSection,
    "skills": SkillsSection,
    "projects": ProjectsSection,
    "certificates": CertificatesSection,
}
```

- [ ] **Step 4: Run to confirm passing**

```
uv run pytest tests/test_resume_models.py -v
```
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/resume_models.py tests/test_resume_models.py
git commit -m "feat: add Pydantic section models for resume onboarding"
```

---

## Task 2: Onboarding Extraction Prompts

**Files:**
- Modify: `src/prompts.py` (append at end of file)
- Test: covered inline by Task 3 tests

- [ ] **Step 1: Append prompts to `src/prompts.py`**

Add this block at the very end of `src/prompts.py`:

```python
# ---------------------------------------------------------------------------
# Resume onboarding extraction prompts — one system prompt per section.
# Each is passed as `system` to parser_model via _call_with_retry.
# The user's raw input (typed or pasted) is passed as the `prompt` parameter.
# ---------------------------------------------------------------------------

ONBOARDING_EXTRACT_BASICS = """\
Extract contact and profile information from the text below.
Return ONLY valid JSON matching this schema exactly:
{
  "name": "string",
  "email": "string",
  "phone": "string",
  "summary": "string",
  "location": {"city": "string", "region": "string", "countryCode": "string"},
  "profiles": [{"network": "string", "username": "string", "url": "string"}]
}
Leave fields as empty strings or empty lists if the information is not present. Do NOT hallucinate.
"""

ONBOARDING_EXTRACT_WORK = """\
Extract all work experience entries from the text below.
Return ONLY valid JSON matching this schema exactly:
{
  "work": [
    {
      "name": "string (company name)",
      "location": "string",
      "position": "string (job title)",
      "description": "string (paragraph summary of the role; empty string if not available)",
      "startDate": "string (year or YYYY-MM)",
      "endDate": "string (year, YYYY-MM, or empty string if current role)",
      "highlights": ["string (achievement or responsibility bullet)"]
    }
  ]
}
Leave endDate as empty string for current roles. Do NOT hallucinate details not present.
"""

ONBOARDING_EXTRACT_EDUCATION = """\
Extract all education entries from the text below.
Return ONLY valid JSON matching this schema exactly:
{
  "education": [
    {
      "institution": "string",
      "area": "string (field of study)",
      "studyType": "string (e.g. BSc, MSc, PhD, Diploma)",
      "degree": "string (full degree name)",
      "description": "string (optional notes; empty string if not available)",
      "startDate": "string (year)",
      "endDate": "string (year)"
    }
  ]
}
Do NOT hallucinate. Leave fields as empty strings if not present.
"""

ONBOARDING_EXTRACT_SKILLS = """\
Extract skills from the text below, organized into named categories.
Return ONLY valid JSON matching this schema exactly:
{
  "skills": [
    {
      "name": "string (category name, e.g. 'Programming Languages', 'Cloud & DevOps')",
      "keywords": ["string"]
    }
  ]
}
Group related skills into logical categories. Do NOT hallucinate skills not mentioned in the text.
"""

ONBOARDING_EXTRACT_PROJECTS = """\
Extract portfolio or personal project entries from the text below.
Return ONLY valid JSON matching this schema exactly:
{
  "projects": [
    {
      "name": "string",
      "description": "string (one-line summary of the project)",
      "url": "string (GitHub or live URL; empty string if not mentioned)",
      "highlights": ["string (feature or achievement bullet)"]
    }
  ]
}
Do NOT hallucinate. Leave url as empty string if not mentioned.
"""

ONBOARDING_EXTRACT_CERTIFICATES = """\
Extract certifications, courses, or credentials from the text below.
Return ONLY valid JSON matching this schema exactly:
{
  "certificates": [
    {
      "name": "string (certification or course name)",
      "issuer": "string (issuing organization; empty string if not mentioned)"
    }
  ]
}
Do NOT hallucinate. Leave issuer as empty string if not mentioned.
"""

ONBOARDING_SECTION_PROMPTS: dict[str, str] = {
    "basics":       ONBOARDING_EXTRACT_BASICS,
    "work":         ONBOARDING_EXTRACT_WORK,
    "education":    ONBOARDING_EXTRACT_EDUCATION,
    "skills":       ONBOARDING_EXTRACT_SKILLS,
    "projects":     ONBOARDING_EXTRACT_PROJECTS,
    "certificates": ONBOARDING_EXTRACT_CERTIFICATES,
}
```

- [ ] **Step 2: Verify prompts are importable**

```
uv run python -c "from src.prompts import ONBOARDING_SECTION_PROMPTS; print(list(ONBOARDING_SECTION_PROMPTS.keys()))"
```
Expected:
```
['basics', 'work', 'education', 'skills', 'projects', 'certificates']
```

- [ ] **Step 3: Commit**

```bash
git add src/prompts.py
git commit -m "feat: add onboarding extraction prompts to prompts.py"
```

---

## Task 3: Onboarding Interview Loop

**Files:**
- Create: `src/onboarding.py`
- Create: `tests/test_onboarding.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_onboarding.py
import yaml
import pytest
from unittest.mock import patch, MagicMock

from src.resume_models import (
    BasicsSection, WorkSection, WorkEntry,
    EducationSection, SkillsSection, ProjectsSection, CertificatesSection,
)


# ---------------------------------------------------------------------------
# extract_section
# ---------------------------------------------------------------------------

def test_extract_section_basics_calls_call_with_retry(sample_config):
    mock_provider = MagicMock()
    expected = BasicsSection(name="Jane Doe", email="jane@example.com")

    with patch("src.onboarding._call_with_retry", return_value=expected) as mock_retry:
        from src.onboarding import extract_section
        result = extract_section(
            "basics", "Jane Doe, jane@example.com",
            mock_provider, ["model"], sample_config["llm"],
        )

    assert result.name == "Jane Doe"
    assert mock_retry.called


def test_extract_section_correction_appends_to_input(sample_config):
    mock_provider = MagicMock()
    expected = BasicsSection(name="Jane Smith")

    with patch("src.onboarding._call_with_retry", return_value=expected) as mock_retry:
        from src.onboarding import extract_section
        extract_section(
            "basics", "Jane Doe", mock_provider, ["model"], sample_config["llm"],
            correction="My last name is Smith",
        )

    # The 5th positional arg to _call_with_retry is the user prompt text
    call_args = mock_retry.call_args[0]
    user_text = call_args[4]
    assert "Original input" in user_text
    assert "User correction" in user_text
    assert "My last name is Smith" in user_text


# ---------------------------------------------------------------------------
# _section_to_dict
# ---------------------------------------------------------------------------

def test_section_to_dict_basics_returns_flat_dict():
    from src.onboarding import _section_to_dict
    basics = BasicsSection(name="Jane Doe", email="jane@example.com")
    result = _section_to_dict("basics", basics)
    assert isinstance(result, dict)
    assert result["name"] == "Jane Doe"


def test_section_to_dict_work_returns_list():
    from src.onboarding import _section_to_dict
    work = WorkSection(work=[WorkEntry(name="Acme", position="Engineer")])
    result = _section_to_dict("work", work)
    assert isinstance(result, list)
    assert result[0]["name"] == "Acme"


# ---------------------------------------------------------------------------
# _empty_section
# ---------------------------------------------------------------------------

def test_empty_section_basics_returns_empty_dict():
    from src.onboarding import _empty_section
    assert _empty_section("basics") == {}


def test_empty_section_work_returns_empty_list():
    from src.onboarding import _empty_section
    assert _empty_section("work") == []


def test_empty_section_certificates_returns_empty_list():
    from src.onboarding import _empty_section
    assert _empty_section("certificates") == []


# ---------------------------------------------------------------------------
# _interview_section — yes flow
# ---------------------------------------------------------------------------

def test_interview_section_yes_flow(sample_config):
    mock_provider = MagicMock()
    expected = BasicsSection(name="Jane Doe", email="jane@example.com")
    inputs = iter(["Jane Doe, jane@example.com", "yes"])

    with patch("src.onboarding.extract_section", return_value=expected):
        with patch("builtins.input", side_effect=inputs):
            from src.onboarding import _interview_section
            result = _interview_section("basics", mock_provider, ["model"], sample_config["llm"])

    assert result["name"] == "Jane Doe"


# ---------------------------------------------------------------------------
# _interview_section — skip flow
# ---------------------------------------------------------------------------

def test_interview_section_skip_at_prompt_returns_empty(sample_config):
    mock_provider = MagicMock()
    inputs = iter(["skip"])

    with patch("builtins.input", side_effect=inputs):
        from src.onboarding import _interview_section
        result = _interview_section("work", mock_provider, ["model"], sample_config["llm"])

    assert result == []


def test_interview_section_skip_at_confirm_returns_empty(sample_config):
    mock_provider = MagicMock()
    expected = WorkSection(work=[WorkEntry(name="Acme")])
    inputs = iter(["Acme Corp, Engineer, 2022-present", "skip"])

    with patch("src.onboarding.extract_section", return_value=expected):
        with patch("builtins.input", side_effect=inputs):
            from src.onboarding import _interview_section
            result = _interview_section("work", mock_provider, ["model"], sample_config["llm"])

    assert result == []


# ---------------------------------------------------------------------------
# run_onboarding — integration (mocks _interview_section)
# ---------------------------------------------------------------------------

def test_run_onboarding_writes_resume_yaml(tmp_path, sample_config):
    sample_config["paths"]["resume_yaml"] = str(tmp_path / "resume.yaml")

    section_values = {
        "basics": {"name": "Jane Doe", "email": "jane@example.com", "phone": "", "summary": "", "location": {}, "profiles": []},
        "work": [],
        "education": [],
        "skills": [],
        "projects": [],
        "certificates": [],
    }

    with patch("src.onboarding._interview_section", side_effect=lambda s, *a, **k: section_values[s]):
        with patch("src.providers.get_provider", return_value=MagicMock()):
            with patch("src.providers.resolve_models", return_value=(["m"], ["m"])):
                from src.onboarding import run_onboarding
                resume = run_onboarding(sample_config, "local")

    assert (tmp_path / "resume.yaml").exists()
    loaded = yaml.safe_load((tmp_path / "resume.yaml").read_text(encoding="utf-8"))
    assert loaded["basics"]["name"] == "Jane Doe"
    assert loaded["work"] == []
    assert resume["basics"]["name"] == "Jane Doe"


def test_run_onboarding_returns_complete_resume_dict(tmp_path, sample_config):
    sample_config["paths"]["resume_yaml"] = str(tmp_path / "resume.yaml")

    section_values = {s: ({} if s == "basics" else []) for s in
                      ("basics", "work", "education", "skills", "projects", "certificates")}

    with patch("src.onboarding._interview_section", side_effect=lambda s, *a, **k: section_values[s]):
        with patch("src.providers.get_provider", return_value=MagicMock()):
            with patch("src.providers.resolve_models", return_value=(["m"], ["m"])):
                from src.onboarding import run_onboarding
                resume = run_onboarding(sample_config, "local")

    for section in ("basics", "work", "education", "skills", "projects", "certificates"):
        assert section in resume
```

- [ ] **Step 2: Run to confirm failure**

```
uv run pytest tests/test_onboarding.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.onboarding'`

- [ ] **Step 3: Create `src/onboarding.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_onboarding.py -v
```
Expected: `12 passed`

- [ ] **Step 5: Run full suite**

```
uv run pytest --tb=short -q
```
Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/onboarding.py tests/test_onboarding.py
git commit -m "feat: add resume onboarding interview loop"
```

---

## Task 4: Wire Missing-File Check into Agent Entry Point

**Files:**
- Modify: `src/agent.py`
- Modify: `main.py`
- Modify: `tests/test_agent.py`

The `run_agent_chat` signature currently takes `resume: dict` as a parameter. `main.py` loads the resume before calling it. This task moves resume loading inside `run_agent_chat` so it can detect a missing file and run onboarding first.

- [ ] **Step 1: Read current `src/agent.py` line 72 onwards**

Confirm `run_agent_chat` starts at line 72 with signature:
```python
def run_agent_chat(config: dict, resume: dict, provider_name: str) -> None:
```

- [ ] **Step 2: Write the new failing tests**

Append these two tests to `tests/test_agent.py`:

```python
def test_run_agent_chat_calls_onboarding_when_resume_missing(tmp_path, sample_config, sample_resume):
    """run_agent_chat triggers run_onboarding when resume.yaml does not exist."""
    sample_config["paths"]["resume_yaml"] = str(tmp_path / "resume.yaml")
    # File does NOT exist — tmp_path / "resume.yaml" is not created

    with patch("src.agent.run_onboarding", return_value=sample_resume) as mock_onboard, \
         patch("src.agent.MemoryManager") as mock_mm, \
         patch("src.agent.build_agent", return_value=MagicMock()), \
         patch("builtins.input", side_effect=KeyboardInterrupt):
        mock_mm.return_value.recall.return_value = ""
        mock_mm.return_value.start.return_value = None
        mock_mm.return_value.stop.return_value = None
        from src.agent import run_agent_chat
        run_agent_chat(config=sample_config, provider_name="local")

    mock_onboard.assert_called_once_with(sample_config, "local")


def test_run_agent_chat_loads_resume_from_disk_when_exists(tmp_path, sample_config, sample_resume):
    """run_agent_chat reads resume.yaml from disk when the file exists."""
    import yaml as _yaml
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(_yaml.dump(sample_resume), encoding="utf-8")
    sample_config["paths"]["resume_yaml"] = str(resume_path)

    with patch("src.agent.run_onboarding") as mock_onboard, \
         patch("src.agent.MemoryManager") as mock_mm, \
         patch("src.agent.build_agent", return_value=MagicMock()), \
         patch("builtins.input", side_effect=KeyboardInterrupt):
        mock_mm.return_value.recall.return_value = ""
        mock_mm.return_value.start.return_value = None
        mock_mm.return_value.stop.return_value = None
        from src.agent import run_agent_chat
        run_agent_chat(config=sample_config, provider_name="local")

    mock_onboard.assert_not_called()
```

- [ ] **Step 3: Run to confirm failure**

```
uv run pytest tests/test_agent.py::test_run_agent_chat_calls_onboarding_when_resume_missing tests/test_agent.py::test_run_agent_chat_loads_resume_from_disk_when_exists -v
```
Expected: `TypeError` (wrong number of arguments to `run_agent_chat`)

- [ ] **Step 4: Update `src/agent.py`**

Replace the `run_agent_chat` function (starting at line 72) with:

```python
def run_agent_chat(config: dict, provider_name: str) -> None:
    """Start the interactive chat loop with the job search agent.

    If resume.yaml does not exist, runs the onboarding interview first.
    """
    import yaml as _yaml

    resume_path = config["paths"]["resume_yaml"]
    if not Path(resume_path).exists():
        from src.onboarding import run_onboarding
        resume = run_onboarding(config, provider_name)
    else:
        with open(resume_path, encoding="utf-8") as f:
            resume = _yaml.safe_load(f)

    memory = MemoryManager(config=config, resume=resume, provider_name=provider_name)
    memory.start()

    recalled_prefs = memory.recall("What are this user's job search preferences?")
    recalled_jobs = memory.recall("What jobs has this user already been shown?")
    recalled_memories = "\n".join(filter(None, [recalled_prefs, recalled_jobs]))

    agent = build_agent(config, resume, provider_name, recalled_memories)
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    print("\nJob Search Agent ready. Type 'exit' to quit.\n")

    history: list[dict] = []

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAgent: Goodbye!")
                break

            if user_input.lower() in ("exit", "quit", "bye"):
                print("Agent: Goodbye! Good luck with your applications.")
                break

            if not user_input:
                continue

            history.append({"role": "user", "content": user_input})

            print("Agent: ", end="", flush=True)
            try:
                result = agent.invoke({"messages": history}, thread_config)
                last_msg = result["messages"][-1]
                response_text = (
                    last_msg.content
                    if isinstance(last_msg.content, str)
                    else str(last_msg.content)
                )
                print(response_text)
                history = result["messages"]
                memory.retain(
                    f"User said: {user_input}\nAgent responded: {response_text[:300]}",
                    context="conversation",
                )
            except Exception as exc:
                print(f"\n[Agent error: {exc}]")
    finally:
        memory.stop()
```

Also add `from pathlib import Path` to the imports at the top of `src/agent.py` if not already present.

- [ ] **Step 5: Update `main.py`**

In `run_jobs`, move `resume = load_resume(...)` inside the `if direct_url:` block and remove it from the agent branch.

Replace this section of `run_jobs`:

```python
    config  = load_config(config_path)
    resume  = load_resume(config["paths"]["resume_yaml"])

    from src.providers import get_provider, resolve_models
    resolved_provider = provider_name or "local"

    # --- Direct URL mode (existing pipeline, unchanged) ---
    if direct_url:
        llm_cfg = config["llm"]
        provider = get_provider(resolved_provider, llm_cfg)
```

With:

```python
    config = load_config(config_path)

    from src.providers import get_provider, resolve_models
    resolved_provider = provider_name or "local"

    # --- Direct URL mode (existing pipeline, unchanged) ---
    if direct_url:
        resume = load_resume(config["paths"]["resume_yaml"])
        llm_cfg = config["llm"]
        provider = get_provider(resolved_provider, llm_cfg)
```

And replace the agent mode call:

```python
    # --- Agent mode (default when no --url) ---
    from src.agent import run_agent_chat
    run_agent_chat(config=config, resume=resume, provider_name=resolved_provider)
```

With:

```python
    # --- Agent mode (default when no --url) ---
    from src.agent import run_agent_chat
    run_agent_chat(config=config, provider_name=resolved_provider)
```

- [ ] **Step 6: Run the new tests**

```
uv run pytest tests/test_agent.py -v
```
Expected: `4 passed` (2 existing + 2 new)

- [ ] **Step 7: Run full suite**

```
uv run pytest --tb=short -q
```
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/agent.py main.py tests/test_agent.py
git commit -m "feat: wire onboarding into agent entry point; auto-run when resume.yaml missing"
```

---

## Self-Review

### Spec Coverage

| Spec requirement | Task |
|-----------------|------|
| Auto-detect missing resume.yaml | Task 4 |
| Structured section-by-section interview | Task 3 (`_interview_section`) |
| Accept pasted text at any point | Task 3 (raw input passed to LLM extractor) |
| LLM extraction via parser_model | Task 3 (`extract_section` → `_call_with_retry`) |
| Pydantic validation | Task 1 (models) + Task 3 (used in extraction) |
| json-repair retry on invalid JSON | Inherited from `_call_with_retry` in Task 3 |
| Confirmation UX (yes / edit / skip) | Task 3 (`_interview_section`) |
| Edit flow appends correction to original input | Task 3 (`extract_section` with `correction`) |
| Write resume.yaml on completion | Task 3 (`run_onboarding`) |
| Transition directly to job search loop | Task 4 (`run_agent_chat` continues after `run_onboarding`) |
| Opening prompts per section | Task 3 (`_OPENING_PROMPTS`) |
| skip keyword skips section with empty value | Task 3 |

### Placeholder Scan

No TBDs, TODOs, or vague steps. All code blocks are complete.

### Type Consistency

- `extract_section` returns a Pydantic `BaseModel` subclass
- `_section_to_dict` takes that model and returns `dict` (basics) or `list` (all others)
- `run_onboarding` assembles via `{section: sections[section]}` — values are already plain dicts/lists
- `run_agent_chat(config, provider_name)` — no `resume` param; consistent across `main.py` call and new tests
- `build_agent(config, resume, provider_name, recalled_memories)` — unchanged, still takes `resume`
