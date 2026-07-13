def test_record_table_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SRC-" in resp.text


def test_category_filter_narrows_results(client):
    resp = client.get("/", params={"category": "Concrete"})
    assert resp.status_code == 200
    assert "CONC" in resp.text
    assert "GYP BD" not in resp.text


def test_all_category_filter_shows_all_records(client):
    resp = client.get("/", params={"category": "All"})
    assert resp.status_code == 200
    assert "SRC-" in resp.text
    assert "No records." not in resp.text
