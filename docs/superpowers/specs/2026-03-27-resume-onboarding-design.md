# Resume Onboarding — Design Spec
**Date:** 2026-03-27
**Status:** Approved

---

## Overview

When a new user runs `uv run python main.py run` and no `resume.yaml` exists, the tool automatically enters an interactive onboarding interview before starting the job search loop. The interview walks the user through their resume section by section, accepts typed answers or pasted text (LinkedIn, PDF copy-paste, old resume), extracts structured data using the lightweight `parser_model`, validates it with Pydantic, confirms with the user, and writes `resume.yaml`. Once complete, the session transitions directly into the job search agent loop — no restart required.

---

## Goals

- Zero-friction first run: no manual `cp example_resume.yaml resume.yaml` step
- Accept any form of input — typed sentences, bullet lists, pasted LinkedIn/resume text
- Use `parser_model` (lightweight) for extraction; Pydantic for schema validation
- Confirm each section with the user before saving
- Transition directly to the job search loop after onboarding completes

---

## Architecture

### Entry Point

`run_agent_chat` in `src/agent.py` checks whether `resume.yaml` exists at `config["paths"]["resume_yaml"]` before loading it. If the file is missing, it calls:

```python
from src.onboarding import run_onboarding
resume = run_onboarding(config, provider_name)
```

`run_onboarding` returns the completed resume dict. `run_agent_chat` then continues normally with that dict — no restart, same session.

### New File: `src/onboarding.py`

Owns the full interview loop. No agents, no tools, no LangGraph — just a structured Python loop with LLM extraction calls.

```
run_onboarding(config, provider_name)
  └── for each section in SECTION_ORDER:
        ask_section(section)         # print opening prompt, read user input
        extract_section(section, raw_input, llm)   # LLM + json-repair + Pydantic
        confirm_section(section, extracted)        # show result, get yes/edit/skip
        if edit: re-extract with correction appended
        if skip: store empty value
  └── assemble_resume(sections)      # merge all confirmed sections into full dict
  └── write resume.yaml
  └── return resume dict
```

### New File: `src/resume_models.py`

Pydantic v2 models for each resume section. Used by both the onboarding extractor and (optionally) the existing `write_resume_section` tool for validation.

```python
class Profile(BaseModel): ...
class Basics(BaseModel): ...
class WorkEntry(BaseModel): ...
class EducationEntry(BaseModel): ...
class SkillGroup(BaseModel): ...
class Project(BaseModel): ...
class Certificate(BaseModel): ...
```

### Modified File: `src/agent.py`

Add missing-file check before `run_agent_chat` loads `resume.yaml`:

```python
resume_path = config["paths"]["resume_yaml"]
if not Path(resume_path).exists():
    resume = run_onboarding(config, provider_name)
else:
    resume = load_resume(resume_path)
```

### Modified File: `src/prompts.py`

Add one extraction prompt per section (`ONBOARDING_EXTRACT_{SECTION}`). Each prompt instructs the model to return only JSON matching the section's schema, leaving unknown fields empty rather than hallucinating.

---

## Section Interview Flow

Sections are visited in this fixed order:

| # | Section | Opening prompt |
|---|---------|---------------|
| 1 | `basics` | "Let's start with your basic info. What's your name, email, phone, location, and any LinkedIn or GitHub profiles? You can type it out or paste from your profile." |
| 2 | `work` | "Tell me about your work history. Start with your most recent role — or paste multiple jobs at once." |
| 3 | `education` | "What's your educational background? Include your degree, field of study, institution, and years." |
| 4 | `skills` | "What are your key skills? List them freely, by category, or paste from your resume." |
| 5 | `projects` | "Do you have any personal or portfolio projects to include? (Type 'skip' to leave this section empty)" |
| 6 | `certificates` | "Any certifications or completed courses? (Type 'skip' to leave this section empty)" |

---

## Extraction Pipeline (per section)

```
raw_input (str)
    │
    ▼
parser_model LLM call
  prompt: ONBOARDING_EXTRACT_{SECTION}.format(user_input=raw_input)
    │
    ▼
json-repair (already a dependency)
    │
    ▼
Pydantic model parse (e.g. list[WorkEntry])
    │
    ├── ValidationError → append error to prompt, retry (max 2 retries)
    │
    ▼
confirmed extracted dict
```

### Edit flow

When the user responds `edit`, their correction text is appended to the original input and re-sent:

```
Original input:
{original_raw_input}

User correction:
{correction_text}

Apply the correction and return updated JSON.
```

This gives the model full context — both what was extracted and what the user wants changed.

---

## Confirmation UX

After extraction, the tool prints the result in a readable format and waits:

```
Here's what I captured for your work history:

  Acme Corporation (2022–present) — Senior Software Engineer
    • Built and maintained a high-traffic REST API...
    • Led migration of legacy monolith to microservices...

  Startup Inc. (2020–2022) — Software Engineer
    • Developed a real-time data pipeline...

Does this look right? (yes / edit / skip)
>
```

- **yes** — section saved, move to next
- **edit** — user types correction; extraction reruns with original + correction
- **skip** — section stored as empty (`[]` or `{}`), move to next

---

## Completion

After all 6 sections are confirmed:

1. Assemble the full resume dict from confirmed sections
2. Write `resume.yaml` to `config["paths"]["resume_yaml"]`
3. Print: `"resume.yaml created. Let's find you some jobs!\n"`
4. Return the resume dict to `run_agent_chat`

The job search loop starts immediately in the same terminal session.

---

## Pydantic Models (`src/resume_models.py`)

```python
from pydantic import BaseModel, Field

class Profile(BaseModel):
    network: str = ""
    username: str = ""
    url: str = ""

class Basics(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    location: dict = Field(default_factory=dict)
    profiles: list[Profile] = Field(default_factory=list)

class WorkEntry(BaseModel):
    name: str = ""
    location: str = ""
    position: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""
    highlights: list[str] = Field(default_factory=list)

class EducationEntry(BaseModel):
    institution: str = ""
    area: str = ""
    studyType: str = ""
    degree: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""

class SkillGroup(BaseModel):
    name: str = ""
    keywords: list[str] = Field(default_factory=list)

class Project(BaseModel):
    name: str = ""
    description: str = ""
    url: str = ""
    highlights: list[str] = Field(default_factory=list)

class Certificate(BaseModel):
    name: str = ""
    issuer: str = ""
```

All fields have defaults so partial extraction is always valid — the model never raises on missing fields, only on type mismatches.

---

## New Files

```
src/
  onboarding.py        # interview loop, extraction, confirmation, YAML write
  resume_models.py     # Pydantic models for all 6 resume sections
```

## Modified Files

```
src/agent.py           # add missing-file check; call run_onboarding if needed
src/prompts.py         # add ONBOARDING_EXTRACT_* prompts (one per section)
```

No new dependencies — uses `parser_model`, `json-repair`, and `pydantic` already in the project.

---

## Out of Scope

- Editing an existing `resume.yaml` via onboarding (use the existing `write_resume_section` tool in the agent chat loop)
- Web scraping LinkedIn to auto-populate (requires authentication; paste is sufficient)
- Multi-session resume building (onboarding completes in one session)
