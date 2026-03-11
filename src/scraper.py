import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, ElementHandle


class ScraperError(Exception):
    pass


def _clean_text(text: str) -> str:
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _try_selectors(page, selectors: list[str]) -> ElementHandle | None:
    """Return the first matching element or None."""
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            return el
    return None


def scrape_job(url: str) -> dict:
    """
    Scrape a LinkedIn job posting using a headless browser.

    Returns:
        {"description": str, "company": str, "title": str}

    Raises:
        ScraperError: if the page is blocked or the description cannot be found.
    """
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
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError as e:
            browser.close()
            raise ScraperError(f"Timed out loading {url}: {e}") from e

        # Dismiss login modal if present
        try:
            page.wait_for_selector(".modal__dismiss, button[aria-label='Dismiss']", timeout=4000)
            page.keyboard.press("Escape")
        except PlaywrightTimeoutError:
            pass

        # Wait for any description element to appear (authenticated or guest selectors)
        desc_selectors = [
            "#job-details",                                 # authenticated view
            ".jobs-description-content__text--stretch",    # authenticated view
            ".show-more-less-html__markup",                 # guest view
            ".description__text",                          # guest view (older)
        ]
        try:
            page.wait_for_selector(", ".join(desc_selectors), timeout=10000)
        except PlaywrightTimeoutError:
            browser.close()
            raise ScraperError(
                "Could not find the job description on this page. "
                "LinkedIn may have changed its HTML structure or requires login."
            )

        # --- Job description ---
        desc_el = _try_selectors(page, desc_selectors)
        if not desc_el:
            browser.close()
            raise ScraperError("Could not find the job description on this page.")
        description = _clean_text(desc_el.inner_text())

        # --- Company name ---
        company_el = _try_selectors(page, [
            ".job-details-jobs-unified-top-card__company-name",  # authenticated
            ".topcard__org-name-link",                           # guest view
            ".sub-nav-cta__optional-url",                        # guest view fallback
        ])
        company = company_el.inner_text().strip() if company_el else ""

        # --- Job title ---
        title_el = _try_selectors(page, [
            "h1.top-card-layout__title",   # guest view
            "h1",                          # fallback
        ])
        title = title_el.inner_text().strip() if title_el else ""

        browser.close()

    return {"description": description, "company": company, "title": title}
