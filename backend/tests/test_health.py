def test_health_shape(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["records"] == 150
    assert body["matched"] == 150
    assert set(body["tiers"]) == {"green", "yellow", "red"}
    assert body["tiers"] == {"green": 59, "yellow": 67, "red": 24}
    assert sum(body["tiers"].values()) == body["matched"]
