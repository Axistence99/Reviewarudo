"""Run with the frontend served on port 8080. Requires Python Playwright."""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8080/',wait_until='networkidle')
    page.screenshot(path='tests/desktop.png',full_page=True)
    assert page.locator('.material-option').count()==9
    page.locator('#demo').click()
    page.locator('#view-reviewer h1').wait_for()
    assert 'Cell Biology' in page.locator('#view-reviewer h1').inner_text()
    page.locator('[data-read="0"]').check()
    assert '1 of 3' in page.locator('#read-count').inner_text()
    page.locator('[data-view="flashcards"]').click()
    page.locator('#flashcard').click()
    assert page.locator('#flashcard').get_attribute('aria-pressed')=='true'
    page.locator('[data-card="known"]').click()
    assert '1 KNOWN' in page.locator('#view-flashcards .counter').inner_text()
    page.locator('[data-card="next"]').click()
    assert 'CARD 2' in page.locator('#view-flashcards .counter').inner_text()
    page.locator('[data-view="quiz"]').click()
    page.locator('[data-choice="1"]').click()
    page.locator('[data-quiz="submit"]').click()
    assert 'Correct' in page.locator('#quiz-feedback').inner_text()
    assert page.locator('[data-quiz="submit"]').is_disabled()
    page.locator('[data-quiz="next"]').click()
    assert 'QUESTION 2' in page.locator('#view-quiz .counter').inner_text()
    page.locator('[data-mode="fill_in_the_blank"]').click()
    page.locator('#practice-answer').fill('ribosome')
    page.locator('[data-quiz="submit"]').click()
    assert 'Correct' in page.locator('#quiz-feedback').inner_text()
    page.locator('[data-view="key_terms"]').click()
    assert page.locator('.terms article').count()==6
    page.locator('[data-view="study_guide"]').click()
    assert page.locator('#view-study_guide .panel').count()==8
    page.locator('[data-view="export"]').click()
    with page.expect_download() as info:page.locator('[data-export="json"]').click()
    assert info.value.suggested_filename=='reviewarudo.json'
    page.locator('#theme').click()
    assert page.locator('html').get_attribute('class')=='dark'
    page.reload(wait_until='networkidle')
    page.locator('[data-view="reviewer"]').click()
    assert 'Cell Biology' in page.locator('#view-reviewer h1').inner_text()
    page.locator('#theme').click()
    page.set_viewport_size({'width':390,'height':844})
    page.locator('[data-view="upload"]').click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path='tests/mobile.png',full_page=True)
    assert not errors,errors
    browser.close()
    print('Browser smoke checks passed: demo, read progress, flip, known, next, quiz, fill-in, glossary, guide, download, theme, reload, mobile overflow.')
