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
from src.template_agent import run_template_wizard

load_dotenv()


# ---------------------------------------------------------------------------
# Config / resume loaders
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.yaml") -> dict:
    """Load and return config.yaml as a dict."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_resume(resume_path: str) -> dict:
    """Load and return resume.yaml as a dict."""
    with open(resume_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
@click.option("--config", "config_path", default=None,
              help="Path to config.yaml (alternative to passing it to each sub-command).")
@click.pass_context
def cli(ctx, config_path):
    """Job Profiler Tool — auto-tailor resumes and cover letters."""
    if config_path is not None:
        ctx.ensure_object(dict)
        ctx.default_map = ctx.default_map or {}
        for cmd in ("run", "list", "template"):
            ctx.default_map.setdefault(cmd, {})["config_path"] = config_path


@cli.command("list")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
def list_jobs(config_path):
    """List all jobs from the Google Sheet."""
    from src.sheets import get_jobs  # pylint: disable=import-outside-toplevel
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


@cli.command("template")
@click.option("--provider", "provider_name", default=None,
              type=click.Choice(["local", "cloud", "openai", "anthropic", "gemini"]),
              help="LLM provider to use for customization extraction.")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
def set_template(provider_name, config_path):
    """Interactively choose and customize your resume template."""
    from pathlib import Path  # pylint: disable=import-outside-toplevel
    if not Path(config_path).exists():
        from src.setup_wizard import run_setup_wizard
        config = run_setup_wizard(config_path)
    else:
        config = load_config(config_path)

    resolved_provider = provider_name or config.get("provider", "local")

    from src.setup_wizard import ensure_provider_ready
    ensure_provider_ready(resolved_provider, config)
    run_template_wizard(config, resolved_provider)


@cli.command("run")
@click.option("--url", "direct_url", default=None,
              help="Process a single job URL directly (bypasses agent).")
@click.option("--resume-only", is_flag=True, default=False,
              help="Generate only the resume (skip cover letter). URL mode only.")
@click.option("--cover-only", is_flag=True, default=False,
              help="Generate only the cover letter (skip resume). URL mode only.")
@click.option("--provider", "provider_name", default=None,
              type=click.Choice(["local", "cloud", "openai", "anthropic", "gemini"]),
              help="LLM provider. Omit for local Ollama (default).")
@click.option("--config", "config_path", default="config.yaml", show_default=True)
@click.option("--debug", is_flag=True, default=False,
              help="Log scraped content and LLM outputs to debug.db.")
@click.option("--row", "row_num", type=int, default=None, hidden=True)
@click.option("--all", "run_all", is_flag=True, default=False, hidden=True)
@click.option("--force", is_flag=True, default=False, hidden=True)
def run_jobs(direct_url, resume_only, cover_only, provider_name, config_path, debug,
             row_num, run_all, force):
    """Search for jobs with the agent, or process a single URL with --url."""
    if row_num is not None or run_all or force:
        raise click.UsageError(
            "--row, --all, and --force are no longer supported.\n"
            "Run without --url to use the new agent-driven search mode.\n"
            "The Google Sheet is now an output log — the agent writes to it automatically."
        )

    if resume_only and cover_only:
        raise click.UsageError("Cannot use --resume-only and --cover-only together.")

    from pathlib import Path  # pylint: disable=import-outside-toplevel

    # --- First-run: config.yaml doesn't exist yet ---
    if not Path(config_path).exists():
        import src.setup_wizard as _sw  # pylint: disable=import-outside-toplevel
        config = _sw.run_setup_wizard(config_path)
        resolved_provider = provider_name or config.get("provider", "local")

        resume_yaml = config["paths"]["resume_yaml"]
        if not Path(resume_yaml).exists():
            import src.onboarding as _ob  # pylint: disable=import-outside-toplevel
            _ob.run_onboarding(config, resolved_provider)

        template_yaml = config.get("paths", {}).get("template_yaml", "template.yaml")
        if not Path(template_yaml).exists():
            run_template_wizard(config, resolved_provider)

        if not click.confirm(
            "\nSetup complete! Ready to start the job search agent?", default=False
        ):
            click.echo("\nRun 'uv run python main.py run' when you're ready.\n")
            return

        from src.agent import run_agent_chat  # pylint: disable=import-outside-toplevel
        run_agent_chat(config=config, provider_name=resolved_provider)
        return

    # --- Normal flow: config.yaml exists ---
    config = load_config(config_path)
    if "template_yaml" not in config.get("paths", {}):
        config.setdefault("paths", {})["template_yaml"] = "template.yaml"

    from src.providers import get_provider, resolve_models  # pylint: disable=import-outside-toplevel
    resolved_provider = provider_name or config.get("provider", "local")

    from src.setup_wizard import ensure_provider_ready  # pylint: disable=import-outside-toplevel
    ensure_provider_ready(resolved_provider, config)

    # --- Direct URL mode ---
    if direct_url:
        resume = load_resume(config["paths"]["resume_yaml"])
        llm_cfg = config["llm"]
        provider = get_provider(resolved_provider, llm_cfg)
        models, parser_models = resolve_models(resolved_provider, llm_cfg)
        click.echo(
            f"Provider: {resolved_provider}  |  model: {models[0]}  |  parser: {parser_models[0]}"
        )

        from src.debug import init_db, log_run  # pylint: disable=import-outside-toplevel
        if debug:
            init_db()
            click.echo(click.style("  Debug mode enabled — logging to debug.db", fg="cyan"))

        from src.pipeline import process_job  # pylint: disable=import-outside-toplevel
        job = {"url": direct_url, "job_title": "", "status": "", "details": "", "row": None}
        click.echo(f"\nProcessing: {direct_url}")
        debug_run_id = (
            log_run(direct_url, resolved_provider, models[0], parser_models[0]) if debug else None
        )
        folder, _, resume_json = process_job(
            job, config, resume, provider, models, parser_models,
            resume_only=resume_only, cover_only=cover_only,
            debug_run_id=debug_run_id,
        )
        if resume_json is not None:
            click.echo(
                f"  Priority: {resume_json.priority}/10 — {resume_json.priority_reasoning}"
            )
        click.echo(click.style(f"\n  Saved to: {folder}", fg="green"))
        return

    # --- Agent mode ---
    from src.agent import run_agent_chat  # pylint: disable=import-outside-toplevel
    run_agent_chat(config=config, provider_name=resolved_provider)


if __name__ == "__main__":
    cli()
