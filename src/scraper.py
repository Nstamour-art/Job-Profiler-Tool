"""Job posting scraper — fetches and cleans raw page text from a URL."""

import ipaddress
import re
import socket
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class ScraperError(Exception):
    """Error raised when scraping or parsing a job posting fails."""
    pass


def _validate_url(url: str) -> None:
    """Block URLs targeting private, loopback, or link-local addresses (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ScraperError(f"Unsupported URL scheme: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise ScraperError(f"No hostname in URL: {url}")

    port = parsed.port or (80 if parsed.scheme == "http" else 443)

    # Resolve hostname to IP(s) and reject private/reserved addresses
    try:
        addrinfos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ScraperError(f"Cannot resolve hostname {hostname!r}: {e}") from e

    for family, _type, _proto, _canonname, sockaddr in addrinfos:
        ip = ipaddress.ip_address(sockaddr[0])
        if not ip.is_global or ip.is_multicast or ip.is_unspecified:
            raise ScraperError(
                f"URL targets a private/reserved address ({ip}). "
                "Only public URLs are allowed."
            )


# ---------------------------------------------------------------------------
# CSS selector priority list — ordered from highest-quality to most-generic.
# Tries targeted content containers across major job boards first; falls back
# to full body text if nothing matches.
#
# Coverage: LinkedIn (auth + guest), Indeed, Glassdoor, Greenhouse, Lever,
#           Workday, SmartRecruiters, Ashby, Rippling, Jobvite, BambooHR,
#           generic HTML5 landmarks.
# ---------------------------------------------------------------------------
_CONTENT_SELECTORS: list[str] = [
    # LinkedIn
    "#job-details",
    ".jobs-description-content__text--stretch",
    ".show-more-less-html__markup",
    ".description__text",
    # Indeed
    "#jobDescriptionText",
    # Glassdoor
    "[class*='JobDetails_jobDescription']",
    "[class*='jobDescriptionContent']",
    # Greenhouse
    "#content",
    "#application",
    # Lever
    ".posting-description",
    # Workday
    "[data-automation-id='jobPostingDescription']",
    # SmartRecruiters
    "[class*='job-description']",
    ".job-description",
    # Ashby
    "[class*='ashby-job-posting-brief-description']",
    "[class*='JobPosting_description']",
    # Rippling
    "[class*='JobPostingLayout']",
    # Jobvite
    "#job-description",
    # BambooHR
    "#BambooHR-ATS",
    # Generic HTML5 landmarks
    "main",
    "article",
    "[role='main']",
]

_MAX_CHARS = 15_000


def _clean_text(text: str) -> str:
    """Normalize whitespace and trim to token-safe length."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text[:_MAX_CHARS]


def _try_selectors(page, selectors: list[str]):
    """Return the first matching element handle, or None."""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                return el
        except Exception:  # pylint: disable=broad-exception-caught
            continue
    return None


def _dismiss_modals(page) -> None:
    """Attempt to dismiss common login/cookie modals without crashing."""
    try:
        page.keyboard.press("Escape")
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    dismiss_selectors = [
        ".modal__dismiss",
        "button[aria-label='Dismiss']",
        "button[id*='accept']",
        "button[class*='cookie-accept']",
        "button[class*='consent-accept']",
        "[aria-label*='Accept']",
        "[aria-label*='Close']",
        "button[class*='close']",
        "button[data-testid='close-button']",
    ]
    for sel in dismiss_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                break
        except Exception:  # pylint: disable=broad-exception-caught
            continue


def scrape_job(url: str) -> dict:
    """
    Scrape a job posting from any site using a headless browser.

    Strategy:
      1. Load the page with Playwright (handles JS-heavy ATSs).
      2. Wait for networkidle then dismiss login/cookie modals.
      3. Try a prioritized list of known content selectors across major job
         boards. Use the first match. Fall back to full <body> text.
      4. Clean and truncate the extracted text.

    Returns:
        {"description": str}

    Raises:
        ScraperError: if the page times out or yields no usable text.
    """
    _validate_url(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError as e:
                raise ScraperError(f"Timed out loading {url}: {e}") from e

            # Give JS-rendered pages a moment to settle
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                pass  # not all pages reach networkidle; proceed anyway

            _dismiss_modals(page)

            # Try targeted content selectors; fall back to full body text
            el = _try_selectors(page, _CONTENT_SELECTORS)
            if el:
                raw_text = el.inner_text()
            else:
                try:
                    raw_text = page.inner_text("body")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    raise ScraperError(f"Could not extract page text from {url}: {e}") from e
        finally:
            browser.close()

    description = _clean_text(raw_text)
    if not description:
        raise ScraperError(
            f"No text content found on {url}. "
            "The page may require authentication or be dynamically gated."
        )

    return {"description": description}
