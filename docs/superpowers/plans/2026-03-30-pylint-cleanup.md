# Pylint Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the codebase to a clean pylint score by fixing every real issue through code changes — no blanket suppression.

**Architecture:** Mechanical fixes first (docstrings, line length, imports), then structural refactors (dataclasses, helper extractions), then a final sweep of broad exceptions and test-file cleanup. Each task leaves tests green.

**Tech Stack:** Python 3.12, pylint, pytest via `uv run pytest`, dataclasses, ABC, TypedDict, cast()

---

## Task 1: Docstrings — all src/ modules, classes, and functions

**Files:**
- Modify: `src/llm.py`, `src/models.py`, `src/prompts.py`, `src/scraper.py`, `src/sheets.py`
- Modify: `src/providers.py`, `src/resume_models.py`, `src/themes.py`
- Modify: `src/debug.py`

- [ ] **Step 1: Verify baseline**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 2: Add module docstrings to src/ files missing them**

`src/llm.py` — add after `from __future__ import annotations` (which doesn't exist here; add at top):
```python
"""LLM call utilities — retry logic, JSON parsing, and document generators."""
```

`src/models.py` — add at top:
```python
"""Pydantic models for structured LLM output: job details, resume, cover letter, suggestions."""
```

`src/prompts.py` — add at top:
```python
"""System and user prompt constants for every LLM call in the pipeline."""
```

`src/scraper.py` — add at top:
```python
"""Job posting scraper — fetches and cleans raw page text from a URL."""
```

`src/sheets.py` — add at top:
```python
"""Google Sheets integration — read jobs and append/update rows."""
```

- [ ] **Step 3: Add class docstrings to src/ classes missing them**

`src/models.py` — add a one-liner docstring to each Pydantic model class that lacks one, e.g.:
```python
class SuggestedRole(BaseModel):
    """A single job title suggestion with reasoning derived from the resume."""
    title: str
    reasoning: str
```

`src/resume_models.py` — add one-liner docstrings to every class that lacks one (same pattern).

`src/themes.py` — add one-liner docstrings to `ThemeConfig` and any other un-documented class.

`src/scraper.py` — add one-liner to `ScraperError` class.

- [ ] **Step 4: Add function docstrings to src/debug.py**

`src/debug.py` currently has 5 functions without docstrings. Add one-liners:
```python
def log_output_folder(run_id: int, folder: str) -> None:
    """Record the output folder path for a debug run."""

def log_scraped(run_id: int, url: str, content: str) -> None:
    """Store raw scraped page content for a debug run."""

def log_job_details(run_id: int, details) -> None:
    """Persist parsed job details for a debug run."""

def log_resume(run_id: int, resume_json) -> None:
    """Persist the generated resume JSON for a debug run."""

def log_cover_letter(run_id: int, cover_json) -> None:
    """Persist the generated cover letter JSON for a debug run."""
```

- [ ] **Step 5: Add missing docstring to `main.py` helper functions**

`load_config` and `load_resume` in `main.py` lack docstrings:
```python
def load_config(config_path: str = "config.yaml") -> dict:
    """Load and return config.yaml as a dict."""
    ...

def load_resume(resume_path: str) -> dict:
    """Load and return resume.yaml as a dict."""
    ...
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 7: Commit**

```bash
git add src/llm.py src/models.py src/prompts.py src/scraper.py src/sheets.py \
        src/providers.py src/resume_models.py src/themes.py src/debug.py main.py
git commit -m "style: add missing module, class, and function docstrings (C0114/C0115/C0116)"
```

---

## Task 2: Mechanical fixes — long lines, import order, and misc one-liners

**Files:**
- Modify: `main.py`, `src/llm.py`, `src/memory.py`, `src/models.py`, `src/pipeline.py`
- Modify: `src/setup_wizard.py`, `src/template_agent.py`, `src/tools/resume_editor.py`
- Modify: `src/onboarding.py`, `src/providers.py`, `src/memory.py`

- [ ] **Step 1: Fix long lines (C0301) — wrap at 100 chars**

For any line over 100 characters, break it using Python's implicit line continuation inside brackets or explicit `\`. Example pattern for `src/llm.py` line 46:
```python
# Before
raw = provider.call(model=model, system=system, prompt=prompt, temperature=temperature)
# After (if over 100 chars)
raw = provider.call(
    model=model, system=system, prompt=prompt, temperature=temperature
)
```
Apply this pattern to every affected line across: `main.py`, `src/llm.py`, `src/memory.py`, `src/models.py`, `src/pipeline.py`, `src/setup_wizard.py`, `src/template_agent.py`, `src/tools/resume_editor.py`.

- [ ] **Step 2: Fix import order (C0411/C0413)**

`src/llm.py` — move `from typing import Type, TypeVar` to the top (before third-party imports):
```python
# Correct order:
import json
import yaml                      # stdlib
from typing import Type, TypeVar # stdlib

from pydantic import BaseModel, ValidationError  # third-party
import json_repair                               # third-party

from src.models import ...   # local
from src.prompts import ...  # local
from src.providers import ... # local
```

- [ ] **Step 3: Fix W0107 — remove unnecessary `pass` in src/memory.py**

Find the bare `pass` after an empty `except` or empty method body in `src/memory.py` and remove it. If the body becomes empty, add a docstring or a `return` as appropriate.

- [ ] **Step 4: Fix W1309 — f-string without interpolation in src/onboarding.py:172**

Find the line that reads something like `f"some literal string"` with no `{...}` substitution and remove the `f` prefix:
```python
# Before
click.echo(f"Let's move on to the next section.")
# After
click.echo("Let's move on to the next section.")
```

- [ ] **Step 5: Fix C0209 — %-format strings in src/document.py**

Two locations use `"...%s..." % x` style. Convert to f-strings:
```python
# Before (document.py:146 area)
paragraph.add_run("%s" % value)
# After
paragraph.add_run(f"{value}")
```

- [ ] **Step 6: Fix R1705 — else after return in src/onboarding.py:124**

```python
# Before
if condition:
    return value
else:
    do_other_thing()

# After
if condition:
    return value
do_other_thing()
```

- [ ] **Step 7: Fix R1723 — else after break**

`src/setup_wizard.py:167` and `src/template_agent.py:119`:
```python
# Before
while True:
    val = input(...)
    if val in valid:
        break
    else:
        print("invalid")

# After
while True:
    val = input(...)
    if val in valid:
        break
    print("invalid")
```

- [ ] **Step 8: Fix W0707 — raise without `from` in src/providers.py (3 places)**

Find all bare `raise ImportError(...)` inside `except ImportError:` blocks and add `from` chaining:
```python
# Before
try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI SDK not installed. Run: uv add openai")

# After
try:
    from openai import OpenAI
except ImportError as exc:
    raise ImportError("OpenAI SDK not installed. Run: uv add openai") from exc
```
Apply to all three provider `__init__` methods (`OpenAIProvider`, `AnthropicProvider`, `GeminiProvider`).

- [ ] **Step 9: Fix R1732 — use `with` for urlopen in src/setup_wizard.py:46**

```python
# Before
response = urllib.request.urlopen(url, timeout=3)
return True

# After
with urllib.request.urlopen(url, timeout=3):
    return True
```

- [ ] **Step 10: Fix W0404 — duplicate re-imports in test files**

Open `tests/test_pipeline.py`, `tests/test_setup_wizard.py`, `tests/test_template_cli.py` and remove any `import` statements that import the same name twice in the same file.

- [ ] **Step 11: Run tests**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 12: Commit**

```bash
git add main.py src/llm.py src/memory.py src/models.py src/pipeline.py \
        src/setup_wizard.py src/template_agent.py src/tools/resume_editor.py \
        src/onboarding.py src/providers.py \
        tests/test_pipeline.py tests/test_setup_wizard.py tests/test_template_cli.py
git commit -m "style: fix long lines, import order, and misc mechanical issues (C0301/C0411/R1705/W0707/W0107/W1309/C0209/R1723/R1732/W0404)"
```

---

## Task 3: Unused imports and variables (W0611/W0612/W0613)

**Files:**
- Modify: all test files with unused imports, `src/memory.py`, `src/setup_wizard.py`

- [ ] **Step 1: Remove unused imports from test files**

Common offenders — open each test file and remove imports that are never referenced:
- `pytest` imported but unused as a direct reference (only used for `@pytest.fixture` etc. — keep if used, remove if truly unused)
- Unused theme constants imported in `test_document_themes.py`
- Unused `MagicMock` or `patch` re-imports

Work through each test file systematically. Run `uv run pylint tests/` to identify which imports remain flagged.

- [ ] **Step 2: Prefix unused arguments with `_`**

For every function argument that is never referenced in its body, prepend `_`:
- `src/memory.py` `__init__`: `provider_name` → `_provider_name` (if unused after init assignment)
- `src/setup_wizard.py` `ensure_provider_ready`: `config` → `_config` for the `local` and `cloud` branches where config is not used

Pattern:
```python
# Before
def ensure_provider_ready(provider: str, config: dict) -> None:
    if provider in ("local", "cloud"):
        ...  # config never used here

# After
def ensure_provider_ready(provider: str, _config: dict) -> None:
    if provider in ("local", "cloud"):
        ...
```

- [ ] **Step 3: Remove or assign unused variables to `_`**

In `main.py` and `src/pipeline.py`, any variable assigned but never read:
```python
# Before
folder, _, resume_json = process_job(...)

# After (if folder truly unused here)
_, _, resume_json = process_job(...)
```
Apply only where confirmed unused.

- [ ] **Step 4: Run tests**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "style: remove unused imports and prefix unused arguments with _ (W0611/W0612/W0613)"
```

---

## Task 4: C0415 — inline suppress on intentional lazy imports

**Files:**
- Modify: `main.py`, `src/agent.py`, `src/llm.py`, `src/onboarding.py`, `src/providers.py`, `src/setup_wizard.py`, `src/tools/search.py`

- [ ] **Step 1: Add inline suppress to each lazy import in main.py**

Every `import` statement that appears inside a function body in `main.py` gets a comment:
```python
from src.sheets import get_jobs  # pylint: disable=import-outside-toplevel
from pathlib import Path  # pylint: disable=import-outside-toplevel
from src.setup_wizard import run_setup_wizard  # pylint: disable=import-outside-toplevel
from src.setup_wizard import ensure_provider_ready  # pylint: disable=import-outside-toplevel
from src.onboarding import run_onboarding  # pylint: disable=import-outside-toplevel  (if present)
from src.debug import init_db, log_run  # pylint: disable=import-outside-toplevel
from src.pipeline import process_job  # pylint: disable=import-outside-toplevel
from src.providers import get_provider, resolve_models  # pylint: disable=import-outside-toplevel
from src.agent import run_agent_chat  # pylint: disable=import-outside-toplevel
import src.setup_wizard as _sw  # pylint: disable=import-outside-toplevel
import src.onboarding as _ob  # pylint: disable=import-outside-toplevel
```

- [ ] **Step 2: Add inline suppress to lazy imports in src/agent.py**

```python
from langchain_core.tools import tool as lc_tool  # pylint: disable=import-outside-toplevel
from langchain_core.runnables import RunnableConfig  # pylint: disable=import-outside-toplevel
import yaml as _yaml  # pylint: disable=import-outside-toplevel
```

- [ ] **Step 3: Add inline suppress to lazy import in src/llm.py**

```python
import click  # pylint: disable=import-outside-toplevel
```

- [ ] **Step 4: Add inline suppress to lazy imports in src/onboarding.py**

Any `from src.providers import ...` inside a function body.

- [ ] **Step 5: Add inline suppress to optional SDK imports in src/providers.py**

```python
from ollama import generate  # pylint: disable=import-outside-toplevel
from ollama import Client  # pylint: disable=import-outside-toplevel
from openai import OpenAI  # pylint: disable=import-outside-toplevel
import anthropic  # pylint: disable=import-outside-toplevel
from anthropic.types import TextBlock  # pylint: disable=import-outside-toplevel
from google import genai  # pylint: disable=import-outside-toplevel
from google.genai import types  # pylint: disable=import-outside-toplevel
```

- [ ] **Step 6: Add inline suppress to lazy import in src/setup_wizard.py**

```python
from dotenv import load_dotenv  # pylint: disable=import-outside-toplevel
```

- [ ] **Step 7: Add inline suppress in src/tools/search.py**

```python
from langchain_tavily import TavilySearch  # pylint: disable=import-outside-toplevel
```

- [ ] **Step 8: Run tests**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 9: Commit**

```bash
git add main.py src/agent.py src/llm.py src/onboarding.py src/providers.py \
        src/setup_wizard.py src/tools/search.py
git commit -m "style: add pylint suppress comments on intentional lazy imports (C0415)"
```

---

## Task 5: src/providers.py — BaseProvider ABC, TypedDicts for E1101, R0903

**Files:**
- Modify: `src/providers.py`

- [ ] **Step 1: Verify existing provider tests pass**

```bash
uv run pytest --tb=short -q
```

- [ ] **Step 2: Add `stream()` method to `LLMProvider` to fix R0903**

`LLMProvider` currently has only the abstract `call()` method. Add a default `stream()` so subclasses each have two public methods:

```python
class LLMProvider(ABC):
    """Abstract base for all LLM provider implementations."""

    @abstractmethod
    def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
        """Send a prompt and return the full response string."""

    def stream(self, system: str, prompt: str):
        """Non-streaming fallback — override in providers that support streaming."""
        return None
```

Add a one-liner docstring to every provider class that is missing one:
```python
class OpenAIProvider(LLMProvider):
    """OpenAI chat completions provider (requires OPENAI_API_KEY)."""

class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider (requires ANTHROPIC_API_KEY)."""

class GeminiProvider(LLMProvider):
    """Google Gemini provider via google-genai SDK (requires GEMINI_API_KEY)."""
```

- [ ] **Step 3: Add TypedDicts for ollama E1101**

The ollama generator returns objects whose `.response` and `.message` attributes pylint cannot see. Fix using TypedDict and cast():

Add near the top of `src/providers.py`, after the `import os` block:

```python
from typing import TypedDict, cast


class _GenerateChunk(TypedDict):
    response: str


class _ChatChunk(TypedDict):
    message: dict
```

- [ ] **Step 4: Update LocalOllamaProvider.call() to use cast()**

```python
def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
    """Call ollama.generate() and return the response string."""
    from ollama import generate  # pylint: disable=import-outside-toplevel
    raw = generate(
        model=model,
        prompt=prompt,
        system=system,
        format="json",
        options={"temperature": temperature},
    )
    chunk = cast(_GenerateChunk, raw)
    return chunk["response"]
```

- [ ] **Step 5: Update OllamaCloudProvider.call() to use cast()**

```python
def call(self, model: str, system: str, prompt: str, temperature: float) -> str:
    """Call ollama.Client.chat() and return the message content string."""
    raw = self._client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        format="json",
        options={"temperature": temperature},
    )
    chunk = cast(_ChatChunk, raw)
    return chunk["message"].get("content") or ""
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 7: Commit**

```bash
git add src/providers.py
git commit -m "refactor: add BaseProvider stream() default, TypedDict+cast for ollama E1101, R0903 fix"
```

---

## Task 6: main.py — structural refactor (R0913/R0917/R0914)

**Files:**
- Modify: `main.py`
- Test: `tests/test_setup_wizard.py` (run_command tests cover main.py)

- [ ] **Step 1: Run existing main.py tests**

```bash
uv run pytest tests/test_setup_wizard.py -v
```
Expected: all passing.

- [ ] **Step 2: Remove dead CLI options and replace --resume-only/--cover-only with --mode**

In `main.py`, update the `run_jobs` command decorator:

```python
@cli.command("run")
@click.option("--url", "direct_url", default=None,
              help="Process a single job URL directly (bypasses agent).")
@click.option(
    "--mode",
    type=click.Choice(["both", "resume", "cover"]),
    default="both",
    show_default=True,
    help="Which documents to generate in --url mode.",
)
@click.option("--provider", "provider_name", default=None,
              type=click.Choice(["local", "cloud", "openai", "anthropic", "gemini"]),
              help="LLM provider. Omit for local Ollama (default).")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
@click.option("--debug", is_flag=True, default=False,
              help="Log scraped content and LLM outputs to debug.db.")
def run_jobs(direct_url, mode, provider_name, config_path, debug):
    """Search for jobs with the agent, or process a single URL with --url."""
```

The old `row_num / run_all / force` options and their guard are removed entirely.

Translate `mode` to boolean flags for the pipeline call:
```python
resume_only = (mode == "resume")
cover_only = (mode == "cover")
```

- [ ] **Step 3: Extract `_handle_first_run()` helper**

```python
def _handle_first_run(config_path: str, provider_name: str | None) -> None:
    """Run first-time setup: wizard → onboarding → template → optional agent start."""
    from src.setup_wizard import run_setup_wizard  # pylint: disable=import-outside-toplevel
    config = run_setup_wizard(config_path)
    resolved = provider_name or config.get("provider", "local")

    resume_yaml = config["paths"]["resume_yaml"]
    if not Path(resume_yaml).exists():
        import src.onboarding as _ob  # pylint: disable=import-outside-toplevel
        _ob.run_onboarding(config, resolved)

    template_yaml = config.get("paths", {}).get("template_yaml", "template.yaml")
    if not Path(template_yaml).exists():
        run_template_wizard(config, resolved)

    if not click.confirm("\nSetup complete! Ready to start the job search agent?", default=False):
        click.echo("\nRun 'uv run python main.py run' when you're ready.\n")
        return

    from src.agent import run_agent_chat  # pylint: disable=import-outside-toplevel
    run_agent_chat(config=config, provider_name=resolved)
```

- [ ] **Step 4: Extract `_handle_direct_url()` helper**

```python
def _handle_direct_url(
    config: dict,
    direct_url: str,
    mode: str,
    resolved_provider: str,
    debug: bool,
) -> None:
    """Scrape, parse, and generate documents for a single URL."""
    from src.providers import get_provider, resolve_models  # pylint: disable=import-outside-toplevel
    from src.debug import init_db, log_run  # pylint: disable=import-outside-toplevel
    from src.pipeline import process_job  # pylint: disable=import-outside-toplevel

    resume = load_resume(config["paths"]["resume_yaml"])
    llm_cfg = config["llm"]
    provider = get_provider(resolved_provider, llm_cfg)
    models, parser_models = resolve_models(resolved_provider, llm_cfg)
    click.echo(
        f"Provider: {resolved_provider}  |  model: {models[0]}  |  "
        f"parser: {parser_models[0]}"
    )

    if debug:
        init_db()
        click.echo(click.style("  Debug mode enabled — logging to debug.db", fg="cyan"))

    job = {"url": direct_url, "job_title": "", "status": "", "details": "", "row": None}
    click.echo(f"\nProcessing: {direct_url}")
    debug_run_id = log_run(direct_url, resolved_provider, models[0], parser_models[0]) if debug else None
    resume_only = (mode == "resume")
    cover_only = (mode == "cover")
    folder, _, resume_json = process_job(
        job, config, resume, provider, models, parser_models,
        resume_only=resume_only, cover_only=cover_only,
        debug_run_id=debug_run_id,
    )
    if resume_json is not None:
        click.echo(f"  Priority: {resume_json.priority}/10 — {resume_json.priority_reasoning}")
    click.echo(click.style(f"\n  Saved to: {folder}", fg="green"))
```

- [ ] **Step 5: Update run_jobs to be a thin dispatcher**

```python
def run_jobs(direct_url, mode, provider_name, config_path, debug):
    """Search for jobs with the agent, or process a single URL with --url."""
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    if not Path(config_path).exists():
        _handle_first_run(config_path, provider_name)
        return

    config = load_config(config_path)
    if "template_yaml" not in config.get("paths", {}):
        config.setdefault("paths", {})["template_yaml"] = "template.yaml"

    from src.setup_wizard import ensure_provider_ready  # pylint: disable=import-outside-toplevel
    resolved_provider = provider_name or config.get("provider", "local")
    ensure_provider_ready(resolved_provider, config)

    if direct_url:
        _handle_direct_url(config, direct_url, mode, resolved_provider, debug)
        return

    from src.agent import run_agent_chat  # pylint: disable=import-outside-toplevel
    run_agent_chat(config=config, provider_name=resolved_provider)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_setup_wizard.py -v
```
Expected: all passing. If `test_run_command_uses_config_provider_as_default` fails because it passes `resume_only`/`cover_only`, update the test to use `mode="both"`.

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "refactor: replace --resume-only/--cover-only with --mode, extract _handle_first_run/_handle_direct_url (R0913/R0914)"
```

---

## Task 7: src/pipeline.py — JobOptions dataclass (R0913/R0917/R0914)

**Files:**
- Modify: `src/pipeline.py`
- Modify: `main.py` (caller update)
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Run existing pipeline tests**

```bash
uv run pytest tests/test_pipeline.py -v
```
Expected: all passing.

- [ ] **Step 2: Add JobOptions dataclass to src/pipeline.py**

Add after the existing imports:

```python
from dataclasses import dataclass, field


@dataclass
class JobOptions:
    """Flags that control which documents process_job generates."""

    resume_only: bool = False
    cover_only: bool = False
    debug_run_id: int | None = None
```

- [ ] **Step 3: Extract `_run_debug_init` helper**

```python
def _run_debug_init(url: str, provider: str, model: str, parser_model: str) -> int:
    """Initialise debug DB and log a new run; return the run ID."""
    from src.debug import init_db, log_run  # pylint: disable=import-outside-toplevel
    init_db()
    return log_run(url, provider, model, parser_model)
```

- [ ] **Step 4: Update `process_job` signature**

Change the signature from:
```python
def process_job(job, config, resume, provider, models, parser_models,
                resume_only=False, cover_only=False, debug_run_id=None):
```
To:
```python
def process_job(
    job: dict,
    config: dict,
    resume: dict,
    provider,
    models: list[str],
    parser_models: list[str],
    options: JobOptions | None = None,
) -> tuple:
    """Scrape, parse, and generate resume/cover letter documents for one job."""
    if options is None:
        options = JobOptions()
```

Then replace all references to `resume_only`, `cover_only`, `debug_run_id` in the body with `options.resume_only`, `options.cover_only`, `options.debug_run_id`.

- [ ] **Step 5: Update callers in main.py**

In `_handle_direct_url`:
```python
from src.pipeline import process_job, JobOptions  # pylint: disable=import-outside-toplevel

opts = JobOptions(
    resume_only=(mode == "resume"),
    cover_only=(mode == "cover"),
    debug_run_id=debug_run_id,
)
folder, _, resume_json = process_job(job, config, resume, provider, models, parser_models, opts)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_pipeline.py tests/test_setup_wizard.py -v
```
Expected: all passing. Update any test that passes `resume_only=` as a keyword arg to construct a `JobOptions` instead.

- [ ] **Step 7: Commit**

```bash
git add src/pipeline.py main.py tests/test_pipeline.py
git commit -m "refactor: introduce JobOptions dataclass, reduce process_job to 7 params (R0913/R0914)"
```

---

## Task 8: src/sheets.py + src/tools/sheet_log.py — JobRow dataclass (R0913/R0917)

**Files:**
- Modify: `src/sheets.py`
- Modify: `src/tools/sheet_log.py`
- Test: `tests/test_sheets.py`, `tests/test_sheet_log.py`

- [ ] **Step 1: Run existing sheet tests**

```bash
uv run pytest tests/test_sheets.py tests/test_sheet_log.py -v
```
Expected: all passing.

- [ ] **Step 2: Read the full append_job_row signature in src/sheets.py**

Open `src/sheets.py`, find `append_job_row` and note its current parameter list. It currently takes `config` plus individual column kwargs.

- [ ] **Step 3: Add JobRow dataclass to src/sheets.py**

```python
from dataclasses import dataclass


@dataclass
class JobRow:
    """All column values for a single job row appended to the sheet."""

    job_title: str
    company: str
    url: str
    status: str
    date_found: str
    details: str = ""
    priority: str = ""
    reasoning: str = ""
```

- [ ] **Step 4: Update append_job_row signature**

```python
def append_job_row(config: dict, row: JobRow) -> None:
    """Append a new job row to the configured Google Sheet."""
    sheet = _open_sheet(config)
    cols = config["google_sheets"]["columns"]
    headers = sheet.row_values(1)
    new_row = [""] * len(headers)
    mapping = {
        cols.get("job_title"): row.job_title,
        cols.get("company"): row.company,
        cols.get("url"): row.url,
        cols.get("status"): row.status,
        cols.get("date_found"): row.date_found,
        cols.get("details"): row.details,
        cols.get("priority"): row.priority,
        cols.get("reasoning"): row.reasoning,
    }
    for col_name, value in mapping.items():
        if col_name and col_name in headers:
            new_row[headers.index(col_name)] = value
    sheet.append_row(new_row)
```

- [ ] **Step 5: Update src/tools/sheet_log.py caller**

```python
from src.sheets import append_job_row, JobRow

# Inside log_job_to_sheet:
append_job_row(
    config,
    JobRow(
        job_title=title,
        company=company,
        url=url,
        status=status,
        date_found=date.today().isoformat(),
    ),
)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_sheets.py tests/test_sheet_log.py -v
```
Expected: all passing. Update any test that calls `append_job_row` with old positional/keyword args to use `JobRow`.

- [ ] **Step 7: Commit**

```bash
git add src/sheets.py src/tools/sheet_log.py tests/test_sheets.py tests/test_sheet_log.py
git commit -m "refactor: introduce JobRow dataclass, reduce append_job_row to 2 params (R0913/R0917)"
```

---

## Task 9: src/agent.py — extract helpers to reduce local count (R0914)

**Files:**
- Modify: `src/agent.py`
- Test: `tests/test_agent.py`

- [ ] **Step 1: Run existing agent tests**

```bash
uv run pytest tests/test_agent.py -v
```
Expected: all passing.

- [ ] **Step 2: Extract `_build_tools()` from `build_agent()`**

Add this function above `build_agent`:

```python
def _build_tools(
    config: dict,
    resume: dict,
    provider,
    provider_name: str,
    models: list[str],
    parser_models: list[str],
) -> list:
    """Assemble and return the full tool list for the agent."""
    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    max_jobs = config.get("agent", {}).get("max_jobs", 10)
    agent_model_placeholder = None  # set by build_agent after init_chat_model

    search_tool = create_search_tool(None, tavily_api_key, max_jobs)
    generate_tool = create_generate_tool(config, resume, provider, models, parser_models)
    read_resume, write_resume = create_resume_tools(config["paths"]["resume_yaml"])
    sheet_log_tool = create_sheet_log_tool(config)
    change_template_tool = _create_change_template_tool(config, provider_name)
    suggest_roles_tool = create_suggest_roles_tool(config, provider, parser_models)

    return [search_tool, generate_tool, read_resume, write_resume,
            sheet_log_tool, change_template_tool, suggest_roles_tool]
```

Note: `create_search_tool` takes `agent_model` as its first argument. Since we need the model first, keep the search_tool construction in `build_agent` and pass the full list back. Alternatively, restructure: let `_build_tools` take `agent_model` as a param.

Revised version:
```python
def _build_tools(
    agent_model,
    config: dict,
    resume: dict,
    provider,
    provider_name: str,
    models: list[str],
    parser_models: list[str],
) -> list:
    """Assemble and return the full tool list for the agent."""
    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    max_jobs = config.get("agent", {}).get("max_jobs", 10)
    return [
        create_search_tool(agent_model, tavily_api_key, max_jobs),
        create_generate_tool(config, resume, provider, models, parser_models),
        *create_resume_tools(config["paths"]["resume_yaml"]),
        create_sheet_log_tool(config),
        _create_change_template_tool(config, provider_name),
        create_suggest_roles_tool(config, provider, parser_models),
    ]
```

- [ ] **Step 3: Update `build_agent()` to call `_build_tools()`**

```python
def build_agent(config: dict, resume: dict, provider_name: str, recalled_memories: str):
    """Construct and return the compiled Deep Agents orchestrator graph."""
    prefix, model_name = _langchain_model_string(provider_name, config)
    agent_model = init_chat_model(model=model_name, model_provider=prefix)

    models, parser_models = resolve_models(provider_name, config["llm"])
    provider = get_provider(provider_name, config["llm"])
    tools = _build_tools(agent_model, config, resume, provider, provider_name, models, parser_models)

    system_prompt = AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        candidate_name=resume["basics"]["name"],
        candidate_location=resume["basics"].get("location", "Not specified"),
        recalled_memories=recalled_memories or "No previous sessions found.",
    )
    return create_deep_agent(model=agent_model, tools=tools, system_prompt=system_prompt)
```

- [ ] **Step 4: Extract `_process_message()` from `run_agent_chat()`**

```python
def _process_message(
    agent,
    history: list,
    thread_config: dict,
) -> tuple[str, list]:
    """Invoke the agent with the current message history; return (response_text, updated_history)."""
    from langchain_core.runnables import RunnableConfig  # pylint: disable=import-outside-toplevel
    result = agent.invoke(
        {"messages": history},
        config=RunnableConfig(configurable=thread_config),
    )
    last_msg = result["messages"][-1]
    if isinstance(last_msg.content, list) and last_msg.content and "text" in last_msg.content[0]:
        response_text = last_msg.content[0]["text"]
    elif isinstance(last_msg.content, str):
        response_text = last_msg.content
    else:
        response_text = ""
    return response_text, result["messages"]
```

Then update `run_agent_chat` to call `_process_message(agent, history, thread_config)`.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_agent.py -v
```
Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add src/agent.py
git commit -m "refactor: extract _build_tools and _process_message from agent.py to reduce locals (R0914)"
```

---

## Task 10: src/template_agent.py — extract helpers (R0914/R0912/R0915)

**Files:**
- Modify: `src/template_agent.py`
- Test: `tests/test_template_agent.py`

- [ ] **Step 1: Run existing template agent tests**

```bash
uv run pytest tests/test_template_agent.py -v
```
Expected: all passing.

- [ ] **Step 2: Read template_agent.py fully**

```bash
# Use the Read tool to view src/template_agent.py completely before editing
```

- [ ] **Step 3: Extract `_prompt_for_overrides()`**

Find the block in `run_template_wizard` that collects user colour/font input and extract it:

```python
def _prompt_for_overrides(theme: "ThemeConfig") -> "TemplateOverrides":
    """Interactively prompt the user for colour and font overrides for the chosen theme."""
    # move the input/LLM extraction block here
    # return a TemplateOverrides instance
```

- [ ] **Step 4: Extract `_apply_overrides()`**

Find the block that writes overrides to template YAML and extract it:

```python
def _apply_overrides(template_path: str, theme_name: str, overrides: "TemplateOverrides") -> None:
    """Write theme name and user overrides to template.yaml."""
    # move the yaml write block here
```

- [ ] **Step 5: Update `run_template_wizard()` to call the helpers**

The function becomes a coordinator:
```python
def run_template_wizard(config: dict, provider_name: str) -> "ThemeConfig":
    """Interactively choose a resume theme and apply overrides."""
    theme = _pick_theme()
    overrides = _prompt_for_overrides(theme)
    _apply_overrides(config["paths"]["template_yaml"], theme.name, overrides)
    return theme
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_template_agent.py -v
```
Expected: all passing.

- [ ] **Step 7: Commit**

```bash
git add src/template_agent.py
git commit -m "refactor: extract _prompt_for_overrides and _apply_overrides from run_template_wizard (R0914)"
```

---

## Task 11: src/onboarding.py — R0913 fix via CallContext

**Files:**
- Modify: `src/llm.py` (add CallContext)
- Modify: `src/onboarding.py` (use CallContext)
- Test: `tests/test_onboarding.py`

- [ ] **Step 1: Run existing onboarding tests**

```bash
uv run pytest tests/test_onboarding.py -v
```
Expected: all passing.

- [ ] **Step 2: Add CallContext dataclass to src/llm.py**

```python
from dataclasses import dataclass
from src.providers import LLMProvider  # already imported


@dataclass
class CallContext:
    """Bundles provider, LLM config, and model lists for _call_with_retry callers."""

    provider: LLMProvider
    llm_cfg: dict
    parser_models: list[str]
```

Export it so `src/onboarding.py` can import it.

- [ ] **Step 3: Update extract_section in src/onboarding.py**

Current signature:
```python
def extract_section(section, raw_input, provider, parser_models, llm_cfg, correction=None):
```

New signature (5 params, down from 6):
```python
from src.llm import _call_with_retry, CallContext

def extract_section(
    section: str,
    raw_input: str,
    ctx: "CallContext",
    correction: str | None = None,
) -> Any:
    """Send raw user input to parser_model and return a validated Pydantic section model."""
```

Replace all uses of `provider`, `parser_models`, `llm_cfg` in the body with `ctx.provider`, `ctx.parser_models`, `ctx.llm_cfg`.

- [ ] **Step 4: Update all callers of extract_section inside onboarding.py**

Wherever `run_onboarding` calls `extract_section(section, raw, provider, parser_models, llm_cfg)`, replace with:
```python
ctx = CallContext(provider=provider, llm_cfg=llm_cfg, parser_models=parser_models)
result = extract_section(section, raw, ctx)
```
(Create `ctx` once at the top of `run_onboarding`, reuse it throughout.)

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_onboarding.py -v
```
Expected: all passing. Update any test that calls `extract_section` with the old signature to pass a `CallContext` object.

- [ ] **Step 6: Commit**

```bash
git add src/llm.py src/onboarding.py tests/test_onboarding.py
git commit -m "refactor: add CallContext dataclass, reduce extract_section to 4 params (R0913)"
```

---

## Task 12: src/document.py — C0103 renames, W0212 wrappers, section renderers

**Files:**
- Modify: `src/document.py`
- Test: `tests/test_document_themes.py`

- [ ] **Step 1: Run existing document tests**

```bash
uv run pytest tests/test_document_themes.py -v
```
Expected: all passing.

- [ ] **Step 2: Add W0212 helper functions near the top of src/document.py**

Add immediately after the import block:

```python
def _para_xml(paragraph):
    return paragraph._p   # pylint: disable=protected-access


def _cell_xml(cell):
    return cell._tc       # pylint: disable=protected-access


def _run_xml(run):
    return run._r         # pylint: disable=protected-access
```

- [ ] **Step 3: Replace all direct protected access with helpers**

Search `src/document.py` for every occurrence of:
- `paragraph._p` → `_para_xml(paragraph)`
- `cell._tc` → `_cell_xml(cell)`
- `run._r` → `_run_xml(run)`

After this change, `W0212` appears in exactly 3 lines (inside the helpers), not scattered everywhere.

- [ ] **Step 4: Rename camelCase locals (C0103)**

In `src/document.py`, find and rename these identifiers everywhere they appear:

| Old | New |
|-----|-----|
| `pPr` | `para_props` |
| `pBdr` | `para_border` |
| `tcPr` | `cell_props` |
| `tcBorders` | `tc_borders` |
| `keepNext` | `keep_next` |

Use a search-and-replace within the file scope only.

- [ ] **Step 5: Extract per-section renderer functions**

Find the large `build_resume` function and extract these helpers:

```python
def _render_header(doc, personal: dict, theme) -> None:
    """Add candidate name and contact line to the document."""
    # move the name/contact block here

def _render_summary(doc, summary: str, theme) -> None:
    """Add professional summary section to the document."""
    # move the summary block here

def _render_experience(doc, work: list, theme) -> None:
    """Add work history section to the document."""
    # move the work history block here

def _render_education_certs(doc, education: list, certifications: list, theme) -> None:
    """Add education and certifications table to the document."""
    # move the education/certs block here

def _render_skills(doc, skills: list, theme) -> None:
    """Add skills section to the document."""
    # move the skills block here
```

For `build_cover_letter`, extract:

```python
def _render_cover_body(doc, content: list[str], theme) -> None:
    """Add cover letter body paragraphs to the document."""
    # move the paragraph rendering loop here
```

`build_resume` and `build_cover_letter` become thin coordinators calling these helpers.

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_document_themes.py -v
```
Expected: all passing.

- [ ] **Step 7: Commit**

```bash
git add src/document.py
git commit -m "refactor: add W0212 xml helpers, rename camelCase vars, extract section renderers (C0103/W0212/R0914)"
```

---

## Task 13: W0718 — narrow broad exceptions across all remaining files

**Files:**
- Modify: `src/agent.py`, `src/llm.py`, `src/memory.py`, `src/onboarding.py`, `src/pipeline.py`
- Modify: `src/scraper.py`, `src/setup_wizard.py`, `src/template_agent.py`
- Modify: `src/tools/generate.py`, `src/tools/search.py`, `src/tools/sheet_log.py`
- Modify: `main.py`

- [ ] **Step 1: Apply exception narrowing per the spec table**

For each `except Exception` in the following files, replace with the specific tuple:

| File | Context | Replacement |
|------|---------|-------------|
| `src/agent.py` line ~40 | Tool wrapper returning error string | `(RuntimeError, ValueError, OSError)` |
| `src/agent.py` line ~157 | Agent invocation in chat loop | `(RuntimeError, ConnectionError, ValueError)` |
| `src/llm.py` line ~47 | Provider call in retry loop | `(RuntimeError, ValueError, ConnectionError, TimeoutError)` |
| `src/llm.py` line ~62 | JSON parse in retry loop | `(ValueError, json.JSONDecodeError)` |
| `src/memory.py` ×4 | Memory bank operations | `(RuntimeError, OSError, ConnectionError)` |
| `src/onboarding.py` ×2 | LLM interview call | `(RuntimeError, ValueError, ConnectionError)` |
| `src/pipeline.py` ~62 | Job scraping | `(RuntimeError, OSError, ConnectionError, TimeoutError)` |
| `src/scraper.py` ×2 | HTTP requests | `(OSError, ConnectionError, TimeoutError, ValueError)` |
| `src/setup_wizard.py` ~48 | URL check | `(OSError, ConnectionError)` |
| `src/template_agent.py` ×2 | LLM call / template write | `(RuntimeError, ValueError, OSError)` |
| `src/tools/generate.py` ~60 | Tool wrapper | `(RuntimeError, ValueError, OSError, ConnectionError)` |
| `src/tools/search.py` ~46 | Tool wrapper | `(RuntimeError, OSError, ConnectionError, TimeoutError)` |
| `src/tools/sheet_log.py` ~43 | Tool wrapper | `(RuntimeError, OSError, ConnectionError)` |
| `main.py` ~61 | Sheet read in list_jobs | `(OSError, ConnectionError, RuntimeError)` |

Example edit pattern:
```python
# Before
except Exception as exc:
    return f"Sheet logging unavailable: {exc}"

# After
except (RuntimeError, OSError, ConnectionError) as exc:
    return f"Sheet logging unavailable: {exc}"
```

- [ ] **Step 2: Run all tests**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 3: Commit**

```bash
git add src/agent.py src/llm.py src/memory.py src/onboarding.py src/pipeline.py \
        src/scraper.py src/setup_wizard.py src/template_agent.py \
        src/tools/generate.py src/tools/search.py src/tools/sheet_log.py main.py
git commit -m "refactor: narrow broad except Exception to specific exception tuples (W0718)"
```

---

## Task 14: Test file cleanup + conftest.py updates

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_agent.py`, `tests/test_document_themes.py`, `tests/test_generate_tool.py`
- Modify: `tests/test_memory.py`, `tests/test_onboarding.py`, `tests/test_pipeline.py`
- Modify: `tests/test_resume_editor.py`, `tests/test_resume_models.py`, `tests/test_search_tool.py`
- Modify: `tests/test_sheet_log.py`, `tests/test_sheets.py`, `tests/test_setup_wizard.py`
- Modify: `tests/test_suggest_roles.py`, `tests/test_template_agent.py`, `tests/test_template_cli.py`
- Modify: `tests/test_themes.py`

- [ ] **Step 1: Run full test suite as baseline**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 2: Add module docstrings to every test file**

Add a one-liner at the top of each test file:
```python
"""Tests for src/agent.py — build_agent construction and chat loop."""
```
```python
"""Tests for src/document.py theme rendering."""
```
```python
"""Tests for src/tools/generate.py — document generation tool."""
```
...and so on for every test file.

- [ ] **Step 3: Add function docstrings to all undocumented test functions**

Add one-line docstrings to every `def test_*` that lacks one. Keep them short and factual:
```python
def test_build_agent_includes_suggest_roles_tool():
    """build_agent passes suggest_roles_tool in the tool list."""
```
```python
def test_ollama_reachable_returns_true_when_server_up():
    """_ollama_reachable returns True when urlopen succeeds."""
```

- [ ] **Step 4: Fix import order in test files**

Reorder to: stdlib → third-party → local in all affected files. Common pattern:
```python
# stdlib
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
# third-party
import pytest
import yaml
# local
from src.agent import build_agent
```

Files needing this: `tests/test_onboarding.py`, `tests/test_setup_wizard.py`, `tests/test_template_agent.py`, `tests/test_template_cli.py`.

- [ ] **Step 5: Fix W0621 — move fixtures to conftest.py**

`test_document_themes.py` defines `sample_resume_json` and `sample_personal` fixtures that conflict with local function parameters (W0621). Move both to `tests/conftest.py`:

```python
@pytest.fixture
def sample_resume_json():
    """Minimal ResumeJSON-compatible dict for document generation tests."""
    from src.models import ResumeJSON, WorkEntry  # pylint: disable=import-outside-toplevel
    return ResumeJSON(
        name="Jane Doe",
        email="jane@example.com",
        phone="555-1234",
        location="Montreal, QC",
        summary="Experienced engineer.",
        experience=[],
        education=[],
        skills=[],
        certifications=[],
        priority=7,
        priority_reasoning="Good match",
    )


@pytest.fixture
def sample_personal():
    """Minimal personal dict used in document header rendering tests."""
    return {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "location": "Montreal, QC",
    }
```

Remove these fixture definitions from `test_document_themes.py`. The tests continue to receive them by name from conftest.

- [ ] **Step 6: Fix R0801 — extract build_agent_patches to conftest.py**

`test_agent.py` and `test_template_cli.py` share an identical 7-line `with patch(...)` block. Add a context manager to `tests/conftest.py`:

```python
from contextlib import contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def build_agent_patches():
    """Context manager that patches all src.agent dependencies for unit tests."""
    with patch("src.agent.create_deep_agent"), \
         patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.get_provider", return_value=MagicMock()), \
         patch("src.agent.create_search_tool", return_value=MagicMock()), \
         patch("src.agent.create_generate_tool", return_value=MagicMock()), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())), \
         patch("src.agent.create_sheet_log_tool", return_value=MagicMock()):
        yield
```

Update the two tests that contain the duplicated block to use `with build_agent_patches():` instead.

- [ ] **Step 7: Fix R1732 in test_template_agent.py**

Find `NamedTemporaryFile` calls that are not wrapped in `with`. Wrap each:
```python
# Before
f = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
...

# After
with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as f:
    ...
```

- [ ] **Step 8: Run all tests**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Step 9: Commit**

```bash
git add tests/
git commit -m "style: test file docstrings, import order, move shared fixtures to conftest, fix W0621/R0801 (test cleanup)"
```

---

## Final verification

- [ ] **Run the full test suite one last time**

```bash
uv run pytest --tb=short -q
```
Expected: all passing.

- [ ] **Run pylint on src/ and main.py**

```bash
uv run pylint src/ main.py --disable=E0401,E1120
```
Expected: score ≥ 9.0/10, no C/W/R/E codes outside the excluded venv false-positives.

- [ ] **Run pylint on tests/**

```bash
uv run pylint tests/ --disable=E0401,E1120,C0415
```
Expected: score ≥ 9.0/10 (C0415 excluded for test-function-local imports used for patching).
