# Agent-Driven Job Search — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Deep Agents-powered interactive job search mode that finds, presents, and generates application documents for matching jobs — while preserving the existing `--url` pipeline unchanged.

**Architecture:** A main `create_deep_agent` orchestrator handles the streaming chat loop, calls a Tavily-powered search sub-agent (isolated context), and calls a generation tool that wraps the existing pipeline. Hindsight embedded memory persists preferences and seen jobs across sessions. The Google Sheet becomes an output log, not an input queue.

**Tech Stack:** `deepagents`, `langchain-community` (Tavily), `langchain-core`, `langchain-anthropic/openai/google-genai/ollama`, `hindsight-all`, `tavily-python`, existing `src/` modules.

---

## File Map

**New files:**
- `tests/conftest.py` — shared pytest fixtures (config dict, resume dict)
- `tests/test_pipeline.py` — tests for the extracted process_job function
- `tests/test_sheets.py` — tests for append_job_row
- `tests/test_memory.py` — tests for MemoryManager
- `tests/test_resume_editor.py` — tests for read/write section tools
- `tests/test_sheet_log.py` — tests for the sheet log tool
- `tests/test_search_tool.py` — tests for the search tool factory
- `tests/test_generate_tool.py` — tests for the generate tool factory
- `tests/test_agent.py` — smoke test for agent creation
- `src/pipeline.py` — `process_job()` extracted from main.py
- `src/memory.py` — `MemoryManager` class (Hindsight wrapper)
- `src/tools/__init__.py` — empty
- `src/tools/resume_editor.py` — `create_resume_tools(resume_path)` factory
- `src/tools/sheet_log.py` — `create_sheet_log_tool(config)` factory
- `src/tools/search.py` — `create_search_tool(agent_model, tavily_api_key, max_jobs)` factory
- `src/tools/generate.py` — `create_generate_tool(config, resume, provider, models, parser_models)` factory
- `src/agent.py` — `run_agent_chat(config, resume, provider_name)` entry point

**Modified files:**
- `pyproject.toml` — add new dependencies
- `.env.example` — add `TAVILY_API_KEY`
- `example_config.yaml` + `config.yaml` — add `agent:` section and new sheet columns
- `src/prompts.py` — add three agent system prompts
- `src/sheets.py` — add `append_job_row()`
- `main.py` — route bare `run` to agent; retire `--row`/`--all`/`--force`

---

## Task 1: Dependencies, config, and test scaffold

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `example_config.yaml`
- Modify: `config.yaml`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add dependencies to pyproject.toml**

Replace the `dependencies` list in `pyproject.toml`:

```toml
dependencies = [
    "beautifulsoup4>=4.14.3",
    "click>=8.1.8",
    "google-auth>=2.49.0",
    "gspread>=6.2.1",
    "ollama>=0.6.1",
    "pydantic>=2",
    "python-docx>=1.2.0",
    "python-dotenv>=1.2.1",
    "pyyaml>=6.0.3",
    "json-repair>=0.30.0",
    "playwright>=1.40.0",
    "requests>=2.32.5",
    "openai>=2.26.0",
    "anthropic>=0.84.0",
    "google-genai>=1.66.0",
    "deepagents>=0.1.0",
    "langchain>=0.2.0",
    "langchain-core>=0.2.0",
    "langchain-community>=0.2.0",
    "langchain-anthropic>=0.1.0",
    "langchain-openai>=0.1.0",
    "langchain-google-genai>=0.1.0",
    "langchain-ollama>=0.1.0",
    "tavily-python>=0.3.0",
    "hindsight-all>=0.1.0",
    "pytest>=8.0.0",
]
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync
```

Expected: All packages installed without errors.

- [ ] **Step 3: Add TAVILY_API_KEY to .env.example**

Append to `.env.example`:

```env
TAVILY_API_KEY=your_tavily_api_key_here   # agent search mode
```

- [ ] **Step 4: Add agent section to example_config.yaml**

Append to `example_config.yaml`:

```yaml
agent:
  max_jobs: 10        # max job listings surfaced per search session
  memory_bank: ""     # defaults to resume basics.name if empty
  memory_model: ""    # defaults to parser_model for your provider if empty
```

Also update the `google_sheets.columns` block in `example_config.yaml` to add the two new columns:

```yaml
google_sheets:
  spreadsheet_id: "your_google_spreadsheet_id_here"
  worksheet_name: "Sheet1"
  columns:
    job_title: "Title"
    company: "Company"
    url: "URL"
    status: "Status"
    date_found: "Date Found"
    details: "Details"
    priority: "Priority"
    reasoning: "Reasoning"
```

- [ ] **Step 5: Mirror the same changes in config.yaml**

Apply the same `agent:` section and updated `google_sheets.columns` to your local `config.yaml`.

- [ ] **Step 6: Create tests/conftest.py**

```python
import pytest


@pytest.fixture
def sample_config():
    return {
        "llm": {
            "temperature": 0.3,
            "max_retries": 1,
            "model": "llama3.2:latest",
            "parser_model": "llama3.2:latest",
            "anthropic": {
                "model": "claude-haiku-4-5-20251001",
                "parser_model": "claude-haiku-4-5-20251001",
                "fallback_models": [],
                "parser_fallback_models": [],
            },
        },
        "paths": {
            "resume_yaml": "resume.yaml",
            "output_dir": "output",
            "credentials": "credentials/google_service_account.json",
        },
        "google_sheets": {
            "spreadsheet_id": "test-sheet-id",
            "worksheet_name": "Sheet1",
            "columns": {
                "job_title": "Title",
                "company": "Company",
                "url": "URL",
                "status": "Status",
                "date_found": "Date Found",
                "details": "Details",
                "priority": "Priority",
                "reasoning": "Reasoning",
            },
        },
        "agent": {
            "max_jobs": 10,
            "memory_bank": "",
            "memory_model": "",
        },
    }


@pytest.fixture
def sample_resume():
    return {
        "basics": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-1234",
            "location": "Montreal, QC",
        },
        "work": [
            {
                "company": "Acme Corp",
                "position": "Software Engineer",
                "startDate": "2022-01",
                "endDate": "",
                "description": "Built internal tools.",
                "highlights": ["Built a pipeline that reduced latency by 30%."],
            }
        ],
        "education": [],
        "skills": [{"name": "Languages", "keywords": ["Python", "TypeScript"]}],
        "projects": [],
        "certificates": [],
    }
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .env.example example_config.yaml config.yaml tests/conftest.py
git commit -m "chore: add agent dependencies, config skeleton, and test scaffold"
```

---

## Task 2: Extract process_job to src/pipeline.py

**Files:**
- Create: `src/pipeline.py`
- Modify: `main.py` (remove process_job, import from pipeline)
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline.py`:

```python
from unittest.mock import MagicMock, patch
import pytest


def test_process_job_uses_cached_description(sample_config, sample_resume, tmp_path):
    """process_job skips scraping when 'details' is already present."""
    sample_config["paths"]["output_dir"] = str(tmp_path)

    job = {
        "url": "https://example.com/job/123",
        "job_title": "AI Engineer",
        "status": "",
        "details": "We are looking for an AI engineer with Python skills.",
        "row": None,
    }

    fake_job_details = MagicMock()
    fake_job_details.company = "Acme"
    fake_job_details.title = "AI Engineer"
    fake_resume_json = MagicMock()
    fake_resume_json.priority = 3
    fake_resume_json.priority_reasoning = "Good match."

    with patch("src.pipeline.parse_job_description", return_value=fake_job_details), \
         patch("src.pipeline.generate_resume", return_value=fake_resume_json), \
         patch("src.pipeline.generate_cover_letter", return_value=MagicMock()), \
         patch("src.pipeline.build_resume"), \
         patch("src.pipeline.build_cover_letter"):
        from src.pipeline import process_job
        folder, job_data, resume_json = process_job(
            job, sample_config, sample_resume,
            provider=MagicMock(), models=["m"], parser_models=["m"],
        )

    assert not job_data["_scraped_fresh"]
    assert resume_json.priority == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: `ImportError: cannot import name 'process_job' from 'src.pipeline'`

- [ ] **Step 3: Create src/pipeline.py by moving process_job from main.py**

Create `src/pipeline.py` with this content (the function body is identical to the existing `process_job` in `main.py` — only the import at the top changes):

```python
"""
Core job processing pipeline — scrape, parse, generate, write docs.
Extracted from main.py so it can be imported by both CLI and agent tools.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from src.models import ResumeJSON
    from src.providers import LLMProvider


def _unique_path(path: Path) -> Path:
    """Return path with ' (1)', ' (2)', … suffix if it already exists."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _safe_name(text: str) -> str:
    """Slugify a string for use in a directory name."""
    text = re.sub(r"[^\w\s\-]", "", text)
    return re.sub(r"\s+", "_", text).strip("_")[:40]


def process_job(
    job: dict,
    config: dict,
    resume: dict,
    provider: "LLMProvider",
    models: list[str],
    parser_models: list[str],
    resume_only: bool = False,
    cover_only: bool = False,
    debug_run_id: int | None = None,
) -> tuple[str, dict, "ResumeJSON | None"]:
    """
    Full pipeline for one job:
      scrape (or use cached details) → parse → LLM resume → LLM cover letter → write docx files
    Returns (output_directory_path, job_data, resume_json).
    """
    from src.scraper import scrape_job, ScraperError
    from src.llm import parse_job_description, generate_resume, generate_cover_letter
    from src.document import build_resume, build_cover_letter
    from src.debug import log_scraped, log_job_details, log_resume, log_cover_letter, log_output_folder

    url = job.get("url", "")
    if not url:
        raise ValueError("Job has no URL.")

    cached_description = job.get("details", "").strip()
    if cached_description:
        click.echo("  Using cached job description from sheet.")
        job_data = {**job, "description": cached_description}
        scraped_fresh = False
    else:
        click.echo(f"  Scraping {url} …")
        try:
            scraped = scrape_job(url)
        except ScraperError as e:
            raise click.ClickException(str(e))
        job_data = {**job, **scraped}
        scraped_fresh = True

    job_data["_scraped_fresh"] = scraped_fresh

    if debug_run_id is not None:
        log_scraped(debug_run_id, job_data.get("description", ""))

    click.echo("  Parsing job description …")
    job_details = parse_job_description(job_data, config, provider, parser_models)
    company = job_details.company or job_data.get("company") or job.get("job_title", "Unknown")
    title   = job_details.title   or job_data.get("title")   or job.get("job_title", "Role")

    if debug_run_id is not None:
        log_job_details(debug_run_id, job_details)

    resume_json = None
    if not cover_only:
        click.echo("  Generating tailored resume …")
        resume_json = generate_resume(job_details, resume, config, provider, models)

    cover_json = None
    if not resume_only:
        if resume_json is None:
            click.echo("  Generating resume context for cover letter …")
            resume_json = generate_resume(job_details, resume, config, provider, models)
        click.echo("  Generating cover letter …")
        cover_json = generate_cover_letter(job_details, resume, resume_json, config, provider, models)

    if debug_run_id is not None:
        if resume_json is not None:
            log_resume(debug_run_id, resume_json)
        if cover_json is not None:
            log_cover_letter(debug_run_id, cover_json)

    today_str = date.today().isoformat()
    folder = Path(config["paths"]["output_dir"]) / f"{_safe_name(company)}_{_safe_name(title)}_{today_str}"
    folder.mkdir(parents=True, exist_ok=True)

    if debug_run_id is not None:
        log_output_folder(debug_run_id, str(folder))

    candidate_name = resume["basics"]["name"]
    safe_title = re.sub(r"[^\w\s\-]", "", title).strip()

    if not cover_only and resume_json is not None:
        resume_path = str(_unique_path(folder / f"{candidate_name} - {safe_title} - Resume.docx"))
        click.echo("  Building resume.docx …")
        build_resume(
            resume_json=resume_json,
            personal=resume["basics"],
            education=resume.get("education", []),
            output_path=resume_path,
        )

    if not resume_only and cover_json is not None:
        cover_path = str(_unique_path(folder / f"{candidate_name} - {safe_title} - Cover Letter.docx"))
        click.echo("  Building cover_letter.docx …")
        build_cover_letter(
            cover_json=cover_json,
            personal=resume["basics"],
            company=company,
            job_title=title,
            output_path=cover_path,
        )

    return str(folder), job_data, resume_json
```

- [ ] **Step 4: Update main.py to import process_job from src.pipeline**

In `main.py`, remove the `_unique_path`, `_safe_name`, and `process_job` function definitions entirely. Replace the local `from src...` imports inside `process_job` by importing at the top of the function in main.py where it's called:

Change the import inside `run_jobs` from:
```python
folder, _, resume_json = process_job(
```
to:
```python
from src.pipeline import process_job
folder, _, resume_json = process_job(
```

And the same in the other call site in `run_jobs`. Also remove the `TYPE_CHECKING` block for `ResumeJSON` and `LLMProvider` from main.py if they're now unused.

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: `PASSED`

- [ ] **Step 6: Verify the existing --url flow still works end-to-end**

```bash
uv run python main.py --help
uv run python main.py run --help
```

Expected: Both print usage without errors.

- [ ] **Step 7: Commit**

```bash
git add src/pipeline.py main.py tests/test_pipeline.py
git commit -m "refactor: extract process_job to src/pipeline.py"
```

---

## Task 3: Extend sheets.py with append_job_row

**Files:**
- Modify: `src/sheets.py`
- Create: `tests/test_sheets.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sheets.py`:

```python
from unittest.mock import MagicMock, patch
import pytest


def _make_mock_sheet(headers):
    sheet = MagicMock()
    sheet.row_values.return_value = headers
    return sheet


def test_append_job_row_calls_append_row(sample_config):
    headers = ["Title", "Company", "URL", "Status", "Date Found", "Details", "Priority", "Reasoning"]
    mock_sheet = _make_mock_sheet(headers)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import append_job_row
        append_job_row(
            config=sample_config,
            title="AI Engineer",
            company="Acme Corp",
            url="https://example.com/job/1",
            status="Seen",
            date_found="2026-03-27",
        )

    mock_sheet.append_row.assert_called_once()
    appended = mock_sheet.append_row.call_args[0][0]
    assert appended[headers.index("Title")] == "AI Engineer"
    assert appended[headers.index("Company")] == "Acme Corp"
    assert appended[headers.index("URL")] == "https://example.com/job/1"
    assert appended[headers.index("Status")] == "Seen"
    assert appended[headers.index("Date Found")] == "2026-03-27"


def test_append_job_row_skips_missing_columns(sample_config):
    """If a column like 'Company' isn't in the sheet yet, skip it gracefully."""
    headers = ["Title", "URL", "Status"]  # no Company or Date Found column
    mock_sheet = _make_mock_sheet(headers)

    with patch("src.sheets._open_sheet", return_value=mock_sheet):
        from src.sheets import append_job_row
        append_job_row(
            config=sample_config,
            title="ML Engineer",
            company="Stripe",
            url="https://example.com/job/2",
            status="Seen",
            date_found="2026-03-27",
        )

    appended = mock_sheet.append_row.call_args[0][0]
    assert appended[headers.index("Title")] == "ML Engineer"
    assert appended[headers.index("URL")] == "https://example.com/job/2"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_sheets.py -v
```

Expected: `ImportError: cannot import name 'append_job_row' from 'src.sheets'`

- [ ] **Step 3: Add append_job_row to src/sheets.py**

Append to the bottom of `src/sheets.py`:

```python
def append_job_row(
    config: dict,
    title: str,
    company: str,
    url: str,
    status: str,
    date_found: str,
    priority: str = "",
    reasoning: str = "",
) -> None:
    """Append a new job row to the sheet.

    Aligns values to the sheet's header row. Skips any column not present in the sheet.
    """
    sheet = _open_sheet(config)
    cols = config["google_sheets"]["columns"]
    headers = sheet.row_values(1)

    row = [""] * len(headers)
    field_map = {
        "job_title": title,
        "company": company,
        "url": url,
        "status": status,
        "date_found": date_found,
        "priority": priority,
        "reasoning": reasoning,
    }
    for field, value in field_map.items():
        col_name = cols.get(field, "")
        if col_name and col_name in headers:
            row[headers.index(col_name)] = value

    sheet.append_row(row)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_sheets.py -v
```

Expected: Both tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/sheets.py tests/test_sheets.py
git commit -m "feat: add append_job_row to sheets.py"
```

---

## Task 4: Build src/memory.py — Hindsight wrapper

**Files:**
- Create: `src/memory.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory.py`:

```python
from unittest.mock import MagicMock, patch
import pytest


def test_memory_manager_retain_and_recall(sample_config, sample_resume):
    mock_client = MagicMock()
    mock_client.recall.return_value = "User prefers remote roles above $130k."
    mock_server = MagicMock()
    mock_server.__enter__ = MagicMock(return_value=mock_server)
    mock_server.__exit__ = MagicMock(return_value=False)
    mock_server.url = "http://localhost:8888"

    with patch("src.memory.HindsightServer", return_value=mock_server), \
         patch("src.memory.HindsightClient", return_value=mock_client):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        mgr.retain("User prefers remote roles above $130k.", context="preferences")
        result = mgr.recall("What are the user's job preferences?")
        mgr.stop()

    mock_client.retain.assert_called_once_with(
        bank_id="Jane Doe",
        content="User prefers remote roles above $130k.",
        context="preferences",
    )
    assert result == "User prefers remote roles above $130k."


def test_memory_manager_uses_resume_name_as_bank_id(sample_config, sample_resume):
    mock_client = MagicMock()
    mock_server = MagicMock()
    mock_server.__enter__ = MagicMock(return_value=mock_server)
    mock_server.__exit__ = MagicMock(return_value=False)
    mock_server.url = "http://localhost:8888"

    with patch("src.memory.HindsightServer", return_value=mock_server), \
         patch("src.memory.HindsightClient", return_value=mock_client):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()
        mgr.retain("some fact")
        mgr.stop()

    call_kwargs = mock_client.retain.call_args[1]
    assert call_kwargs["bank_id"] == "Jane Doe"


def test_memory_manager_start_failure_is_silent(sample_config, sample_resume):
    """If Hindsight fails to start, MemoryManager degrades gracefully."""
    with patch("src.memory.HindsightServer", side_effect=Exception("Server failed")):
        from src.memory import MemoryManager
        mgr = MemoryManager(config=sample_config, resume=sample_resume, provider_name="anthropic")
        mgr.start()  # should not raise
        result = mgr.recall("anything")
        mgr.stop()

    assert result == ""  # empty string when memory is unavailable
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_memory.py -v
```

Expected: `ImportError: No module named 'src.memory'`

- [ ] **Step 3: Create src/memory.py**

```python
"""
Hindsight memory wrapper for the job search agent.

Provides a MemoryManager that retains and recalls information across sessions
using Hindsight's embedded server (hindsight-all package).

Fails silently if Hindsight cannot start — the agent still works, just without
persistent memory.
"""

from __future__ import annotations

import os


# Provider name (our tool) → Hindsight llm_provider string
_HINDSIGHT_PROVIDER_MAP: dict[str, tuple[str, str]] = {
    "openai":    ("openai",    "OPENAI_API_KEY"),
    "anthropic": ("anthropic", "ANTHROPIC_API_KEY"),
    "gemini":    ("gemini",    "GEMINI_API_KEY"),
    "local":     ("ollama",    ""),
    "cloud":     ("ollama",    "OLLAMA_API_KEY"),
}


def _resolve_memory_model(config: dict, provider_name: str) -> str:
    """Return the model to use for Hindsight memory processing."""
    override = config.get("agent", {}).get("memory_model", "").strip()
    if override:
        return override
    from src.providers import resolve_models
    _, parser_models = resolve_models(provider_name, config["llm"])
    return parser_models[0]


try:
    from hindsight import HindsightServer, HindsightClient
    _HINDSIGHT_AVAILABLE = True
except ImportError:
    _HINDSIGHT_AVAILABLE = False


class MemoryManager:
    """Thin wrapper around Hindsight retain/recall for the job search agent."""

    def __init__(self, config: dict, resume: dict, provider_name: str) -> None:
        self._bank_id = (
            config.get("agent", {}).get("memory_bank", "").strip()
            or resume["basics"]["name"]
        )
        self._provider_name = provider_name
        self._config = config
        self._available = False
        self._server = None
        self._client = None

    def start(self) -> None:
        """Start the embedded Hindsight server. Fails silently on error."""
        if not _HINDSIGHT_AVAILABLE:
            return
        try:
            hindsight_provider, api_key_env = _HINDSIGHT_PROVIDER_MAP.get(
                self._provider_name, ("ollama", "")
            )
            memory_model = _resolve_memory_model(self._config, self._provider_name)
            api_key = os.environ.get(api_key_env, "") if api_key_env else ""

            self._server = HindsightServer(
                llm_provider=hindsight_provider,
                llm_model=memory_model,
                llm_api_key=api_key,
            )
            self._server.__enter__()
            self._client = HindsightClient(base_url=self._server.url)
            self._available = True
        except Exception as exc:
            print(f"  [memory] Hindsight unavailable ({exc}) — running without persistent memory.")
            self._available = False

    def stop(self) -> None:
        """Shut down the embedded Hindsight server."""
        if self._server is not None:
            try:
                self._server.__exit__(None, None, None)
            except Exception:
                pass

    def retain(self, content: str, context: str = "") -> None:
        """Store a fact or experience in the memory bank."""
        if not self._available or self._client is None:
            return
        try:
            self._client.retain(bank_id=self._bank_id, content=content, context=context)
        except Exception:
            pass

    def recall(self, query: str) -> str:
        """Retrieve memories relevant to the query. Returns empty string if unavailable."""
        if not self._available or self._client is None:
            return ""
        try:
            result = self._client.recall(bank_id=self._bank_id, query=query)
            if isinstance(result, list):
                return "\n".join(str(r) for r in result)
            return str(result) if result else ""
        except Exception:
            return ""

    def reflect(self, query: str) -> str:
        """Reflect on memories to generate insights. Returns empty string if unavailable."""
        if not self._available or self._client is None:
            return ""
        try:
            result = self._client.reflect(bank_id=self._bank_id, query=query)
            return str(result) if result else ""
        except Exception:
            return ""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_memory.py -v
```

Expected: All three tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/memory.py tests/test_memory.py
git commit -m "feat: add Hindsight memory wrapper (src/memory.py)"
```

---

## Task 5: Build src/tools/resume_editor.py

**Files:**
- Create: `src/tools/__init__.py`
- Create: `src/tools/resume_editor.py`
- Create: `tests/test_resume_editor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_resume_editor.py`:

```python
import yaml
import pytest


def test_read_resume_section_returns_section(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    read_tool, _ = create_resume_tools(str(resume_path))
    result = read_tool.invoke({"section": "basics"})

    assert "Jane Doe" in result


def test_read_resume_section_rejects_unknown_section(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    read_tool, _ = create_resume_tools(str(resume_path))
    result = read_tool.invoke({"section": "unknown_section"})

    assert "Invalid section" in result


def test_write_resume_section_persists_change(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    read_tool, write_tool = create_resume_tools(str(resume_path))

    new_certs = [{"name": "AWS Solutions Architect", "issuer": "Amazon Web Services"}]
    write_tool.invoke({"section": "certificates", "new_content": yaml.dump(new_certs)})

    updated = yaml.safe_load(resume_path.read_text(encoding="utf-8"))
    assert updated["certificates"][0]["name"] == "AWS Solutions Architect"


def test_write_resume_section_rejects_unknown_section(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    _, write_tool = create_resume_tools(str(resume_path))
    result = write_tool.invoke({"section": "nonexistent", "new_content": "{}"})

    assert "Invalid section" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_resume_editor.py -v
```

Expected: `ImportError: No module named 'src.tools.resume_editor'`

- [ ] **Step 3: Create src/tools/__init__.py**

Create an empty file:
```python
```

- [ ] **Step 4: Create src/tools/resume_editor.py**

```python
"""
Resume YAML editor tools for the job search agent.

Provides read_resume_section and write_resume_section as LangChain tools
that operate on one section of resume.yaml at a time.

The agent MUST present the proposed change to the user and receive explicit
confirmation before calling write_resume_section.
"""

from __future__ import annotations

import yaml
from langchain_core.tools import tool


VALID_SECTIONS = frozenset({"basics", "work", "education", "skills", "projects", "certificates"})


def create_resume_tools(resume_path: str):
    """Return (read_resume_section, write_resume_section) LangChain tools bound to resume_path."""

    @tool
    def read_resume_section(section: str) -> str:
        """Read a single section of the candidate's resume YAML.

        Args:
            section: One of: basics, work, education, skills, projects, certificates.

        Returns:
            The section content as a YAML string, or an error message.
        """
        if section not in VALID_SECTIONS:
            return f"Invalid section '{section}'. Valid sections: {', '.join(sorted(VALID_SECTIONS))}"
        with open(resume_path, encoding="utf-8") as f:
            resume = yaml.safe_load(f)
        content = resume.get(section, [])
        return yaml.dump(content, allow_unicode=True)

    @tool
    def write_resume_section(section: str, new_content: str) -> str:
        """Overwrite a single section of the candidate's resume YAML.

        IMPORTANT: Always show the user the proposed change and get explicit
        confirmation ('yes') before calling this tool.

        Args:
            section: One of: basics, work, education, skills, projects, certificates.
            new_content: The new section content as a YAML string.

        Returns:
            A confirmation message or an error message.
        """
        if section not in VALID_SECTIONS:
            return f"Invalid section '{section}'. Valid sections: {', '.join(sorted(VALID_SECTIONS))}"
        try:
            parsed = yaml.safe_load(new_content)
        except yaml.YAMLError as e:
            return f"Invalid YAML: {e}"

        with open(resume_path, encoding="utf-8") as f:
            resume = yaml.safe_load(f)

        resume[section] = parsed

        with open(resume_path, "w", encoding="utf-8") as f:
            yaml.dump(resume, f, allow_unicode=True, default_flow_style=False)

        return f"resume.yaml updated: '{section}' section replaced successfully."

    return read_resume_section, write_resume_section
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_resume_editor.py -v
```

Expected: All four tests `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/tools/__init__.py src/tools/resume_editor.py tests/test_resume_editor.py
git commit -m "feat: add section-targeted resume editor tools"
```

---

## Task 6: Build src/tools/sheet_log.py

**Files:**
- Create: `src/tools/sheet_log.py`
- Create: `tests/test_sheet_log.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sheet_log.py`:

```python
from unittest.mock import patch, MagicMock
import pytest


def test_log_job_to_sheet_calls_append(sample_config):
    with patch("src.tools.sheet_log.append_job_row") as mock_append:
        from src.tools.sheet_log import create_sheet_log_tool
        log_tool = create_sheet_log_tool(sample_config)
        log_tool.invoke({
            "title": "AI Engineer",
            "company": "Acme Corp",
            "url": "https://example.com/job/1",
            "status": "Seen",
        })

    mock_append.assert_called_once()
    kwargs = mock_append.call_args[1]
    assert kwargs["title"] == "AI Engineer"
    assert kwargs["company"] == "Acme Corp"
    assert kwargs["status"] == "Seen"


def test_log_job_to_sheet_handles_sheet_error(sample_config):
    """Returns an error string instead of raising when the sheet is unavailable."""
    with patch("src.tools.sheet_log.append_job_row", side_effect=Exception("No credentials")):
        from src.tools.sheet_log import create_sheet_log_tool
        log_tool = create_sheet_log_tool(sample_config)
        result = log_tool.invoke({
            "title": "AI Engineer",
            "company": "Acme",
            "url": "https://example.com/job/1",
            "status": "Seen",
        })

    assert "Sheet logging unavailable" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_sheet_log.py -v
```

Expected: `ImportError: No module named 'src.tools.sheet_log'`

- [ ] **Step 3: Create src/tools/sheet_log.py**

```python
"""
Google Sheet logging tool for the job search agent.

Provides a LangChain tool that appends found jobs to the configured sheet.
Fails gracefully if the sheet is not configured.
"""

from __future__ import annotations

from datetime import date

from langchain_core.tools import tool

from src.sheets import append_job_row


def create_sheet_log_tool(config: dict):
    """Return a log_job_to_sheet LangChain tool bound to config."""

    @tool
    def log_job_to_sheet(title: str, company: str, url: str, status: str = "Seen") -> str:
        """Log a found job to the Google Sheet.

        Args:
            title: Job title.
            company: Company name.
            url: Job posting URL.
            status: Row status — 'Seen' when found, 'Generated' after documents are made.

        Returns:
            Confirmation string or error message.
        """
        try:
            append_job_row(
                config=config,
                title=title,
                company=company,
                url=url,
                status=status,
                date_found=date.today().isoformat(),
            )
            return f"Logged '{title}' at {company} to sheet (Status: {status})."
        except Exception as exc:
            return f"Sheet logging unavailable: {exc}"

    return log_job_to_sheet
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_sheet_log.py -v
```

Expected: Both tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/tools/sheet_log.py tests/test_sheet_log.py
git commit -m "feat: add sheet log tool"
```

---

## Task 7: Add agent system prompts to src/prompts.py

**Files:**
- Modify: `src/prompts.py`

- [ ] **Step 1: Append the three agent prompts to src/prompts.py**

Append to the bottom of `src/prompts.py`:

```python
# ---------------------------------------------------------------------------
# Agent system prompts
# ---------------------------------------------------------------------------

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
- search_jobs: Search the web for job listings. Provide a preferences summary as input.
  Always call this after gathering the candidate's role, location, and salary preferences.
- generate_documents: Generate a tailored resume and cover letter for a specific job URL.
  Only call this after the candidate has confirmed which jobs they want.
- read_resume_section: Read one section of the candidate's resume YAML.
- write_resume_section: Update one section of the candidate's resume YAML.
  YOU MUST show the candidate exactly what you are about to write and receive
  explicit confirmation ("yes") before calling this tool. Never write without confirmation.
- log_job_to_sheet: Log a found job to the candidate's Google Sheet.

WORKFLOW:
1. Greet the candidate and ask what roles they are targeting.
2. Ask for location/remote preference, then salary range — one question at a time.
3. Call search_jobs with a preferences summary, then log each found job to the sheet.
4. Present the results as a numbered list. Ask which jobs to generate documents for.
5. Call generate_documents for each confirmed job.
6. Offer to update the resume if the candidate mentions new skills or certifications.

RULES:
- Never generate documents without explicit job selection from the candidate.
- Never write to the resume without showing the change and getting explicit confirmation.
- Keep your context lean: present job summaries (title, company, salary), not full descriptions.
- If the candidate says "exit", "quit", or "bye", wrap up and say goodbye.
"""

SEARCH_SUBAGENT_SYSTEM_PROMPT = """\
You are a job listing search specialist. Your task is to find job listings matching
the candidate's preferences using the Tavily search tool.

INSTRUCTIONS:
1. Make 3-5 targeted Tavily searches using varied queries derived from the preferences.
   - Include the job title, location/remote, and seniority in each query.
   - Try variations: "site:linkedin.com/jobs", "site:greenhouse.io", general queries.
2. Deduplicate results — remove listings with the same company and title.
3. Filter for relevance: only keep listings that match the target role and location.
4. Return EXACTLY the following JSON and nothing else — no markdown, no explanation:

{
  "jobs": [
    {
      "title": "Senior AI Engineer",
      "company": "Acme Corp",
      "url": "https://...",
      "location": "Remote",
      "salary": "$130k-$160k"
    }
  ]
}

Return at most {max_jobs} jobs. If fewer are found, return what you have.
If no jobs are found, return: {"jobs": []}
"""

GENERATION_SUBAGENT_SYSTEM_PROMPT = """\
You are a document generation assistant. Call the available tools to generate a
tailored resume and cover letter for the given job URL, then report the result.
"""
```

- [ ] **Step 2: Verify the file parses without errors**

```bash
uv run python -c "from src.prompts import AGENT_SYSTEM_PROMPT_TEMPLATE, SEARCH_SUBAGENT_SYSTEM_PROMPT, GENERATION_SUBAGENT_SYSTEM_PROMPT; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/prompts.py
git commit -m "feat: add agent, search sub-agent, and generation sub-agent system prompts"
```

---

## Task 8: Build src/tools/search.py

**Files:**
- Create: `src/tools/search.py`
- Create: `tests/test_search_tool.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_search_tool.py`:

```python
from unittest.mock import MagicMock, patch
import json
import pytest


def test_search_tool_returns_job_list(sample_config):
    fake_jobs = {"jobs": [
        {"title": "AI Engineer", "company": "Acme", "url": "https://example.com/1",
         "location": "Remote", "salary": "$130k"},
    ]}
    fake_agent = MagicMock()
    fake_agent.invoke.return_value = {
        "messages": [MagicMock(content=json.dumps(fake_jobs))]
    }

    with patch("src.tools.search.create_deep_agent", return_value=fake_agent):
        from src.tools.search import create_search_tool
        tool = create_search_tool(
            agent_model=MagicMock(),
            tavily_api_key="test-key",
            max_jobs=10,
        )
        result = tool.invoke({"preferences_summary": "AI Engineer, Remote, $130k+"})

    assert "AI Engineer" in result
    assert "Acme" in result


def test_search_tool_handles_agent_error(sample_config):
    fake_agent = MagicMock()
    fake_agent.invoke.side_effect = Exception("Tavily timeout")

    with patch("src.tools.search.create_deep_agent", return_value=fake_agent):
        from src.tools.search import create_search_tool
        tool = create_search_tool(
            agent_model=MagicMock(),
            tavily_api_key="test-key",
            max_jobs=10,
        )
        result = tool.invoke({"preferences_summary": "AI Engineer"})

    assert "Search failed" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_search_tool.py -v
```

Expected: `ImportError: No module named 'src.tools.search'`

- [ ] **Step 3: Create src/tools/search.py**

```python
"""
Tavily-powered job search tool for the job search agent.

Creates a search sub-agent (via Deep Agents) with only the Tavily tool.
The sub-agent makes multiple targeted searches, deduplicates results, and
returns a compact JSON job list. Its context is discarded after each call.
"""

from __future__ import annotations

from langchain_core.tools import tool as lc_tool
from deepagents import create_deep_agent

from src.prompts import SEARCH_SUBAGENT_SYSTEM_PROMPT


def create_search_tool(agent_model, tavily_api_key: str, max_jobs: int = 10):
    """Return a search_jobs LangChain tool that uses a Tavily search sub-agent.

    Args:
        agent_model: A LangChain chat model instance for the sub-agent.
        tavily_api_key: Tavily API key.
        max_jobs: Maximum number of jobs to return.
    """
    from langchain_community.tools.tavily_search import TavilySearchResults

    tavily = TavilySearchResults(max_results=30, tavily_api_key=tavily_api_key)

    system_prompt = SEARCH_SUBAGENT_SYSTEM_PROMPT.replace("{max_jobs}", str(max_jobs))

    @lc_tool
    def search_jobs(preferences_summary: str) -> str:
        """Search the web for job listings matching the candidate's preferences.

        Args:
            preferences_summary: A summary of the candidate's target roles, location,
                salary range, and key skills.

        Returns:
            A JSON string with a 'jobs' list. Each job has: title, company, url,
            location, salary.
        """
        try:
            sub_agent = create_deep_agent(
                model=agent_model,
                tools=[tavily],
                system_prompt=system_prompt,
            )
            result = sub_agent.invoke({
                "messages": [{"role": "user", "content": preferences_summary}]
            })
            return result["messages"][-1].content
        except Exception as exc:
            return f"Search failed: {exc}"

    return search_jobs
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_search_tool.py -v
```

Expected: Both tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/tools/search.py tests/test_search_tool.py
git commit -m "feat: add Tavily search sub-agent tool"
```

---

## Task 9: Build src/tools/generate.py

**Files:**
- Create: `src/tools/generate.py`
- Create: `tests/test_generate_tool.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_generate_tool.py`:

```python
from unittest.mock import MagicMock, patch
import pytest


def test_generate_documents_returns_summary(sample_config, sample_resume):
    fake_resume_json = MagicMock()
    fake_resume_json.priority = 2
    fake_resume_json.priority_reasoning = "Strong match."

    with patch("src.tools.generate.process_job",
               return_value=("output/Acme_AI_Engineer_2026-03-27", {}, fake_resume_json)):
        from src.tools.generate import create_generate_tool
        gen_tool = create_generate_tool(
            config=sample_config,
            resume=sample_resume,
            provider=MagicMock(),
            models=["model"],
            parser_models=["model"],
        )
        result = gen_tool.invoke({
            "url": "https://example.com/job/1",
            "job_title": "AI Engineer",
            "company": "Acme Corp",
        })

    assert "Acme Corp" in result
    assert "Priority: 2/10" in result


def test_generate_documents_handles_pipeline_error(sample_config, sample_resume):
    with patch("src.tools.generate.process_job",
               side_effect=Exception("Scrape failed")):
        from src.tools.generate import create_generate_tool
        gen_tool = create_generate_tool(
            config=sample_config,
            resume=sample_resume,
            provider=MagicMock(),
            models=["model"],
            parser_models=["model"],
        )
        result = gen_tool.invoke({
            "url": "https://example.com/job/1",
            "job_title": "AI Engineer",
            "company": "Acme Corp",
        })

    assert "Failed" in result
    assert "Acme Corp" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_generate_tool.py -v
```

Expected: `ImportError: No module named 'src.tools.generate'`

- [ ] **Step 3: Create src/tools/generate.py**

```python
"""
Document generation tool for the job search agent.

Wraps the existing process_job pipeline. The tool boundary provides the
context isolation — the main agent only sees the short return string, never
the full resume YAML or job description.
"""

from __future__ import annotations

from langchain_core.tools import tool as lc_tool

from src.pipeline import process_job
from src.providers import LLMProvider


def create_generate_tool(
    config: dict,
    resume: dict,
    provider: LLMProvider,
    models: list[str],
    parser_models: list[str],
):
    """Return a generate_documents LangChain tool bound to the current session's pipeline."""

    @lc_tool
    def generate_documents(url: str, job_title: str, company: str) -> str:
        """Generate a tailored resume and cover letter for a specific job posting.

        Args:
            url: The job posting URL.
            job_title: Job title (used for file naming and context).
            company: Company name (used for file naming and context).

        Returns:
            A short summary of what was generated, including priority score.
        """
        job = {
            "url": url,
            "job_title": job_title,
            "company": company,
            "status": "",
            "details": "",
            "row": None,
        }
        try:
            folder, _, resume_json = process_job(
                job, config, resume, provider, models, parser_models
            )
            priority_msg = ""
            if resume_json is not None:
                priority_msg = (
                    f" Priority: {resume_json.priority}/10 "
                    f"— {resume_json.priority_reasoning}"
                )
            return (
                f"Generated documents for {company} ({job_title}). "
                f"Saved to {folder}.{priority_msg}"
            )
        except Exception as exc:
            return f"Failed to generate documents for {company} ({job_title}): {exc}"

    return generate_documents
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_generate_tool.py -v
```

Expected: Both tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/tools/generate.py tests/test_generate_tool.py
git commit -m "feat: add document generation tool wrapping existing pipeline"
```

---

## Task 10: Build src/agent.py — main orchestrator

**Files:**
- Create: `src/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_agent.py`:

```python
from unittest.mock import MagicMock, patch
import pytest


def test_build_agent_returns_compiled_graph(sample_config, sample_resume):
    """build_agent returns a LangGraph-compiled graph without making any API calls."""
    fake_graph = MagicMock()

    with patch("src.agent.create_deep_agent", return_value=fake_graph), \
         patch("src.agent.init_chat_model", return_value=MagicMock()):
        from src.agent import build_agent
        agent = build_agent(
            config=sample_config,
            resume=sample_resume,
            provider_name="anthropic",
            recalled_memories="No prior sessions.",
        )

    assert agent is fake_graph


def test_build_agent_system_prompt_includes_candidate_name(sample_config, sample_resume):
    """The system prompt injected into the agent includes the candidate's name."""
    captured_prompt = {}

    def fake_create_deep_agent(model, tools, system_prompt):
        captured_prompt["value"] = system_prompt
        return MagicMock()

    with patch("src.agent.create_deep_agent", side_effect=fake_create_deep_agent), \
         patch("src.agent.init_chat_model", return_value=MagicMock()):
        from src.agent import build_agent
        build_agent(
            config=sample_config,
            resume=sample_resume,
            provider_name="anthropic",
            recalled_memories="",
        )

    assert "Jane Doe" in captured_prompt["value"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_agent.py -v
```

Expected: `ImportError: No module named 'src.agent'`

- [ ] **Step 3: Create src/agent.py**

```python
"""
Main job search agent — orchestrator entry point.

Initialises Hindsight memory, builds the Deep Agents orchestrator with all
tools, and runs the streaming chat loop.
"""

from __future__ import annotations

import os
import uuid

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from src.memory import MemoryManager
from src.prompts import AGENT_SYSTEM_PROMPT_TEMPLATE
from src.providers import resolve_models, get_provider


# Map provider_name → LangChain init_chat_model prefix
_LANGCHAIN_PREFIX: dict[str, str] = {
    "openai":    "openai",
    "anthropic": "anthropic",
    "gemini":    "google-genai",
    "local":     "ollama",
    "cloud":     "ollama",
}


def _langchain_model_string(provider_name: str, config: dict) -> str:
    """Return the init_chat_model string for the primary model of this provider."""
    prefix = _LANGCHAIN_PREFIX.get(provider_name, "ollama")
    models, _ = resolve_models(provider_name, config["llm"])
    return f"{prefix}:{models[0]}"


def build_agent(config: dict, resume: dict, provider_name: str, recalled_memories: str):
    """Construct and return the compiled Deep Agents orchestrator graph.

    Separated from run_agent_chat so it can be tested without starting a chat loop.
    """
    from src.tools.search import create_search_tool
    from src.tools.generate import create_generate_tool
    from src.tools.resume_editor import create_resume_tools
    from src.tools.sheet_log import create_sheet_log_tool

    model_str = _langchain_model_string(provider_name, config)
    agent_model = init_chat_model(model_str)

    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    max_jobs = config.get("agent", {}).get("max_jobs", 10)

    models, parser_models = resolve_models(provider_name, config["llm"])
    provider = get_provider(provider_name, config["llm"])

    search_tool = create_search_tool(agent_model, tavily_api_key, max_jobs)
    generate_tool = create_generate_tool(config, resume, provider, models, parser_models)
    read_resume, write_resume = create_resume_tools(config["paths"]["resume_yaml"])
    sheet_log_tool = create_sheet_log_tool(config)

    system_prompt = AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        candidate_name=resume["basics"]["name"],
        candidate_location=resume["basics"].get("location", "Not specified"),
        recalled_memories=recalled_memories or "No previous sessions found.",
    )

    return create_deep_agent(
        model=agent_model,
        tools=[search_tool, generate_tool, read_resume, write_resume, sheet_log_tool],
        system_prompt=system_prompt,
    )


def run_agent_chat(config: dict, resume: dict, provider_name: str) -> None:
    """Start the interactive streaming chat loop.

    Initialises Hindsight memory, builds the agent, then enters a
    read-print-read loop until the user exits.
    """
    memory = MemoryManager(config=config, resume=resume, provider_name=provider_name)
    memory.start()

    recalled_prefs = memory.recall("What are this user's job search preferences?")
    recalled_jobs = memory.recall("What jobs has this user already been shown?")
    recalled_memories = "\n".join(filter(None, [recalled_prefs, recalled_jobs]))

    agent = build_agent(config, resume, provider_name, recalled_memories)
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    print(f"\nJob Search Agent ready. Type 'exit' to quit.\n")

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
                # Persist what the agent just learned
                memory.retain(
                    f"User said: {user_input}\nAgent responded: {response_text[:300]}",
                    context="conversation",
                )
            except Exception as exc:
                print(f"\n[Agent error: {exc}]")
    finally:
        memory.stop()
```

- [ ] **Step 4: Run smoke tests to verify they pass**

```bash
uv run pytest tests/test_agent.py -v
```

Expected: Both tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/agent.py tests/test_agent.py
git commit -m "feat: add main orchestrator agent (src/agent.py)"
```

---

## Task 11: Wire CLI in main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update the run command in main.py**

Replace the `run_jobs` function signature and initial flag block. The retired flags (`--row`, `--all`, `--force`) are replaced with a clear error. The default path (no `--url`) routes to the agent.

Find the `@cli.command("run")` block and replace it entirely with:

```python
@cli.command("run")
@click.option("--url", "direct_url", default=None,
              help="Process a single job URL directly (bypasses agent).")
@click.option("--resume-only", is_flag=True, default=False,
              help="Generate only the resume (skip cover letter). URL mode only.")
@click.option("--cover-only", is_flag=True, default=False,
              help="Generate only the cover letter (skip resume). URL mode only.")
@click.option("--provider", "provider_name", default=None,
              type=click.Choice(["local", "cloud", "openai", "anthropic", "gemini"]),
              help="LLM provider. Omit for local Ollama (default).")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
@click.option("--debug", is_flag=True, default=False,
              help="Log scraped content and LLM outputs to debug.db.")
@click.option("--row", "row_num", type=int, default=None, hidden=True)
@click.option("--all", "run_all", is_flag=True, default=False, hidden=True)
@click.option("--force", is_flag=True, default=False, hidden=True)
def run_jobs(direct_url, resume_only, cover_only, provider_name, config_path, debug,
             row_num, run_all, force):
    """Search for jobs with the agent, or process a single URL with --url."""
    if row_num is not None or run_all or force:
        raise click.UsageError(
            "--row, --all, and --force are no longer supported.\n"
            "Run without --url to use the new agent-driven search mode.\n"
            "The Google Sheet is now an output log — the agent writes to it automatically."
        )

    if resume_only and cover_only:
        raise click.UsageError("Cannot use --resume-only and --cover-only together.")

    config  = load_config(config_path)
    resume  = load_resume(config["paths"]["resume_yaml"])

    from src.providers import get_provider, resolve_models
    resolved_provider = provider_name or "local"

    # --- Direct URL mode (existing pipeline, unchanged) ---
    if direct_url:
        llm_cfg = config["llm"]
        provider = get_provider(resolved_provider, llm_cfg)
        models, parser_models = resolve_models(resolved_provider, llm_cfg)
        click.echo(f"Provider: {resolved_provider}  |  model: {models[0]}  |  parser: {parser_models[0]}")

        from src.debug import init_db, log_run
        if debug:
            init_db()
            click.echo(click.style("  Debug mode enabled — logging to debug.db", fg="cyan"))

        from src.pipeline import process_job
        job = {"url": direct_url, "job_title": "", "status": "", "details": "", "row": None}
        click.echo(f"\nProcessing: {direct_url}")
        debug_run_id = log_run(direct_url, resolved_provider, models[0], parser_models[0]) if debug else None
        folder, _, resume_json = process_job(
            job, config, resume, provider, models, parser_models,
            resume_only=resume_only, cover_only=cover_only,
            debug_run_id=debug_run_id,
        )
        if resume_json is not None:
            click.echo(f"  Priority: {resume_json.priority}/10 — {resume_json.priority_reasoning}")
        click.echo(click.style(f"\n  Saved to: {folder}", fg="green"))
        return

    # --- Agent mode (default) ---
    from src.agent import run_agent_chat
    run_agent_chat(config=config, resume=resume, provider_name=resolved_provider)
```

- [ ] **Step 2: Run all tests to confirm nothing is broken**

```bash
uv run pytest tests/ -v
```

Expected: All tests `PASSED`

- [ ] **Step 3: Smoke test the --url flag still works**

```bash
uv run python main.py run --help
```

Expected: Help text shows `--url`, `--provider`, `--config`, `--debug`, `--resume-only`, `--cover-only`. Does not show `--row`, `--all`, `--force`.

- [ ] **Step 4: Smoke test the retired flags show the right error**

```bash
uv run python main.py run --all 2>&1 | head -5
```

Expected: Output contains `--row, --all, and --force are no longer supported`.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: wire agent mode as default run command; retire sheet-queue flags"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ New dependencies — Task 1
- ✅ `src/pipeline.py` extraction — Task 2
- ✅ `append_job_row` in `src/sheets.py` — Task 3
- ✅ `src/memory.py` Hindsight wrapper — Task 4
- ✅ `src/tools/resume_editor.py` section-targeted editor with confirmation guardrail in prompt — Task 5 + Task 7
- ✅ `src/tools/sheet_log.py` — Task 6
- ✅ Agent system prompts — Task 7
- ✅ `src/tools/search.py` Tavily sub-agent — Task 8
- ✅ `src/tools/generate.py` generation tool — Task 9
- ✅ `src/agent.py` orchestrator + chat loop — Task 10
- ✅ `main.py` CLI wiring, retire `--row`/`--all`/`--force` — Task 11
- ✅ `config.yaml` + `example_config.yaml` `agent:` section — Task 1
- ✅ `.env.example` `TAVILY_API_KEY` — Task 1

**Type consistency across tasks:**
- `MemoryManager(config, resume, provider_name)` defined in Task 4, used in Task 10 ✅
- `create_search_tool(agent_model, tavily_api_key, max_jobs)` defined in Task 8, used in Task 10 ✅
- `create_generate_tool(config, resume, provider, models, parser_models)` defined in Task 9, used in Task 10 ✅
- `create_resume_tools(resume_path)` returns `(read_tool, write_tool)` defined in Task 5, used in Task 10 ✅
- `create_sheet_log_tool(config)` defined in Task 6, used in Task 10 ✅
- `append_job_row(config, title, company, url, status, date_found, priority, reasoning)` defined in Task 3, used in Task 6 ✅
- `process_job(job, config, resume, provider, models, parser_models, ...)` defined in Task 2, used in Task 9 ✅
- `build_agent(config, resume, provider_name, recalled_memories)` defined in Task 10, tested in `tests/test_agent.py` ✅
- `run_agent_chat(config, resume, provider_name)` defined in Task 10, called in Task 11 ✅
