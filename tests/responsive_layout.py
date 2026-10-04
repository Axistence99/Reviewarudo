"""Run against the frontend server on port 8080 with Python Playwright."""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
    page.locator("#demo").click()
    page.locator("#view-reviewer").wait_for(state="visible")
    page.locator(".nav-create").click()
    for theme in ["light", "dark"]:
        page.evaluate(
            '(dark) => document.documentElement.classList.toggle("dark", dark)',
            theme == "dark",
        )
        for width in [
            320,
            360,
            375,
            390,
            430,
            640,
            768,
            980,
            1024,
            1180,
            1280,
            1440,
            1920,
        ]:
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), (theme, width, "overflow")
            mark = page.locator(".brand-mark").bounding_box()
            name = page.locator(".brand-name").bounding_box()
            assert name["x"] - (mark["x"] + mark["width"]) >= 11.9, (
                theme,
                width,
                "brand gap",
            )
            actions = page.locator(".header-actions").bounding_box()
            assert name["x"] + name["width"] <= actions["x"], (theme, width, "overlap")
            for control in ["#theme", ".nav-create"]:
                box = page.locator(control).bounding_box()
                assert box["height"] >= 43.9, (width, control, "touch target")
                assert box["x"] + box["width"] <= width, (width, control, "clipped")
            page.locator('[data-view="export"]').click()
            assert page.locator("#view-export").is_visible()
            page.locator('[data-view="upload"]').click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=f"tests/layout-mobile-{theme}.png", full_page=True)
    browser.close()
    print(
        "Layout checks passed at 13 widths in light/dark: no overflow, logo spacing, controls, navigation."
    )
