# tests/test_template_cli.py
from unittest.mock import patch, MagicMock
from click.testing import CliRunner


def test_template_subcommand_exists():
    from main import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["template", "--help"])
    assert result.exit_code == 0


def test_template_subcommand_calls_wizard(tmp_path):
    from main import cli
    runner = CliRunner()
    config_path = tmp_path / "config.yaml"
    config_path.touch()

    with patch("main.load_config", return_value={
            "provider": "local", "llm": {}, "paths": {"template_yaml": "template.yaml"}}), \
         patch("src.setup_wizard.ensure_provider_ready"), \
         patch("main.run_template_wizard", return_value=MagicMock()) as mock_wiz:
        runner.invoke(cli, ["template", "--config", str(config_path)])

    mock_wiz.assert_called_once()


def test_run_agent_chat_has_change_template_tool():
    """build_agent includes a change_template tool."""
    captured_tools = {}

    def fake_create(model, tools, system_prompt):  # pylint: disable=unused-argument
        captured_tools["tools"] = [t.name for t in tools]
        return MagicMock()

    sample_config = {
        "llm": {"temperature": 0.3, "max_retries": 1,
                "model": "llama3.2:latest", "parser_model": "llama3.2:latest"},
        "paths": {"resume_yaml": "resume.yaml", "template_yaml": "template.yaml",
                  "output_dir": "output", "credentials": "creds.json"},
        "google_sheets": {"spreadsheet_id": "", "worksheet_name": ""},
        "agent": {"max_jobs": 10, "memory_bank": "", "memory_model": ""},
    }
    sample_resume = {"basics": {"name": "Jane Doe", "location": "Montreal"}}

    with patch("src.agent.create_deep_agent", side_effect=fake_create), \
         patch("src.agent.init_chat_model", return_value=MagicMock()), \
         patch("src.agent.get_provider", return_value=MagicMock()), \
         patch("src.agent.create_search_tool", return_value=MagicMock()), \
         patch("src.agent.create_generate_tool", return_value=MagicMock()), \
         patch("src.agent.create_resume_tools", return_value=(MagicMock(), MagicMock())):
        from src.agent import build_agent
        build_agent(sample_config, sample_resume, "local", "")

    assert "change_template" in captured_tools["tools"]
