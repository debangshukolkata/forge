# 7. Improving a UI that already exists (when the user says it looks bad, or asks to restyle)
Do not patch single classes and do not rewrite from scratch. Follow this order:
1. **Scan**: framework, styling method, Tailwind version, current tokens, which screens exist.
2. **Prove the styling works** (section 0). An unstyled-looking page is a setup bug, not a design problem.
3. **Diagnose**: screenshot every screen at 1280 and 375, read the audit, and list every generic pattern, missing state,
   inconsistency and weak spot you can name (at least ten, specific to elements).
4. **Write or update DESIGN.md** with the target system.
5. **Fix in priority order**, one pass each, checking the screenshot after every pass: (a) fonts, (b) colour cleanup and
   one accent, (c) hover, focus and press states, (d) layout, spacing and hierarchy, (e) replace weak components,
   (f) loading, empty and error states, (g) polish: tracking, alignment, shadows, copy. Keep the app working: run
   its tests and flows after each pass.
6. **Review** with `design-critic` and fix what it lists.
If the user asks you to change the look a second time, the first attempt did not change enough: make the change large
enough to be seen at a glance (palette, type and composition), and say what is now different.
