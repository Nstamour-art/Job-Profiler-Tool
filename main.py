"""
Job Profiler Tool — CLI entry point.

Usage:
  uv run python main.py list                     # list all jobs from Google Sheet
  uv run python main.py run --row 2              # process row 2
  uv run python main.py run --all                # process all rows with no status
  uv run python main.py run --url <linkedin_url> # ad-hoc, skip sheet
"""

from __future__ import annotations

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
@click.option("--provider", "provider_name", default=None, show_default=True,
              type=click.Choice(["local", "cloud", "openai", "anthropic", "gemini"]),
              help="LLM provider. Omit for local Ollama (default).")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
@click.option("--debug", is_flag=True, default=False,
              help="Log scraped content and LLM outputs to debug.db (SQLite).")
def run_jobs(row_num, run_all, direct_url, resume_only, cover_only, force, provider_name, config_path, debug):
    """Scrape, tailor, and generate resume + cover letter documents."""
    if resume_only and cover_only:
        raise click.UsageError("Cannot use --resume-only and --cover-only together.")

    config  = load_config(config_path)
    resume  = load_resume(config["paths"]["resume_yaml"])

    from src.providers import get_provider, resolve_models
    resolved_provider = provider_name or "local"
    llm_cfg = config["llm"]
    provider = get_provider(resolved_provider, llm_cfg)
    models, parser_models = resolve_models(resolved_provider, llm_cfg)
    click.echo(f"Provider: {resolved_provider}  |  model: {models[0]}  |  parser: {parser_models[0]}")

    from src.debug import init_db, log_run
    from src.pipeline import process_job
    if debug:
        init_db()
        click.echo(click.style("  Debug mode enabled — logging to debug.db", fg="cyan"))

    # --- Ad-hoc URL mode ---
    if direct_url:
        job = {"url": direct_url, "job_title": "", "status": "", "details": "", "row": None}
        click.echo(f"\nProcessing: {direct_url}")
        debug_run_id = log_run(direct_url, resolved_provider, models[0], parser_models[0]) if debug else None
        folder, _, resume_json = process_job(
            job, config, resume, provider, models, parser_models,
            resume_only=resume_only, cover_only=cover_only,
            debug_run_id=debug_run_id,
        )
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
            debug_run_id = log_run(job.get("url", ""), resolved_provider, models[0], parser_models[0]) if debug else None
            folder, job_data, resume_json = process_job(
                job, config, resume, provider, models, parser_models,
                resume_only=resume_only, cover_only=cover_only,
                debug_run_id=debug_run_id,
            )
            click.echo(click.style(f"  Saved to: {folder}", fg="green"))

            if resume_json is not None:
                click.echo(f"  Priority: {resume_json.priority}/10 (1=apply now, 10=low priority) — {resume_json.priority_reasoning}")

            # Write details, priority, reasoning, and status back to sheet in one request
            updates = {"status": "Generated"}
            if job_data.get("_scraped_fresh") and job_data.get("description"):
                updates["details"] = job_data["description"]
            if resume_json is not None:
                updates["priority"] = str(resume_json.priority)
                updates["reasoning"] = resume_json.priority_reasoning
            update_row(config, job["row"], **updates)
            click.echo("  Sheet updated.")
        except Exception as e:
            click.echo(click.style(f"  ERROR: {e}", fg="red"), err=True)


if __name__ == "__main__":
    cli()
