# Clean-room rules for the document and presentation skills (TODO W0)

DebCraft makes PowerPoint decks, Excel workbooks, Word documents and PDFs. The tools and skills that do this are written here, from
public specifications and our own experience. They are not copies of, or close paraphrases of, anyone else's skills.

## The rules
1. **Sources we may use:** the ECMA-376 / ISO 29500 specification (Office Open XML), the PDF specification (ISO 32000), the published
   documentation of the libraries we use (python-pptx, python-docx, openpyxl, pypdf, pypdfium2, reportlab), Microsoft's public Office
   automation (COM) object model documentation, and what we learn by building and testing files ourselves (including opening them in
   PowerPoint, Word and Excel on the build machine).
2. **Sources we do not use:** the files, scripts, prompts or wording of other vendors' document skills (for example the `pptx`, `docx`,
   `xlsx` and `pdf` skills that ship with other agents). We do not fetch them, read them, copy them, keep them in the repository or the
   user's folders, or write text that follows them closely. When the user installs such a skill themselves (`forge skill add`), that is the
   user's choice and licence; DebCraft's own skills do not depend on it.
3. **Words:** each skill and tool description is written fresh from what the code does and what we observed. A good test: if a sentence
   could be a rewording of another skill's sentence, throw it away and describe our own behaviour instead.
4. **Libraries:** each is used through its public API, imported lazily, and its licence is recorded below. No library code is copied into
   the repository. Nothing is added that has a copyleft licence (GPL, AGPL) or a licence we have not read.
5. **Assets** (icons, fonts, pictures, templates) follow the asset standard in TODO `L0`: a licence ledger entry per asset, only licences
   that allow commercial use and changes (CC0, public domain, CC BY, MIT, ISC, Apache-2.0, OFL), the credit line kept.
6. **Records:** every decision that adds a document capability says in `docs/DECISIONS.md` which references it used (the specification
   chapter, the library documentation page, or "our own tests").
7. **Security:** a document from outside is untrusted: archive and XML checks before reading, macros never run, external links never
   followed (see `docs/PRESENTATION_SECURITY.md`; the same checks serve every format).

## How the presentation work was done (checked against the rules)
The `make-presentation` skill and the slide tools (D-240 to D-242, and every later presentation decision) were written from python-pptx's
documentation, the Open Office XML specification, and measurement: pictures rendered by PowerPoint itself, PowerPoint's own text
measurement (COM), the package validator written from the packaging rules, and benchmark runs. No other skill's files were fetched or read.
The one comparison made was by the user's request in TODO C18 (the Superpowers and mattpocock skills for *coding*, MIT-licensed); its
outcome is in `docs/SKILLS_STUDY.md` and nothing of it entered the document skills. Result of the check: conforms.

## Libraries and licences
| Library | Used for | Licence |
|---|---|---|
| python-pptx | presentations | MIT |
| python-docx | Word documents | MIT |
| openpyxl | Excel workbooks | MIT |
| pypdf | PDF reading, merging, forms | BSD-3-Clause |
| pypdfium2 | PDF page pictures | BSD-3-Clause / Apache-2.0 |
| reportlab | PDF creation | BSD |
| lxml | XML (comes with python-pptx) | BSD-3-Clause |
| Pillow | pictures | HPND (MIT-like) |
| truststore | operating-system certificates | MIT |
| httpx / openai SDK | web and Azure calls | BSD-3-Clause / Apache-2.0 |

Microsoft Office itself (PowerPoint, Word, Excel) is driven through COM on the user's own computer; nothing of it is redistributed.

## Not decided here
Whether the individual licence files of the other vendors' document skills match their presentation skill: not looked at, on purpose (rule 2);
nothing in the plan depends on it.
