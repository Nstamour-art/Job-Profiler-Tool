<div align="center">

# ◆ Job Profiler Tool

**AI-powered job search agent with a rich terminal UI**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge)](LICENSE)
[![uv](https://img.shields.io/badge/uv-package%20manager-7c3aed?style=for-the-badge)](https://docs.astral.sh/uv/)

> Search jobs · Scrape postings · Tailor your resume & cover letter · All in one session

</div>

---

### Supported Providers

| Provider | Flag | Model examples |
|:--------:|:----:|:---------------|
| 🦙 **Ollama** (local) | `--provider local` | `llama3.2` |
| ☁️ **Ollama Cloud** | `--provider cloud` | `llama3.2` |
| 🧠 **OpenAI** | `--provider openai` | `gpt-4o`, `gpt-4o-mini` |
| 🎭 **Anthropic** | `--provider anthropic` | `claude-opus-4-6`, `claude-sonnet-4-6` |
| 💎 **Google Gemini** | `--provider gemini` | `gemini-2.5-pro`, `gemini-3.0-flash` |

---

## ✨ Features

<table>
<tr>
<td width="50%">

**🤖 Interactive Agent**
- Conversational job search with rich markdown rendering
- Claude Code-style terminal UI with spinners & panels
- Agent greets you on launch — no typing needed

</td>
<td width="50%">

**📄 Document Generation**
- Tailored resume & cover letter per posting
- Four professional DOCX themes
- ATS-friendly formatting

</td>
</tr>
<tr>
<td width="50%">

**🔍 Smart Search**
- Tavily-powered job discovery
- Playwright web scraping for full descriptions
- Priority scoring with reasoning

</td>
<td width="50%">

**🧠 Memory & Logging**
- Encrypted persistent memory across sessions (Fernet AES-128)
- Google Sheets integration for tracking
- Automatic fallback across models

</td>
</tr>
</table>

---

## How It Works

### Agent mode (default)

```
╭───────────────────────────────── ◆  Job Profiler ─────────────────────────────────╮
│                                                                                    │
│  Hello, Jane!                                                                      │
│                                                                                    │
│  I'm your job search assistant. Tell me what kind of roles you're                  │
│  looking for — location, seniority, company, or anything else — and                │
│  I'll search, tailor your resume, and generate a cover letter for each match.      │
│                                                                                    │
│  Type exit to quit at any time.                                                    │
│                                                                                    │
╰────────────────────────────────────────────────────────────────────────────────────╯

You › Find me backend engineering roles in Toronto
⠋ Thinking…
```

Running `uv run python main.py run` starts an interactive session:

1. **🛠 First-run setup** — if `config.yaml` doesn't exist yet, a setup wizard walks you through choosing a provider and (optionally) configuring Google Sheets. Everything is written to `config.yaml` and `.env` automatically.
2. **📋 Resume onboarding** — if `resume.yaml` doesn't exist yet, the tool interviews you section by section before starting. Accepts typed answers or pasted content (LinkedIn profile, old resume, bullet lists). Extracts structured data automatically and asks you to confirm each section before saving.
3. **🎨 Template selection** — if `template.yaml` doesn't exist yet, the tool prompts you to pick a resume theme and optionally customize it in natural language.
4. **🔎 Job search loop** — the agent searches for relevant job listings based on your resume, scrapes each posting, and tailors your resume and cover letter to match.
5. **📊 Sheet logging** — each processed job is logged to your Google Sheet with its priority score and reasoning (optional — see [Google Sheets Setup](#google-sheets-setup-optional)).

You can also pass a job URL directly to process a single posting without entering the agent loop:

```bash
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..."
```

This mode requires `resume.yaml` to already exist.

---

## Prerequisites

| Requirement | Details |
|:------------|:--------|
| **Python** | 3.11+ |
| **Package manager** | [uv](https://docs.astral.sh/uv/) |
| **LLM provider** | At least one — see [provider table](#supported-providers) above |
| **Search** | [Tavily](https://tavily.com) API key (free tier, agent mode only) |

<details>
<summary><b>Provider API keys</b></summary>

| Provider | Key variable |
|:---------|:-------------|
| Ollama (local) | _none needed_ |
| Ollama Cloud | `OLLAMA_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` |

</details>

---

## 🚀 Getting Started

### 1. Install uv

If you don't have `uv` installed:

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal after installing.

### 2. Clone and install dependencies

```bash
git clone https://github.com/nstamour-art/Job-Profiler-Tool.git
cd Job-Profiler-Tool
uv sync
uv run playwright install chromium
```

### 3. Add your API keys

```bash
cp .env.example .env
```

Edit `.env` and add the key(s) you need:

```env
OLLAMA_API_KEY=your_key_here      # --provider cloud
OPENAI_API_KEY=your_key_here      # --provider openai
ANTHROPIC_API_KEY=your_key_here   # --provider anthropic
GEMINI_API_KEY=your_key_here      # --provider gemini
TAVILY_API_KEY=your_key_here      # required for agent mode
```

No key is needed for `--provider local` (the default).

### 4. Run

```bash
uv run python main.py run
```

If `config.yaml` doesn't exist yet, the setup wizard runs automatically — it will ask you to choose a provider, optionally configure Google Sheets, and write everything to `config.yaml`. From there, resume onboarding and template selection follow in the same session.

To configure manually instead, copy the examples:

```bash
cp example_config.yaml config.yaml
cp example_resume.yaml resume.yaml   # optional — wizard can build this interactively
```

---

## ⚙️ Configuration

`config.yaml` controls model selection, paths, and agent behaviour. Each provider has its own subsection for `model` and `parser_model`:

```yaml
llm:
  temperature: 0.3
  max_retries: 3         # retries per model if JSON parsing fails after repair

  # Default models for --provider local (no flag)
  model: "llama3.2:latest"
  parser_model: "llama3.2:latest"

  # Per-provider overrides — used when --provider <name> is passed.
  # fallback_models: tried in order if the primary model returns a rate/capacity error (503, 429).
  # parser_fallback_models: same, but for the lightweight parsing step.
  openai:
    model: "gpt-4o"
    fallback_models:
      - "gpt-4o-mini"
    parser_model: "gpt-4o-mini"
    parser_fallback_models: []

  anthropic:
    model: "claude-sonnet-4-6"
    fallback_models:
      - "claude-opus-4-6" 
      - "claude-haiku-4-5-20251001"
    parser_model: "claude-haiku-4-5-20251001"
    parser_fallback_models: []

  gemini:
    model: "gemini-2.5-pro"
    fallback_models:
      - "gemini-3.0-flash"
      - "gemini-3.0-flash-lite"
    parser_model: "gemini-3.0-flash"
    parser_fallback_models:
      - "gemini-3.0-flash-lite"

agent:
  max_jobs: 10        # max job listings surfaced per search session
  memory_bank: ""     # defaults to resume basics.name if empty
```

**`parser_model`** is used for the job description parsing step and resume onboarding extraction — a lightweight model keeps these fast and cheap. If omitted, `model` is used for all stages.

**`fallback_models`** / **`parser_fallback_models`** are tried in order when the primary model returns a rate-limit or capacity error (HTTP 503 / 429). If a fallback is available, the tool switches automatically and prints a notice.

**`max_retries`** controls how many times the tool re-calls the same model when the LLM returns unparseable JSON (after automatic repair). Set to `1` to disable retries.

**`agent.max_jobs`** caps how many job listings the agent surfaces per session.

---

## 🎨 Resume Templates

The tool ships with four named themes. Your choice is saved to `template.yaml` and applied to every document generated after that.

| Theme | Font | Style |
| --- | --- | --- |
| **Classic** | Arial | Black on white, centered name, ruled section borders |
| **Modern** | Calibri | Navy accent, left-aligned name, underlined headings |
| **Creative** | Georgia | Dark sidebar with contact/skills/education, main column for experience |
| **Minimal** | Helvetica Neue | No borders, grey section labels, generous margins |

> **Note:** The Creative theme uses a two-column sidebar layout. Most modern ATS systems handle it fine, but some older ones may misread the columns — the tool prints a warning when you select it.

### Set or change your template

```bash
# Interactive wizard — pick a theme and optionally customize it in natural language
uv run python main.py template

# Use a specific LLM provider for the customization extraction step
uv run python main.py template --provider anthropic
```

The wizard lets you describe customizations in plain language after picking a theme:

```
──────────────────── Template Selection ────────────────────

  1 ─ Classic    Arial, black on white, ruled borders
  2 ─ Modern     Calibri, navy accent, underlined headings
  3 ─ Creative   Georgia serif, dark sidebar layout
  4 ─ Minimal    Helvetica Neue, no borders, grey labels

Enter 1–4 › 2

Anything to customize? (font, size, accent color — Enter for defaults)
› 12pt body text and dark green accent
⠋ Applying customization…
```

Your selection is saved to `template.yaml` (gitignored). You can re-run `template` at any time to switch themes. In agent mode, just tell the agent you want to change your template and it will launch the wizard for you.

---

## 💻 Usage

### Agent mode

```bash
uv run python main.py run
uv run python main.py run --provider anthropic
uv run python main.py run --provider openai
```

Starts an interactive job search session. The agent searches for relevant listings, generates tailored application documents, and logs results. Requires `TAVILY_API_KEY`.

### Direct URL mode

Process a single job posting without entering the agent loop:

```bash
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..."
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..." --provider openai
```

Output files are saved to `output/<Company>_<Role>_<date>/`.

### All flags

| Flag | Description |
| --- | --- |
| `--url <url>` | Process a single job URL directly, no Google Sheet needed |
| `--provider` | LLM backend: `local` (default), `cloud`, `openai`, `anthropic`, `gemini` |
| `--resume-only` | Generate only the resume, skip the cover letter |
| `--cover-only` | Generate only the cover letter, skip the resume |
| `--config` | Path to a custom config file (default: `config.yaml`) |
| `--debug` | Log scraped content and all LLM outputs to `debug.db` (SQLite) |

---

## 📋 Resume Onboarding

When `resume.yaml` doesn't exist, the tool automatically runs a guided interview before starting the job search:

```
╭─────────────────────────── Resume Onboarding ───────────────────────────╮
│                                                                          │
│  Let's start with your basic info. What's your name, email, phone,       │
│  location, and any LinkedIn or GitHub profiles?                          │
│                                                                          │
│  You can type it out or paste from your profile.                         │
│                                                                          │
╰──────────────────────────────────────────────────────────────────────────╯

You › Jane Doe, jane@example.com, Toronto ON, github.com/janedoe
⠋ Parsing your input…

╭──────────────── Extracted ────────────────╮
│  Name:     Jane Doe                       │
│  Email:    jane@example.com               │
│  Location: Toronto, ON                    │
│  GitHub:   github.com/janedoe             │
╰───────────────────────────────────────────╯

Does this look right? (yes / edit / skip) ›
```

- **yes** — section saved, move to next
- **edit** — type a correction; the tool re-extracts with your original input and the correction combined
- **skip** — section left empty, move to next

Sections covered: basics, work history, education, skills, projects, certificates.

After all sections are confirmed, `resume.yaml` is written and the job search loop starts immediately in the same session.

> **Tip:** You can paste a full LinkedIn About section, resume PDF copy-paste, or bullet list — the tool extracts structured data from any format.

---

## 📊 Google Sheets Setup (Optional)

Only needed if you want the agent to log processed jobs to a spreadsheet.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Sheets API** and **Google Drive API**.
3. Create a **Service Account** and download the JSON key file.
4. Create a `credentials/` directory in the project root and place the key file there as `google_service_account.json`.
5. Share your Google Sheet with the service account's email address (give it Editor access).
6. In `config.yaml`, set your spreadsheet ID and worksheet name:

```yaml
google_sheets:
  spreadsheet_id: "your_spreadsheet_id_here"
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

Your sheet should have columns matching the names configured above. After each job is processed, the agent writes:

| Column | Value |
| --- | --- |
| **Status** | `Generated` |
| **Details** | Scraped job description |
| **Priority** | 1–10 score (1 = apply immediately, 10 = low priority) |
| **Reasoning** | One-sentence explanation of the priority score |

The setup wizard can configure this for you interactively when you first run the tool.

---

## 🧠 Persistent Memory

The agent automatically remembers facts across sessions — jobs you've seen, preferences you've expressed, search strategies that worked.

No setup required. Memory starts working on first run.

### How it works

- **Storage:** `~/.job-profiler/<your-name>.enc` — one encrypted file per user, outside the repo so it is never committed.
- **Encryption:** [Fernet](https://cryptography.io/en/latest/fernet/) (AES-128-CBC + HMAC-SHA256). The key lives at `~/.job-profiler/.key` with permissions `0o600` (owner read/write only).
- **Capacity:** The 30 most recent retained facts are injected into the agent's system prompt at the start of each session.
- **Graceful degradation:** If the key file cannot be created (e.g. read-only filesystem), all memory operations silently no-op — the agent still runs normally.

### Optional: customise the memory bank ID

By default the bank ID is your name from `resume.yaml`. To use a different identifier (e.g. to separate different job search campaigns):

```yaml
agent:
  memory_bank: "my-2026-search"   # any string — defaults to resume basics.name
```

---

## 📁 Output

Each run creates a timestamped folder under `output/`:

```
output/
└── CGI_AI_Engineering_2026-03-10/
    ├── Jane Doe - AI Engineer - Resume.docx
    └── Jane Doe - AI Engineer - Cover Letter.docx
```

---

## ⚠️ Disclaimer

This tool is intended for **personal use only**. The web scraping feature is provided as a convenience for individuals automating their own job search.

- Users are solely responsible for complying with the Terms of Service of any website they scrape, including LinkedIn.
- This tool does not store, transmit, or redistribute any data obtained from third-party websites.
- The author makes no representations about the legality of scraping any particular website in any jurisdiction.

Use at your own discretion.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
<sub>Built with ❤️ and too much coffee</sub>
</div>
