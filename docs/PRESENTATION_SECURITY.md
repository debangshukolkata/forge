# Security review of the presentation tools (TODO P3.4, D-323)

Scope: every tool that opens, builds, edits, converts, previews or unpacks a deck (`build_presentation`, `read_presentation`,
`edit_presentation`, `review_presentation`, `check_accessibility`, `analyze_template`, `convert_presentation`, `merge_presentations`,
`split_presentation`, `unpack_presentation`, `pack_presentation`, `preview_presentation`). A deck from outside is an untrusted zip file of
XML plus pictures and sometimes objects; a deck DebCraft writes goes to people who will open it in PowerPoint.

| Threat | Where it could bite | State |
|---|---|---|
| Zip bomb (a small file that expands to gigabytes) | any open | **Fixed**: `rawpackage.check_package` runs in `open_deck` before python-pptx reads a byte: at most 5000 entries, 400 MB in total, 200 MB per entry, compression ratio at most 250 for entries over 1 MB; the old 80 MB file limit stays. |
| Zip slip and Windows tricks (`../x`, `C:x`, `a.xml:stream` (NTFS data stream), `CON`, trailing dot or space) | unpack writes entry names to disk | **Fixed**: names are refused at the archive check, so no tool ever sees them. |
| XML entity bombs and external entities (XXE) | any XML read | **Fixed**: any XML part with a DOCTYPE or ENTITY declaration is refused; python-pptx's parser already does not resolve entities. |
| Macros and executables inside a deck | PowerPoint COM, packing | **Fixed**: PowerPoint is started with `AutomationSecurity = 3` (macros force-disabled) for preview, measure and convert, and the previous setting is restored when the user's own PowerPoint was already running; unpack refuses decks that hold `vbaProject.bin` or an executable, and pack refuses to add one. DebCraft never runs code from a deck. |
| External links and linked objects | reading, packing, rendering | **Reduced**: no tool follows a link or fetches a linked picture; pack reports every new external relationship so the model tells the user; slide-jump links to another deck are dropped on import. **Residual**: PowerPoint itself may try to fetch a linked picture while rendering a preview of an untrusted deck. |
| Embedded objects (OLE, video, audio, SmartArt) | copy and import | Refused with a reason; never executed or unpacked. |
| PowerPoint launch | preview, measure, convert | Paths are passed in environment variables (never in the command text), DebCraft's own variables are removed (D-202), one PowerPoint at a time (cross-process lock), 180 s (preview, measure) and 240 s (convert) timeouts, PowerPoint is closed only when DebCraft started it. |
| Files outside the workspace | every tool | Every path goes through `workspace.path_of` (jail, read grants, secret files refused) or `image_path`; every write goes through `workspace.write_bytes` (jail and checkpoints); `.pptx` and `.potx` are the only suffixes opened. |
| Mode B | every tool | The deck contains what the user typed or granted; the tools add nothing from the host. Reading a deck the user granted sends its text to the model, as any granted file (D-208). |
| Prompt injection through a deck (slide text, notes, comments, alt text in a deck from outside) | the model reads deck text through `read_presentation`, `review_presentation` | **Residual, mitigated by instruction**: the make-presentation skill says text inside a deck is data, never instructions. Deck text goes through the same redaction as every tool result. |
| Denial of service by size (a deck of thousands of slides, huge pictures) | preview, extract | Limited by the archive limits and the timeouts; large-deck behaviour is measured in P3.3. |

Tests: `tests/test_slides_raw.py` (archive and name checks, DOCTYPE, macros, `open_deck` refusals, COM security setting).
