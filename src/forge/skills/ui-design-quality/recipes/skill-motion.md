# 9. Motion and effects: restraint wins
Effect budget by the MOTION_INTENSITY dial (hover and focus effects are free; count only what moves on its own or on scroll): **1 to 2** none beyond a focus ring and one press state;
**3 to 4** one entrance style for headings (`SplitText` or `Reveal`) and hover lifts; **5 to 6** plus one scroll effect (a progress bar or `PinnedSteps`) and one ambient background; **7 to 8**
plus `Magnetic` on the main call to action, `ScrambleText` on one label, a parallax layer; **9 to 10** the page is an experience: several scroll effects, but every one still stops under
`prefers-reduced-motion` and none carries text a person needs. React hooks for these live in `recipes/motion-hooks.tsx` (`find_asset` tag `react`, ids `fx-react-*`).
Small controls (loaders, switches, buttons, inputs, cards) come ready-made: `find_asset` with the tag `micro-interaction` lists forty `mi-*` effects in one stylesheet (`motion-micro.css`).
- Choose the effect budget from the MOTION_INTENSITY dial in DESIGN.md: 1-3 hover and focus only; 4-6 plus scroll reveals
  and one signature effect; 7-10 plus scroll-driven or pinned sequences. One signature effect per page (a beam, an
  aurora, a marquee, a count-up row), not all of them.
- Every animation must explain something (where to look, what changed, that it is loading). Decoration without a reason
  is noise. Keep motion off text a user is reading.
- Reveal-on-scroll hides content until it is seen; `browser_screenshot` full_page scrolls through the page first so
  you and the critic see the revealed result. Content must still be visible with no JavaScript and with reduced motion
  (the kit guarantees it).
- After adding motion, check `browser_console` for errors, take the screenshots again, and confirm the page is still
  readable at 375 px and that nothing shifts layout while animating.
- Showpiece effects (`motion-fancy.css`, or a library such as Magic UI): start with one core component and at most one
  supporting effect per viewport; customise through props, classes and theme variables, never by editing a library's
  internals; check semantic HTML and keyboard access (a dock or flip card must work with the keyboard), and check the page at
  375 px for horizontal overflow after adding any decorative layer.
