"""KPIs, plant comparison and supplier scorecards on the seeded demo data.

The seed is deterministic, so these numbers are fixed. They also document the built-in stories.
"""

from tests.conftest import plant_id, provider_id, service_id


def kpi(summary: dict, key: str) -> dict:
    return next(card for card in summary["kpis"] if card["key"] == key)


def test_october_kpis_match_the_stories(client, sqm):
    summary = client.get("/kpis?month=2026-10", headers=sqm).json()
    assert summary["is_partial"] is False
    assert kpi(summary, "sla_resolution")["value"] == 95.4
    assert kpi(summary, "sla_resolution")["rag"] == "green"
    assert kpi(summary, "sla_response")["rag"] == "green"
    # Story 4: the failed ERP release pulls the change success rate below 95 %.
    assert kpi(summary, "change_success")["value"] == 90.0
    assert kpi(summary, "change_success")["rag"] == "amber"
    assert kpi(summary, "change_success")["previous"] == 98.3
    # Story 5: four old requests at Illerau.
    backlog = kpi(summary, "backlog_over_30")
    assert backlog["value"] == 4 and backlog["rag"] == "amber"
    assert sum(backlog["detail"]["buckets"].values()) == backlog["detail"]["open"]
    mttr = kpi(summary, "mttr")
    assert set(mttr["detail"]["by_priority"]) <= {"1", "2", "3", "4"} and mttr["detail"]["median"] is not None


def test_default_month_is_the_running_month(client, sqm):
    summary = client.get("/kpis", headers=sqm).json()
    assert summary["month"] == "2026-11" and summary["is_partial"] is True


def test_trend_has_six_months(client, sqm):
    trend = client.get("/kpis/trend?month=2026-10", headers=sqm).json()
    assert trend["months"] == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    assert len(trend["series"]["sla_resolution"]) == 6
    assert trend["series"]["sla_resolution"][4] == 94.5  # September: AlpNet and Printwise


def test_filters_by_plant_and_service(client, sqm):
    sal, printing = plant_id(client, sqm, "SAL"), service_id(client, sqm, "Printing")
    september = client.get(f"/kpis?month=2026-09&plant_id={sal}&service_id={printing}", headers=sqm).json()
    october = client.get(f"/kpis?month=2026-10&plant_id={sal}&service_id={printing}", headers=sqm).json()
    # Story 3: label printers in September (no spares) vs October (spare printers on site).
    assert kpi(september, "mttr")["value"] == 18.3
    assert kpi(october, "mttr")["value"] == 1.4
    assert kpi(october, "sla_resolution")["value"] == 100.0


def test_reopen_story_at_rhinval(client, sqm):
    rhv, workplace = plant_id(client, sqm, "RHV"), service_id(client, sqm, "Workplace")
    summary = client.get(f"/kpis?month=2026-09&plant_id={rhv}&service_id={workplace}", headers=sqm).json()
    assert kpi(summary, "reopen_rate")["value"] == 15.0
    assert kpi(summary, "reopen_rate")["rag"] == "red"


def test_by_plant_table(client, sqm):
    rows = client.get("/kpis/by-plant?month=2026-10", headers=sqm).json()
    assert [r["plant_code"] for r in rows] == ["INN", "SAL", "ILL", "RHV", "VVD"]
    by_code = {r["plant_code"]: r for r in rows}
    assert by_code["ILL"]["values"]["backlog_over_30"] == 4
    assert by_code["VVD"]["rag"]["sla_resolution"] == "red"  # the WAN story hits Vale Verde


def test_scorecards_compare_internal_and_external_providers(client, sqm):
    data = client.get("/suppliers?month=2026-10", headers=sqm).json()
    rows = {r["short_name"]: r for r in data["rows"]}
    assert [r["kind"] for r in data["rows"]][:2] == ["central", "plant_it"]
    assert rows["VIS"]["agreement"] == "OLA" and rows["ALPNET"]["agreement"] == "Contract"
    # Story 1: AlpNet misses its 97 % contract target.
    assert rows["ALPNET"]["resolution_compliance"] == 68.8
    assert rows["ALPNET"]["rag"] == "red" and rows["ALPNET"]["target_pct"] == 97.0
    assert rows["ALPNET"]["top_breach_services"][0]["service"] == "WAN connectivity"
    assert rows["PRINTWISE"]["rag"] == "green" and rows["PRINTWISE"]["trend"] == "up"


def test_september_scorecards(client, sqm):
    rows = {r["short_name"]: r for r in client.get("/suppliers?month=2026-09", headers=sqm).json()["rows"]}
    assert rows["ALPNET"]["resolution_compliance"] == 69.6
    assert rows["PRINTWISE"]["resolution_compliance"] == 77.6 and rows["PRINTWISE"]["rag"] == "red"


def test_scorecard_detail(client, sqm):
    alpnet = provider_id(client, sqm, "ALPNET")
    detail = client.get(f"/suppliers/{alpnet}/scorecard?month=2026-10", headers=sqm).json()
    assert detail["scorecard"]["short_name"] == "ALPNET"
    assert [row["month"] for row in detail["trend"]][-2:] == ["2026-09", "2026-10"]
    assert detail["breaches"] and all(b["provider_name"] == "AlpNet Carrier" for b in detail["breaches"])
    assert any("AlpNet" in i["title"] for i in detail["improvements"])
    assert client.get("/suppliers/999/scorecard", headers=sqm).status_code == 404


def test_changes_page(client, sqm):
    data = client.get("/changes?month=2026-10", headers=sqm).json()
    assert data["success_rate"] == 90.0 and data["rag"] == "amber"
    failed = [c for c in data["items"] if c["outcome"] == "caused_incident"]
    assert any("ERP release 26.10" in c["title"] for c in failed)
    erp = next(c for c in failed if "ERP release 26.10" in c["title"])
    detail = client.get(f"/tickets/{erp['id']}", headers=sqm).json()
    assert len(detail["linked"]) == 3  # three P2 incidents on Monday morning
    rhv = plant_id(client, sqm, "RHV")
    assert all(
        c["plant_code"] == "RHV"
        for c in client.get(f"/changes?month=2026-10&plant_id={rhv}", headers=sqm).json()["items"]
    )
    scheduled = client.get("/changes?month=2026-11&outcome=successful", headers=sqm).json()
    assert all(c["outcome"] == "successful" for c in scheduled["items"])
