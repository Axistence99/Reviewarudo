"""Targeted browser checks, not a full accessibility audit. No live AI calls."""

import copy
import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEMO = json.loads((ROOT / "frontend/assets/demo.json").read_text())


def check_visible_control_names(page):
    missing = page.evaluate(
        """() => [...document.querySelectorAll('button,input,select,progress')]
        .filter(el => el.getClientRects().length && el.type !== 'hidden')
        .filter(el => {
          if (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby')) return false;
          if (el.tagName === 'BUTTON') return !el.textContent.trim();
          return !el.labels?.length;
        }).map(el => el.id || el.outerHTML.slice(0, 100))"""
    )
    assert not missing, missing


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for width in [390, 1440]:
        page = browser.new_page(viewport={"width": width, "height": 900})
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on(
            "console",
            lambda msg: errors.append(msg.text) if msg.type == "error" else None,
        )
        page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        check_visible_control_names(page)
        assert page.locator("[data-create]").get_attribute("aria-current") == "page"
        page.locator("#theme").focus()
        page.keyboard.press("Enter")
        assert "dark" not in (page.locator("html").get_attribute("class") or "")
        assert (
            page.locator("#theme").evaluate("el => getComputedStyle(el).outlineStyle")
            != "none"
        )
        check_visible_control_names(page)
        page.emulate_media(reduced_motion="reduce")
        assert (
            page.locator(".spinner").evaluate(
                "el => getComputedStyle(el).animationName"
            )
            == "none"
        )
        page.locator("#demo").click()
        page.locator("#view-reviewer").wait_for(state="visible")
        check_visible_control_names(page)
        page.locator('[data-view="flashcards"]').click()
        page.locator("#flashcard").focus()
        page.keyboard.press("Space")
        assert page.locator("#flashcard").get_attribute("aria-pressed") == "true"
        page.keyboard.press("ArrowRight")
        assert "CARD 2" in page.locator("#view-flashcards .counter").inner_text()
        with page.expect_download() as info:
            page.locator('[data-card="image"]').click()
        assert Path(info.value.path()).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        page.locator('[data-view="quiz"]').click()
        check_visible_control_names(page)
        page.locator('[data-view="progress"]').click()
        check_visible_control_names(page)
        page.locator('[data-view="reviewer"]').click()
        page.locator("#download-scope").select_option("all")
        # Headless Chromium cannot operate the OS Save dialog. Inspect its print output instead.
        page.evaluate("window.print = () => {}")
        page.locator('[data-download="print"]').click()
        page.emulate_media(media="print")
        pdf_path = ROOT / f"tests/reviewer-print-{width}.pdf"
        page.pdf(path=str(pdf_path), print_background=True)
        text = "\n".join(p.extract_text() or "" for p in PdfReader(pdf_path).pages)
        assert "Cell Biology" in text and "Answer key" in text
        assert "Cell Biology" in page.locator("#print-content").text_content()
        assert not errors, errors
        page.close()

    # Model text/filenames must remain text in study, library, source and print templates.
    hostile = copy.deepcopy(DEMO)
    payload = '<img src=x onerror="window.untrustedExecuted=true"><script>window.untrustedExecuted=true</script>'
    hostile["title"] = payload
    hostile["source_files"][0] = payload
    hostile["topics"][0]["summary"] = payload
    hostile["topics"][0]["source_reference"]["file"] = payload
    hostile["flashcards"][0]["question"] = payload
    page = browser.new_page()
    page.route("**/assets/demo.json", lambda route: route.fulfill(json=hostile))
    page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
    page.locator("#demo").click()
    page.locator("#view-reviewer").wait_for(state="visible")
    for view in ["reviewer", "flashcards", "library"]:
        page.locator(f'[data-view="{view}"]').click()
        assert (
            page.locator(f"#view-{view} img[onerror], #view-{view} script").count() == 0
        )
        assert not page.evaluate("Boolean(window.untrustedExecuted)")
    page.locator('[data-view="reviewer"]').click()
    page.evaluate("window.print = () => {}")
    page.locator('[data-download="print"]').click()
    assert (
        page.locator("#print-content script, #print-content img[onerror]").count() == 0
    )
    assert payload in page.locator("#print-content").text_content()
    assert not page.evaluate("Boolean(window.untrustedExecuted)")
    page.close()
    browser.close()

print(
    "Targeted control names, keyboard/focus, reduced motion, escaped content, PNG and print-PDF checks passed."
)
