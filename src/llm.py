"""LLM call utilities — retry logic, JSON parsing, and document generators."""

import json
import yaml
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError
import json_repair
from src.models import JobDetails, ResumeJSON, CoverLetterJSON
from src.prompts import RESUME_SYSTEM_PROMPT, COVER_LETTER_SYSTEM_PROMPT, JOB_PARSER_SYSTEM_PROMPT
from src.providers import BaseProvider, _is_rate_error

T = TypeVar("T", bound=BaseModel)


def _parse_llm_response(model_class: Type[T], raw: str) -> T:
    """Try to parse raw LLM output; attempt json_repair if direct parse fails."""
    try:
        return model_class.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError):
        pass
    repaired = json_repair.repair_json(raw, return_objects=True)
    return model_class.model_validate(repaired)


def _call_with_retry(
    model_class: Type[T],
    provider: BaseProvider,
    llm_cfg: dict,
    system: str,
    prompt: str,
    models: list[str],
) -> T:
    """Call the provider and parse the response.

    - Retries the same model up to max_retries times on JSON parse failures.
    - On rate/availability errors, skips immediately to the next fallback model.
    - Raises once all models and retries are exhausted.
    """
    import click  # pylint: disable=import-outside-toplevel
    max_retries = llm_cfg.get("max_retries", 3)
    temperature = llm_cfg.get("temperature", 0.3)
    last_error: Exception = RuntimeError("No attempts made.")

    for i, model in enumerate(models):
        for attempt in range(1, max_retries + 1):
            try:
                raw = provider.call(
                    model=model, system=system, prompt=prompt, temperature=temperature
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                last_error = e
                if _is_rate_error(e) and i < len(models) - 1:
                    click.echo(
                        f"  {model} unavailable (rate/capacity), switching to {models[i + 1]} ..."
                    )
                    break  # skip to next model
                raise RuntimeError(f"LLM provider error: {e}") from e

            if raw is None:
                last_error = RuntimeError("Provider returned None")
                if attempt < max_retries:
                    click.echo(
                        f"  Provider returned None (attempt {attempt}/{max_retries}), retrying ..."
                    )
                continue

            try:
                return _parse_llm_response(model_class, raw)
            except Exception as e:  # pylint: disable=broad-exception-caught
                last_error = e
                if attempt < max_retries:
                    click.echo(
                        f"  JSON parse failed (attempt {attempt}/{max_retries}), retrying ..."
                    )
        else:
            # Exhausted retries on this model without a rate-error break — give up
            raise ValueError(
                f"LLM returned invalid JSON after {max_retries} attempts on {model}. "
                f"Last error: {last_error}"
            ) from last_error

    raise RuntimeError(
        f"All {len(models)} model(s) unavailable. Last error: {last_error}"
    ) from last_error


def _normalize_work_dates(resume: dict) -> dict:
    """Return a shallow-copied resume where work entries missing endDate get endDate='Present'."""
    work = [
        {**entry, "endDate": "Present"} if not entry.get("endDate") else entry
        for entry in resume.get("work", [])
    ]
    return {**resume, "work": work}


def _format_job_details(details: JobDetails) -> str:
    """Format parsed job details into a compact structured block for LLM prompts."""
    lines = [
        f"COMPANY: {details.company}",
        f"TITLE: {details.title}",
        f"SENIORITY: {details.seniority}",
        f"INDUSTRY: {details.industry}",
        f"REQUIRED SKILLS: {', '.join(details.required_skills)}",
    ]
    if details.preferred_skills:
        lines.append(f"PREFERRED SKILLS: {', '.join(details.preferred_skills)}")
    if details.responsibilities:
        lines.append("KEY RESPONSIBILITIES:")
        lines.extend(f"  - {r}" for r in details.responsibilities)
    if details.culture_signals:
        lines.append(f"CULTURE / TONE: {', '.join(details.culture_signals)}")
    if details.salary_range:
        lines.append(f"SALARY RANGE: {details.salary_range}")
    return "\n".join(lines)


def parse_job_description(
    job: dict, config: dict, provider: BaseProvider, parser_models: list[str]
) -> JobDetails:
    """Use a lightweight model to extract structured details from the raw page content."""
    prompt = f"""JOB TITLE (from URL/sheet): {job.get('title', job.get('job_title', ''))}
COMPANY (from URL/sheet): {job.get('company', '')}

RAW PAGE CONTENT:
{job['description']}
"""
    return _call_with_retry(
        JobDetails, provider, config["llm"], JOB_PARSER_SYSTEM_PROMPT, prompt, parser_models
    )


def generate_resume(
    job_details: JobDetails, resume: dict, config: dict, provider: BaseProvider, models: list[str]
) -> ResumeJSON:
    """Produce a tailored ResumeJSON for the given job."""
    prompt = f"""{_format_job_details(job_details)}

---

CANDIDATE RESUME DATA (YAML):
{yaml.dump(_normalize_work_dates(resume), allow_unicode=True, encoding=None)}
"""
    return _call_with_retry(
        ResumeJSON, provider, config["llm"], RESUME_SYSTEM_PROMPT, prompt, models
    )


def generate_cover_letter(
    job_details: JobDetails,
    resume: dict,
    resume_json: ResumeJSON,
    config: dict,
    provider: BaseProvider,
    models: list[str],
) -> CoverLetterJSON:
    """Produce a tailored CoverLetterJSON."""
    prompt = f"""{_format_job_details(job_details)}

---

CANDIDATE NAME: {resume['basics']['name']}

TAILORED RESUME SUMMARY:
{resume_json.summary}

TAILORED EXPERIENCE:
{yaml.dump([e.model_dump() for e in resume_json.experience], allow_unicode=True, encoding=None)}
"""
    return _call_with_retry(
        CoverLetterJSON, provider, config["llm"], COVER_LETTER_SYSTEM_PROMPT, prompt, models
    )
