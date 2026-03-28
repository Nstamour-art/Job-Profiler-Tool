import yaml
import pytest


def test_read_resume_section_returns_section(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    read_tool, _ = create_resume_tools(str(resume_path))
    result = read_tool.invoke({"section": "basics"})

    assert "Jane Doe" in result


def test_read_resume_section_rejects_unknown_section(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    read_tool, _ = create_resume_tools(str(resume_path))
    result = read_tool.invoke({"section": "unknown_section"})

    assert "Invalid section" in result


def test_write_resume_section_persists_change(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    read_tool, write_tool = create_resume_tools(str(resume_path))

    new_certs = [{"name": "AWS Solutions Architect", "issuer": "Amazon Web Services"}]
    write_tool.invoke({"section": "certificates", "new_content": yaml.dump(new_certs)})

    updated = yaml.safe_load(resume_path.read_text(encoding="utf-8"))
    assert updated["certificates"][0]["name"] == "AWS Solutions Architect"


def test_write_resume_section_rejects_unknown_section(tmp_path, sample_resume):
    resume_path = tmp_path / "resume.yaml"
    resume_path.write_text(yaml.dump(sample_resume), encoding="utf-8")

    from src.tools.resume_editor import create_resume_tools
    _, write_tool = create_resume_tools(str(resume_path))
    result = write_tool.invoke({"section": "nonexistent", "new_content": "{}"})

    assert "Invalid section" in result
