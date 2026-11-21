"""Login, health checks and role-based access (RBAC)."""

from tests.conftest import login, plant_id, service_id


def test_health_does_not_need_the_database(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/db").json()["database"] == "reachable"


def test_login_and_me(client, sqm):
    me = client.get("/auth/me", headers=sqm).json()
    assert me["role"] == "sqm" and me["full_name"] == "Mara Lindner"


def test_plant_lead_knows_their_plant(client, plant_lead):
    me = client.get("/auth/me", headers=plant_lead).json()
    assert me["role"] == "plant_lead" and me["plant_code"] == "INN"


def test_wrong_password_and_missing_token(client):
    response = client.post("/auth/login", data={"username": "sqm@valdora.example", "password": "nope"})
    assert response.status_code == 401
    assert client.get("/kpis").status_code == 401
    assert client.get("/kpis", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_email_is_case_insensitive(client):
    assert login(client, "SQM@valdora.example ")


def test_management_is_read_only(client, management):
    assert client.get("/kpis", headers=management).status_code == 200
    assert client.get("/reports/monthly", headers=management).status_code == 200
    assert client.post("/simulate/next-day", headers=management).status_code == 200  # demo control
    assert client.post("/demo/reset", headers=management).status_code == 403
    assert client.patch("/tickets/1", json={"status": "Resolved"}, headers=management).status_code == 403
    assert client.post("/improvements", json={}, headers=management).status_code == 403


def test_only_the_service_quality_manager_changes_the_catalogue(client, plant_lead, sqm):
    sid = service_id(client, sqm, "Backup")
    assert client.patch(f"/services/{sid}", json={"owner_name": "X Y"}, headers=plant_lead).status_code == 403
    assert client.patch(f"/services/{sid}", json={"owner_name": "Ines Ferreira"}, headers=sqm).status_code == 200


def test_plant_lead_cannot_change_another_plant(client, plant_lead, sqm):
    ill = plant_id(client, sqm, "ILL")
    ticket = client.get(f"/tickets?plant_id={ill}&open=true", headers=sqm).json()["items"][0]
    response = client.patch(f"/tickets/{ticket['id']}", json={"status": "Resolved"}, headers=plant_lead)
    assert response.status_code == 403
    assert "own plant" in response.json()["detail"]


def test_supplier_sees_only_its_own_scorecard(client, supplier):
    rows = client.get("/suppliers?month=2026-10", headers=supplier).json()["rows"]
    assert [r["short_name"] for r in rows] == ["ALPNET"]
    own = rows[0]["provider_id"]
    assert client.get(f"/suppliers/{own}/scorecard?month=2026-10", headers=supplier).status_code == 200
    assert client.get(f"/suppliers/{own + 1 if own == 1 else 1}/scorecard", headers=supplier).status_code == 403
    assert client.get("/kpis", headers=supplier).status_code == 403
    assert client.get("/tickets", headers=supplier).status_code == 403


def test_meta_is_public_and_lists_the_rules(client):
    meta = client.get("/meta").json()
    assert meta["problem_rule"] == {"min_incidents": 3, "window_days": 14}
    assert [p["resolution_min"] for p in meta["priorities"]] == [240, 480, 960, 2400]
    assert len(meta["priority_matrix"]) == 9
    assert {k["key"] for k in meta["kpis"]} >= {"sla_resolution", "mttr", "change_success"}
    assert client.get("/demo/clock").json()["demo_now"].startswith("2026-11-18T09:00")
