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

from src.scraper import scrape_job, ScraperError
from src.llm import parse_job_description, generate_resume, generate_cover_letter
from src.document import build_resume, build_cover_letter
from src.debug import log_scraped, log_job_details, log_resume, log_cover_letter, log_output_folder

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
