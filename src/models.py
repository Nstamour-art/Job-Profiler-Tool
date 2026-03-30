"""Pydantic models for structured LLM output: job details, resume, cover letter, suggestions."""

from pydantic import BaseModel


class JobDetails(BaseModel):
    """The complete parsed job posting: title, company, seniority, skills, responsibilities, culture."""
    company: str
    title: str
    seniority: str                  # e.g. "Senior", "Mid-level", "Entry-level"
    industry: str                   # e.g. "SaaS", "Gaming", "Finance"
    required_skills: list[str]      # must-have skills / tools explicitly stated
    preferred_skills: list[str]     # nice-to-have skills
    responsibilities: list[str]     # 3-6 core responsibilities
    culture_signals: list[str]      # tone/culture keywords (e.g. "fast-paced", "remote-first")
    salary_range: str = ""          # e.g. "$120k-$150k", "EUR 60,000-80,000/year", "" if not stated


class SkillCategory(BaseModel):
    """A grouping of related skills (e.g. 'Backend', 'Cloud', 'Analytics')."""
    name: str
    skills: list[str]


class ExperienceEntry(BaseModel):
    """A single work experience entry with company, role, duration, and accomplishments."""
    company: str
    role: str
    dates: str
    bullets: list[str]


class ProjectEntry(BaseModel):
    """A portfolio project with title, focus area, highlights, and optional URL."""
    title: str
    focus: str
    bullets: list[str]
    url: str = ""


class ResumeJSON(BaseModel):
    """Tailored resume content: summary, skills, experience, projects, certifications, and priority score."""
    summary: str
    skill_categories: list[SkillCategory]
    experience: list[ExperienceEntry]
    projects_section_heading: str
    projects: list[ProjectEntry]
    certifications: list[str]
    priority: int           # 1=apply now, 10=low priority
    priority_reasoning: str # one concise sentence explaining the score


class CoverLetterJSON(BaseModel):
    """Complete cover letter content: subject, opening, body, highlights, and closing."""
    subject_line: str
    opening: str
    body_paragraphs: list[str]  # 1-3 body paragraphs
    highlights_intro: str = ""  # short transition sentence before bullets (empty string = use default)
    highlights: list[str]       # bullet points for emphasis (empty list = omit)
    closing: str


class SuggestedRole(BaseModel):
    """A single job title suggestion with reasoning derived from the resume."""
    title: str
    reasoning: str


class SuggestedRoles(BaseModel):
    """A list of job title suggestions for the candidate."""
    roles: list[SuggestedRole]
