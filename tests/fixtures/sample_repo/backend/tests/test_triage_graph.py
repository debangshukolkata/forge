from __future__ import annotations

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from claims_app.graphs.triage_graph import build_triage_graph

CLAIM = {"id": 7, "amount": 250000, "description": "Warehouse fire destroyed stock."}


def test_high_value_claim_gets_high_priority():
    llm = FakeListChatModel(responses=["fire", "Fire claim for 250000."])

    result = build_triage_graph(llm).invoke({"claim": CLAIM})

    assert result["category"] == "fire"
    assert result["priority"] == "high"


def test_suspicious_claim_goes_to_fraud_check():
    llm = FakeListChatModel(responses=["suspicious", "Suspicious claim."])

    result = build_triage_graph(llm).invoke({"claim": CLAIM})

    assert result["priority"] == "investigate"


def test_unknown_category_falls_back_to_other():
    llm = FakeListChatModel(responses=["meteor strike", "Other claim."])

    result = build_triage_graph(llm).invoke({"claim": CLAIM})

    assert result["category"] == "other"


def test_graph_structure():
    graph = build_triage_graph(FakeListChatModel(responses=["other"])).get_graph()

    assert {"classify", "assess_priority", "fraud_check", "summarise"} <= set(graph.nodes)
