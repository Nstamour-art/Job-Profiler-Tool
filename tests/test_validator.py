from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# _is_url_live
# ---------------------------------------------------------------------------

def test_is_url_live_returns_true_for_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("src.validator.requests.head", return_value=mock_resp):
        from src.validator import _is_url_live
        assert _is_url_live("https://example.com/job/1") is True


def test_is_url_live_returns_false_for_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("src.validator.requests.head", return_value=mock_resp):
        from src.validator import _is_url_live
        assert _is_url_live("https://example.com/job/1") is False


def test_is_url_live_returns_false_on_request_exception():
    import requests as req
    with patch("src.validator.requests.head", side_effect=req.RequestException("timeout")):
        from src.validator import _is_url_live
        assert _is_url_live("https://example.com/job/1") is False


# ---------------------------------------------------------------------------
# _fetch_snippet
# ---------------------------------------------------------------------------

def test_fetch_snippet_returns_cleaned_text():
    mock_resp = MagicMock()
    mock_resp.text = "<html><body><p>Apply now. Responsibilities include building AI systems.</p></body></html>"
    mock_resp.raise_for_status.return_value = None
    with patch("src.validator.requests.get", return_value=mock_resp):
        from src.validator import _fetch_snippet
        result = _fetch_snippet("https://example.com/job/1")
    assert "Apply now" in result
    assert "<html>" not in result


def test_fetch_snippet_returns_none_on_failure():
    import requests as req
    with patch("src.validator.requests.get", side_effect=req.RequestException("conn error")):
        from src.validator import _fetch_snippet
        assert _fetch_snippet("https://example.com/job/1") is None


# ---------------------------------------------------------------------------
# _heuristic_score
# ---------------------------------------------------------------------------

def test_heuristic_score_high_for_real_job_page():
    from src.validator import _heuristic_score
    text = (
        "Acme Corp is hiring a Senior AI Engineer. "
        "Responsibilities include building ML pipelines. "
        "Qualifications: 5+ years Python. Apply now via the button below. " * 20
    )
    score = _heuristic_score(text, title="Senior AI Engineer", company="Acme Corp")
    assert score >= 3


def test_heuristic_score_low_for_generic_homepage():
    from src.validator import _heuristic_score
    text = "Welcome to Acme Corp. We build great software. Contact us. About. Blog."
    score = _heuristic_score(text, title="Senior AI Engineer", company="Acme Corp")
    assert score <= 2


def test_heuristic_score_zero_for_empty_page():
    from src.validator import _heuristic_score
    score = _heuristic_score("", title="Engineer", company="Corp")
    assert score == 0


# ---------------------------------------------------------------------------
# validate_job_links
# ---------------------------------------------------------------------------

def test_validate_job_links_drops_dead_urls(sample_config):
    jobs = [
        {"url": "https://example.com/job/1", "title": "AI Engineer", "company": "Acme"},
        {"url": "https://example.com/job/dead", "title": "ML Eng", "company": "Beta"},
    ]

    def fake_is_live(url):
        return "dead" not in url

    with patch("src.validator._is_url_live", side_effect=fake_is_live), \
         patch("src.validator._fetch_snippet", return_value="Acme is hiring AI Engineer. Responsibilities qualifications apply." * 10), \
         patch("src.validator._heuristic_score", return_value=4):
        from src.validator import validate_job_links
        result = validate_job_links(jobs, sample_config, MagicMock(), ["model"], max_jobs=10)

    assert len(result) == 1
    assert result[0]["url"] == "https://example.com/job/1"


def test_validate_job_links_caps_at_max_jobs(sample_config):
    jobs = [{"url": f"https://example.com/job/{i}", "title": "Eng", "company": "Corp"} for i in range(10)]

    with patch("src.validator._is_url_live", return_value=True), \
         patch("src.validator._fetch_snippet", return_value="Corp Eng responsibilities qualifications apply apply apply" * 10), \
         patch("src.validator._heuristic_score", return_value=4):
        from src.validator import validate_job_links
        result = validate_job_links(jobs, sample_config, MagicMock(), ["model"], max_jobs=3)

    assert len(result) == 3


def test_validate_job_links_uses_ai_for_uncertain_score(sample_config):
    jobs = [{"url": "https://example.com/job/1", "title": "AI Engineer", "company": "Acme"}]

    with patch("src.validator._is_url_live", return_value=True), \
         patch("src.validator._fetch_snippet", return_value="Some page content."), \
         patch("src.validator._heuristic_score", return_value=1), \
         patch("src.validator._ask_parser", return_value=True) as mock_ai:
        from src.validator import validate_job_links
        result = validate_job_links(jobs, sample_config, MagicMock(), ["model"], max_jobs=10)

    mock_ai.assert_called_once()
    assert len(result) == 1


def test_validate_job_links_drops_if_ai_says_no(sample_config):
    jobs = [{"url": "https://example.com/job/1", "title": "AI Engineer", "company": "Acme"}]

    with patch("src.validator._is_url_live", return_value=True), \
         patch("src.validator._fetch_snippet", return_value="Some page content."), \
         patch("src.validator._heuristic_score", return_value=1), \
         patch("src.validator._ask_parser", return_value=False):
        from src.validator import validate_job_links
        result = validate_job_links(jobs, sample_config, MagicMock(), ["model"], max_jobs=10)

    assert len(result) == 0
