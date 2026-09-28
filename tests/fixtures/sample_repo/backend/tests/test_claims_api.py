from __future__ import annotations


def test_list_claims_is_paginated_newest_first(client, auth_headers):
    response = client.get("/api/claims/?page=1&page_size=2", headers=auth_headers)

    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 3
    assert [item["claim_number"] for item in body["items"]] == ["CLM-2025-00003", "CLM-2025-00002"]


def test_list_claims_filters_by_status(client, auth_headers):
    response = client.get("/api/claims/?status=approved", headers=auth_headers)

    assert response.get_json()["total"] == 1


def test_list_claims_requires_token(client):
    assert client.get("/api/claims/").status_code == 401


def test_get_missing_claim_returns_404(client, auth_headers):
    response = client.get("/api/claims/999", headers=auth_headers)

    assert response.status_code == 404
    assert response.get_json()["message"] == "Claim 999 not found"


def test_create_claim_on_active_policy(client, auth_headers):
    payload = {"policy_id": 1, "amount": 15000, "description": "Hailstorm cracked two windows."}

    response = client.post("/api/claims/", json=payload, headers=auth_headers)

    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "submitted"
    assert body["claim_number"].endswith("-00004")


def test_create_claim_on_lapsed_policy_is_rejected(client, auth_headers):
    payload = {"policy_id": 2, "amount": 15000, "description": "Hailstorm cracked two windows."}

    response = client.post("/api/claims/", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_triage_claim_uses_graph(client, auth_headers, fake_llm_responses):
    fake_llm_responses.responses = ["water_damage", "Water damage claim for 45000 after a burst pipe."]

    response = client.post("/api/claims/1/triage", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json() == {
        "claim_id": 1,
        "category": "water_damage",
        "priority": "normal",
        "summary": "Water damage claim for 45000 after a burst pipe.",
    }
    assert client.get("/api/claims/1", headers=auth_headers).get_json()["status"] == "triaged"


def test_openapi_lists_claim_endpoints(client):
    paths = client.get("/openapi.json").get_json()["paths"]

    assert "/api/claims/" in paths
    assert "/api/claims/{claim_id}/triage" in paths
