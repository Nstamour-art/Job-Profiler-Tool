from unittest.mock import MagicMock, patch

from src.models import Outcome


def test_generate_batch_returns_per_job_summary(sample_config, sample_resume):
    fake_resume_json = MagicMock()
    fake_resume_json.priority = 2
    fake_resume_json.priority_reasoning = "Strong match."

    with patch("src.tools.generate.process_job",
               return_value=("output/Acme", {}, fake_resume_json,
                             Outcome(success=True, message="Logged."))):
        from src.tools.generate import create_generate_batch_tool
        tool = create_generate_batch_tool(
            config=sample_config,
            resume=sample_resume,
            provider=MagicMock(),
            models=["model"],
            parser_models=["model"],
        )
        result = tool.invoke({"jobs": [
            {"url": "https://example.com/job/1", "title": "AI Engineer", "company": "Acme"},
        ]})

    assert "✓" in result
    assert "Acme" in result
    assert "Priority: 2/10" in result


def test_generate_batch_marks_failed_jobs(sample_config, sample_resume):
    with patch("src.tools.generate.process_job",
               side_effect=Exception("scrape failed")):
        from src.tools.generate import create_generate_batch_tool
        tool = create_generate_batch_tool(
            config=sample_config,
            resume=sample_resume,
            provider=MagicMock(),
            models=["model"],
            parser_models=["model"],
        )
        result = tool.invoke({"jobs": [
            {"url": "https://example.com/job/1", "title": "AI Engineer", "company": "Acme"},
        ]})

    assert "✗" in result
    assert "Acme" in result


def test_generate_batch_returns_message_for_empty_jobs(sample_config, sample_resume):
    from src.tools.generate import create_generate_batch_tool
    tool = create_generate_batch_tool(
        config=sample_config,
        resume=sample_resume,
        provider=MagicMock(),
        models=["model"],
        parser_models=["model"],
    )
    result = tool.invoke({"jobs": []})
    assert "No jobs provided" in result


def test_generate_batch_sleeps_between_batches(sample_config, sample_resume):
    """With batch_size=2 and 3 jobs, sleep should be called once (between batch 1 and 2)."""
    sample_config["agent"]["batch_size"] = 2
    sample_config["agent"]["batch_delay_seconds"] = 1
    fake_resume_json = MagicMock()
    fake_resume_json.priority = 3
    fake_resume_json.priority_reasoning = "Good match."

    with patch("src.tools.generate.process_job",
               return_value=("output/Co", {}, fake_resume_json, Outcome(success=True, message=""))), \
         patch("src.tools.generate.time.sleep") as mock_sleep:
        from src.tools.generate import create_generate_batch_tool
        tool = create_generate_batch_tool(
            config=sample_config,
            resume=sample_resume,
            provider=MagicMock(),
            models=["model"],
            parser_models=["model"],
        )
        tool.invoke({"jobs": [
            {"url": f"https://example.com/job/{i}", "title": "Eng", "company": "Co"}
            for i in range(3)
        ]})

    mock_sleep.assert_called_once_with(1)
