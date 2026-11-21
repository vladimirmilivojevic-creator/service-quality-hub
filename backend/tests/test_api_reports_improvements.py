"""Monthly service review, Excel export, improvement register and catalogue changes."""

import io

from openpyxl import load_workbook

from tests.conftest import plant_id, service_id


def test_monthly_report_defaults_to_the_last_full_month(client, sqm):
    report = client.get("/reports/monthly", headers=sqm).json()
    assert report["month"] == "2026-10" and report["is_partial"] is False
    assert 3 <= len(report["summary"]) <= 5
    assert any("AlpNet Carrier" in point for point in report["summary"])
    assert len(report["kpis"]) == 6 and len(report["trend"]["months"]) == 6
    assert len(report["plants"]) == 5 and len(report["suppliers"]) == 9
    assert len(report["top_breaches"]) == 10
    assert report["changes"]["success_rate"] == 90.0
    assert any("ERP release 26.10" in c["title"] for c in report["changes"]["not_successful"])
    assert any(p["title"].startswith("Unstable WAN line") for p in report["problems"])
    assert report["improvements"]["overdue"] == []  # WAN monitoring is due on 31 October, so not yet late
    assert {i["title"] for i in report["improvements"]["done_in_month"]} == {
        "Monthly service review with Printwise including MTTR per plant"
    }
    assert any(a.startswith("Service review with AlpNet Carrier") for a in report["next_actions"])
    assert any("Illerau Works" in a for a in report["next_actions"])


def test_the_same_month_always_gives_the_same_report(client, sqm):
    first = client.get("/reports/monthly?month=2026-09", headers=sqm).json()
    client.post("/simulate/next-day", headers=sqm)  # new activity happens after September
    second = client.get("/reports/monthly?month=2026-09", headers=sqm).json()
    for section in ("summary", "kpis", "plants", "suppliers", "next_actions", "changes"):
        assert first[section] == second[section]


def test_excel_export(client, sqm):
    response = client.get("/reports/monthly.xlsx?month=2026-10", headers=sqm)
    assert response.status_code == 200
    assert 'filename="service-review-2026-10.xlsx"' in response.headers["content-disposition"]
    workbook = load_workbook(io.BytesIO(response.content))
    assert workbook.sheetnames == ["Summary", "KPI", "KPI trend", "Plants", "Suppliers", "Breaches", "Improvements"]
    assert workbook["Suppliers"].max_row == 10  # header + 9 providers
    assert workbook["KPI"]["A2"].value == "SLA compliance – resolution"


def test_improvement_register(client, sqm):
    items = client.get("/improvements", headers=sqm).json()
    assert len(items) == 13
    overdue = client.get("/improvements?overdue=true", headers=sqm).json()
    assert sorted(i["title"].split()[0] for i in overdue) == ["Monitor", "Resolve"]
    assert all(i["status"] == "done" for i in client.get("/improvements?status=done", headers=sqm).json())


def test_add_and_update_improvement(client, sqm):
    alpnet = next(r for r in client.get("/suppliers", headers=sqm).json()["rows"] if r["short_name"] == "ALPNET")
    body = {
        "title": "Escalation drill with AlpNet",
        "source": "service_review",
        "provider_id": alpnet["provider_id"],
        "owner": "Mara Lindner",
        "due_date": "2026-11-10",
        "kpi": "sla_resolution",
        "kpi_baseline": 63.2,
        "kpi_target": 97,
    }
    created = client.post("/improvements", json=body, headers=sqm)
    assert created.status_code == 201
    item = created.json()
    assert item["overdue"] is True and item["provider_name"] == "AlpNet Carrier"
    done = client.patch(f"/improvements/{item['id']}", json={"status": "done"}, headers=sqm).json()
    assert done["completed_at"] and done["overdue"] is False
    assert client.get(f"/improvements?provider_id={alpnet['provider_id']}", headers=sqm).json()
    assert client.patch("/improvements/9999", json={"status": "done"}, headers=sqm).status_code == 404
    bad = client.post("/improvements", json={**body, "plant_id": 999}, headers=sqm)
    assert bad.status_code == 422


def test_plant_lead_manages_only_own_plant_improvements(client, plant_lead, sqm):
    inn, ill = plant_id(client, sqm, "INN"), plant_id(client, sqm, "ILL")
    body = {"title": "Label printer spare at Innfeld", "source": "idea", "owner": "Tobias Gruber"}
    assert client.post("/improvements", json={**body, "plant_id": inn}, headers=plant_lead).status_code == 201
    assert client.post("/improvements", json={**body, "plant_id": ill}, headers=plant_lead).status_code == 403
    illerau_item = client.get(f"/improvements?plant_id={ill}", headers=sqm).json()[0]
    response = client.patch(f"/improvements/{illerau_item['id']}", json={"status": "approved"}, headers=plant_lead)
    assert response.status_code == 403


def test_catalogue_and_sla_exception(client, sqm):
    services = client.get("/services", headers=sqm).json()
    assert {s["lifecycle"] for s in services} == {"pipeline", "live", "retired"}
    mes = next(s for s in services if s["name"].startswith("MES"))
    assert mes["sla_targets"][0] == {"priority": 1, "response_min": 10, "resolution_min": 120, "is_exception": True}
    assert mes["provider_name"] == "Plant IT (each plant)" and mes["support_hours"] == "24x7"
    assert len(client.get("/services?lifecycle=live", headers=sqm).json()) == 11


def test_new_sla_targets_only_apply_to_new_tickets(client, sqm):
    sid = service_id(client, sqm, "Backup")
    old = client.get(f"/tickets?service_id={sid}&priority=4&size=1", headers=sqm).json()["items"][0]
    body = {"sla_overrides": [{"priority": 4, "response_min": 60, "resolution_min": 600}], "criticality": "high"}
    updated = client.patch(f"/services/{sid}", json=body, headers=sqm).json()
    assert updated["sla_targets"][3]["resolution_min"] == 600 and updated["criticality"] == "high"
    still = client.get(f"/tickets/{old['id']}", headers=sqm).json()
    assert still["resolution_target_min"] == old["resolution_target_min"] == 2400  # frozen at creation
    reset = client.patch(f"/services/{sid}", json={"sla_overrides": []}, headers=sqm).json()
    assert reset["sla_targets"][3] == {
        "priority": 4,
        "response_min": 480,
        "resolution_min": 2400,
        "is_exception": False,
    }


def test_sla_override_validation(client, sqm):
    sid = service_id(client, sqm, "Backup")
    wrong = {"sla_overrides": [{"priority": 1, "response_min": 300, "resolution_min": 200}]}
    assert client.patch(f"/services/{sid}", json=wrong, headers=sqm).status_code == 422
    twice = {"sla_overrides": [{"priority": 1, "response_min": 5, "resolution_min": 60}] * 2}
    assert client.patch(f"/services/{sid}", json=twice, headers=sqm).status_code == 422
    assert client.patch("/services/999", json={"criticality": "low"}, headers=sqm).status_code == 404


def test_running_month_report_shows_overdue_actions(client, sqm):
    report = client.get("/reports/monthly?month=2026-11", headers=sqm).json()
    assert report["is_partial"] is True
    assert len(report["improvements"]["overdue"]) == 2
    assert any("overdue improvement" in a for a in report["next_actions"])
