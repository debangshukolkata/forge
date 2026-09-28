from __future__ import annotations


def test_list_active_policies(client, auth_headers):
    response = client.get("/api/policies/active", headers=auth_headers)

    assert response.status_code == 200
    assert [policy["policy_number"] for policy in response.get_json()] == ["POL-1001"]


def test_get_policy(client, auth_headers):
    response = client.get("/api/policies/2", headers=auth_headers)

    assert response.get_json()["status"] == "lapsed"
