from unittest.mock import MagicMock, patch
import pytest


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
        folder, job_data, resume_json = process_job(
            job, sample_config, sample_resume,
            provider=MagicMock(), models=["m"], parser_models=["m"],
        )

    assert not job_data["_scraped_fresh"]
    assert resume_json.priority == 3
