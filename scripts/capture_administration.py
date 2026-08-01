"""Capture the canonical Administration database editor at its required viewports."""

from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5173"
OUTPUT = Path("docs/user-guide/images/current")
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in VIEWPORTS:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            page.goto(f"{BASE_URL}/administration/database")
            page.get_by_role("heading", name="Database design", exact=True).wait_for(timeout=30_000)
            page.get_by_role("navigation", name="Database objects").wait_for(timeout=30_000)
            page.get_by_role("combobox", name="Current table", exact=True).wait_for(timeout=30_000)
            page.wait_for_function(
                "() => !document.body.innerText.includes('Loading…') "
                "&& !document.body.innerText.includes('Loading schema')",
                timeout=30_000,
            )
            if page.evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
            ):
                raise RuntimeError(f"Administration has horizontal overflow at {width}x{height}")
            page.screenshot(path=str(OUTPUT / f"administration-database-{width}x{height}.png"))
            context.close()
        browser.close()


if __name__ == "__main__":
    main()
