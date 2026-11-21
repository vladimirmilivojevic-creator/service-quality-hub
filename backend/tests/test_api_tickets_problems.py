"""Tickets (SLA clock, status changes), problem candidates and problem records."""

from tests.conftest import plant_id


def test_ticket_list_and_filters(client, sqm):
    page = client.get("/tickets?size=5", headers=sqm).json()
    assert len(page["items"]) == 5 and page["total"] > 3000
    assert {t["type"] for t in page["items"]} <= {"incident", "request"}
    p1 = client.get("/tickets?priority=1&type=incident&size=200", headers=sqm).json()["items"]
    assert p1 and all(t["priority"] == 1 for t in p1)
    found = client.get("/tickets?q=line 3", headers=sqm).json()["items"]
    assert any("line 3" in t["title"] for t in found)
    october = client.get("/tickets?month=2026-10&breached=true&size=200", headers=sqm).json()["items"]
    assert october and all(t["response_breached"] or t["resolution_breached"] for t in october)
    assert all(t["created_at"].startswith("2026-10") for t in october)


def test_open_tickets_have_a_live_sla_clock(client, sqm):
    risky = client.get("/tickets?sla=at_risk,breached", headers=sqm).json()
    assert risky["total"] >= 4
    first = risky["items"][0]
    assert first["resolution_status"] == "breached"  # breached ones come first
    illerau = [t for t in risky["items"] if t["plant_code"] == "ILL" and "budget" in t["title"]]
    assert illerau and illerau[0]["resolution_elapsed_min"] > illerau[0]["resolution_target_min"]


def test_ticket_detail_shows_targets_and_links(client, sqm):
    incident = client.get("/tickets?q=Goods receipt booking fails&type=incident", headers=sqm).json()["items"][0]
    detail = client.get(f"/tickets/{incident['id']}", headers=sqm).json()
    assert detail["priority"] == 2 and detail["resolution_target_min"] == 480
    assert detail["problem"]["title"].startswith("ERP release 26.10")
    assert detail["caused_by_change"]["outcome"] == "caused_incident"
    assert detail["support_hours_label"].startswith("Shift hours")
    assert client.get("/tickets/999999", headers=sqm).status_code == 404


def _new_open_ticket(client, headers, plant_code: str = "INN") -> dict:
    pid = plant_id(client, headers, plant_code)
    return client.get(f"/tickets?plant_id={pid}&open=true&size=200", headers=headers).json()["items"]


def test_status_flow_pending_resolve_reopen(client, plant_lead):
    ticket = next(t for t in _new_open_ticket(client, plant_lead) if t["status"] in ("New", "In progress"))
    url = f"/tickets/{ticket['id']}"
    assert client.patch(url, json={"status": "Pending"}, headers=plant_lead).json()["pending_since"]
    resolved = client.patch(url, json={"status": "Resolved"}, headers=plant_lead).json()
    assert resolved["resolved_at"] and resolved["first_response_at"]
    assert resolved["resolution_business_min"] is not None and resolved["resolution_breached"] is not None
    reopened = client.patch(url, json={"status": "In progress"}, headers=plant_lead).json()
    assert reopened["reopen_count"] == ticket["reopen_count"] + 1 and reopened["resolved_at"] is None
    closed = client.patch(url, json={"status": "Closed", "title": "Fixed for good"}, headers=plant_lead).json()
    assert closed["closed_at"] and closed["title"] == "Fixed for good"


def test_problems_and_changes_are_not_edited_as_tickets(client, sqm):
    problem = client.get("/problems", headers=sqm).json()[0]
    assert client.patch(f"/tickets/{problem['id']}", json={"status": "Closed"}, headers=sqm).status_code == 409


def test_problem_candidates_from_the_stories(client, sqm):
    candidates = client.get("/problems/candidates", headers=sqm).json()
    groups = {(c["plant_code"], c["category"]) for c in candidates}
    assert ("RHV", "VPN") in groups and ("VVD", "Battery") in groups
    assert all(c["count"] >= 3 for c in candidates)


def test_create_problem_links_incidents_and_removes_the_candidate(client, sqm):
    candidate = next(c for c in client.get("/problems/candidates", headers=sqm).json() if c["category"] == "VPN")
    ids = [i["id"] for i in candidate["incidents"]]
    response = client.post("/problems", json={"incident_ids": ids, "title": candidate["suggested_title"]}, headers=sqm)
    assert response.status_code == 201
    problem = response.json()
    assert problem["type"] == "problem" and problem["problem_status"] == "investigating"
    assert problem["key"].startswith("PRB-") and len(problem["linked"]) == len(ids)
    remaining = {(c["plant_code"], c["category"]) for c in client.get("/problems/candidates", headers=sqm).json()}
    assert ("RHV", "VPN") not in remaining
    again = client.post("/problems", json={"incident_ids": ids}, headers=sqm)
    assert again.status_code == 409


def test_problem_rules(client, sqm, plant_lead):
    candidate = next(c for c in client.get("/problems/candidates", headers=sqm).json() if c["category"] == "Battery")
    ids = [i["id"] for i in candidate["incidents"]]
    assert client.post("/problems", json={"incident_ids": ids}, headers=plant_lead).status_code == 403  # other plant
    problem = client.post("/problems", json={"incident_ids": ids}, headers=sqm).json()
    url = f"/problems/{problem['id']}"
    assert client.patch(url, json={"problem_status": "known_error"}, headers=sqm).status_code == 409
    known = client.patch(url, json={"problem_status": "known_error", "workaround": "Swap batteries"}, headers=sqm)
    assert known.status_code == 200 and known.json()["problem_status"] == "known_error"
    assert client.patch(url, json={"problem_status": "resolved"}, headers=sqm).status_code == 409
    done = client.patch(url, json={"problem_status": "resolved", "root_cause": "Old batteries"}, headers=sqm).json()
    assert done["status"] == "Closed" and done["resolved_at"]
    assert client.get(url, headers=sqm).json()["root_cause"] == "Old batteries"


def test_problem_validation(client, sqm):
    assert client.post("/problems", json={"incident_ids": [999999]}, headers=sqm).status_code == 404
    requests = client.get("/tickets?type=request&size=1", headers=sqm).json()["items"]
    assert client.post("/problems", json={"incident_ids": [requests[0]["id"]]}, headers=sqm).status_code == 409
    inn = client.get("/tickets?type=incident&q=MES terminal&size=50", headers=sqm).json()["items"]
    unlinked = [t for t in inn if t["problem_id"] is None]
    other = client.get("/tickets?type=incident&q=VPN drops after&size=5", headers=sqm).json()["items"]
    if unlinked and other:
        mixed = client.post("/problems", json={"incident_ids": [unlinked[0]["id"], other[0]["id"]]}, headers=sqm)
        assert mixed.status_code == 409
    listed = client.get("/problems", headers=sqm).json()
    mes = next(p for p in listed if "MES terminal freezes" in p["title"])
    assert mes["incident_count"] == 4 and mes["problem_status"] == "resolved"
    assert client.get(f"/problems/{inn[0]['id']}", headers=sqm).status_code == 404
