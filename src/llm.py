import json
import os
import yaml
from pydantic import ValidationError

from ollama import Client
from src.models import ResumeJSON, CoverLetterJSON


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

NEVER USE em-dashes or other special characters that might break JSON formatting. Use plain text only.

You MUST respond with valid JSON only — no markdown, no explanation. The JSON must match this schema exactly:
{
  "summary": "string",
  "skill_categories": [{"name": "string", "skills": ["string"]}],
  "experience": [{"company": "string", "role": "string", "dates": "string", "bullets": ["string"]}],
  "projects_section_heading": "string",
  "projects": [{"title": "string", "focus": "string", "bullets": ["string"], "url": "string"}],
  "certifications": ["string"]
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
- Keep it professional but personable — not generic
- opening: a strong hook paragraph that names the role and leads with a compelling reason to hire
- body_paragraphs: 1-3 paragraphs that connect the candidate's background to the job requirements
- highlights: 2-5 bullet points that call out specific achievements or skills if they add emphasis;
  use an empty list [] if bullets aren't needed
- closing: a confident call-to-action paragraph
- Cover letters can be more than one page — write as much as needed to make a strong case
- Do NOT fabricate anything not in the provided resume about the candidate's background, experience, or skills. You have creative license to reframe and connect the dots, but you MUST NOT invent new facts.
- Do not hallucinate specific accomplishments, metrics, projects, or skills that aren't in the resume data. You can reframe and emphasize what's there, but you can't add new details.

You MUST respond with valid JSON only — no markdown, no explanation. The JSON must match this schema exactly:
{
  "subject_line": "string",
  "opening": "string",
  "body_paragraphs": ["string"],
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


def _call_ollama(ollama_cfg: dict, system: str, user: str) -> str:
    client = _get_client(ollama_cfg)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        response = client.chat(
            model=ollama_cfg["model"],
            messages=messages,
            format="json",
            options={"temperature": ollama_cfg["temperature"]},
        )
    except Exception as e:
        raise RuntimeError(f"Ollama Cloud API error: {e}") from e

    return response.message.content


def generate_resume(job: dict, resume: dict, config: dict) -> ResumeJSON:
    """Call Ollama Cloud to produce a tailored ResumeJSON for the given job."""
    ollama_cfg = config["ollama"]
    user_prompt = f"""JOB TITLE: {job.get('title', job.get('job_title', ''))}
COMPANY: {job.get('company', '')}

JOB DESCRIPTION:
{job['description']}

---

CANDIDATE RESUME DATA (YAML):
{yaml.dump(resume, allow_unicode=True)}
"""
    raw = _call_ollama(ollama_cfg, RESUME_SYSTEM_PROMPT, user_prompt)
    try:
        return ResumeJSON.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError) as e:
        raise ValueError(
            f"LLM returned invalid JSON for resume. Raw output:\n{raw}\n\nError: {e}"
        ) from e


def generate_cover_letter(job: dict, resume: dict,
                           resume_json: ResumeJSON, config: dict) -> CoverLetterJSON:
    """Call Ollama Cloud to produce a tailored CoverLetterJSON."""
    ollama_cfg = config["ollama"]
    user_prompt = f"""JOB TITLE: {job.get('title', job.get('job_title', ''))}
COMPANY: {job.get('company', '')}

JOB DESCRIPTION:
{job['description']}

---

CANDIDATE NAME: {resume['basics']['name']}

TAILORED RESUME SUMMARY:
{resume_json.summary}

TAILORED EXPERIENCE:
{yaml.dump([e.model_dump() for e in resume_json.experience], allow_unicode=True)}
"""
    raw = _call_ollama(ollama_cfg, COVER_LETTER_SYSTEM_PROMPT, user_prompt)
    try:
        return CoverLetterJSON.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError) as e:
        raise ValueError(
            f"LLM returned invalid JSON for cover letter. Raw output:\n{raw}\n\nError: {e}"
        ) from e
