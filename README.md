# Job Profiler Tool

Automatically tailors your resume and generates a cover letter for any job posting. Paste a LinkedIn URL, and the tool scrapes the job description, sends it to an LLM alongside your resume data, and outputs a ready-to-send `.docx` resume and cover letter. LLM responses are validated against strict JSON schemas, with automatic repair and retry logic to handle malformed output.

Also supports referencing a Google Sheet via the Google Cloud API — see [Google Sheets Setup](#google-sheets-setup-optional).

---

## How It Works

1. Reads your resume from `resume.yaml`
2. Checks the Google Sheet's **Details** column for a cached job description — scrapes the URL only if it is empty
3. Parses the raw job description using a lightweight model (`parser_model`) to extract structured details: company, title, seniority, industry, required skills, responsibilities, and culture signals
4. Sends the structured job details and resume to the main Ollama Cloud LLM to generate a tailored resume, cover letter, and priority rating
5. Validates LLM output against strict JSON schemas — automatically repairs malformed JSON and retries the full LLM call if repair fails (configurable via `max_retries` in `config.yaml`)
6. Writes named `.docx` files to a dated output folder
7. Writes the job description, priority score, reasoning, and status back to the sheet in one request

Optionally, jobs can be queued in a Google Sheet and processed in batch.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- An [Ollama Cloud](https://ollama.com) account and API key

---

## Required Files

Before running the tool, you need four files in place. Three are gitignored and must be created locally:

| File | Source | Purpose |
| --- | --- | --- |
| `.env` | Copy from `.env.example` | Ollama API key |
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

Edit `.env` and add your Ollama Cloud API key:

```env
OLLAMA_API_KEY=your_ollama_api_key_here
```

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

Edit `config.yaml` to set your Ollama model, host, and paths:

```yaml
ollama:
  host: "https://ollama.com"
  model: "gpt-oss:120b"               # any model on your Ollama account (resume/cover letter generation)
  parser_model: "nemotron-3-nano:30b"  # lightweight model for job description parsing (falls back to model if omitted)
  temperature: 0.3
  max_retries: 3                       # LLM call retries if JSON parsing fails after repair

paths:
  resume_yaml: "resume.yaml"
  output_dir: "output"
  credentials: "credentials/google_service_account.json"
```

`parser_model` is used in a separate pre-processing step to extract structured information (company, title, skills, responsibilities) from the raw scraped job description before passing it to the main model. Using a smaller model here keeps costs and latency low. If omitted, `model` is used for both stages.

`max_retries` controls how many times the tool will re-call the LLM if the response cannot be parsed or repaired. Set to `1` to disable retries.

---

## Usage

### Process a single job URL (no Google Sheet needed)

```bash
uv run python main.py run --url "https://www.linkedin.com/jobs/view/..."
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

After each successful run, the tool automatically writes back to the sheet:

| Column | Value |
| --- | --- |
| **Status** | `Generated` |
| **Details** | Scraped job description (cached for future runs — skips re-scraping) |
| **Priority** | 1-10 score (1 = apply immediately, 10 = low priority) |
| **Reasoning** | One-sentence explanation of the priority score |

Any row with a non-blank Status is skipped on future runs. Use `--force` to reprocess it, or clear the Status cell manually.

### Optional flags

| Flag | Description |
| --- | --- |
| `--resume-only` | Generate only the resume, skip the cover letter |
| `--cover-only` | Generate only the cover letter, skip the resume |
| `--force` | Reprocess rows that already have a Status set |

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
    Nicolas St-Amour - AI Engineering - Resume.docx
    Nicolas St-Amour - AI Engineering - Cover Letter.docx
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
