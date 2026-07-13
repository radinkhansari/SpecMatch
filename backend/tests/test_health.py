def test_health_shape(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["records"] == 150
    assert body["matched"] >= 0
    assert set(body["tiers"]) == {"green", "yellow", "red"}
    assert sum(body["tiers"].values()) == body["matched"]
