"""Is the brief an application screen (back office) or a brand page? (D-488)

The ten back-office screens and the 24 before them are in the catalogue, but the model wrote application screens from a blank file (D-406, D-485). The first step
is to notice what kind of request this is, in plain words and without a model call: the words a person uses for a tool (approvals, a queue, stock, tickets,
an import, a timeline, a dashboard) against the words for a page that sells or introduces something (landing page, portfolio, homepage). Strong words count
two, weak ones one; the answer says why, so the model can disagree for a stated reason."""

from __future__ import annotations

import re
from dataclasses import dataclass

STRONG_APPLICATION = re.compile(
    r"\b(back[- ]?office|admin(?:istration)?(?: panel| console| tool| screen)?|dashboards?|approvals?|approve|queues?|inventory|help ?desk|support desk|tickets?|crm|erp|"
    r"internal tools?|web ?apps?|audit logs?|kanban|data tables?|case management|workflows?|work ?orders?|fulfil\w*|receivables?|payables?|ageing|rota|resource planning)\b",
    re.IGNORECASE,
)
WEAK_APPLICATION = re.compile(
    r"\b(orders?|invoices?|stock|warehouse|import|csv|reports?|timeline|scheduling|schedule|jobs|settings|portal|monitor\w*|roles?|permissions?|users?|accounts?|"
    r"table|filters?|bulk|records?)\b",
    re.IGNORECASE,
)
BRAND_PAGE = re.compile(
    r"\b(landing pages?|marketing (?:site|page)|home ?pages?|portfolio|brochure|campaign|one[- ]page|hero|promotional|storefront|launch page|wait ?list|website for)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BriefKind:
    kind: str  # "application", "brand" or "unclear"
    reason: str


def classify_brief(text: str) -> BriefKind:
    strong = sorted({m.group(0).lower() for m in STRONG_APPLICATION.finditer(text)})
    weak = sorted({m.group(0).lower() for m in WEAK_APPLICATION.finditer(text)} - set(strong))
    brand = sorted({m.group(0).lower() for m in BRAND_PAGE.finditer(text)})
    application_score = 2 * len(strong) + len(weak)
    brand_score = 2 * len(brand)
    if application_score >= 2 and application_score > brand_score:
        shown = ", ".join((strong + weak)[:4])
        return BriefKind("application", f"it talks about {shown}")
    if brand_score > 0 and brand_score >= application_score:
        return BriefKind("brand", f"it asks for {', '.join(brand[:3])}")
    return BriefKind("unclear", "no clear words either way")
