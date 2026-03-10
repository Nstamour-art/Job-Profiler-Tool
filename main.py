"""
Job Profiler Tool — CLI entry point.

Usage:
  uv run python main.py list                     # list all jobs from Google Sheet
  uv run python main.py run --row 2              # process row 2
  uv run python main.py run --all                # process all rows with no status
  uv run python main.py run --url <linkedin_url> # ad-hoc, skip sheet
"""

import os
import re
import sys
from datetime import date
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Config / resume loaders
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_resume(resume_path: str) -> dict:
    with open(resume_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    return re.sub(r"[^\w\-]", "_", text).strip("_")[:40]


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def process_job(job: dict, config: dict, resume: dict,
                resume_only: bool = False, cover_only: bool = False) -> tuple[str, dict]:
    """
    Full pipeline for one job:
      scrape (or use cached details) → LLM resume → LLM cover letter → write docx files
    Returns (output_directory_path, job_data) where job_data contains description,
    company, title, and _scraped_fresh (True if we just scraped, False if details were cached).
    """
    from src.scraper import scrape_job, ScraperError
    from src.llm import generate_resume, generate_cover_letter
    from src.document import build_resume, build_cover_letter

    url = job.get("url", "")
    if not url:
        raise ValueError("Job has no URL.")

    # 1. Use cached description from Details column if available, otherwise scrape
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
    company = job_data.get("company") or job.get("job_title", "Unknown")
    title   = job_data.get("title") or job.get("job_title", "Role")

    # 2. LLM — resume (needed for cover letter context too)
    resume_json = None
    if not cover_only:
        click.echo("  Generating tailored resume …")
        resume_json = generate_resume(job_data, resume, config)

    # 3. LLM — cover letter
    cover_json = None
    if not resume_only:
        if resume_json is None:
            click.echo("  Generating resume context for cover letter …")
            resume_json = generate_resume(job_data, resume, config)
        click.echo("  Generating cover letter …")
        cover_json = generate_cover_letter(job_data, resume, resume_json, config)

    # 4. Build output directory
    today_str = date.today().isoformat()
    folder = Path(config["paths"]["output_dir"]) / f"{_safe_name(company)}_{_safe_name(title)}_{today_str}"
    folder.mkdir(parents=True, exist_ok=True)

    candidate_name = resume["basics"]["name"]

    # 5. Build documents
    if not cover_only:
        resume_path = str(_unique_path(folder / f"{candidate_name} - {title} - Resume.docx"))
        click.echo("  Building resume.docx …")
        build_resume(
            resume_json=resume_json,
            personal=resume["basics"],
            education=resume.get("education", []),
            output_path=resume_path,
        )

    if not resume_only:
        cover_path = str(_unique_path(folder / f"{candidate_name} - {title} - Cover Letter.docx"))
        click.echo("  Building cover_letter.docx …")
        build_cover_letter(
            cover_json=cover_json,
            personal=resume["basics"],
            company=company,
            job_title=title,
            output_path=cover_path,
        )

    return str(folder), job_data, resume_json


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Job Profiler Tool — auto-tailor resumes and cover letters."""


@cli.command("list")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
def list_jobs(config_path):
    """List all jobs from the Google Sheet."""
    from src.sheets import get_jobs
    config = load_config(config_path)
    try:
        jobs = get_jobs(config)
    except Exception as e:
        raise click.ClickException(f"Could not read Google Sheet: {e}")

    if not jobs:
        click.echo("No jobs found in the sheet.")
        return

    click.echo(f"\n{'Row':<5} {'Status':<12} {'Job Title':<30} {'URL'}")
    click.echo("-" * 80)
    for j in jobs:
        click.echo(f"{j['row']:<5} {j['status']:<12} {j['job_title'][:28]:<30} {j['url'][:50]}")


@cli.command("run")
@click.option("--row", "row_num", type=int, default=None,
              help="Process a specific sheet row number.")
@click.option("--all", "run_all", is_flag=True, default=False,
              help="Process all rows where Status is blank.")
@click.option("--url", "direct_url", default=None,
              help="Process a single LinkedIn URL directly (skips sheet).")
@click.option("--resume-only", is_flag=True, default=False,
              help="Generate only the resume (skip cover letter).")
@click.option("--cover-only", is_flag=True, default=False,
              help="Generate only the cover letter (skip resume).")
@click.option("--force", is_flag=True, default=False,
              help="Reprocess rows even if Status is already set.")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
def run_jobs(row_num, run_all, direct_url, resume_only, cover_only, force, config_path):
    """Scrape, tailor, and generate resume + cover letter documents."""
    if resume_only and cover_only:
        raise click.UsageError("Cannot use --resume-only and --cover-only together.")

    config  = load_config(config_path)
    resume  = load_resume(config["paths"]["resume_yaml"])

    # --- Ad-hoc URL mode ---
    if direct_url:
        job = {"url": direct_url, "job_title": "", "status": "", "details": "", "row": None}
        click.echo(f"\nProcessing: {direct_url}")
        folder, _, resume_json = process_job(job, config, resume, resume_only=resume_only, cover_only=cover_only)
        if resume_json is not None:
            click.echo(f"  Priority: {resume_json.priority}/10 (1=apply now, 10=low priority) — {resume_json.priority_reasoning}")
        click.echo(click.style(f"\n  Saved to: {folder}", fg="green"))
        return

    # --- Sheet modes ---
    from src.sheets import get_jobs, update_row
    try:
        all_jobs = get_jobs(config)
    except Exception as e:
        raise click.ClickException(f"Could not read Google Sheet: {e}")

    if row_num is not None:
        jobs_to_run = [j for j in all_jobs if j["row"] == row_num]
        if not jobs_to_run:
            raise click.ClickException(f"Row {row_num} not found in sheet.")
        if jobs_to_run[0]["status"].strip() and not force:
            click.echo(click.style(
                f"  Row {row_num} already has status '{jobs_to_run[0]['status']}'. "
                "Use --force to reprocess.", fg="yellow"
            ))
            return
    elif run_all:
        jobs_to_run = [j for j in all_jobs if not j["status"].strip() or force]
    else:
        raise click.UsageError("Provide --row N, --all, or --url <url>.")

    if not jobs_to_run:
        click.echo("No matching jobs to process.")
        return

    for job in jobs_to_run:
        label = job.get("job_title") or job.get("url", "")
        click.echo(f"\nProcessing row {job['row']}: {label}")
        try:
            folder, job_data, resume_json = process_job(job, config, resume, resume_only=resume_only, cover_only=cover_only)
            click.echo(click.style(f"  Saved to: {folder}", fg="green"))

            if resume_json is not None:
                click.echo(f"  Priority: {resume_json.priority}/10 (1=apply now, 10=low priority) — {resume_json.priority_reasoning}")

            # Write details, priority, reasoning, and status back to sheet in one request
            updates = {"status": "Generated"}
            if job_data.get("_scraped_fresh") and job_data.get("description"):
                updates["details"] = job_data["description"]
            if resume_json is not None:
                updates["priority"] = resume_json.priority
                updates["reasoning"] = resume_json.priority_reasoning
            update_row(config, job["row"], **updates)
            click.echo("  Sheet updated.")
        except Exception as e:
            click.echo(click.style(f"  ERROR: {e}", fg="red"), err=True)


if __name__ == "__main__":
    cli()
