# Resume-Driven Role Suggestion — Design Spec

**Date:** 2026-03-30
**Branch target:** `feature/resume-role-suggestion`

---

## Goal

When a user starts the job search agent without knowing what role to target, the agent can suggest job titles derived from their resume using the parser LLM. The user can either let the agent auto-search all suggested roles, or pick one title from the list before continuing. In both cases the normal flow (location → salary → search) follows.

---

## User Flow

```
Agent: "Do you have a specific role in mind?"

  ├── YES → ask location/remote → ask salary → search_jobs (unchanged)
  │
  └── NO  → "Would you like me to auto-search based on your resume,
              or would you prefer to pick from a suggested list?"
              │
              ├── AUTO  → call suggest_roles
              │           → call search_jobs once with all titles in the preferences summary
              │           → present combined job list
              │           (location from resume basics.location or "Remote" if absent;
              │            salary omitted from query if not known)
              │
              └── LIST  → call suggest_roles
                          → present numbered list: title + one-line reasoning
                          → user picks one title
                          → ask location/remote → ask salary → search_jobs
```

---

## Data Model

Add to `src/models.py`:

```python
class SuggestedRole(BaseModel):
    title: str
    reasoning: str

class SuggestedRoles(BaseModel):
    roles: list[SuggestedRole]
```

`SuggestedRoles` is passed to `_call_with_retry` exactly like `JobDetails` and `ResumeJSON` — parser model, `json_repair` fallback, and retry logic are all inherited automatically.

---

## New Files

### `src/tools/suggest_roles.py`

```
create_suggest_roles_tool(config, provider, parser_models) -> LangChain tool
```

- Loads the full resume YAML from `config["paths"]["resume_yaml"]`
- Calls `_call_with_retry(SuggestedRoles, provider, config["llm"], SUGGEST_ROLES_PROMPT, resume_yaml_str, parser_models)`
- Returns a formatted string:
  ```
  1. UX Designer — based on 3 years of Figma and user research experience
  2. Product Designer — transferable from your interaction design and prototyping work
  ...
  ```
- On error: returns a plain error string so the agent can recover gracefully

### `src/prompts.py` — new constant

`SUGGEST_ROLES_PROMPT`: instructs the parser to read the candidate's full resume and return 5–7 job titles they are qualified for. JSON only, matching the `SuggestedRoles` schema:

```json
{"roles": [{"title": "...", "reasoning": "..."}]}
```

Rules for the prompt:
- Derive titles only from actual skills, experience, and education in the resume
- Prefer realistic, searchable titles (e.g. "Senior UX Designer" not "Creative Technologist")
- Vary seniority appropriately based on years of experience
- No fabrication — reasoning must cite something present in the resume

---

## Modified Files

### `src/tools/search.py` — multi-role support

Update `SEARCH_SUBAGENT_SYSTEM_PROMPT` (in `src/prompts.py`) to instruct the sub-agent that the preferences summary may contain multiple role titles. When it does, it should make searches for each title and combine results before deduplicating.

The `search_jobs` tool signature is unchanged (`preferences_summary: str`) — the agent simply includes all titles in the summary string, e.g.:

```
Roles: UX Designer, Product Designer, Interaction Designer
Location: Remote
Salary: $80k–$110k
Key skills: Figma, user research, prototyping
```

The sub-agent's prompt update ensures it fans out searches across all listed roles.

### `src/agent.py` — `build_agent()`

Import `create_suggest_roles_tool` and add it to the tools list:

```python
from src.tools.suggest_roles import create_suggest_roles_tool

suggest_roles_tool = create_suggest_roles_tool(config, provider, parser_models)

return create_deep_agent(
    model=agent_model,
    tools=[search_tool, generate_tool, read_resume, write_resume,
           sheet_log_tool, change_template_tool, suggest_roles_tool],
    system_prompt=system_prompt,
)
```

### `src/prompts.py` — `AGENT_SYSTEM_PROMPT_TEMPLATE`

Replace step 1 of the WORKFLOW section:

```
WORKFLOW:
1. Ask the candidate: "Do you have a specific role in mind?"
   - YES: proceed to step 2.
   - NO: ask "Would you like me to auto-search based on your resume, or pick from a list?"
     - AUTO: call suggest_roles, then call search_jobs once with all suggested titles
       included in the preferences summary. The search sub-agent fans out searches
       across all roles and returns a combined deduplicated list.
       Skip location/salary questions — use resume context for search queries.
     - LIST: call suggest_roles, present results as a numbered list with reasoning,
       wait for the candidate to pick one title, then proceed to step 2.
2. Ask for location/remote preference.
3. Ask for salary range.
4. Call search_jobs with a preferences summary, then log each found job to the sheet.
5. Present the results as a numbered list. Ask which jobs to generate documents for.
6. Call generate_documents for each confirmed job.
7. If the candidate asks to change their template, call change_template immediately.
8. Offer to update the resume if the candidate mentions new skills or certifications.
```

Also add `suggest_roles` to the TOOLS AVAILABLE section:

```
- suggest_roles: Read the candidate's resume and return a list of job titles they
  are qualified for, each with one-line reasoning. Call this only when the candidate
  says they don't have a specific role in mind.
```

---

## Testing

| Test | File | What it validates |
|------|------|-------------------|
| `test_suggest_roles_returns_formatted_string` | `tests/test_suggest_roles.py` | Mock `_call_with_retry` → verify numbered string output |
| `test_suggest_roles_handles_llm_error` | `tests/test_suggest_roles.py` | Exception from provider → returns error string, does not raise |
| `test_suggested_roles_model_valid` | `tests/test_suggest_roles.py` | `SuggestedRoles.model_validate(...)` accepts valid JSON |
| `test_suggested_roles_model_rejects_invalid` | `tests/test_suggest_roles.py` | `ValidationError` on missing fields |

No changes to existing tests — pipeline, sheet logging, and document generation are untouched.

---

## File Map

| File | Action |
|------|--------|
| `src/models.py` | Add `SuggestedRole`, `SuggestedRoles` |
| `src/prompts.py` | Add `SUGGEST_ROLES_PROMPT`; update `AGENT_SYSTEM_PROMPT_TEMPLATE`; update `SEARCH_SUBAGENT_SYSTEM_PROMPT` for multi-role |
| `src/tools/suggest_roles.py` | **Create** |
| `src/agent.py` | Wire `suggest_roles_tool` into `build_agent()` |
| `tests/test_suggest_roles.py` | **Create** |
