---
name: deep-modules
description: Use when you design a new module or class, add an abstraction, split or refactor code, or the user asks for a clean design - keep interfaces small and behaviour deep, avoid wrappers and speculative layers
---

# Designing deep modules

Weak designs over-engineer: one-line wrappers, a class per function, interfaces with one implementation "for later". Aim the other way:
**much behaviour behind a small interface**.

## Words to use precisely
- **Module**: anything with an interface and an implementation (a function, class, package).
- **Interface**: everything a caller must know to use it correctly: the signature and also the invariants, ordering rules, error cases,
  configuration and performance expectations. It is more than the method names.
- **Seam**: the place where the interface sits and behaviour can be swapped without editing the callers. **Adapter**: what fills the seam.
- **Depth**: how much behaviour a caller (or a test) gets per unit of interface it has to learn. **Leverage**: what callers gain from depth.
  **Locality**: what maintainers gain: a change or bug lives in one place.

## Rules of thumb
1. **Fewer, simpler entry points.** Before you add a method or a parameter ask whether the module can decide it itself.
2. **The deletion test.** Imagine deleting the module. If the complexity disappears, it was a pass-through: remove it. If the complexity
   reappears in many callers, the module earns its place.
3. **A seam needs two adapters.** One implementation is a hypothetical seam: write the plain code. Add the abstraction when a second real
   case (a fake for tests counts) appears.
4. **Accept dependencies, return results.** Pass the clock, the client or the store in instead of creating it inside; return a value instead
   of changing a hidden state. That makes the module testable through its interface alone.
5. **Test through the interface.** If you must reach past it to test something, the module has the wrong shape.
6. **No speculative generality.** No options, hooks or base classes nobody asked for. Duplication twice is fine; abstract on the third.

## Design it twice (for a new module that others will use)
Before you commit to an interface, sketch two or three really different ones (for example a function taking a config object, a small class
with state, a pipeline of steps) and write for each: how a caller uses it in five lines, what it hides, what is awkward. Choose one and
say why in one or two sentences in the docstring or your summary. For a big choice, give each sketch to its own `explore` or builder
subagent and compare the answers.

## Refactoring an existing repository
Look for shallow spots: tiny wrappers that only forward, the same knowledge repeated across callers (a rule applied in five places),
modules that are hard to test because they create their own dependencies. Deepen one at a time, keep behaviour the same, run the tests
between steps, and do not rename or restructure what the task did not ask for.

## Gotchas
- A class with only `__init__` and one method is usually a function.
- A "manager", "helper" or "utils" module is a sign that behaviour has no home yet.
