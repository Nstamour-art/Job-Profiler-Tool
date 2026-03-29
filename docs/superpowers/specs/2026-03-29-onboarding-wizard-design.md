# Onboarding Wizard — Design Spec
**Date:** 2026-03-29
**Status:** Approved
**Branch:** feature/onboarding-wizard

---

## Overview

The tool currently requires a non-technical user to manually copy and edit three files before anything runs (`.env`, `config.yaml`, `resume.yaml`). This spec covers an interactive first-run wizard that replaces all manual file editing with guided terminal prompts.

When `config.yaml` is missing, the tool runs a full setup sequence automatically — provider selection, API key entry, optional Google Sheets config, resume interview (already built), and template selection (already built) — before offering to start the job search agent. On subsequent runs, the chosen provider is remembered as the default, and any attempt to use an unconfigured provider triggers a targeted setup step instead of a hard error.

---

## Goals

- Zero file editing required on first run
- Chosen provider persists as default for all future commands
- Runtime provider check: graceful wizard instead of cryptic error when a provider isn't set up
- Google Sheets setup included as an optional step, not a separate manual process
- No changes to existing `src/onboarding.py` or `src/template_agent.py` — they plug in as-is

---

## Architecture

### New File: `src/setup_wizard.py`

Owns the technical setup interview: provider selection, API key prompting, `.env` write, `config.yaml` write, and optional Google Sheets config. Has two entry points:

**`run_setup_wizard() -> dict`**
Full first-run setup. Called when `config.yaml` is missing. Returns the completed config dict.

**`ensure_provider_ready(provider_name: str, config: dict) -> None`**
Runtime check. Called before any LLM work on every command. If the requested provider is not ready (missing API key or Ollama unreachable), runs just the provider setup step, updates `.env` and `config.yaml`, and returns. Raises `SystemExit` only if the user declines to set up and the command cannot continue.

### Modified: `main.py`

- On any command, before loading config:
  - If `config.yaml` missing → run full setup sequence (wizard → resume onboarding → template wizard → start prompt)
  - If `config.yaml` exists → load it, use `config["provider"]` as default when no `--provider` flag passed
- Before any LLM call → call `ensure_provider_ready(resolved_provider, config)`
- Provider resolution in every command:
  ```python
  resolved_provider = provider_name or config.get("provider", "local")
  ```

### Modified: `example_config.yaml`

Add `provider` as a top-level key:

```yaml
provider: "local"   # default provider — set by setup wizard, overridden by --provider flag

llm:
  temperature: 0.3
  max_retries: 3
  # ... rest unchanged
```

---

## Full First-Run Sequence

Triggered when `config.yaml` is missing (any command):

```
1. run_setup_wizard()
     ├── Welcome banner
     ├── Provider selection menu (1–5)
     ├── Provider-specific setup (API key or Ollama check)
     ├── Google Sheets setup (optional)
     ├── Write config.yaml
     └── Write .env (if API key entered)

2. run_onboarding(config, provider)         # skipped if resume.yaml already exists
     └── (existing — section-by-section resume interview)

3. run_template_wizard(config, provider)    # skipped if template.yaml already exists
     └── (existing — theme menu + optional customization)

4. "Setup complete! Ready to start the job search agent? (yes / no)"
     └── yes → run_agent_chat(config, resume, provider)
     └── no  → print usage hint and exit
```

---

## `run_setup_wizard()` Flow

### Step 1: Welcome

```
Welcome to Job Profiler Tool!

Let's get you set up. This will take about 2 minutes.
```

### Step 2: Provider Selection

```
Which AI provider would you like to use?

  1. Local Ollama  (free, runs on your machine — requires Ollama installed)
  2. OpenAI        (requires API key)
  3. Anthropic     (requires API key)
  4. Google Gemini (requires API key)
  5. Ollama Cloud  (requires API key)

Enter 1–5:
```

### Step 3: Provider-Specific Setup

**If local (Ollama):**
- HTTP GET `http://localhost:11434/` to check if Ollama is running
- If reachable: confirm model (`llama3.2:latest`), offer to pull it now (`ollama pull llama3.2:latest`)
- If not reachable:
  ```
  Ollama doesn't appear to be running.

  Install it from https://ollama.com, then run this tool again.
  (Or choose a different provider — press Enter to go back)
  ```
  Loop back to provider menu if user presses Enter, otherwise exit.

**If cloud provider (OpenAI / Anthropic / Gemini / Ollama Cloud):**
```
Enter your <Provider> API key:
> _
```
- Validate non-empty
- Written to `.env` as `OPENAI_API_KEY=...` (etc.)
- Not echoed to terminal (use `getpass` or mask input)

### Step 4: Google Sheets (Optional)

```
Do you want to track jobs in a Google Sheet? (yes / no)
```

**If yes:**
```
Enter your Google Sheets spreadsheet ID:
(Find this in your sheet's URL: docs.google.com/spreadsheets/d/<ID>/edit)
> _

Worksheet name (press Enter for "Sheet1"):
> _

Path to your Google service account JSON file:
(Press Enter for default: credentials/google_service_account.json)
> _
```

Written to `config.yaml` under `google_sheets:`. If the user skips, the `google_sheets` section is omitted entirely from `config.yaml`.

### Step 5: Write Files

Writes `config.yaml` from the internal template with:
- `provider: "<chosen>"` at the top level
- Full `llm:` section with all provider subsections (sensible defaults)
- `google_sheets:` section if configured
- `paths:` section with defaults

Writes `.env` if an API key was entered (appends or creates; does not overwrite existing keys for other providers).

---

## `ensure_provider_ready()` Flow

Called before any LLM work. Logic:

```python
def ensure_provider_ready(provider_name: str, config: dict) -> None:
    if provider_name == "local":
        if not _ollama_reachable():
            _guide_ollama_setup()        # print instructions + exit or loop
    else:
        key_var = _API_KEY_VARS[provider_name]
        if not os.environ.get(key_var):
            _prompt_for_api_key(provider_name, key_var, config)  # write to .env + reload
```

`_API_KEY_VARS` maps provider names to their env var names:
```python
_API_KEY_VARS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "cloud": "OLLAMA_API_KEY",
}
```

`_prompt_for_api_key()` shows a short explanation of where to get the key, prompts for it, appends it to `.env`, and calls `load_dotenv()` again to make it available in the current process without requiring a restart.

---

## Provider Default Fix

**Problem:** `template` (and other commands) hardcode `"local"` as the default provider even when the user configured Gemini.

**Fix:** Every command resolves its provider as:
```python
resolved_provider = provider_name or config.get("provider", "local")
```

`config["provider"]` is written by the setup wizard and persists across runs. The `--provider` flag always overrides it.

Affected commands: `template`, `run` (both `--url` and agent mode).

---

## New/Modified Files

| File | Change |
|------|--------|
| `src/setup_wizard.py` | New — full setup wizard and `ensure_provider_ready` |
| `main.py` | Modified — first-run detection, provider default fix, `ensure_provider_ready` calls |
| `example_config.yaml` | Modified — add top-level `provider: "local"` key |

No changes to `src/onboarding.py`, `src/template_agent.py`, `src/providers.py`, or `src/agent.py`.

---

## Out of Scope

- Web UI or GUI — terminal only
- Multi-provider setup in one session (user picks one; can re-run or use `--provider` to switch)
- Google Cloud project creation or service account creation — wizard only collects the JSON path
- Editing an existing `config.yaml` via wizard (use `--provider` flag to switch, or edit manually)
