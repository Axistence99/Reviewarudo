"""Browser regressions for long-page navigation and generation (mock API, no AI cost)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

demo = json.loads((Path(__file__).resolve().parents[1] / 'frontend/assets/demo.json').read_text())
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width in [390, 1440]:
        page = browser.new_page(viewport={'width': width, 'height': 844})
        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.goto('http://127.0.0.1:8080/', wait_until='networkidle')
        page.locator('#generate').click()
        notice = page.locator('#notification').bounding_box()
        header = page.locator('.site-header').bounding_box()
        assert notice['y'] >= header['y'] + header['height'], (width, notice, header)
        assert notice['y'] + notice['height'] < 844
        assert 'Upload your study materials' in page.locator('#notification').inner_text()
        page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
        page.locator('.nav-create').click()
        assert page.evaluate('scrollY') == 0
        assert page.locator('#browse').evaluate('(el) => el === document.activeElement')
        page.route('**/api/extract', lambda route: route.fulfill(json={
            'success': True, 'data': {'files': [{'filename': 'test.pdf', 'source_type': 'pdf', 'sections': [{'page': 1, 'title': 'Cells', 'content': 'Cells are units of life.'}]}], 'characters': 24, 'approximate_tokens': 6}}))
        page.route('**/api/generate', lambda route: route.fulfill(json={'success': True, 'data': demo}))
        page.locator('#file-input').set_input_files({'name': 'test.pdf', 'mimeType': 'application/pdf', 'buffer': b'%PDF-test'})
        page.locator('#generate').click()
        page.wait_for_function('document.getElementById("processing").hidden')
        assert page.locator('#view-reviewer').is_visible()
        assert page.evaluate('scrollY') == 0
        assert not page.locator('.app-shell').evaluate('(el) => el.inert')
        page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
        page.locator('.nav-create').click()
        assert page.locator('#view-upload').is_visible()
        assert page.evaluate('scrollY') == 0
        page.unroute('**/api/generate')
        page.route('**/api/generate', lambda route: route.fulfill(status=502, json={'success': False, 'error': {'code': 'AI_ERROR', 'message': 'Test service failure. Please try again.'}}))
        page.locator('#generate').click()
        page.wait_for_function('document.getElementById("processing").hidden')
        assert 'Test service failure' in page.locator('#notification').inner_text()
        notice = page.locator('#notification').bounding_box()
        header = page.locator('.site-header').bounding_box()
        assert notice['y'] >= header['y'] + header['height']
        assert notice['y'] + notice['height'] < 844
        assert not errors, errors
        page.close()
    browser.close()
print('Mobile/desktop create navigation, visible validation, generation success, and API error recovery passed.')
