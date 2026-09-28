"""LangGraph workflow that triages a submitted claim."""

from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from claims_app.prompts.triage import CLASSIFY_SYSTEM_PROMPT, SUMMARISE_SYSTEM_PROMPT

CATEGORIES = {"water_damage", "theft", "fire", "vehicle", "suspicious", "other"}
HIGH_VALUE_THRESHOLD = 100_000


class TriageState(TypedDict, total=False):
    claim: dict[str, Any]
    category: str
    priority: str
    summary: str


def build_triage_graph(llm: BaseChatModel) -> Any:
    def classify(state: TriageState) -> TriageState:
        response = llm.invoke(
            [SystemMessage(CLASSIFY_SYSTEM_PROMPT), HumanMessage(state["claim"]["description"])]
        )
        category = str(response.content).strip().lower()
        return {"category": category if category in CATEGORIES else "other"}

    def assess_priority(state: TriageState) -> TriageState:
        amount = float(state["claim"]["amount"])
        return {"priority": "high" if amount >= HIGH_VALUE_THRESHOLD else "normal"}

    def fraud_check(state: TriageState) -> TriageState:
        return {"priority": "investigate"}

    def summarise(state: TriageState) -> TriageState:
        claim = state["claim"]
        details = f"Category: {state['category']}. Amount: {claim['amount']}. {claim['description']}"
        response = llm.invoke([SystemMessage(SUMMARISE_SYSTEM_PROMPT), HumanMessage(details)])
        return {"summary": str(response.content).strip()}

    def route_after_classify(state: TriageState) -> str:
        return "fraud_check" if state["category"] == "suspicious" else "assess_priority"

    graph = StateGraph(TriageState)
    graph.add_node("classify", classify)
    graph.add_node("assess_priority", assess_priority)
    graph.add_node("fraud_check", fraud_check)
    graph.add_node("summarise", summarise)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify", route_after_classify, {"fraud_check": "fraud_check", "assess_priority": "assess_priority"}
    )
    graph.add_edge("assess_priority", "summarise")
    graph.add_edge("fraud_check", "summarise")
    graph.add_edge("summarise", END)
    return graph.compile()
