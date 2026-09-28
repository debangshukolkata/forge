"""Hidden acceptance test: copied into the workspace only after Forge has finished."""


def test_stats_counts_by_status(client, auth_headers):
    response = client.get("/api/claims/stats", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 3
    assert body["by_status"].get("submitted") == 2 and body["by_status"].get("approved") == 1


def test_stats_requires_auth(client):
    assert client.get("/api/claims/stats").status_code in (401, 403)
