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
import yaml as _yaml

from src import ui
from src.scraper import scrape_job, ScraperError
from src.llm import parse_job_description, generate_resume, generate_cover_letter
from src.document import build_resume, build_cover_letter
from src.debug import log_scraped, log_job_details, log_resume, log_cover_letter, log_output_folder
from src.themes import ThemeConfig, CLASSIC, PRESETS, merge_overrides, TemplateOverrides

if TYPE_CHECKING:
    from src.models import ResumeJSON, JobDetails, JobOptions, PipelineContext, PipelineResults, ProviderSuite
    from src.providers import BaseProvider


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


def _load_theme(template_path: str) -> ThemeConfig:
    """Load ThemeConfig from template.yaml. Returns CLASSIC if file missing or invalid."""
    try:
        with open(template_path, encoding="utf-8") as f:
            raw = _yaml.safe_load(f) or {}
        theme_name = raw.get("theme", "classic")
        base = PRESETS.get(theme_name, CLASSIC)
        overrides_raw = raw.get("overrides", {})
        if overrides_raw:
            overrides = TemplateOverrides.model_validate(overrides_raw)
            return merge_overrides(base, overrides)
        return base
    except FileNotFoundError:
        return CLASSIC
    except (AttributeError, TypeError, _yaml.YAMLError):
        return CLASSIC


def _get_job_data(job: dict, url: str) -> dict:
    """Scrape or retrieve cached job description."""
    cached_description = job.get("details", "").strip()
    if cached_description:
        ui.print_step("Using cached job description from sheet.")
        job_data = {**job, "description": cached_description}
        scraped_fresh = False
    else:
        ui.print_step(f"Scraping {url} \u2026")
        try:
            scraped = scrape_job(url)
        except ScraperError as e:
            raise click.ClickException(str(e)) from e
        job_data = {**job, **scraped}
        scraped_fresh = True

    job_data["_scraped_fresh"] = scraped_fresh
    return job_data


def _generate_llm_content(
    ctx: "PipelineContext",
    job_details: "JobDetails",
) -> "PipelineResults":
    """Call LLM to generate resume and cover letter content."""
    from src.models import PipelineResults  # pylint: disable=import-outside-toplevel
    resume_json = None
    if not ctx.options.cover_only:
        ui.print_step("Generating tailored resume \u2026")
        resume_json = generate_resume(
            job_details, ctx.resume, ctx.config, ctx.provider_suite.provider, ctx.provider_suite.models
        )

    cover_json = None
    if not ctx.options.resume_only:
        if resume_json is None:
            ui.print_step("Generating resume context for cover letter \u2026")
            resume_json = generate_resume(
                job_details, ctx.resume, ctx.config, ctx.provider_suite.provider, ctx.provider_suite.models
            )
        ui.print_step("Generating cover letter \u2026")
        cover_json = generate_cover_letter(
            job_details, ctx.resume, resume_json, ctx.config,
            ctx.provider_suite.provider, ctx.provider_suite.models
        )
    return PipelineResults(job_details=job_details, resume_json=resume_json, cover_json=cover_json)


def _save_documents(
    ctx: "PipelineContext",
    folder: Path,
    theme: ThemeConfig,
    results: "PipelineResults",
) -> None:
    """Build and save .docx files to the output folder."""
    candidate_name = ctx.resume["basics"]["name"]
    title = results.job_details.title or "Role"
    company = results.job_details.company or "Unknown"
    safe_name = re.sub(r"[^\w\s\-]", "", title).strip()

    if not ctx.options.cover_only and results.resume_json is not None:
        resume_path = str(_unique_path(folder / f"{candidate_name} - {safe_name} - Resume.docx"))
        ui.print_step("Building resume.docx \u2026")
        build_resume(
            resume_json=results.resume_json,
            personal=ctx.resume["basics"],
            education=ctx.resume.get("education", []),
            output_path=resume_path,
            theme=theme,
        )

    if not ctx.options.resume_only and results.cover_json is not None:
        cover_path = str(
            _unique_path(folder / f"{candidate_name} - {safe_name} - Cover Letter.docx")
        )
        ui.print_step("Building cover_letter.docx \u2026")
        build_cover_letter(
            cover_json=results.cover_json,
            personal=ctx.resume["basics"],
            company=company,
            _job_title=title,
            output_path=cover_path,
            theme=theme,
        )


def _create_output_folder(
    config: dict,
    job: dict,
    job_details: "JobDetails",
) -> tuple[Path, ThemeConfig, str, str]:
    """Create and return the output folder, theme, company, and title."""
    template_path = config.get("paths", {}).get("template_yaml", "template.yaml")
    theme = _load_theme(template_path)

    company = job_details.company or job.get("company") or job.get("job_title", "Unknown")
    title   = job_details.title   or job.get("title")   or job.get("job_title", "Role")

    folder = (
        Path(config["paths"]["output_dir"])
        / f"{_safe_name(company)}_{_safe_name(title)}_{date.today().isoformat()}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder, theme, company, title


def process_job(
    job: dict,
    config: dict,
    resume: dict,
    provider_suite: "ProviderSuite",
    options: "JobOptions | None" = None,
) -> tuple[str, dict, "ResumeJSON | None"]:
    """
    Full pipeline for one job:
      scrape (or use cached details) → parse → LLM resume → LLM cover letter → write docx
    Returns (output_directory_path, job_data, resume_json).
    """
    from src.models import PipelineContext, JobOptions  # pylint: disable=import-outside-toplevel
    options = options or JobOptions()
    ctx = PipelineContext(
        config=config,
        resume=resume,
        provider_suite=provider_suite,
        options=options
    )

    url = job.get("url", "")
    if not url:
        raise ValueError("Job has no URL.")

    job_data = _get_job_data(job, url)
    if options.debug_run_id is not None:
        log_scraped(options.debug_run_id, job_data.get("description", ""))

    ui.print_step("Parsing job description \u2026")
    job_details = parse_job_description(
        job_data, config, provider_suite.provider, provider_suite.parser_models
    )
    if options.debug_run_id is not None:
        log_job_details(options.debug_run_id, job_details)

    results = _generate_llm_content(ctx, job_details)
    if options.debug_run_id is not None:
        if results.resume_json is not None:
            log_resume(options.debug_run_id, results.resume_json)
        if results.cover_json is not None:
            log_cover_letter(options.debug_run_id, results.cover_json)

    folder, theme, _, _ = _create_output_folder(config, job, job_details)

    if options.debug_run_id is not None:
        log_output_folder(options.debug_run_id, str(folder))

    _save_documents(ctx, folder, theme, results)

    return str(folder), job_data, results.resume_json
