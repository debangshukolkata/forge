"""Hidden acceptance test: copied into the workspace only after Forge has finished."""


def test_health_category_is_kept(client, auth_headers, fake_llm_responses):
    fake_llm_responses.responses = ["health", "Hospital bills after an accident."]
    response = client.post("/api/claims/3/triage", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["category"] == "health"


def test_unknown_category_still_maps_to_other(client, auth_headers, fake_llm_responses):
    fake_llm_responses.responses = ["spaceship", "Odd claim."]
    assert client.post("/api/claims/3/triage", headers=auth_headers).get_json()["category"] == "other"
