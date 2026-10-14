# ooxml

The package checks every Word, Excel and PowerPoint file goes through (TODO W4, D-345). `check.py` is the safety check run before any library reads an
untrusted file: entry count, total size, expansion ratio and names of the zip (bombs, absolute paths, `..`, Windows device names), encrypted entries, XML
with a DOCTYPE or entity (expansion bombs, external entities); it returns a report of what the file carries that the user should know about (macros,
external links, embedded objects, ActiveX). `validate.py` is the structure validator for a finished file: content types, relationship targets, duplicate
parts, well-formed XML, and the main part for the kind of file; it finds the usual causes of Office's "repair" prompt. Both use only the standard library.

- **Depends on:** errors
- **Invariants:** nothing in a file is executed, followed or fetched; a macro project is reported, never run (the tools that edit refuse to keep it); a refusal says which entry and why.
- **Tests:** test_ooxml.py
- **Decisions:** docs/DECISIONS.md (D-345); the presentation validator in `slides/validate.py` (D-277) is older and stays as it is.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
