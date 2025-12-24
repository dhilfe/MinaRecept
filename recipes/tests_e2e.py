from __future__ import annotations

import contextlib

from django.contrib.auth.models import User
from django.test import LiveServerTestCase, tag
from django.urls import reverse

from .models import Recipe, ShoppingList


@tag("e2e")
class E2ERecipeFlowTests(LiveServerTestCase):
    """End-to-end tests using a real browser (Playwright).

    Run with:
      python manage.py test recipes.tests_e2e

    Note: Requires playwright + a browser installed (chromium).
    """

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="e2e", password="password")
        self.recipe = Recipe.objects.create(
            user=self.user,
            title="E2E Recipe",
            ingredients='[{"amount":"1","unit":"st","name":"Tomat"}]',
            steps="Vänta 1 min\nSen gör du B",
            cooking_time=10,
            servings=2,
            difficulty="easy",
            dish_type="everyday",
        )
        self.shopping_list = ShoppingList.objects.create(user=self.user, name="E2E Lista", is_recurring=False)

    def _login(self, page):
        login_url = self.live_server_url + reverse("login")
        page.goto(login_url)
        page.fill('input[name="username"]', "e2e")
        page.fill('input[name="password"]', "password")
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")

    def test_e2e_add_to_shopping_list_and_cook_spacebar(self):
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Playwright is required for E2E tests. Install with: pip install playwright && playwright install chromium"
            ) from exc

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                self._login(page)

                # Go to recipe detail
                detail_url = self.live_server_url + reverse("recipe_detail", args=[self.recipe.pk])
                page.goto(detail_url)

                # Add to shopping list (chooser page)
                page.click('a:has-text("Lägg till i inköpslista")')
                page.wait_for_load_state("networkidle")

                # Select existing list and submit
                page.select_option('select[name="list_id"]', str(self.shopping_list.id))
                page.click('button:has-text("Lägg till")')
                page.wait_for_load_state("networkidle")

                # Verify we landed on the shopping list detail and the item is present
                page.wait_for_selector("table")
                content = page.content().lower()
                assert "tomat" in content

                # Cook mode: ensure Space advances exactly one step (not two)
                # Go back to recipe detail and use the Starta Matlagning button (should reset to step 0)
                detail_url = self.live_server_url + reverse("recipe_detail", args=[self.recipe.pk])
                page.goto(detail_url)

                # Simulate stale saved progress to ensure reset works
                storage_key = f"cookStep:{self.recipe.pk}"
                page.evaluate("([k, v]) => localStorage.setItem(k, v)", [storage_key, "999"])

                page.click('a:has-text("Starta Matlagning")')
                page.wait_for_load_state("networkidle")

                # Ensure intro is visible, then press space once
                page.wait_for_selector("#step-0.step-card.active")
                # Ensure focus is on the page (not a nav button)
                page.click(".cook-container")
                page.keyboard.press("Space")

                # If it jumped twice we'd likely be on Steg 2. Expect Steg 1 after one press.
                page.wait_for_selector(".step-card.active")
                active_id = page.eval_on_selector(".step-card.active", "el => el.id")
                step_label = ""
                if active_id != "step-0" and active_id != "step-finish":
                    step_label = page.inner_text(".step-card.active .step-number")

                assert active_id == "step-1", f"Expected step-1 after one Space, got {active_id} ({step_label})"

                # Start a timer from the step text (so restart needs confirmation)
                page.evaluate("() => { window.__cookTimerAlarmCount = 0; }")
                page.evaluate("() => { window.__cookTimerAlarmBeepCount = 0; window.__cookAlarmActive = false; }")
                page.fill(".step-card.active .timer-minutes", "0.1")
                page.wait_for_selector(".step-card.active .timer-start")
                page.click(".step-card.active .timer-start")
                page.wait_for_selector("#timerBar.show")

                # Alarm should fire when timer completes and keep beeping until acknowledged
                page.wait_for_function("() => window.__cookAlarmActive === true", timeout=15000)
                page.wait_for_function("() => (window.__cookTimerAlarmBeepCount || 0) >= 1", timeout=15000)
                initial_beeps = page.evaluate("() => window.__cookTimerAlarmBeepCount || 0")
                page.wait_for_function(
                    "(n) => (window.__cookTimerAlarmBeepCount || 0) >= n + 2",
                    arg=initial_beeps,
                    timeout=5000,
                )

                # Space acknowledges alarm (should stop it)
                page.keyboard.press("Space")
                page.wait_for_function("() => window.__cookAlarmActive === false", timeout=5000)

                # Next Space should navigate to next step (not start timer again)
                page.keyboard.press("Space")
                page.wait_for_selector("#step-2.step-card.active")

                # Check an ingredient
                page.click("button:has-text(\"Ingredienser\")")
                page.wait_for_selector("#ingredientsPanel.open")
                page.click("#ingredientsPanel li[data-ingid]")
                page.wait_for_selector("#ingredientsPanel li.ing-checked")

                # Close panel so it doesn't intercept clicks on nav controls
                page.click("#ingredientsPanel .btn-close")
                page.wait_for_selector("#ingredientsPanel:not(.open)")

                # Restart should ask for confirmation; dismiss keeps state
                dialog1 = None
                def _dismiss(dialog):
                    nonlocal dialog1
                    dialog1 = dialog
                    dialog.dismiss()
                page.once("dialog", _dismiss)
                page.click('button:has-text("Starta om")')
                assert dialog1 is not None
                page.wait_for_selector("#step-2.step-card.active")
                page.wait_for_selector("#ingredientsPanel li.ing-checked")

                # Restart again; accept should clear timers + checklist and go to intro
                dialog2 = None
                def _accept(dialog):
                    nonlocal dialog2
                    dialog2 = dialog
                    dialog.accept()
                page.once("dialog", _accept)
                page.click('button:has-text("Starta om")')
                assert dialog2 is not None
                page.wait_for_selector("#step-0.step-card.active")
                page.wait_for_function("() => !document.getElementById('timerBar').classList.contains('show')")
                assert page.locator("#ingredientsPanel li.ing-checked").count() == 0
            finally:
                context.close()
                browser.close()
