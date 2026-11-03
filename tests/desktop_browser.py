"""End-to-end browser login, noVNC JavaScript and real remote desktop handshake."""
import shutil
from playwright.sync_api import sync_playwright

chrome=shutil.which('google-chrome') or shutil.which('chromium')
assert chrome, 'Runner browser is unavailable'
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(executable_path=chrome,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1480,'height':980})
    page.goto('http://127.0.0.1:7860/desktop/')
    page.locator('input[name=username]').fill('desktop')
    page.locator('input[name=password]').fill('SmokeTest9Secret')
    page.get_by_role('button').click()
    page.wait_for_function("document.documentElement.classList.contains('noVNC_connected')",timeout=45000)
    page.screenshot(path='desktop-browser.png')
    browser.close()
print('PASS: browser form login and actual noVNC connection to the XFCE session')
