# tests/test_onboarding.py
import yaml
from unittest.mock import patch, MagicMock

from src.resume_models import (
    BasicsSection, WorkSection, WorkEntry,
)
from src.models import ProviderSuite


# ---------------------------------------------------------------------------
# extract_section
# ---------------------------------------------------------------------------

def test_extract_section_basics_calls_call_with_retry(sample_config):
    mock_provider = MagicMock()
    expected = BasicsSection(name="Jane Doe", email="jane@example.com")
    ps = ProviderSuite(provider=mock_provider, models=["model"], parser_models=["model"], name="local")

    with patch("src.onboarding._call_with_retry", return_value=expected) as mock_retry:
        from src.onboarding import extract_section
        result = extract_section(
            "basics", "Jane Doe, jane@example.com",
            ps, sample_config["llm"],
        )

    assert result.name == "Jane Doe"
    assert mock_retry.called


def test_extract_section_correction_appends_to_input(sample_config):
    mock_provider = MagicMock()
    expected = BasicsSection(name="Jane Smith")
    ps = ProviderSuite(provider=mock_provider, models=["model"], parser_models=["model"], name="local")

    with patch("src.onboarding._call_with_retry", return_value=expected) as mock_retry:
        from src.onboarding import extract_section
        extract_section(
            "basics", "Jane Doe", ps, sample_config["llm"],
            correction="My last name is Smith",
        )

    # The 5th positional arg to _call_with_retry is the user prompt text
    call_args = mock_retry.call_args[0]
    user_text = call_args[4]
    assert "Original input" in user_text
    assert "User correction" in user_text
    assert "My last name is Smith" in user_text


# ---------------------------------------------------------------------------
# _section_to_dict
# ---------------------------------------------------------------------------

def test_section_to_dict_basics_returns_flat_dict():
    from src.onboarding import _section_to_dict
    basics = BasicsSection(name="Jane Doe", email="jane@example.com")
    result = _section_to_dict("basics", basics)
    assert isinstance(result, dict)
    assert result["name"] == "Jane Doe"


def test_section_to_dict_work_returns_list():
    from src.onboarding import _section_to_dict
    work = WorkSection(work=[WorkEntry(name="Acme", position="Engineer")])
    result = _section_to_dict("work", work)
    assert isinstance(result, list)
    assert result[0]["name"] == "Acme"


# ---------------------------------------------------------------------------
# _empty_section
# ---------------------------------------------------------------------------

def test_empty_section_basics_returns_empty_dict():
    from src.onboarding import _empty_section
    assert _empty_section("basics") == {}


def test_empty_section_work_returns_empty_list():
    from src.onboarding import _empty_section
    assert _empty_section("work") == []


def test_empty_section_certificates_returns_empty_list():
    from src.onboarding import _empty_section
    assert _empty_section("certificates") == []


# ---------------------------------------------------------------------------
# _interview_section — yes flow
# ---------------------------------------------------------------------------

def test_interview_section_yes_flow(sample_config):
    mock_provider = MagicMock()
    expected = BasicsSection(name="Jane Doe", email="jane@example.com")
    inputs = iter(["Jane Doe, jane@example.com", "yes"])
    ps = ProviderSuite(provider=mock_provider, models=["model"], parser_models=["model"], name="local")

    with patch("src.onboarding.extract_section", return_value=expected):
        with patch("builtins.input", side_effect=inputs):
            from src.onboarding import _interview_section
            result = _interview_section("basics", ps, sample_config["llm"])

    assert result["name"] == "Jane Doe"


# ---------------------------------------------------------------------------
# _interview_section — skip flow
# ---------------------------------------------------------------------------

def test_interview_section_skip_at_prompt_returns_empty(sample_config):
    mock_provider = MagicMock()
    inputs = iter(["skip"])
    ps = ProviderSuite(provider=mock_provider, models=["model"], parser_models=["model"], name="local")

    with patch("builtins.input", side_effect=inputs):
        from src.onboarding import _interview_section
        result = _interview_section("work", ps, sample_config["llm"])

    assert result == []


def test_interview_section_skip_at_confirm_returns_empty(sample_config):
    mock_provider = MagicMock()
    expected = WorkSection(work=[WorkEntry(name="Acme")])
    inputs = iter(["Acme Corp, Engineer, 2022-present", "skip"])
    ps = ProviderSuite(provider=mock_provider, models=["model"], parser_models=["model"], name="local")

    with patch("src.onboarding.extract_section", return_value=expected):
        with patch("builtins.input", side_effect=inputs):
            from src.onboarding import _interview_section
            result = _interview_section("work", ps, sample_config["llm"])

    assert result == []


# ---------------------------------------------------------------------------
# run_onboarding — integration (mocks _interview_section)
# ---------------------------------------------------------------------------

def test_run_onboarding_writes_resume_yaml(tmp_path, sample_config):
    sample_config["paths"]["resume_yaml"] = str(tmp_path / "resume.yaml")

    section_values = {
        "basics": {"name": "Jane Doe", "email": "jane@example.com", "phone": "", "summary": "", "location": {}, "profiles": []},
        "work": [],
        "education": [],
        "skills": [],
        "projects": [],
        "certificates": [],
    }

    with patch("src.onboarding._interview_section", side_effect=lambda s, *a, **k: section_values[s]):
        with patch("src.providers.get_provider", return_value=MagicMock()):
            with patch("src.providers.resolve_models", return_value=(["m"], ["m"])):
                from src.onboarding import run_onboarding
                resume = run_onboarding(sample_config, "local")

    assert (tmp_path / "resume.yaml").exists()
    loaded = yaml.safe_load((tmp_path / "resume.yaml").read_text(encoding="utf-8"))
    assert loaded["basics"]["name"] == "Jane Doe"
    assert loaded["work"] == []
    assert resume["basics"]["name"] == "Jane Doe"


def test_run_onboarding_returns_complete_resume_dict(tmp_path, sample_config):
    sample_config["paths"]["resume_yaml"] = str(tmp_path / "resume.yaml")

    section_values = {s: ({} if s == "basics" else []) for s in
                      ("basics", "work", "education", "skills", "projects", "certificates")}

    with patch("src.onboarding._interview_section", side_effect=lambda s, *a, **k: section_values[s]):
        with patch("src.providers.get_provider", return_value=MagicMock()):
            with patch("src.providers.resolve_models", return_value=(["m"], ["m"])):
                from src.onboarding import run_onboarding
                resume = run_onboarding(sample_config, "local")

    for section in ("basics", "work", "education", "skills", "projects", "certificates"):
        assert section in resume


def test_interview_section_edit_reextraction_failure_keeps_original(sample_config):
    mock_provider = MagicMock()
    original = BasicsSection(name="Jane Doe", email="jane@example.com")

    call_count = {"n": 0}

    def fake_extract(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return original
        raise ValueError("LLM error")

    # Inputs: initial answer, "edit" at confirm, correction text, "yes" at second confirm
    inputs = iter(["Jane Doe", "edit", "fix something", "yes"])

    ps = ProviderSuite(provider=mock_provider, models=["model"], parser_models=["model"], name="local")
    with patch("src.onboarding.extract_section", side_effect=fake_extract):
        with patch("builtins.input", side_effect=inputs):
            from src.onboarding import _interview_section
            result = _interview_section("basics", ps, sample_config["llm"])

    # Should return original extracted value, not crash
    assert result["name"] == "Jane Doe"
