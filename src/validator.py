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
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.providers import BaseProvider

# ---------------------------------------------------------------------------
# Blocked domains — known sources of fake, scam, or low-quality job listings.
# Checked both at the Tavily search level (exclude_domains) and during link
# validation as a second safety net.
# ---------------------------------------------------------------------------
BLOCKED_DOMAINS: set[str] = {
    # Scam / fake-job aggregators
    "jooble.org",
    "neuvoo.com",
    "talent.com",
    "jobrapido.com",
    "careerjet.com",
    "jobvertise.com",
    "us.jobrapido.com",
    "clicktracker.in",
    "jobleads.com",
    "recruit.net",
    "jobisland.com",
    "learn4good.com",
    "startwire.com",
    "jobomas.com",
    # Low-quality aggregators that surface stale or generic listings
    "adzuna.com",
    "adzuna.ca",
    "adzuna.co.uk",
    "ziprecruiter.com",
    "simplyhired.com",
    "snagajob.com",
    "jora.com",
    "jobcase.com",
    "getwork.com",
    # Freelance / gig platforms (not traditional job postings)
    "fiverr.com",
    "upwork.com",
    "freelancer.com",
    "peopleperhour.com",
    # URL shorteners & redirectors (can mask destinations)
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "ow.ly",
    "is.gd",
}

_FAKE_JOB_SIGNALS = re.compile(
    r"pay\s*(?:per|for)\s*click|"
    r"(?:wire|transfer)\s*(?:money|funds)|"
    r"(?:upfront|advance)\s*(?:fee|payment|deposit)|"
    r"(?:no\s*experience\s*(?:needed|required|necessary).*(?:\$|usd|salary))|"
    r"(?:work\s*from\s*home.*\$\d{3,}\s*(?:/\s*day|per\s*day|daily))|"
    r"(?:guaranteed\s*income)|"
    r"(?:processing\s*(?:rebates|refunds|payments))",
    re.IGNORECASE,
)

_CLOSED_POSTING_SIGNALS = re.compile(
    r"no\s*longer\s*accept(?:ing|s)?\s*(?:applications|submissions|candidates)|"
    r"this\s*(?:job|position|role|posting)\s*(?:has\s*been|is|was)\s*(?:closed|filled|expired|removed|archived)|"
    r"(?:position|role|job)\s*(?:has\s*been|is|was)\s*(?:closed|filled|expired)|"
    r"(?:application|applications)\s*(?:are|is)\s*(?:now\s*)?closed|"
    r"this\s*(?:listing|posting)\s*(?:has\s*)?expired|"
    r"no\s*longer\s*(?:available|listed|active|open)|"
    r"(?:sorry|unfortunately).*(?:position|role|job).*(?:filled|closed|expired)|"
    r"this\s*job\s*is\s*(?:no\s*longer\s*)?(?:available|active)",
    re.IGNORECASE,
)


def _is_blocked_domain(url: str) -> bool:
    """Return True if the URL's domain (or parent domain) is on the blocklist."""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:  # pylint: disable=broad-exception-caught
        return True  # unparseable URLs are suspect
    hostname = hostname.lower().removeprefix("www.")
    # Single-label hostnames (e.g. 'localhost') are treated as blocked
    if "." not in hostname:
        return True
    # Check exact match and one-level parent (e.g. jobs.jooble.org → jooble.org)
    parts = hostname.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in BLOCKED_DOMAINS:
            return True
    return False


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


# ---------------------------------------------------------------------------
# Multi-listing page resolver — detects pages that aggregate many jobs
# (e.g. hnhiring.com, "Who's Hiring" threads) and extracts the specific
# job URL that matches the given title / company.
# ---------------------------------------------------------------------------

_MULTI_LISTING_SIGNALS = re.compile(
    r"\d+\s*jobs?\s*found|"
    r"who(?:'s|\s+is)\s*hiring|"
    r"hiring\s*thread|"
    r"showing\s*\d+\s*results",
    re.IGNORECASE,
)

# Domains that typically host individual job postings (worth following links to)
_JOB_LINK_DOMAINS = {
    "greenhouse.io", "lever.co", "ashbyhq.com", "jobvite.com",
    "bamboohr.com", "smartrecruiters.com", "workday.com",
    "linkedin.com", "indeed.com", "wellfound.com", "angel.co",
    "jobs.lever.co", "boards.greenhouse.io", "jobs.ashbyhq.com",
    "myworkdayjobs.com",
}


def _fetch_page_links(url: str) -> list[tuple[str, str]]:
    """Fetch a page and return a list of (href, anchor_text) tuples."""
    try:
        resp = requests.get(
            url,
            timeout=_GET_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = str(a_tag["href"]).strip()
            if href.startswith(("http://", "https://")):
                anchor = a_tag.get_text(separator=" ", strip=True)
                links.append((href, anchor))
        return links
    except requests.RequestException:
        return []


def _is_multi_listing_page(text: str, url: str) -> bool:
    """Return True if the page appears to be a multi-listing / aggregator page."""
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    if hostname in BLOCKED_DOMAINS:
        return True
    if _MULTI_LISTING_SIGNALS.search(text):
        return True
    # Pages with very dense job keyword counts relative to length
    # (many "apply" / "hiring" mentions) are likely aggregators
    text_lower = text.lower()
    apply_count = text_lower.count("apply") + text_lower.count("hiring")
    if apply_count >= 8 and len(text) > 2000:
        return True
    return False


def _resolve_multi_listing(url: str, title: str, company: str) -> str | None:
    """Given a multi-listing page URL, try to find the specific job link.

    Scores each link on the page by how well it matches the expected
    title and company, and whether it points to a known job board.
    Returns the best matching URL, or None if no good match is found.
    """
    links = _fetch_page_links(url)
    if not links:
        return None

    title_words = {w.lower() for w in re.split(r"\W+", title) if len(w) > 3}
    company_lower = company.lower().strip()

    best_url = None
    best_score = 0

    for href, anchor in links:
        # Skip links back to the same page or to blocked domains
        if _is_blocked_domain(href):
            continue

        link_score = 0
        combined = (anchor + " " + href).lower()

        # Company name in the anchor text or URL
        if company_lower and company_lower in combined:
            link_score += 3

        # Title words in the anchor text
        matched_title_words = sum(1 for w in title_words if w in combined)
        link_score += matched_title_words

        # Links to known job boards get a bonus
        try:
            link_host = urlparse(href).hostname or ""
            link_host = link_host.lower().removeprefix("www.")
            parts = link_host.split(".")
            for i in range(len(parts) - 1):
                if ".".join(parts[i:]) in _JOB_LINK_DOMAINS:
                    link_score += 2
                    break
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        if link_score > best_score:
            best_score = link_score
            best_url = href

    # Require a minimum score to avoid random links
    if best_score >= 3:
        return best_url
    return None


def _heuristic_score(text: str, title: str, company: str, url: str = "") -> int:
    """Score a page 0–5 based on signals that it is a specific job posting.

    Returns -1 for expired/closed postings (hard reject).

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

    # Hard reject: posting is explicitly closed / expired / filled
    if _CLOSED_POSTING_SIGNALS.search(text_lower):
        return -1
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

    # Penalize bare homepage / root URLs with no job-specific path
    if url:
        path = urlparse(url).path.rstrip("/")
        if not path or path == "":
            score -= 3

    # Penalize pages that contain common fake-job / scam language
    if _FAKE_JOB_SIGNALS.search(text_lower):
        score -= 3

    # Reserve -1 exclusively for explicit closed/expired postings above.
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
      0. Block known scam domains
      1. HEAD check — skip dead URLs
      2. Lightweight text fetch — compute heuristic score
      3. Multi-listing detection — if the page aggregates many jobs, try to
         resolve the specific job URL and re-validate it
      4. score >= _HEURISTIC_PASS_THRESHOLD → include
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

        # Block known fake / scam / low-quality domains
        if _is_blocked_domain(url):
            continue

        if not _is_url_live(url):
            continue

        snippet = fetch_page_snippet(url)
        if snippet is None:
            continue

        title = job.get("title", "")
        company = job.get("company", "")

        # Check if this is a multi-listing page; if so, try to resolve
        # the specific job URL and re-validate with the resolved link.
        if _is_multi_listing_page(snippet, url):
            resolved = _resolve_multi_listing(url, title, company)
            if resolved and not _is_blocked_domain(resolved) and _is_url_live(resolved):
                resolved_snippet = fetch_page_snippet(resolved)
                if resolved_snippet is not None:
                    resolved_score = _heuristic_score(
                        resolved_snippet, title, company, url=resolved,
                    )
                    if resolved_score >= _HEURISTIC_PASS_THRESHOLD:
                        job = {**job, "url": resolved}
                        validated.append(job)
                        continue
                    if resolved_score >= _HEURISTIC_DROP_THRESHOLD:
                        if _ask_parser(
                            resolved_snippet, title, company,
                            provider, config, parser_models,
                        ):
                            job = {**job, "url": resolved}
                            validated.append(job)
                            continue
            # Could not resolve a specific job from the multi-listing page — skip
            continue

        score = _heuristic_score(snippet, title, company, url=url)

        # Hard reject: closed / expired posting (score == -1)
        if score < 0:
            continue

        if score >= _HEURISTIC_PASS_THRESHOLD:
            validated.append(job)
        elif score < _HEURISTIC_DROP_THRESHOLD:
            continue
        else:
            if _ask_parser(snippet, title, company, provider, config, parser_models):
                validated.append(job)

    return validated
