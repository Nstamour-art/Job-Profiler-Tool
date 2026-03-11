import json
import os
import yaml
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar

import json_repair
from ollama import Client
from src.models import JobDetails, ResumeJSON, CoverLetterJSON

T = TypeVar("T", bound=BaseModel)


RESUME_SYSTEM_PROMPT = """\
You are an expert resume writer. Your job is to tailor a candidate's resume for a specific job posting.

STRICT RULES — YOU MUST FOLLOW ALL OF THESE:

1. ONE PAGE ONLY. Omit jobs, bullets, or sections that don't fit. Limit bullets to 2-3 per job.

2. NO HALLUCINATION. Only use facts explicitly provided in the resume data. Do NOT invent:
   - New job titles, companies, dates, or responsibilities
   - Projects, metrics, or accomplishments not in the source data
   - Education or credentials not provided
   - Skills or tools not listed (unless you can infer a category as per rule #3)

3. SKILLS — limited creative license:
   - You MAY infer umbrella/category terms from specific tools listed
     (e.g. "Maya + Blender" → "3D Animation", "Claude Code + GitHub Copilot" → "Vibe Coding / AI-Assisted Development")
   - You MAY NOT claim proficiency in tools or technologies not mentioned or clearly implied
   - Can add "(Actively Learning)" or "(Rapidly Upskilling)" as needed to skills that are mentioned in the role, but not listed in the candidate's resume if these skills are relevant and the candidate has demonstrated some related experience or aptitude.

4. EXPERIENCE REWRITING — be aggressive and strategic:
   - Rewrite bullets to directly mirror the language, keywords, and priorities of the job description
   - Lead with the most relevant aspect of each experience for this specific role
   - Surface transferable skills — reframe past work to show how it maps to what this job needs
   - Use strong action verbs that align with the job posting's tone
   - Make every bullet feel like it was written for this job specifically
   - You MUST NOT add specifics (metrics, tools, companies, dates) not present in the source
   - You HAVE FULL CREATIVE FREEDOM to reframe, restructure, and reorder what is there
   - The goal is to get the candidate hired — prioritize relevance and impact

5. Select only certifications relevant to this role from the provided list. Omit unrelated ones.

6. Include the projects section only if it directly strengthens this application. If included, choose the most relevant projects.

7. Skill category names should mirror the language of the job posting (2-4 categories max).

8. The projects section heading is dynamic — rename it to best fit the role
   (e.g. "AI Prototyping & Agent Design", "Creative Projects", "Selected Projects").

NEVER USE em-dashes, "—" or other special characters that might break JSON formatting. Use plain text only.

Also rate the application priority for this candidate against this job posting.
Consider: required skills overlap, seniority level, domain experience, and role type fit.
priority: 1 means apply immediately (near-perfect match), 10 means lowest priority (almost no overlap).
Be honest and calibrated — most roles should score between 3 and 7.

You MUST respond with valid JSON only — no markdown, no explanation. The JSON must match this schema exactly:
{
  "summary": "string",
  "skill_categories": [{"name": "string", "skills": ["string"]}],
  "experience": [{"company": "string", "role": "string", "dates": "string", "bullets": ["string"]}],
  "projects_section_heading": "string",
  "projects": [{"title": "string", "focus": "string", "bullets": ["string"], "url": "string"}],
  "certifications": ["string"],
  "priority": <integer 1-10>,
  "priority_reasoning": "<one concise sentence explaining the score>"
}
"""

COVER_LETTER_SYSTEM_PROMPT = """\
You are an expert cover letter writer. Write a compelling cover letter tailored to the job.

Rules:
- Do not fabricate any information not explicitly present in the resume data or job description, but you have creative license to reframe and connect the dots in a way that best positions the candidate for this specific role.
- Do not use em-dashes or other special characters that might break JSON formatting. Use plain text only.
- Avoid clichés and generic statements that could apply to any job or candidate. The letter should feel like it was written specifically for this role and company.
- Be specific to this role and company — reference the job description directly
- Highlight the most relevant experience and skills from the resume
- If no single experience perfectly matches the job, creatively reframe the most relevant aspects of the candidate's background to show how they can still excel in this role
- Keep it professional but personable — not generic
- If a company name or role is written in multiple languages, pick English.
- opening: a strong hook paragraph that names the role and leads with a compelling reason to hire the candidate
- body_paragraphs: 1-3 paragraphs that connect the candidate's background to the job requirements; If the role is not a perfect match to the candidate's experience, use this space to proactively address potential concerns and reframe the candidate's unique strengths as assets for this role. If highlights are included, end the last body paragraph so it flows naturally into the bullet list.
- highlights_intro: a short transition sentence (e.g. "A few highlights from my background:") that leads into the bullet points; use an empty string "" if highlights is empty
- highlights: 2-5 bullet points that call out specific achievements or skills if they add emphasis;
  use an empty list [] if bullets aren't needed
- closing: a confident call-to-action paragraph that wraps up the letter and thanks the reader for their time
- Cover letters can be more than one page — write as much as needed to make a strong case
- Do NOT fabricate anything not in the provided resume about the candidate's background, experience, or skills. You have creative license to reframe and connect the dots, but you MUST NOT invent new facts.
- Do not hallucinate specific accomplishments, metrics, projects, or skills that aren't in the resume data. You can reframe and emphasize what's there, but you can't add new details.
- The goal is to make the strongest possible case for this candidate for THIS specific job. Be strategic and thoughtful about how to position their background in the best light for this role, but do NOT fabricate any details. Use only what's provided, but feel free to reframe and connect the dots in a way that tells a compelling story tailored to this job description.
- The cover letter should feel natural and human-written, avoiding generic or formulaic language.

- Do not use em-dashes, "—" or other special characters that might break JSON formatting. Use plain text only.

You MUST respond with valid JSON only — no markdown, no explanation. The JSON must match this schema exactly:
{
  "subject_line": "string",
  "opening": "string",
  "body_paragraphs": ["string"],
  "highlights_intro": "string",
  "highlights": ["string"],
  "closing": "string"
}
"""


def _get_client(ollama_cfg: dict) -> Client:
    api_key = os.environ.get("OLLAMA_API_KEY", "")
    return Client(
        host=ollama_cfg["host"],
        headers={"Authorization": f"Bearer {api_key}"},
    )


def _call_ollama(ollama_cfg: dict, system: str, user: str,
                 model_override: str | None = None) -> str | None:
    client = _get_client(ollama_cfg)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        response = client.chat(
            model=model_override or ollama_cfg["model"],
            messages=messages,
            format="json",
            options={"temperature": ollama_cfg["temperature"]},
        )
    except Exception as e:
        raise RuntimeError(f"Ollama Cloud API error: {e}") from e

    return response.message.content


def _parse_llm_response(model_class: Type[T], raw: str) -> T:
    """Try to parse raw LLM output; attempt json_repair if direct parse fails."""
    try:
        return model_class.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError):
        pass
    repaired, _ = json_repair.repair_json(raw)
    return model_class.model_validate_json(json.dumps(repaired))


def _call_with_retry(model_class: Type[T], ollama_cfg: dict, system: str, user: str,
                     model_override: str | None = None) -> T:
    """Call Ollama and parse the response, retrying the full LLM call on failure."""
    max_retries = ollama_cfg.get("max_retries", 3)
    last_error: Exception = RuntimeError("No attempts made.")
    for attempt in range(1, max_retries + 1):
        raw = _call_ollama(ollama_cfg, system, user, model_override=model_override)
        if raw is None:
            last_error = RuntimeError("Ollama returned None")
            if attempt < max_retries:
                import click
                click.echo(f"  Ollama returned None (attempt {attempt}/{max_retries}), retrying …")
            continue
        try:
            return _parse_llm_response(model_class, raw)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                import click
                click.echo(f"  JSON parse failed (attempt {attempt}/{max_retries}), retrying …")
    raise ValueError(
        f"LLM returned invalid JSON after {max_retries} attempts. "
        f"Last error: {last_error}"
    ) from last_error


JOB_PARSER_SYSTEM_PROMPT = """\
Extract structured information from the job posting below.
Be precise and concise — do not invent details not present in the text.
Respond with valid JSON only matching this schema exactly:
{
  "company": "string",
  "title": "string",
  "seniority": "string",
  "industry": "string",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "responsibilities": ["string"],
  "culture_signals": ["string"]
}
"""


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
    return "\n".join(lines)


def parse_job_description(job: dict, config: dict) -> JobDetails:
    """Use a lightweight model to extract structured details from the raw job description."""
    ollama_cfg = config["ollama"]
    parser_model = ollama_cfg.get("parser_model", ollama_cfg["model"])
    user_prompt = f"""JOB TITLE (from URL/sheet): {job.get('title', job.get('job_title', ''))}
COMPANY (from URL/sheet): {job.get('company', '')}

RAW JOB DESCRIPTION:
{job['description']}
"""
    return _call_with_retry(
        JobDetails, ollama_cfg, JOB_PARSER_SYSTEM_PROMPT, user_prompt,
        model_override=parser_model,
    )


def generate_resume(job_details: JobDetails, resume: dict, config: dict) -> ResumeJSON:
    """Call Ollama Cloud to produce a tailored ResumeJSON for the given job."""
    ollama_cfg = config["ollama"]
    user_prompt = f"""{_format_job_details(job_details)}

---

CANDIDATE RESUME DATA (YAML):
{yaml.dump(resume, allow_unicode=True)}
"""
    return _call_with_retry(ResumeJSON, ollama_cfg, RESUME_SYSTEM_PROMPT, user_prompt)


def generate_cover_letter(job_details: JobDetails, resume: dict,
                           resume_json: ResumeJSON, config: dict) -> CoverLetterJSON:
    """Call Ollama Cloud to produce a tailored CoverLetterJSON."""
    ollama_cfg = config["ollama"]
    user_prompt = f"""{_format_job_details(job_details)}

---

CANDIDATE NAME: {resume['basics']['name']}

TAILORED RESUME SUMMARY:
{resume_json.summary}

TAILORED EXPERIENCE:
{yaml.dump([e.model_dump() for e in resume_json.experience], allow_unicode=True)}
"""
    return _call_with_retry(CoverLetterJSON, ollama_cfg, COVER_LETTER_SYSTEM_PROMPT, user_prompt)
