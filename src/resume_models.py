"""
Pydantic v2 models for each resume section.

Used by the onboarding extractor to validate LLM-extracted JSON.
All fields have defaults so partial extraction never raises ValidationError.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Profile(BaseModel):
    network: str = ""
    username: str = ""
    url: str = ""


class Location(BaseModel):
    city: str = ""
    region: str = ""
    countryCode: str = ""


class BasicsSection(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    summary: str = ""
    location: Location = Field(default_factory=Location)
    profiles: list[Profile] = Field(default_factory=list)


class WorkEntry(BaseModel):
    name: str = ""
    location: str = ""
    position: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""
    highlights: list[str] = Field(default_factory=list)


class WorkSection(BaseModel):
    work: list[WorkEntry] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str = ""
    area: str = ""
    studyType: str = ""
    degree: str = ""
    description: str = ""
    startDate: str = ""
    endDate: str = ""


class EducationSection(BaseModel):
    education: list[EducationEntry] = Field(default_factory=list)


class SkillGroup(BaseModel):
    name: str = ""
    keywords: list[str] = Field(default_factory=list)


class SkillsSection(BaseModel):
    skills: list[SkillGroup] = Field(default_factory=list)


class Project(BaseModel):
    name: str = ""
    description: str = ""
    url: str = ""
    highlights: list[str] = Field(default_factory=list)


class ProjectsSection(BaseModel):
    projects: list[Project] = Field(default_factory=list)


class Certificate(BaseModel):
    name: str = ""
    issuer: str = ""


class CertificatesSection(BaseModel):
    certificates: list[Certificate] = Field(default_factory=list)


SECTION_MODEL_MAP: dict[str, type] = {
    "basics": BasicsSection,
    "work": WorkSection,
    "education": EducationSection,
    "skills": SkillsSection,
    "projects": ProjectsSection,
    "certificates": CertificatesSection,
}
