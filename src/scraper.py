import re
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class ScraperError(Exception):
    pass


def _clean_text(text: str) -> str:
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text(element) -> str:
    """Convert a BS4 element to clean plain text, preserving bullet structure."""
    lines = []
    for child in element.descendants:
        if child.name == "li":
            lines.append("• " + child.get_text(separator=" ", strip=True))
        elif child.name in ("p", "br"):
            lines.append("\n")
    if not lines:
        lines.append(element.get_text(separator="\n", strip=True))
    return _clean_text("\n".join(lines))


def scrape_job(url: str) -> dict:
    """
    Scrape a LinkedIn job posting.

    Returns:
        {"description": str, "company": str, "title": str}

    Raises:
        ScraperError: if the page is blocked or the description cannot be found.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        raise ScraperError(f"Network error fetching {url}: {e}") from e

    if resp.status_code != 200:
        raise ScraperError(
            f"LinkedIn returned HTTP {resp.status_code}. "
            "The page may require login or the URL is invalid."
        )

    soup = BeautifulSoup(resp.text, "lxml")

    # Check for login redirect
    if soup.find("input", {"name": "session_key"}):
        raise ScraperError(
            "LinkedIn redirected to the login page. "
            "This job may require authentication to view."
        )

    # --- Job description ---
    desc_el = soup.find(id="job-details")
    if not desc_el:
        desc_el = soup.find(class_="jobs-description-content__text--stretch")
    if not desc_el:
        raise ScraperError(
            "Could not find the job description on this page. "
            "LinkedIn may have changed its HTML structure."
        )
    description = _extract_text(desc_el)

    # --- Company name ---
    company = ""
    company_el = soup.find(class_="job-details-jobs-unified-top-card__company-name")
    if company_el:
        a = company_el.find("a")
        company = (a or company_el).get_text(strip=True)

    # --- Job title ---
    title = ""
    title_el = soup.find("h1")
    if title_el:
        title = title_el.get_text(strip=True)

    return {"description": description, "company": company, "title": title}
