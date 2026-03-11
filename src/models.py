from pydantic import BaseModel


class JobDetails(BaseModel):
    company: str
    title: str
    seniority: str                  # e.g. "Senior", "Mid-level", "Entry-level"
    industry: str                   # e.g. "SaaS", "Gaming", "Finance"
    required_skills: list[str]      # must-have skills / tools explicitly stated
    preferred_skills: list[str]     # nice-to-have skills
    responsibilities: list[str]     # 3-6 core responsibilities
    culture_signals: list[str]      # tone/culture keywords (e.g. "fast-paced", "remote-first")


class SkillCategory(BaseModel):
    name: str
    skills: list[str]


class ExperienceEntry(BaseModel):
    company: str
    role: str
    dates: str
    bullets: list[str]


class ProjectEntry(BaseModel):
    title: str
    focus: str
    bullets: list[str]
    url: str = ""


class ResumeJSON(BaseModel):
    summary: str
    skill_categories: list[SkillCategory]
    experience: list[ExperienceEntry]
    projects_section_heading: str
    projects: list[ProjectEntry]
    certifications: list[str]
    priority: int           # 1=apply now, 10=low priority
    priority_reasoning: str # one concise sentence explaining the score


class CoverLetterJSON(BaseModel):
    subject_line: str
    opening: str
    body_paragraphs: list[str]  # 1-3 body paragraphs
    highlights_intro: str = ""  # short transition sentence before bullets (empty string = use default)
    highlights: list[str]       # bullet points for emphasis (empty list = omit)
    closing: str
