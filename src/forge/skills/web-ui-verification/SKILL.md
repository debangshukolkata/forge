---
name: web-ui-verification
description: Verify a web UI feature in a real browser before calling it done: run the app, use it like a user (including the error case), read the result, look at a screenshot, and optionally leave a Playwright script that repeats the check.
---
# Verifying a web UI in a real browser

Unit tests passing does not prove the page shows the button, label or message the requirement asked for. For any
task that changes what a user sees, do this before task_update(done) or telling the user it works:

1. **Start the app** with `start_background` (give it a ready_pattern such as "Running on") on the port the
   requirement names. Note the URL.
2. **Use it like a user** with the browser tools: `browser_open` the page, then `browser_fill` / `browser_click`
   through the main flow of the feature, then the error case (empty field, invalid value, duplicate, second click).
   After each step read the snapshot and compare it with the requirement word by word: exact button labels,
   field labels, messages, columns, links, the page's heading. Anything missing or different is a bug: fix it.
3. **Look at it**: `browser_screenshot`, then `view_image` on the file, when layout, colours or a chart matter
   (a chart with no bars, overlapping text and a cut-off table are all visible only here). Check a narrow
   (375px wide) viewport too if the requirement says it must work on a phone.
4. **Check other pages still work**: open the pages the change did not touch and repeat one earlier flow.
5. **Ask for an independent check.** `spawn_subagent` with agent "verifier" and a task that contains the
   requirement (exact labels and messages), what you changed, and how to start the app. It did not write your
   code: it lists acceptance checks, writes and runs its own Playwright script under tests/e2e/, and replies
   with PASS/FAIL per check and `VERDICT: PASS|FAIL`. Fix the real failures and run it again.
6. **Or leave a repeatable check yourself.** When the feature is a user flow worth keeping, write
   `tests/e2e/test_ui.py` with Playwright and run it. Install it with `python -m pip install playwright` (the user
   is asked to approve); no browser download is needed because Microsoft Edge is already on Windows:

   ```python
   from playwright.sync_api import sync_playwright


   def test_check_in_flow(live_server):
       with sync_playwright() as p:
           browser = p.chromium.launch(channel="msedge", headless=True)
           page = browser.new_page()
           page.goto(live_server + "/")
           page.get_by_role("button", name="Check in").click()
           assert "checked in" in page.inner_text("body").lower()
           browser.close()
   ```
   `live_server` is a fixture that starts the app on a free port in a thread or subprocess and yields its URL.
   Mark the module with `pytest.importorskip("playwright")` so the suite still passes where it isn't installed.
7. **Stop the server** with `stop_background`, and say in the task_update `verification` what you saw
   (pages opened, clicks made, messages and values read). Never write "verified" for something you did not open.
