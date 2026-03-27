# Job Profiler Tool

Automatically tailors your resume and generates a cover letter for any job posting. Paste a job URL, and the tool scrapes the posting, sends it to an LLM alongside your resume data, and outputs a ready-to-send `.docx` resume and cover letter. LLM responses are validated against strict JSON schemas, with automatic repair and retry logic to handle malformed output.

Supports any major job board or ATS — LinkedIn, Indeed, Glassdoor, Greenhouse, Lever, Workday, and more.

Supports local Ollama, Ollama Cloud, OpenAI, Anthropic, and Google Gemini via a `--provider` flag.

Also supports referencing a Google Sheet via the Google Cloud API for batch processing — see [Google Sheets Setup](#google-sheets-setup-optional).

---

## How It Works

1. Reads your resume from `resume.yaml`
2. Checks the Google Sheet's **Details** column for a cached job description — scrapes the URL only if it is empty
3. Parses the raw page content using a lightweight model (`parser_model`) to extract structured details: company, title, seniority, industry, salary range, required skills, responsibilities, and culture signals
4. Sends the structured job details and resume to the main LLM to generate a tailored resume, cover letter, and priority rating
5. Validates LLM output against strict JSON schemas — automatically repairs malformed JSON and retries the full LLM call if repair fails (configurable via `max_retries` in `config.yaml`)
6. Writes named `.docx` files to a dated output folder
7. Writes the job description, priority score, reasoning, and status back to the sheet in one request

Optionally, jobs can be queued in a Google Sheet and processed in batch.

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

---

## Required Files

Before running the tool, you need four files in place. Three are gitignored and must be created locally:

| File | Source | Purpose |
| --- | --- | --- |
| `.env` | Copy from `.env.example` | API key(s) for your chosen provider |
| `resume.yaml` | Copy from `example_resume.yaml` | Your resume data |
| `config.yaml` | Copy from `example_config.yaml` | Model and path settings |
| `credentials/google_service_account.json` | Google Cloud Console | Google Sheets access (optional) |

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
```

No key is needed for `--provider local` (the default).

### 4. Fill out your resume

```bash
cp example_resume.yaml resume.yaml
```

Edit `resume.yaml` with your information. The key sections are:

| Section | Description |
| --- | --- |
| `basics` | Name, email, phone, location, LinkedIn/GitHub profiles |
| `work` | Employment history — each entry has a `description` (paragraph summary) and `highlights` (bullet points) |
| `education` | Degree, field of study, institution |
| `skills` | Skill categories with keyword lists |
| `projects` | Portfolio projects with highlights and optional URL |
| `certificates` | Certifications with name and issuer |

> **Tip:** Keep `resume.yaml` as a complete master list. The LLM selects, reorders, and rewrites content to best match each specific job posting. The `description` field on each work entry gives the LLM richer context to draw from — write it like a paragraph summary of your role.

### 5. Configure the tool

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
```

**`parser_model`** is used only for the job description parsing step — a lightweight model keeps this fast and cheap. If omitted, `model` is used for both stages.

**`fallback_models`** / **`parser_fallback_models`** are tried in order when the primary model returns a rate-limit or capacity error (HTTP 503 / 429). If a fallback is available, the tool switches automatically and prints a notice. If none are configured and the primary fails, the script exits with an error.

**`max_retries`** controls how many times the tool re-calls the same model when the LLM returns unparseable JSON (after automatic repair). Set to `1` to disable retries.

---

## Usage

### Process a single job URL (no Google Sheet needed)

Works with any major job board or ATS — LinkedIn, Indeed, Glassdoor, Greenhouse, Lever, Workday, and more.

```bash
# Local Ollama (default — no flag needed)
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..."

# Ollama Cloud
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..." --provider cloud

# OpenAI
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..." --provider openai

# Anthropic
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..." --provider anthropic

# Google Gemini
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..." --provider gemini
```

Output files are saved to `output/<Company>_<Role>_<date>/`.

### Use with a Google Sheet (batch mode)

Set up Google Sheets access first (see [Google Sheets Setup](#google-sheets-setup-optional) below), then:

```bash
# List all jobs in the sheet
uv run python main.py list

# Process a specific row
uv run python main.py run --row 2

# Process all rows where Status is blank
uv run python main.py run --all

# Reprocess a row even if it already has a status
uv run python main.py run --row 2 --force
uv run python main.py run --all --force
```

All sheet commands also accept `--provider` to choose the LLM backend.

After each successful run, the tool automatically writes back to the sheet:

| Column | Value |
| --- | --- |
| **Status** | `Generated` |
| **Details** | Scraped job description (cached for future runs — skips re-scraping) |
| **Priority** | 1-10 score (1 = apply immediately, 10 = low priority) |
| **Reasoning** | One-sentence explanation of the priority score |

Any row with a non-blank Status is skipped on future runs. Use `--force` to reprocess it, or clear the Status cell manually.

### All flags

| Flag | Description |
| --- | --- |
| `--url <url>` | Process a single job URL directly, no Google Sheet needed |
| `--row <n>` | Process a specific row number from the Google Sheet |
| `--all` | Process all rows where Status is blank |
| `--provider` | LLM backend: `local` (default), `cloud`, `openai`, `anthropic`, `gemini` |
| `--resume-only` | Generate only the resume, skip the cover letter |
| `--cover-only` | Generate only the cover letter, skip the resume |
| `--force` | Reprocess rows that already have a Status set |
| `--config` | Path to a custom config file (default: `config.yaml`) |
| `--debug` | Log scraped content and all LLM outputs to `debug.db` (SQLite) |

---

## Google Sheets Setup (Optional)

Only needed if you want to manage job queues via spreadsheet.

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
    url: "URL"
    status: "Status"
    details: "Details"
    priority: "Priority"
    reasoning: "Reasoning"
```

Your sheet should have columns: **Job Title**, **URL**, **Status**, **Details**, **Priority**, **Reasoning**.

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
