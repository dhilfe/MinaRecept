import pytest
from playwright.sync_api import sync_playwright

def test_navbar_responsive():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 375, "height": 667})  # iPhone 8 size
        page.goto("http://localhost:8000/")
        # Kontrollera att hamburgermenyn finns
        assert page.is_visible("button.navbar-toggler")
        # Klicka på hamburgermenyn
        page.click("button.navbar-toggler")
        # Kontrollera att menyn expanderar och länkar syns
        assert page.is_visible("#navbarCollapse.show, .navbar-collapse.show")
        # Kontrollera att "Mina Recept"-länken är synlig
        assert page.is_visible("a.nav-link", timeout=2000)
        browser.close()
