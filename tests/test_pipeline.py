from unittest.mock import MagicMock, patch
from src.models import ProviderSuite


def test_process_job_uses_cached_description(sample_config, sample_resume, tmp_path):
    """process_job skips scraping when 'details' is already present."""
    sample_config["paths"]["output_dir"] = str(tmp_path)

    job = {
        "url": "https://example.com/job/123",
        "job_title": "AI Engineer",
        "status": "",
        "details": "We are looking for an AI engineer with Python skills.",
        "row": None,
    }

    fake_job_details = MagicMock()
    fake_job_details.company = "Acme"
    fake_job_details.title = "AI Engineer"
    fake_resume_json = MagicMock()
    fake_resume_json.priority = 3
    fake_resume_json.priority_reasoning = "Good match."

    with patch("src.pipeline.parse_job_description", return_value=fake_job_details), \
         patch("src.pipeline.generate_resume", return_value=fake_resume_json), \
         patch("src.pipeline.generate_cover_letter", return_value=MagicMock()), \
         patch("src.pipeline.build_resume"), \
         patch("src.pipeline.build_cover_letter"):
        from src.pipeline import process_job
        ps = ProviderSuite(provider=MagicMock(), models=["m"], parser_models=["m"], name="local")
        _, job_data, resume_json, _ = process_job(job, sample_config, sample_resume, ps)

    assert not job_data["_scraped_fresh"]
    assert resume_json.priority == 3


def test_process_job_uses_classic_when_no_template_yaml(tmp_path, monkeypatch):  # pylint: disable=unused-argument
    """process_job falls back to CLASSIC when template.yaml is missing."""
    captured_theme = {}

    def fake_build_resume(*_args, **kwargs):
        captured_theme["theme"] = kwargs.get("theme")
        return "/fake/path"

    config = {
        "llm": {"temperature": 0.3, "max_retries": 1},
        "paths": {
            "output_dir": str(tmp_path),
            "template_yaml": str(tmp_path / "template.yaml"),  # does not exist
        },
        "agent": {},
    }
    job = {"url": "https://example.com", "job_title": "Engineer", "company": "Acme",
           "status": "", "details": "cached description", "row": None}
    resume = {"basics": {"name": "Jane"}, "education": []}

    fake_job_details = MagicMock(company="Acme", title="Engineer",
                                  required_skills=[], preferred_skills=[],
                                  responsibilities=[], culture_signals=[], salary_range="")
    fake_resume_json = MagicMock(priority=5, priority_reasoning="ok",
                                  certifications=[], projects=[])
    fake_cover_json = MagicMock()

    with patch("src.pipeline.parse_job_description", return_value=fake_job_details), \
         patch("src.pipeline.generate_resume", return_value=fake_resume_json), \
         patch("src.pipeline.generate_cover_letter", return_value=fake_cover_json), \
         patch("src.pipeline.build_resume", side_effect=fake_build_resume), \
         patch("src.pipeline.build_cover_letter"):
        from src.pipeline import process_job
        ps = ProviderSuite(provider=MagicMock(), models=["m"], parser_models=["m"], name="local")
        process_job(job, config, resume, ps)

    assert captured_theme.get("theme") is not None
    assert captured_theme["theme"].name == "classic"
