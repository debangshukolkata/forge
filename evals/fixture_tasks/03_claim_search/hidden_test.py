"""Hidden acceptance test: copied into the workspace only after Forge has finished."""


def test_search_filters_by_description(client, auth_headers):
    body = client.get("/api/claims/?q=PIPE", headers=auth_headers).get_json()
    assert [c["id"] for c in body["items"]] == [1] and body["total"] == 1


def test_search_combines_with_status(client, auth_headers):
    body = client.get("/api/claims/?q=the&status=approved", headers=auth_headers).get_json()
    assert all(c["status"] == "approved" for c in body["items"])


def test_no_query_keeps_everything(client, auth_headers):
    assert client.get("/api/claims/", headers=auth_headers).get_json()["total"] == 3
