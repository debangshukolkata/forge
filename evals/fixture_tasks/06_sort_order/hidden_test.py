"""Hidden acceptance test: copied into the workspace only after Forge has finished."""


def test_sort_ascending(client, auth_headers):
    body = client.get("/api/claims/?sort=asc", headers=auth_headers).get_json()
    assert [c["id"] for c in body["items"]] == [1, 2, 3]


def test_default_is_newest_first(client, auth_headers):
    assert [c["id"] for c in client.get("/api/claims/", headers=auth_headers).get_json()["items"]] == [
        3,
        2,
        1,
    ]


def test_invalid_sort_is_rejected(client, auth_headers):
    assert client.get("/api/claims/?sort=sideways", headers=auth_headers).status_code == 422
