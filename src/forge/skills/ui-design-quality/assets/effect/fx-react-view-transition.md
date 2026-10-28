---
id: fx-react-view-transition
type: effect
title: "Shared-element and page transitions (React)"
summary: "A page or state change that cross-fades, and elements that morph from one place to another, such as a card into its detail view."
moods: [polished, modern, smooth]
products: [app, portfolio, shop, gallery, dashboard]
tags: [animation, motion, react, transition, view transition, shared element, route]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (React view transitions, D-517)"
tested: "built with Vite and React (type-checked); in Edge the change runs inside a view transition and the state updates; with reduced motion no transition starts and the state still updates (tests/test_motion_transitions.py, D-517)"
files:
  - from: recipes/motion-transitions.tsx
    to: src/motion-transitions.tsx
  - from: recipes/motion-transitions.css
    to: src/motion-transitions.css
---

## Shared-element and page transitions (React)

Wrap a state change in `runTransition(() => setOpen(true))` and the old and new views cross-fade. Give the element in both views the same name with
`<SharedElement name={`card-${id}`}>` and it morphs between them (a thumbnail into the full picture, a card into its page). For a client-side route change use
`goTo(() => navigate("/pricing"))`. A name may be used by only one element on the page at a time, so build it from an id.

Import `motion-transitions.css` once in main.tsx after index.css and the helpers from `./motion-transitions`. Where the browser has no View Transitions API, or
the user prefers reduced motion, the change happens at once, so nothing breaks. Budget: one transition per user action; count it against the MOTION_INTENSITY dial.
