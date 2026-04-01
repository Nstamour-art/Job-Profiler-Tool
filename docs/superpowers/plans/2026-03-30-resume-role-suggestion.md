# Resume-Driven Role Suggestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a user doesn't know what role to search for, the agent calls a `suggest_roles` tool that uses the parser LLM to derive job titles from their resume, then lets them auto-search all titles or pick one.

**Architecture:** A new `suggest_roles` LangChain tool calls `_call_with_retry` with a new Pydantic model (`SuggestedRoles`) and a new prompt constant (`SUGGEST_ROLES_PROMPT`). The agent system prompt gains branching logic in its workflow. The search sub-agent prompt is updated to handle multiple role titles in one call. All wiring happens in `build_agent()`.

**Tech Stack:** Python, Pydantic v2, LangChain (`langchain_core.tools.tool`), PyYAML, `json_repair`, `pytest`, `uv run pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/models.py` | **Modify** | Add `SuggestedRole`, `SuggestedRoles` Pydantic models |
| `src/prompts.py` | **Modify** | Add `SUGGEST_ROLES_PROMPT`; update `AGENT_SYSTEM_PROMPT_TEMPLATE` and `SEARCH_SUBAGENT_SYSTEM_PROMPT` |
| `src/tools/suggest_roles.py` | **Create** | `create_suggest_roles_tool` factory — loads resume, calls parser, formats output |
| `src/agent.py` | **Modify** | Import and wire `suggest_roles_tool` into `build_agent()` |
| `tests/test_suggest_roles.py` | **Create** | Unit tests for models, tool output, and error handling |

---

## Task 1: Pydantic models for role suggestions

**Files:**
- Modify: `src/models.py`
- Create: `tests/test_suggest_roles.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_suggest_roles.py`:

```python
"""Tests for SuggestedRole/SuggestedRoles models and the suggest_roles tool."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

def test_suggested_roles_model_valid():
    from src.models import SuggestedRoles
    data = {
        "roles": [
            {"title": "UX Designer", "reasoning": "3 years Figma experience"},
            {"title": "Product Designer", "reasoning": "interaction design background"},
        ]
    }
    result = SuggestedRoles.model_validate(data)
    assert len(result.roles) == 2
    assert result.roles[0].title == "UX Designer"
    assert result.roles[0].reasoning == "3 years Figma experience"


def test_suggested_roles_model_rejects_missing_title():
    from src.models import SuggestedRoles
    with pytest.raises(ValidationError):
        SuggestedRoles.model_validate({"roles": [{"reasoning": "no title here"}]})


def test_suggested_roles_model_empty_roles_list():
    from src.models import SuggestedRoles
    result = SuggestedRoles.model_validate({"roles": []})
    assert result.roles == []
```

- [ ] **Step 2: Run tests — verify they fail**

```
uv run pytest tests/test_suggest_roles.py -v
```

Expected: `ImportError` — `SuggestedRole` and `SuggestedRoles` don't exist yet.

- [ ] **Step 3: Add models to `src/models.py`**

Append after the `CoverLetterJSON` class:

```python
class SuggestedRole(BaseModel):
    title: str
    reasoning: str


class SuggestedRoles(BaseModel):
    roles: list[SuggestedRole]
```

- [ ] **Step 4: Run tests — verify they pass**

```
uv run pytest tests/test_suggest_roles.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_suggest_roles.py
git commit -m "feat: add SuggestedRole and SuggestedRoles Pydantic models"
```

---

## Task 2: Prompts — `SUGGEST_ROLES_PROMPT` and multi-role search update

**Files:**
- Modify: `src/prompts.py`
- Modify: `tests/test_suggest_roles.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_suggest_roles.py`:

```python
# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

def test_suggest_roles_prompt_exists_and_is_string():
    from src.prompts import SUGGEST_ROLES_PROMPT
    assert isinstance(SUGGEST_ROLES_PROMPT, str)
    assert len(SUGGEST_ROLES_PROMPT) > 50


def test_search_subagent_prompt_mentions_multiple_roles():
    from src.prompts import SEARCH_SUBAGENT_SYSTEM_PROMPT
    assert "multiple" in SEARCH_SUBAGENT_SYSTEM_PROMPT.lower() or \
           "roles" in SEARCH_SUBAGENT_SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run tests — verify they fail**

```
uv run pytest tests/test_suggest_roles.py::test_suggest_roles_prompt_exists_and_is_string tests/test_suggest_roles.py::test_search_subagent_prompt_mentions_multiple_roles -v
```

Expected: `ImportError` on `SUGGEST_ROLES_PROMPT`.

- [ ] **Step 3: Add `SUGGEST_ROLES_PROMPT` to `src/prompts.py`**

Append after `SEARCH_SUBAGENT_SYSTEM_PROMPT`:

```python
SUGGEST_ROLES_PROMPT = """\
You are a career advisor. Based on the candidate's resume, suggest 5-7 realistic
job titles they are qualified to apply for right now.

RULES:
- Derive titles only from actual skills, experience, and education present in the resume.
- Use realistic, searchable job titles (e.g. "Senior UX Designer", "Data Analyst",
  "Product Manager") — not vague titles like "Creative Technologist".
- Vary seniority based on years of experience shown in the resume.
- For each title, write one concise sentence of reasoning that cites something
  specific from the resume (a skill, tool, or experience).
- Do NOT fabricate skills, companies, or experience not present in the resume.

You MUST respond with valid JSON only — no markdown, no explanation:
{"roles": [{"title": "...", "reasoning": "..."}]}
"""
```

- [ ] **Step 4: Update `SEARCH_SUBAGENT_SYSTEM_PROMPT` for multi-role support**

In `src/prompts.py`, replace the `SEARCH_SUBAGENT_SYSTEM_PROMPT` constant with:

```python
SEARCH_SUBAGENT_SYSTEM_PROMPT = """\
You are a job listing search specialist. Your task is to find job listings matching
the candidate's preferences using the Tavily search tool.

INSTRUCTIONS:
1. The preferences summary may contain a single role title OR multiple role titles
   (listed under "Roles:"). When multiple roles are provided, make searches for
   EACH role title and combine the results.
2. Make 3-5 targeted Tavily searches using varied queries derived from the preferences.
   - Include the job title, location/remote, and seniority in each query.
   - Try variations: "site:linkedin.com/jobs", "site:greenhouse.io", general queries.
3. Deduplicate results — remove listings with the same company and title.
4. Filter for relevance: only keep listings that match a target role and location.
5. Return EXACTLY the following JSON and nothing else — no markdown, no explanation:

{{"jobs": [
  {{
    "title": "Senior AI Engineer",
    "company": "Acme Corp",
    "url": "https://...",
    "location": "Remote",
    "salary": "$130k-$160k"
  }}
]}}

Return at most {max_jobs} jobs. If fewer are found, return what you have.
If no jobs are found, return: {{"jobs": []}}
"""
```

- [ ] **Step 5: Run tests — verify they pass**

```
uv run pytest tests/test_suggest_roles.py -v
```

Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/prompts.py tests/test_suggest_roles.py
git commit -m "feat: add SUGGEST_ROLES_PROMPT and update search prompt for multi-role support"
```

---

## Task 3: `src/tools/suggest_roles.py`

**Files:**
- Create: `src/tools/suggest_roles.py`
- Modify: `tests/test_suggest_roles.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_suggest_roles.py`:

```python
# ---------------------------------------------------------------------------
# suggest_roles tool
# ---------------------------------------------------------------------------

def test_suggest_roles_returns_formatted_string(tmp_path):
    """Tool returns a numbered list of titles with reasoning."""
    import yaml
    from src.models import SuggestedRoles, SuggestedRole

    resume = {"basics": {"name": "Jane", "location": "Remote"}, "work": []}
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(resume))

    config = {
        "paths": {"resume_yaml": str(resume_path)},
        "llm": {"temperature": 0.3, "max_retries": 3, "model": "m", "parser_model": "m"},
    }
    mock_result = SuggestedRoles(roles=[
        SuggestedRole(title="UX Designer", reasoning="3 years Figma experience"),
        SuggestedRole(title="Product Designer", reasoning="interaction design background"),
    ])

    with patch("src.tools.suggest_roles._call_with_retry", return_value=mock_result):
        from src.tools.suggest_roles import create_suggest_roles_tool
        tool = create_suggest_roles_tool(config, MagicMock(), ["parser-model"])
        result = tool.invoke({})

    assert "1. UX Designer" in result
    assert "3 years Figma experience" in result
    assert "2. Product Designer" in result


def test_suggest_roles_handles_llm_error(tmp_path):
    """Tool returns a plain error string instead of raising when LLM fails."""
    import yaml

    resume = {"basics": {"name": "Jane"}}
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(resume))

    config = {
        "paths": {"resume_yaml": str(resume_path)},
        "llm": {"temperature": 0.3, "max_retries": 1, "model": "m", "parser_model": "m"},
    }

    with patch("src.tools.suggest_roles._call_with_retry", side_effect=RuntimeError("LLM down")):
        from src.tools.suggest_roles import create_suggest_roles_tool
        tool = create_suggest_roles_tool(config, MagicMock(), ["parser-model"])
        result = tool.invoke({})

    assert "Could not suggest roles" in result
    assert "LLM down" in result
```

- [ ] **Step 2: Run tests — verify they fail**

```
uv run pytest tests/test_suggest_roles.py::test_suggest_roles_returns_formatted_string tests/test_suggest_roles.py::test_suggest_roles_handles_llm_error -v
```

Expected: `ModuleNotFoundError` — `src.tools.suggest_roles` doesn't exist.

- [ ] **Step 3: Create `src/tools/suggest_roles.py`**

```python
"""
suggest_roles tool — derives job title suggestions from the candidate's resume
using the parser LLM.
"""
from __future__ import annotations

import yaml
from langchain_core.tools import tool as lc_tool

from src.llm import _call_with_retry
from src.models import SuggestedRoles
from src.prompts import SUGGEST_ROLES_PROMPT


def create_suggest_roles_tool(config: dict, provider, parser_models: list[str]):
    """Return a suggest_roles LangChain tool bound to this session's config."""

    @lc_tool
    def suggest_roles() -> str:
        """Suggest job titles the candidate is qualified for based on their resume.

        Returns a numbered list of role titles with one-line reasoning for each.
        Call this only when the candidate says they don't have a specific role in mind.
        """
        try:
            resume_path = config["paths"]["resume_yaml"]
            with open(resume_path, encoding="utf-8") as f:
                resume = yaml.safe_load(f)
            resume_str = yaml.dump(resume, allow_unicode=True)

            result = _call_with_retry(
                SuggestedRoles,
                provider,
                config["llm"],
                SUGGEST_ROLES_PROMPT,
                resume_str,
                parser_models,
            )
            lines = [
                f"{i + 1}. {role.title} — {role.reasoning}"
                for i, role in enumerate(result.roles)
            ]
            return "\n".join(lines)
        except Exception as exc:
            return f"Could not suggest roles: {exc}"

    return suggest_roles
```

- [ ] **Step 4: Run tests — verify they pass**

```
uv run pytest tests/test_suggest_roles.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/tools/suggest_roles.py tests/test_suggest_roles.py
git commit -m "feat: add suggest_roles tool with Pydantic parsing and error handling"
```

---

## Task 4: Wire into agent and update system prompt

**Files:**
- Modify: `src/agent.py`
- Modify: `src/prompts.py`
- Modify: `tests/test_suggest_roles.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_suggest_roles.py`:

```python
# ---------------------------------------------------------------------------
# Agent wiring
# ---------------------------------------------------------------------------

def test_build_agent_includes_suggest_roles_tool():
    """build_agent should include suggest_roles in the tool list."""
    from unittest.mock import patch, MagicMock
    import yaml
    import os

    config = {
        "provider": "local",
        "llm": {"temperature": 0.3, "max_retries": 1, "model": "llama3.2:latest",
                "parser_model": "llama3.2:latest"},
        "paths": {"resume_yaml": "resume.yaml", "template_yaml": "template.yaml",
                  "output_dir": "output", "credentials": "creds.json"},
        "agent": {"max_jobs": 10, "memory_bank": "", "memory_model": ""},
    }
    resume = {"basics": {"name": "Test User", "location": "Remote"}}

    with patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.create_deep_agent") as mock_create, \
         patch("src.agent.create_search_tool", return_value=MagicMock(name="search_jobs")), \
         patch("src.agent.create_generate_tool", return_value=MagicMock(name="generate_documents")), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())), \
         patch("src.agent.create_sheet_log_tool", return_value=MagicMock()), \
         patch("src.agent.create_suggest_roles_tool", return_value=MagicMock(name="suggest_roles")) as mock_suggest, \
         patch.dict(os.environ, {"TAVILY_API_KEY": "test"}):
        from src.agent import build_agent
        build_agent(config, resume, "local", "")

    mock_create.assert_called_once()
    tools_passed = mock_create.call_args[1]["tools"]
    tool_names = [t.name if hasattr(t, "name") else str(t) for t in tools_passed]
    # suggest_roles tool must be in the tool list
    assert mock_suggest.return_value in tools_passed
```

- [ ] **Step 2: Run test — verify it fails**

```
uv run pytest tests/test_suggest_roles.py::test_build_agent_includes_suggest_roles_tool -v
```

Expected: FAIL — `create_suggest_roles_tool` not imported in `src/agent.py`.

- [ ] **Step 3: Update `src/agent.py`**

Add the import after the existing tool imports:

```python
from src.tools.suggest_roles import create_suggest_roles_tool
```

In `build_agent()`, after `change_template_tool = _create_change_template_tool(...)`, add:

```python
suggest_roles_tool = create_suggest_roles_tool(config, provider, parser_models)
```

Update the `create_deep_agent` call to include `suggest_roles_tool`:

```python
return create_deep_agent(
    model=agent_model,
    tools=[search_tool, generate_tool, read_resume, write_resume,
           sheet_log_tool, change_template_tool, suggest_roles_tool],
    system_prompt=system_prompt,
)
```

- [ ] **Step 4: Update `AGENT_SYSTEM_PROMPT_TEMPLATE` in `src/prompts.py`**

Replace the `TOOLS AVAILABLE` section and `WORKFLOW` section inside `AGENT_SYSTEM_PROMPT_TEMPLATE`:

```python
AGENT_SYSTEM_PROMPT_TEMPLATE = """\
You are a proactive job search assistant. Your job is to help the candidate find
matching job postings, present them clearly, generate tailored application documents,
and keep their resume up to date.

CANDIDATE CONTEXT:
Name: {candidate_name}
Location: {candidate_location}

MEMORY FROM PREVIOUS SESSIONS:
{recalled_memories}

TOOLS AVAILABLE:
- suggest_roles: Read the candidate's resume and return a list of job titles they
  are qualified for, each with one-line reasoning. Call this only when the candidate
  says they don't have a specific role in mind.
- search_jobs: Search the web for job listings. Provide a preferences summary as input.
  When multiple roles are provided, include all titles in the summary under "Roles:".
  Always call this after gathering the candidate's role(s), location, and salary preferences.
- generate_documents: Generate a tailored resume and cover letter for a specific job URL.
  Only call this after the candidate has confirmed which jobs they want.
- read_resume_section: Read one section of the candidate's resume YAML.
- write_resume_section: Update one section of the candidate's resume YAML.
  YOU MUST show the candidate exactly what you are about to write and receive
  explicit confirmation ("yes") before calling this tool. Never write without confirmation.
- log_job_to_sheet: Log a found job to the candidate's Google Sheet.
- change_template: Let the user pick a new resume template and customize it.
  Call this when the user asks to change their resume look, theme, or template.

WORKFLOW:
1. Ask the candidate: "Do you have a specific role in mind?"
   - YES: proceed to step 2.
   - NO: ask "Would you like me to auto-search based on your resume, or pick from a list?"
     - AUTO: call suggest_roles, then call search_jobs once with all suggested titles
       in the preferences summary (format: "Roles: Title1, Title2, Title3").
       Use the candidate's location from context (or "Remote" if blank).
       Skip asking for location and salary — go straight to presenting results.
     - LIST: call suggest_roles, present results as a numbered list with reasoning,
       wait for the candidate to pick one title, then proceed to step 2.
2. Ask for location/remote preference.
3. Ask for salary range.
4. Call search_jobs with a preferences summary, then log each found job to the sheet.
5. Present the results as a numbered list. Ask which jobs to generate documents for.
6. Call generate_documents for each confirmed job.
7. If the candidate asks to change their template, call change_template immediately.
8. Offer to update the resume if the candidate mentions new skills or certifications.

RULES:
- Never generate documents without explicit job selection from the candidate.
- Never write to the resume without showing the change and getting explicit confirmation.
- Keep your context lean: present job summaries (title, company, salary), not full descriptions.
- If the candidate says "exit", "quit", or "bye", wrap up and say goodbye.
"""
```

- [ ] **Step 5: Run all tests — verify they pass**

```
uv run pytest tests/test_suggest_roles.py -v
```

Expected: 8 tests pass.

- [ ] **Step 6: Run full test suite**

```
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/agent.py src/prompts.py tests/test_suggest_roles.py
git commit -m "feat: wire suggest_roles into agent and update system prompt with branching workflow"
```
