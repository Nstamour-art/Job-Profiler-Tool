# Job Profiler Tool

An AI-powered job search agent that tailors your resume and cover letter for any job posting. Run once and the agent surfaces relevant listings, generates application documents, and logs results to a Google Sheet — all in one session.

Supports local Ollama, Ollama Cloud, OpenAI, Anthropic, and Google Gemini via a `--provider` flag.

---

## How It Works

### Agent mode (default)

Running `uv run python main.py run` starts an interactive job search session:

1. **Resume onboarding** — if `resume.yaml` doesn't exist yet, the tool interviews you section by section before starting. Accepts typed answers or pasted content (LinkedIn profile, old resume, bullet lists). Extracts structured data automatically and asks you to confirm each section before saving.
2. **Job search loop** — the agent searches for relevant job listings based on your resume, scrapes each posting, and tailors your resume and cover letter to match.
3. **Sheet logging** — each processed job is logged to your Google Sheet with its priority score and reasoning (optional — see [Google Sheets Setup](#google-sheets-setup-optional)).

You can also pass a job URL directly to process a single posting without entering the agent loop:

```bash
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..."
```

This mode requires `resume.yaml` to already exist.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- At least one of the following, depending on your chosen `--provider`:
  - **Local Ollama** (default) — [Ollama](https://ollama.com) installed and running locally, no API key needed
  - **Ollama Cloud** (`--provider cloud`) — an Ollama Cloud account and `OLLAMA_API_KEY`
  - **OpenAI** (`--provider openai`) — an OpenAI account and `OPENAI_API_KEY`
  - **Anthropic** (`--provider anthropic`) — an Anthropic account and `ANTHROPIC_API_KEY`
  - **Google Gemini** (`--provider gemini`) — a Google AI Studio account and `GEMINI_API_KEY`
- **Agent mode only:** a [Tavily](https://tavily.com) account and `TAVILY_API_KEY` (free tier available)

---

## Required Files

Before running the tool, you need two files in place. Both are gitignored and must be created locally:

| File | Source | Purpose |
| --- | --- | --- |
| `.env` | Copy from `.env.example` | API key(s) for your chosen provider |
| `config.yaml` | Copy from `example_config.yaml` | Model and path settings |

`resume.yaml` is created automatically the first time you run `uv run python main.py run` (agent mode). You can also create it manually by copying `example_resume.yaml`.

`credentials/google_service_account.json` is optional — only needed for Google Sheets logging.

---

## Getting Started

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

### 3. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add the API key for your chosen provider:

```env
OLLAMA_API_KEY=your_key_here      # --provider cloud
OPENAI_API_KEY=your_key_here      # --provider openai
ANTHROPIC_API_KEY=your_key_here   # --provider anthropic
GEMINI_API_KEY=your_key_here      # --provider gemini
TAVILY_API_KEY=your_key_here      # required for agent mode
HINDSIGHT_BASE_URL=http://localhost:8888  # optional: Hindsight memory server
```

No key is needed for `--provider local` (the default).

### 4. Configure the tool

```bash
cp example_config.yaml config.yaml
```

Edit `config.yaml` to set your models and paths. Each provider has its own subsection for `model` and `parser_model`:

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
    model: "claude-opus-4-6"
    fallback_models:
      - "claude-sonnet-4-6"
      - "claude-haiku-4-5-20251001"
    parser_model: "claude-haiku-4-5-20251001"
    parser_fallback_models: []

  gemini:
    model: "gemini-2.5-pro-preview-03-25"
    fallback_models:
      - "gemini-2.0-flash"
      - "gemini-2.0-flash-lite"
    parser_model: "gemini-2.0-flash"
    parser_fallback_models:
      - "gemini-2.0-flash-lite"

agent:
  max_jobs: 10        # max job listings surfaced per search session
  memory_bank: ""     # defaults to resume basics.name if empty
  memory_model: ""    # defaults to parser_model for your provider if empty
```

**`parser_model`** is used for the job description parsing step and resume onboarding extraction — a lightweight model keeps these fast and cheap. If omitted, `model` is used for all stages.

**`fallback_models`** / **`parser_fallback_models`** are tried in order when the primary model returns a rate-limit or capacity error (HTTP 503 / 429). If a fallback is available, the tool switches automatically and prints a notice.

**`max_retries`** controls how many times the tool re-calls the same model when the LLM returns unparseable JSON (after automatic repair). Set to `1` to disable retries.

**`agent.max_jobs`** caps how many job listings the agent surfaces per session.

## Resume Templates

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

```text
Choose a resume template:

  1. Classic   — Arial, black on white, centered headings with ruled borders
  2. Modern    — Calibri, navy accent, left-aligned name, underlined headings
  3. Creative  — Georgia serif, dark sidebar layout
  4. Minimal   — Helvetica Neue, no borders, grey section labels, generous margins

Enter 1–4: 2

Anything to customize? (font name, size, accent color — or press Enter for defaults)
> 12pt body text and dark green accent
```

Your selection is saved to `template.yaml` (gitignored). You can re-run `template` at any time to switch themes. In agent mode, just tell the agent you want to change your template and it will launch the wizard for you.

---

## Usage

```bash
# Start an agent job search session (local Ollama)
uv run python main.py run

# Use a different provider
uv run python main.py run --provider anthropic
```

If `resume.yaml` doesn't exist yet, the tool will walk you through building it interactively before starting the search. You can type answers or paste directly from LinkedIn, a PDF copy, or an old resume — the tool extracts the structured data automatically.

---

## Usage

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
| `template` | Interactively choose and customize your resume template |
| `--row <n>` | Process a specific row number from the Google Sheet |
| `--all` | Process all rows where Status is blank |
| `--url <url>` | Process a single job URL directly (skips agent loop) |
| `--provider` | LLM backend: `local` (default), `cloud`, `openai`, `anthropic`, `gemini` |
| `--resume-only` | Generate only the resume, skip the cover letter |
| `--cover-only` | Generate only the cover letter, skip the resume |
| `--config` | Path to a custom config file (default: `config.yaml`) |
| `--debug` | Log scraped content and all LLM outputs to `debug.db` (SQLite) |

---

## Resume Onboarding

When `resume.yaml` doesn't exist, the tool automatically runs a guided interview before starting the job search:

```text
Let's start with your basic info. What's your name, email, phone, location,
and any LinkedIn or GitHub profiles? You can type it out or paste from your profile.
> ...

Here's what I captured for your basic info:

  Name: Jane Doe
  Email: jane@example.com
  ...

Does this look right? (yes / edit / skip)
>
```

- **yes** — section saved, move to next
- **edit** — type a correction; the tool re-extracts with your original input and the correction combined
- **skip** — section left empty, move to next

Sections covered: basics, work history, education, skills, projects, certificates.

After all sections are confirmed, `resume.yaml` is written and the job search loop starts immediately in the same session.

> **Tip:** You can paste a full LinkedIn About section, resume PDF copy-paste, or bullet list — the tool extracts structured data from any format.

---

## Google Sheets Setup (Optional)

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
    job_title: "Job Title"
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
| **Priority** | 1-10 score (1 = apply immediately, 10 = low priority) |
| **Reasoning** | One-sentence explanation of the priority score |

---

## Output

Each run creates a timestamped folder under `output/`. Files are named after the candidate and role:

```text
output/
  CGI_AI_Engineering_2026-03-10/
    John Doe - Some Job Title - Resume.docx
    John Doe - Some Job Title - Cover Letter.docx
```

---

## Disclaimer

This tool is intended for **personal use only**. The web scraping feature is provided as a convenience for individuals automating their own job search.

- Users are solely responsible for complying with the Terms of Service of any website they scrape, including LinkedIn.
- This tool does not store, transmit, or redistribute any data obtained from third-party websites.
- The author makes no representations about the legality of scraping any particular website in any jurisdiction.

Use at your own discretion.

---

## License

MIT — see [LICENSE](LICENSE).
