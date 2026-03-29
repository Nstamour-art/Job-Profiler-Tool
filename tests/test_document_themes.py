# tests/test_document_themes.py
import os
import pytest
from docx import Document as DocxDocument
from src.themes import CLASSIC, MODERN, MINIMAL, CREATIVE
from src.models import ResumeJSON, ExperienceEntry, SkillCategory, CoverLetterJSON


@pytest.fixture
def sample_resume_json():
    return ResumeJSON(
        summary="Experienced software engineer.",
        skill_categories=[SkillCategory(name="Languages", skills=["Python", "Go"])],
        experience=[ExperienceEntry(
            company="Acme Corp", role="Engineer",
            dates="2022-Present", bullets=["Built things."]
        )],
        projects_section_heading="Projects",
        projects=[],
        certifications=[],
        priority=3,
        priority_reasoning="Good fit.",
    )


@pytest.fixture
def sample_personal():
    return {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "location": {"city": "Montreal", "region": "QC"},
        "profiles": [],
    }


def test_build_resume_classic_creates_file(tmp_path, sample_resume_json, sample_personal):
    from src.document import build_resume
    out = str(tmp_path / "resume.docx")
    build_resume(sample_resume_json, sample_personal, [], out, theme=CLASSIC)
    assert os.path.exists(out)


def test_build_resume_modern_creates_file(tmp_path, sample_resume_json, sample_personal):
    from src.document import build_resume
    out = str(tmp_path / "resume_modern.docx")
    build_resume(sample_resume_json, sample_personal, [], out, theme=MODERN)
    assert os.path.exists(out)


def test_build_resume_minimal_creates_file(tmp_path, sample_resume_json, sample_personal):
    from src.document import build_resume
    out = str(tmp_path / "resume_minimal.docx")
    build_resume(sample_resume_json, sample_personal, [], out, theme=MINIMAL)
    assert os.path.exists(out)


def test_build_resume_creative_creates_file(tmp_path, sample_resume_json, sample_personal):
    from src.document import build_resume
    out = str(tmp_path / "resume_creative.docx")
    build_resume(sample_resume_json, sample_personal, [], out, theme=CREATIVE)
    assert os.path.exists(out)


def test_build_cover_letter_classic_creates_file(tmp_path, sample_personal):
    from src.document import build_cover_letter
    cover = CoverLetterJSON(
        subject_line="Application",
        opening="I am excited...",
        body_paragraphs=["My experience..."],
        highlights=[],
        highlights_intro="",
        closing="Thank you.",
    )
    out = str(tmp_path / "cover.docx")
    build_cover_letter(cover, sample_personal, "Acme", "Engineer", out, theme=CLASSIC)
    assert os.path.exists(out)


def test_build_resume_default_theme_is_classic(tmp_path, sample_resume_json, sample_personal):
    """Calling build_resume without theme= uses CLASSIC."""
    from src.document import build_resume
    out = str(tmp_path / "resume_default.docx")
    build_resume(sample_resume_json, sample_personal, [], out)
    assert os.path.exists(out)
