from pydantic import BaseModel


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


class CoverLetterJSON(BaseModel):
    subject_line: str
    opening: str
    body_paragraphs: list[str]  # 1-3 body paragraphs
    highlights: list[str]       # bullet points for emphasis (empty list = omit)
    closing: str


class SuitabilityJSON(BaseModel):
    rating: int       # 1-10
    reasoning: str    # one sentence explaining the score
