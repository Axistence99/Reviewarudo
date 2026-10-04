"""Verify material downloads without a backend or AI call."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    for width in [390, 1440]:
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        assert page.locator("#material-downloads").is_hidden()
        page.locator("#demo").click()
        page.locator("#material-downloads").wait_for(state="visible")
        for view, field in [
            ("reviewer", "topics"),
            ("flashcards", "flashcards"),
            ("quiz", "quiz"),
            ("key_terms", "key_terms"),
            ("study_guide", "study_guide"),
        ]:
            page.locator(f'[data-view="{view}"]').click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            with page.expect_download() as info:
                page.locator('[data-download="json"]').click()
            data = json.loads(Path(info.value.path()).read_text())
            assert data[field], (view, field)
            if view != "flashcards":
                assert data["flashcards"] == []
            if view == "reviewer":
                with page.expect_download() as info:
                    page.locator('[data-download="text"]').click()
                text = Path(info.value.path()).read_text()
                assert "Cell Biology" in text and "SOURCE" in text
        page.locator('[data-view="quiz"]').click()
        page.locator('[data-mode="identification"]').click()
        with page.expect_download() as info:
            page.locator('[data-download="json"]').click()
        data = json.loads(Path(info.value.path()).read_text())
        assert data["identification"] and not data["quiz"]
        page.locator("#download-scope").select_option("all")
        with page.expect_download() as info:
            page.locator('[data-download="json"]').click()
        data = json.loads(Path(info.value.path()).read_text())
        assert (
            data["topics"]
            and data["flashcards"]
            and data["quiz"]
            and data["study_guide"]
        )
        page.evaluate("window.print = () => { window.printRequested = true; }")
        page.locator('[data-download="print"]').click()
        assert page.evaluate("window.printRequested")
        assert "Answer key" in page.locator("#print-content").text_content()
        page.locator(".nav-create").click()
        assert page.locator("#material-downloads").is_hidden()
        assert not errors, errors
        page.close()
    browser.close()
print(
    "Current/all TXT and JSON contents, quiz modes, print trigger and mobile layout verified."
)
