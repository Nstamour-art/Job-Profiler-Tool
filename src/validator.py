"""
Link validation — verifies that job URLs returned by Tavily are real, specific
job postings before they are surfaced to the user or logged to Sheets.

Pipeline per URL:
  1. HEAD request — drop non-2xx (dead links, 404s)
  2. Lightweight GET + BeautifulSoup text extraction (first 3000 chars)
  3. Heuristic score — pass/drop clearly valid or invalid pages
  4. Parser AI fallback — for uncertain scores, ask the lightweight model
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.providers import BaseProvider

_JOB_KEYWORDS = {
    "responsibilities",
    "qualifications",
    "requirements",
    "apply",
    "skills",
    "salary",
    "compensation",
}
_VALIDATION_MAX_CHARS = 3000
_HEAD_TIMEOUT = 5
_GET_TIMEOUT = 10
_HEURISTIC_PASS_THRESHOLD = 3   # score >= this → PASS without AI
_HEURISTIC_DROP_THRESHOLD = 1   # score < this → DROP without AI
_SEARCH_RESULT_PATTERNS = (
    "/jobs/search",
    "/search?",
    "/find-jobs",
    "/job-search",
    "q=",
    "/jobs?",
    "/careers/search",
    "/jobs/q-",  # Dice search URL slug format (e.g. /jobs/q-engineer-l-Remote-jobs)
)


class _ValidatorResult(BaseModel):
    is_job_posting: bool


def _is_url_live(url: str) -> bool:
    """Return True if the URL appears reachable.

    405 and 501 indicate HEAD is not supported by the server — the URL is
    still live and will be checked via GET in fetch_page_snippet.
    """
    try:
        resp = requests.head(
            url,
            timeout=_HEAD_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return 200 <= resp.status_code < 300 or resp.status_code in (405, 501)
    except requests.RequestException:
        return False


def fetch_page_snippet(url: str) -> str | None:
    """Fetch and return up to _VALIDATION_MAX_CHARS of cleaned page text, or None on failure."""
    try:
        resp = requests.get(
            url,
            timeout=_GET_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text)[:_VALIDATION_MAX_CHARS]
    except requests.RequestException:
        return None


def _heuristic_score(text: str, title: str, company: str, url: str = "") -> int:
    """Score a page 0–5 based on signals that it is a specific job posting.

    Scoring:
      +2  company name present in text
      +1  any significant word (>3 chars) from the job title present
      +1  at least 2 of the job-related keywords present
      +1  page text length >= 500 chars (not a stub/redirect/login wall)
      -2  URL matches known search results page patterns
    """
    if not text:
        return 0

    text_lower = text.lower()
    score = 0

    if company and company.lower() in text_lower:
        score += 2

    title_words = [w for w in re.split(r"\W+", title.lower()) if len(w) > 3]
    if any(w in text_lower for w in title_words):
        score += 1

    matched_keywords = sum(1 for kw in _JOB_KEYWORDS if kw in text_lower)
    if matched_keywords >= 2:
        score += 1

    if len(text) >= 500:
        score += 1

    if url and any(pat in url.lower() for pat in _SEARCH_RESULT_PATTERNS):
        score -= 2

    return max(score, 0)


def _ask_parser(
    snippet: str,
    title: str,
    company: str,
    provider: "BaseProvider",
    config: dict,
    parser_models: list[str],
) -> bool:
    """Use the parser AI to determine if the page is a specific job posting.

    Returns True (include) on AI confirmation or on any error — erring on the
    side of inclusion when the AI call fails.
    """
    from src.llm import _call_with_retry  # pylint: disable=import-outside-toplevel
    from src.prompts import (  # pylint: disable=import-outside-toplevel
        LINK_VALIDATOR_SYSTEM_PROMPT,
        LINK_VALIDATOR_USER_PROMPT,
    )

    prompt = LINK_VALIDATOR_USER_PROMPT.format(
        title=title, company=company, content=snippet
    )
    try:
        result = _call_with_retry(
            _ValidatorResult,
            provider,
            config["llm"],
            LINK_VALIDATOR_SYSTEM_PROMPT,
            prompt,
            parser_models,
        )
        return result.is_job_posting
    except Exception:  # pylint: disable=broad-exception-caught
        return True  # include on failure — user can discard manually


def validate_job_links(
    jobs: list[dict],
    config: dict,
    provider: "BaseProvider",
    parser_models: list[str],
    max_jobs: int,
) -> list[dict]:
    """Validate job URLs and return up to max_jobs that are confirmed job postings.

    For each job dict (must have 'url', 'title', 'company'):
      1. HEAD check — skip dead URLs
      2. Lightweight text fetch — compute heuristic score
      3. score >= _HEURISTIC_PASS_THRESHOLD → include
         score <  _HEURISTIC_DROP_THRESHOLD → exclude
         otherwise → ask parser AI
    """
    validated = []
    for job in jobs:
        if len(validated) >= max_jobs:
            break

        url = (job.get("url") or "").strip()
        if not url:
            continue

        if not _is_url_live(url):
            continue

        snippet = fetch_page_snippet(url)
        if snippet is None:
            continue

        title = job.get("title", "")
        company = job.get("company", "")
        score = _heuristic_score(snippet, title, company, url=url)

        if score >= _HEURISTIC_PASS_THRESHOLD:
            validated.append(job)
        elif score < _HEURISTIC_DROP_THRESHOLD:
            continue
        else:
            if _ask_parser(snippet, title, company, provider, config, parser_models):
                validated.append(job)

    return validated
