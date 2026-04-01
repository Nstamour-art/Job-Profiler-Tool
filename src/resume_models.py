"""
Pydantic v2 models for each resume section.

Used by the onboarding extractor to validate LLM-extracted JSON.
All fields have defaults so partial extraction never raises ValidationError.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Profile(BaseModel):
    """A social media or professional network profile (LinkedIn, GitHub, etc.)."""
    network: str = ""
    username: str = ""
    url: str = ""


class Location(BaseModel):
    """Geographic location with city, region, and country code."""
    city: str = ""
    region: str = ""
    countryCode: str = ""


class BasicsSection(BaseModel):
    """Resume basics: name, contact info, location, and social profiles."""
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    location: Location = Field(default_factory=Location)
    profiles: list[Profile] = Field(default_factory=list)


class WorkEntry(BaseModel):
    """A single work experience with employer, role, dates, and accomplishments."""
    name: str = ""
    location: str = ""
    position: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""
    highlights: list[str] = Field(default_factory=list)


class WorkSection(BaseModel):
    """Container for all work experience entries."""
    work: list[WorkEntry] = Field(default_factory=list)


class EducationEntry(BaseModel):
    """A single education entry with institution, degree, field, and dates."""
    institution: str = ""
    area: str = ""
    studyType: str = ""
    degree: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""


class EducationSection(BaseModel):
    """Container for all education entries."""
    education: list[EducationEntry] = Field(default_factory=list)


class SkillGroup(BaseModel):
    """A named group of skills or technologies."""
    name: str = ""
    keywords: list[str] = Field(default_factory=list)


class SkillsSection(BaseModel):
    """Container for all skill groups."""
    skills: list[SkillGroup] = Field(default_factory=list)


class Project(BaseModel):
    """A portfolio project with name, description, URL, and highlights."""
    name: str = ""
    description: str = ""
    url: str = ""
    highlights: list[str] = Field(default_factory=list)


class ProjectsSection(BaseModel):
    """Container for all portfolio projects."""
    projects: list[Project] = Field(default_factory=list)


class Certificate(BaseModel):
    """A certification or credential with name and issuing organization."""
    name: str = ""
    issuer: str = ""


class CertificatesSection(BaseModel):
    """Container for all certifications."""
    certificates: list[Certificate] = Field(default_factory=list)


SECTION_MODEL_MAP: dict[str, type] = {
    "basics": BasicsSection,
    "work": WorkSection,
    "education": EducationSection,
    "skills": SkillsSection,
    "projects": ProjectsSection,
    "certificates": CertificatesSection,
}
