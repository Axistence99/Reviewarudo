"""Exercise the orbit workspace navigation, settings, summary and session progress."""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    for width in [390, 1440]:
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        assert page.locator("html").get_attribute("class") == "dark"
        assert page.locator("#set-types span").count() == 3
        page.locator('input[value="summary"]').check()
        assert page.locator("#set-types span").count() == 4
        page.locator("#file-input").set_input_files(
            {
                "name": "My notes.pdf",
                "mimeType": "application/pdf",
                "buffer": b"%PDF-test",
            }
        )
        assert "My notes.pdf" in page.locator("#set-files").inner_text()
        page.locator(".advanced-settings summary").click()
        page.locator("#difficulty").select_option("advanced")
        page.locator('[data-count="10"]').click()
        assert page.locator("#question-count").input_value() == "10"
        page.locator('[data-remove="0"]').click()
        assert (
            "Your materials will appear here" in page.locator("#set-files").inner_text()
        )
        page.locator("#demo").click()
        page.locator("#view-reviewer").wait_for(state="visible")
        page.locator('[data-read="0"]').check()
        page.locator('[data-view="flashcards"]').click()
        page.locator('[data-card="known"]').click()
        page.locator('[data-view="progress"]').click()
        assert "1 / 3" in page.locator("#view-progress").inner_text()
        assert "1 / 10" in page.locator("#view-progress").inner_text()
        page.locator('[data-view="library"]').click()
        assert page.locator(".resource-card").count() == 9
        page.locator('[data-resource="identification"]').click()
        assert page.locator("#view-quiz").is_visible()
        assert "QUESTION 1 OF 2" in page.locator("#view-quiz").inner_text()
        page.locator("[data-create]").click()
        assert page.locator("#view-upload").is_visible()
        assert page.evaluate("scrollY") == 0
        page.locator("#theme").click()
        assert "dark" not in (page.locator("html").get_attribute("class") or "")
        page.reload(wait_until="networkidle")
        assert "dark" not in (page.locator("html").get_attribute("class") or "")
        assert not errors, errors
        page.close()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
    page.screenshot(path="tests/orbit-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path="tests/orbit-mobile.png", full_page=True)
    browser.close()
print(
    "Orbit library, progress, settings, live selection summary and theme persistence passed."
)
