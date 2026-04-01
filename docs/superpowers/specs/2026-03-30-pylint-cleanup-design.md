# Pylint Cleanup — Design Spec

**Date:** 2026-03-30
**Branch target:** `feature/onboarding-wizard`

---

## Goal

Bring the codebase to a clean pylint score by fixing all real issues through code changes. No blanket suppression — inline `disable` comments are permitted only for the two unavoidable cases: intentional lazy imports (C0415) and python-docx protected-member access (W0212).

Venv-related false positives (E0401, E1120) are excluded — the user will configure pylint separately.
Test-file C0415 (imports inside test functions used for patching) are excluded from this work.

---

## Scope

Issues to fix across all `src/` and `tests/` files, grouped by kind:

| Category | Codes |
|----------|-------|
| Missing docstrings | C0114, C0115, C0116 |
| Long lines | C0301 |
| Import order / position | C0411, C0413 |
| Unused imports / variables / arguments | W0611, W0612, W0613 |
| Lazy import suppress (intentional) | C0415 — add inline `disable` comment |
| f-string issues | C0209, W1309 |
| Raise without from | W0707 |
| Unnecessary pass | W0107 |
| No-else-return / no-else-break | R1705, R1723 |
| Duplicate imports | W0404 |
| Use `with` for resources | R1732 |
| Broad exception caught | W0718 |
| Too many arguments | R0913, R0917 |
| Too many locals / branches / statements | R0914, R0912, R0915 |
| Duplicate code | R0801 |
| Too few public methods | R0903 |
| Redefining outer scope | W0621 |
| Unused argument | W0613 |
| camelCase variable names | C0103 |
| Protected member access (python-docx) | W0212 — wrap + inline `disable` |
| Generator member visibility (ollama) | E1101 — fix with TypedDict + cast() |

---

## Section 1 — Mechanical fixes

Applied in-place across all affected files. No logic changes.

### Docstrings (C0114, C0115, C0116)

Add a concise one-line docstring wherever missing:

- **Module docstrings**: `src/llm.py`, `src/models.py`, `src/prompts.py`, `src/scraper.py`, `src/sheets.py`, all test files
- **Class docstrings**: `src/models.py`, `src/providers.py`, `src/resume_models.py`, `src/scraper.py`, `src/themes.py`
- **Function docstrings**: `src/debug.py` (4 functions), `src/providers.py` (1 function), `tests/conftest.py` (2 functions), ~60 test functions across all test files

### Long lines (C0301)

Wrap at 100 characters. Affected files:
`main.py`, `src/document.py`, `src/llm.py`, `src/memory.py`, `src/models.py`, `src/pipeline.py`,
`src/setup_wizard.py`, `src/template_agent.py`, `src/tools/resume_editor.py`,
`tests/test_agent.py`, `tests/test_onboarding.py`, `tests/test_resume_models.py`, `tests/test_sheets.py`

### Import order (C0411, C0413)

Reorder to: stdlib → third-party → local. Affected:
`src/llm.py`, `tests/test_onboarding.py`, `tests/test_setup_wizard.py`, `tests/test_template_agent.py`, `tests/test_template_cli.py`

### Unused imports (W0611)

Remove unused imports across test files. Primary offenders: `pytest` (imported but not used directly in many files), unused theme constants, unused `MagicMock`/`patch` re-imports.

### Unused variables / arguments (W0612, W0613)

- Remove or assign to `_` for unused variables (`folder`, `read_tool`, `result`)
- Prefix unused arguments with `_`: `_model`, `_tools`, `_system_prompt`, `_args`, `_kwargs`, `_monkeypatch`, `_provider_name`, `_config`

### Other mechanical fixes

| Fix | Code | Location |
|-----|------|----------|
| Remove `pass` after bare `except` | W0107 | `src/memory.py:56` |
| Fix `f"literal"` → `"literal"` | W1309 | `src/onboarding.py:172` |
| Convert `"...%s..." % x` → f-string | C0209 | `src/document.py:146`, `:222` |
| Remove `else` after `return` | R1705 | `src/onboarding.py:124` |
| Remove `else` after `break` | R1723 | `src/setup_wizard.py:167`, `src/template_agent.py:119` |
| Add `raise X from exc` | W0707 | `src/providers.py` (3 places) |
| Use `with` for `urlopen` | R1732 | `src/setup_wizard.py:46` |
| Use `with` for `NamedTemporaryFile` | R1732 | `tests/test_template_agent.py` (3 places) |
| Remove duplicate re-imports | W0404 | `tests/test_pipeline.py`, `tests/test_setup_wizard.py`, `tests/test_template_cli.py` |

---

## Section 2 — C0415: inline suppress on intentional lazy imports

All lazy imports in `src/` files stay in place. Each gets an inline comment:

```python
from src.agent import run_agent_chat  # pylint: disable=import-outside-toplevel
```

Affected locations:
- `main.py`: all imports inside `list_jobs`, `set_template`, `run_jobs` command bodies
- `src/agent.py`: `langchain_core.tools.tool`, `langchain_core.runnables.RunnableConfig`, `yaml`
- `src/llm.py`: `click`
- `src/onboarding.py`: `src.providers`
- `src/providers.py`: `ollama`, `openai`, `anthropic`, `google.genai` (optional-dependency imports)
- `src/setup_wizard.py`: `dotenv.load_dotenv`
- `src/tools/search.py`: `langchain_tavily.TavilySearch`

---

## Section 3 — Structural refactors

### `main.py` — `run_jobs` (R0913, R0917, R0914)

1. Remove `--row`, `--all`, `--force` options (dead code — they only raise `UsageError`)
2. Replace `--resume-only` / `--cover-only` with `--mode` using `click.Choice(["both", "resume", "cover"])`, default `"both"`. This reduces the signature from 9 to 6 parameters, satisfying R0913/R0917.
3. Extract two private helpers to reduce locals:
   - `_handle_first_run(config_path: str, provider_name: str | None) -> None` — handles the first-run setup flow (wizard → onboarding → template → agent)
   - `_handle_direct_url(config: dict, direct_url: str, mode: str, resolved_provider: str, debug: bool) -> None` — handles `--url` processing

`run_jobs` becomes a thin dispatcher calling these helpers.

### `src/agent.py` — `build_agent`, `run_agent_chat` (R0914 ×2)

- Extract `_build_tools(config, resume, provider, provider_name, models, parser_models) -> list` from `build_agent` — returns the assembled tool list
- Extract `_process_message(agent, history: list, thread_config: dict) -> tuple[str, list]` from `run_agent_chat` — invokes the agent and returns `(response_text, updated_history)`

### `src/pipeline.py` — `process_job` (R0913, R0917, R0914, R0912, R0915)

1. Introduce `JobOptions` dataclass:
   ```python
   @dataclass
   class JobOptions:
       resume_only: bool = False
       cover_only: bool = False
       debug_run_id: int | None = None
   ```
   `process_job` signature changes from 9 positional args to 6: `(job, config, resume, provider, models, parser_models, options: JobOptions)`. All callers updated.
2. Extract `_run_debug_init(url: str, provider: str, model: str, parser_model: str) -> int` — initialises debug DB and returns a run ID

### `src/sheets.py` — `append_job_row` (R0913, R0917, R0914)

Introduce a `JobRow` dataclass to bundle the 8 positional arguments:
```python
@dataclass
class JobRow:
    job_title: str
    company: str
    url: str
    status: str
    date_found: str
    details: str
    priority: str
    reasoning: str
```
`append_job_row(config, row: JobRow)` — reduces signature from 10 to 2 args. All callers (in `src/tools/sheet_log.py`) updated.

### `src/template_agent.py` — `run_template_wizard` (R0914, R0912, R0915)

Extract:
- `_prompt_for_overrides(theme: ThemeConfig) -> TemplateOverrides` — collects user colour/font input
- `_apply_overrides(template_path: str, overrides: TemplateOverrides) -> None` — writes overrides to template YAML

### `src/document.py` — `build_resume`, `build_cover_letter` (R0914, R0912, R0915 ×2)

Extract per-section renderers called from each builder:
- `_render_header(doc, personal, theme)` — name + contact line
- `_render_summary(doc, summary, theme)` — professional summary section
- `_render_experience(doc, work, theme)` — work history section
- `_render_education_certs(doc, education, certifications, theme)` — table section
- `_render_skills(doc, skills, theme)` — skills section
- `_render_cover_body(doc, content, theme)` — cover letter body paragraphs

### W0718 — narrow `except Exception` throughout

Replace `except Exception` with specific exception tuples appropriate to each context:

| File | Context | Replacement |
|------|---------|-------------|
| `src/agent.py:40` | Tool wrapper returning error string | `(RuntimeError, ValueError, OSError)` |
| `src/agent.py:157` | Agent invocation in chat loop | `(RuntimeError, ConnectionError, ValueError)` |
| `src/llm.py:62` | LLM call with retry | `(RuntimeError, ValueError, ConnectionError, TimeoutError)` |
| `src/memory.py` ×4 | Memory bank operations | `(RuntimeError, OSError, ConnectionError)` |
| `src/onboarding.py` ×2 | LLM interview call | `(RuntimeError, ValueError, ConnectionError)` |
| `src/pipeline.py:62` | Job scraping | `(RuntimeError, OSError, ConnectionError, TimeoutError)` |
| `src/scraper.py` ×2 | HTTP requests | `(OSError, ConnectionError, TimeoutError, ValueError)` |
| `src/setup_wizard.py:48` | URL check | `(OSError, ConnectionError)` |
| `src/template_agent.py` ×2 | LLM call / template write | `(RuntimeError, ValueError, OSError)` |
| `src/tools/generate.py:60` | Tool wrapper | `(RuntimeError, ValueError, OSError, ConnectionError)` |
| `src/tools/search.py:46` | Tool wrapper | `(RuntimeError, OSError, ConnectionError, TimeoutError)` |
| `src/tools/sheet_log.py:43` | Tool wrapper | `(RuntimeError, OSError, ConnectionError)` |

---

## Section 4 — `document.py` C0103 + W0212

### Rename camelCase locals (C0103)

| Old name | New name |
|----------|----------|
| `pPr` | `para_props` |
| `pBdr` | `para_border` |
| `tcPr` | `cell_props` |
| `tcBorders` | `tc_borders` |
| `keepNext` | `keep_next` |

Applied everywhere these names appear in `src/document.py`.

### Wrap protected access (W0212)

Add three helper functions near the top of `src/document.py`:

```python
def _para_xml(paragraph):
    return paragraph._p   # pylint: disable=protected-access

def _cell_xml(cell):
    return cell._tc       # pylint: disable=protected-access

def _run_xml(run):
    return run._r         # pylint: disable=protected-access
```

Replace every direct `paragraph._p`, `cell._tc`, and `run._r` call in the file with the corresponding helper. W0212 is suppressed in exactly 3 lines.

---

## Section 5 — Test file cleanup (non-C0415)

### Docstrings

- Module docstring on every test file (C0114) — one line describing what module the tests cover
- One-line docstring on every undocumented test function (C0116) — ~60 functions across all test files

### Import and variable hygiene

- Fix import order to stdlib → third-party → local (C0411, C0413) in all affected test files
- Remove all unused imports (W0611)
- Remove unused variables; prefix unused arguments with `_` (W0612, W0613)
- Remove duplicate re-imports (W0404)

### Fixture scope (W0621)

`test_document_themes.py` and `test_template_agent.py` define pytest fixtures at module scope then re-use the same names as function parameters, triggering W0621. Fix by renaming the fixture parameters to match the fixture name (the standard pytest pattern — pytest resolves by name, not by position):

```python
# Before
def test_foo(sample_resume_json, sample_personal):  # W0621: redefines outer scope name

# After (no change needed if names already match — the warning fires because of how the
# fixtures are re-declared inside the test; restructure to use conftest.py fixtures instead)
```

Move `sample_resume_json` and `sample_personal` fixtures from `test_document_themes.py` to `tests/conftest.py` so they are shared and the redefinition warning disappears.

### R0801 — duplicate `build_agent` patch block

`test_agent.py` and `test_template_cli.py` both contain an identical 7-line `with patch(...)` context. Extract to a `build_agent_patches()` context manager fixture in `tests/conftest.py`:

```python
@contextmanager
def build_agent_patches():
    with patch("src.agent.create_deep_agent"), \
         patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.get_provider", return_value=MagicMock()), \
         patch("src.agent.create_search_tool", return_value=MagicMock()), \
         patch("src.agent.create_generate_tool", return_value=MagicMock()), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())), \
         patch("src.agent.create_sheet_log_tool", return_value=MagicMock()):
        yield
```

---

## Section 6 — `providers.py` E1101 type stubs

`ollama.generate()` and `ollama.chat()` return generators whose chunk objects have `.response` and `.message` attributes. pylint can't see these from type information.

Fix using `TypedDict` and `cast()`:

```python
from typing import TypedDict, cast

class _GenerateChunk(TypedDict):
    response: str

class _ChatChunk(TypedDict):
    message: dict
```

Wrap the generator item before attribute access:

```python
# Before
for chunk in generator:
    result += chunk.response

# After
for _chunk in generator:
    chunk = cast(_GenerateChunk, _chunk)
    result += chunk["response"]
```

Note: `TypedDict` items are accessed via `[]` not `.`, so the access pattern changes slightly.

---

## Also: `src/providers.py` R0903 (too few public methods)

Provider classes (`OllamaProvider`, `OpenAIProvider`, etc.) each have only one public method (`complete`), triggering R0903. Fix by extracting the providers to use a common abstract base class:

```python
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    def complete(self, system: str, prompt: str) -> str: ...

    def stream(self, system: str, prompt: str):
        """Default: non-streaming fallback (override to support streaming)."""
        return self.complete(system, prompt)
```

Each provider inherits from `BaseProvider`. The `stream` default gives them a second public method, satisfying R0903. Providers that do support streaming override it.

---

## File Map

| File | Action |
|------|--------|
| `main.py` | Remove dead flags, add `--mode`, extract `_handle_first_run`, `_handle_direct_url`; inline C0415 suppresses; docstrings; wrap long lines |
| `src/agent.py` | Extract `_build_tools`, `_process_message`; inline C0415 suppresses; narrow exceptions |
| `src/debug.py` | Add missing function docstrings |
| `src/document.py` | Add `_para_xml`, `_cell_xml`, `_run_xml` wrappers; rename camelCase vars; extract section renderers; fix f-strings; wrap long lines |
| `src/llm.py` | Module docstring; import order; inline C0415 suppress; narrow exception; wrap long lines |
| `src/memory.py` | Narrow exceptions (×4); remove pass; prefix unused arg; wrap long line |
| `src/models.py` | Module + class docstrings; wrap long line |
| `src/onboarding.py` | R0913 fix; narrow exceptions; remove else-after-return; inline C0415 suppress; fix f-string |
| `src/pipeline.py` | Introduce `JobOptions` dataclass; extract `_run_debug_init`; narrow exception; wrap long lines |
| `src/prompts.py` | Module docstring |
| `src/providers.py` | Add `BaseProvider` ABC; add class/function docstrings; `raise from exc`; inline C0415 suppresses; add `_GenerateChunk`/`_ChatChunk` TypedDicts + cast |
| `src/resume_models.py` | Add class docstrings |
| `src/scraper.py` | Module + class docstrings; narrow exceptions |
| `src/setup_wizard.py` | Wrap long line; narrow exception; use `with`; remove else-after-break; inline C0415 suppress; prefix unused arg |
| `src/sheets.py` | Module docstring; reduce locals |
| `src/template_agent.py` | Extract `_prompt_for_overrides`, `_apply_overrides`; narrow exceptions; remove else-after-break; wrap long lines |
| `src/themes.py` | Add class docstring |
| `src/tools/generate.py` | Narrow exception |
| `src/tools/resume_editor.py` | Wrap long lines |
| `src/tools/search.py` | Inline C0415 suppress; narrow exception |
| `src/tools/sheet_log.py` | Narrow exception |
| `tests/conftest.py` | Module docstring; function docstrings; add `build_agent_patches` fixture; add `sample_resume_json`/`sample_personal` fixtures |
| All test files | Module docstrings; function docstrings; import order; remove unused imports/vars; prefix unused args; remove duplicate imports; fix W0621 |
| `tests/test_template_agent.py` | Use `with` for `NamedTemporaryFile` |

---

## Testing

No new tests required. All existing tests must pass after each change. Run `uv run pytest` after each task.
