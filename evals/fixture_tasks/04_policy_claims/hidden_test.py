"""Hidden acceptance test: copied into the workspace only after Forge has finished."""


def test_lists_claims_of_a_policy_newest_first(client, auth_headers):
    response = client.get("/api/policies/1/claims", headers=auth_headers)
    assert response.status_code == 200
    assert [c["id"] for c in response.get_json()] == [3, 2, 1]


def test_policy_without_claims(client, auth_headers):
    assert client.get("/api/policies/2/claims", headers=auth_headers).get_json() == []


def test_unknown_policy_is_404(client, auth_headers):
    response = client.get("/api/policies/99/claims", headers=auth_headers)
    assert response.status_code == 404 and response.get_json()["code"] == 404
