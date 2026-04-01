from unittest.mock import MagicMock, patch


def test_generate_documents_returns_summary(sample_config, sample_resume):
    fake_resume_json = MagicMock()
    fake_resume_json.priority = 2
    fake_resume_json.priority_reasoning = "Strong match."

    with patch("src.tools.generate.process_job",
               return_value=("output/Acme_AI_Engineer_2026-03-27", {}, fake_resume_json)):
        from src.tools.generate import create_generate_tool
        gen_tool = create_generate_tool(
            config=sample_config,
            resume=sample_resume,
            provider=MagicMock(),
            models=["model"],
            parser_models=["model"],
        )
        result = gen_tool.invoke({
            "url": "https://example.com/job/1",
            "job_title": "AI Engineer",
            "company": "Acme Corp",
        })

    assert "Acme Corp" in result
    assert "Priority: 2/10" in result


def test_generate_documents_handles_pipeline_error(sample_config, sample_resume):
    with patch("src.tools.generate.process_job",
               side_effect=Exception("Scrape failed")):
        from src.tools.generate import create_generate_tool
        gen_tool = create_generate_tool(
            config=sample_config,
            resume=sample_resume,
            provider=MagicMock(),
            models=["model"],
            parser_models=["model"],
        )
        result = gen_tool.invoke({
            "url": "https://example.com/job/1",
            "job_title": "AI Engineer",
            "company": "Acme Corp",
        })

    assert "Failed" in result
    assert "Acme Corp" in result
