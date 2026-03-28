# tests/test_resume_models.py
from src.resume_models import (
    BasicsSection, WorkSection, EducationSection,
    SkillsSection, ProjectsSection, CertificatesSection,
    SECTION_MODEL_MAP,
)


def test_basics_section_parses_full():
    data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "summary": "Engineer",
        "location": {"city": "Montreal", "region": "QC", "countryCode": "CA"},
        "profiles": [{"network": "LinkedIn", "username": "janedoe", "url": "https://linkedin.com/in/janedoe"}],
    }
    result = BasicsSection.model_validate(data)
    assert result.name == "Jane Doe"
    assert result.profiles[0].network == "LinkedIn"
    assert result.location.city == "Montreal"


def test_basics_section_accepts_partial_input():
    result = BasicsSection.model_validate({"name": "Jane Doe"})
    assert result.name == "Jane Doe"
    assert result.email == ""
    assert result.profiles == []


def test_work_section_parses_multiple_entries():
    data = {"work": [
        {"name": "Acme", "position": "Engineer", "startDate": "2022", "highlights": ["Built API"]},
        {"name": "Startup", "position": "Lead", "startDate": "2020", "endDate": "2022"},
    ]}
    result = WorkSection.model_validate(data)
    assert len(result.work) == 2
    assert result.work[0].name == "Acme"
    assert result.work[0].highlights == ["Built API"]


def test_work_section_empty():
    result = WorkSection.model_validate({"work": []})
    assert result.work == []


def test_education_section_parses():
    data = {"education": [{"institution": "McGill", "area": "CS", "studyType": "BSc", "degree": "Bachelor of Science", "startDate": "2018", "endDate": "2022"}]}
    result = EducationSection.model_validate(data)
    assert result.education[0].institution == "McGill"


def test_skills_section_parses_groups():
    data = {"skills": [{"name": "Languages", "keywords": ["Python", "TypeScript"]}]}
    result = SkillsSection.model_validate(data)
    assert result.skills[0].keywords == ["Python", "TypeScript"]


def test_projects_section_parses():
    data = {"projects": [{"name": "My App", "description": "Cool thing", "url": "https://github.com/x", "highlights": ["Did stuff"]}]}
    result = ProjectsSection.model_validate(data)
    assert result.projects[0].name == "My App"


def test_certificates_section_parses():
    data = {"certificates": [{"name": "AWS SAA", "issuer": "Amazon"}]}
    result = CertificatesSection.model_validate(data)
    assert result.certificates[0].name == "AWS SAA"


def test_section_model_map_has_all_six_sections():
    for section in ("basics", "work", "education", "skills", "projects", "certificates"):
        assert section in SECTION_MODEL_MAP
