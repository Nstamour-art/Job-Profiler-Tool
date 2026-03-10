# Job Profiler Tool

Automatically tailors your resume and generates a cover letter for any job posting. Paste a LinkedIn URL, and the tool scrapes the job description, sends it to an LLM alongside your resume data, and outputs a ready-to-send `.docx` resume and cover letter.

---

## How It Works

1. Reads your resume from `resume.yaml`
2. Scrapes the job description from the provided LinkedIn URL
3. Sends both to an Ollama Cloud LLM to generate a tailored resume and cover letter
4. Writes `resume.docx` and `cover_letter.docx` to a dated output folder

Optionally, jobs can be queued in a Google Sheet and processed in batch.

---

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- An [Ollama Cloud](https://ollama.com) account and API key

---

## Required Files

Before running the tool, you need four files in place. Three are gitignored and must be created locally — they are never committed:

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
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Ollama Cloud API key:

```
OLLAMA_API_KEY=your_ollama_api_key_here
```

### 3. Fill out your resume

```bash
cp example_resume.yaml resume.yaml
```

Edit `resume.yaml` with your information. The key sections are:

| Section | Description |
|---|---|
| `basics` | Name, email, phone, location, LinkedIn/GitHub profiles |
| `work` | Employment history — each entry has a `description` (paragraph summary) and `highlights` (bullet points) |
| `education` | Degree, field of study, institution |
| `skills` | Skill categories with keyword lists |
| `projects` | Portfolio projects with highlights and optional URL |
| `certificates` | Certifications with name and issuer |

> **Tip:** Keep `resume.yaml` as a complete master list. The LLM selects, reorders, and rewrites content to best match each specific job posting. The `description` field on each work entry gives the LLM richer context to draw from — write it like a paragraph summary of your role.

### 4. Configure the tool

```bash
cp example_config.yaml config.yaml
```

Edit `config.yaml` to set your Ollama model, host, and paths:

```yaml
ollama:
  host: "https://ollama.com"
  model: "gpt-oss:120b"   # any model available on your Ollama account
  temperature: 0.3

paths:
  resume_yaml: "resume.yaml"
  output_dir: "output"
  credentials: "credentials/google_service_account.json"
```

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
```

After each successful run, the row's Status is automatically set to **Generated**. Any row with a non-blank status is skipped — clear it in the sheet to reprocess.

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
```

Your sheet should have columns: **Job Title**, **URL**, **Status**, **Details**.

---

## Output

Each run creates a timestamped folder under `output/`:

```
output/
  CompanyName_RoleTitle_2025-01-15/
    resume.docx
    cover_letter.docx
```
