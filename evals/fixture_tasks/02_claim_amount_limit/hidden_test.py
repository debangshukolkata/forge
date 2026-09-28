"""Hidden acceptance test: copied into the workspace only after Forge has finished."""


def _post(client, auth_headers, amount):
    return client.post(
        "/api/claims/",
        headers=auth_headers,
        json={"policy_id": 1, "amount": amount, "description": "Storm damaged the roof tiles."},
    )


def test_amount_over_limit_is_rejected(client, auth_headers):
    response = _post(client, auth_headers, 600000)
    assert response.status_code == 422
    assert "limit" in response.get_json()["message"].lower() or "500000" in response.get_json()[
        "message"
    ].replace(",", "")


def test_amount_at_limit_is_accepted(client, auth_headers):
    assert _post(client, auth_headers, 500000).status_code == 201
