"""Jira Service Management CSV import, the demo simulator and the demo reset."""

import pytest

from tests.conftest import SAMPLES

SAMPLE = SAMPLES / "jsm_export_sample.csv"


def upload(client, headers, content: bytes, path: str = "/imports/jsm", **params):
    return client.post(path, headers=headers, params=params, files={"file": ("export.csv", content, "text/csv")})


def test_preview_maps_rows_and_explains_skipped_ones(client, sqm):
    preview = upload(client, sqm, SAMPLE.read_bytes(), "/imports/jsm/preview").json()
    assert preview["total_rows"] == 27 and preview["valid_rows"] == 24
    first = preview["rows"][0]
    assert first["key"] == "ITSD-1" and first["plant_code"] == "INN" and first["priority"] == 2
    assert first["service_name"].startswith("MES")
    reasons = [s["message"] for s in preview["skipped"]]
    assert any("no plant found" in r for r in reasons)
    assert any("'Task' is not imported" in r for r in reasons)
    assert any("cannot read the date '31/Nov/26" in r for r in reasons)
    assert preview["detected"]["first response"].endswith("Date of First Response)")


def test_import_is_idempotent(client, sqm):
    first = upload(client, sqm, SAMPLE.read_bytes()).json()
    assert (first["created"], first["updated"], len(first["skipped"])) == (24, 0, 3)
    second = upload(client, sqm, SAMPLE.read_bytes()).json()
    assert (second["created"], second["updated"]) == (0, 24)
    imported = client.get("/tickets?q=ITSD-&size=200", headers=sqm).json()["items"]
    assert len(imported) == 22  # incidents and requests; the problem and the change are on their own pages
    wan = next(t for t in imported if t["key"] == "ITSD-4")
    assert wan["source"] == "jsm_import" and wan["provider_name"] == "AlpNet Carrier"
    assert wan["priority"] == 1 and wan["resolution_breached"] is True  # our engine: 6 h 15 min > 4 h
    assert "Time to resolution: Breached" in wan["source_sla_note"]
    pending = next(t for t in imported if t["key"] == "ITSD-18")
    assert pending["status"] == "Pending" and pending["resolved_at"] is None


def test_reimport_with_new_priority_updates_the_targets(client, sqm):
    upload(client, sqm, SAMPLE.read_bytes())
    changed = SAMPLE.read_text(encoding="utf-8").replace(
        "ITSD-6,10006,[System] Incident,Resolved,ITSD,Valdora IT Service Desk (Demo),service_desk,Medium",
        "ITSD-6,10006,[System] Incident,Resolved,ITSD,Valdora IT Service Desk (Demo),service_desk,High",
    )
    upload(client, sqm, changed.encode())
    ticket = client.get("/tickets?q=ITSD-6", headers=sqm).json()["items"][0]
    assert ticket["priority"] == 2 and ticket["resolution_target_min"] == 480


def test_excel_style_csv_semicolon_and_windows_encoding(client, sqm):
    text = SAMPLE.read_text(encoding="utf-8").replace(",", ";").replace("Wi-Fi in hall 4", "Wi-Fi in Halle 4 (Störung)")
    preview = upload(client, sqm, text.encode("cp1252"), "/imports/jsm/preview").json()
    assert preview["valid_rows"] == 24
    assert any("Störung" in r["title"] for r in preview["rows"])


def test_site_column_and_repeated_labels(client, sqm):
    csv = (
        "Summary,Issue key,Issue Type,Status,Priority,Created,Resolved,Labels,Labels,Labels,Custom field (Site)\n"
        "Line down,ABC-1,Incident,Done,Highest,2026-11-10 08:00,2026-11-10 10:00,urgent,night,wan,Rhinval\n"
        "No priority,ABC-2,Service request,Open,Whatever,2026-11-10 08:00,,account,,,ILL\n"
    )
    preview = upload(client, sqm, csv.encode(), "/imports/jsm/preview").json()
    rows = {r["key"]: r for r in preview["rows"]}
    assert rows["ABC-1"]["plant_code"] == "RHV" and rows["ABC-1"]["service_name"] == "WAN connectivity"
    assert rows["ABC-2"]["priority"] == 3 and rows["ABC-2"]["status"] == "New"
    assert any("no known priority" in w for w in preview["warnings"])
    assert any("no first-response date" in w for w in preview["warnings"])


@pytest.mark.parametrize(
    ("content", "status", "message"),
    [
        (b"", 422, "empty"),
        (b"a,b\n1,2\n", 422, "does not look like a Jira export"),
    ],
)
def test_bad_files(client, sqm, content, status, message):
    response = upload(client, sqm, content, "/imports/jsm/preview")
    assert response.status_code == status and message in response.json()["detail"]


def test_file_size_limit_and_role(client, sqm, plant_lead):
    big = b"x" * (5 * 1024 * 1024 + 10)
    assert upload(client, sqm, big, "/imports/jsm/preview").status_code == 413
    assert upload(client, plant_lead, SAMPLE.read_bytes()).status_code == 403


def test_unknown_timezone(client, sqm):
    response = upload(client, sqm, SAMPLE.read_bytes(), "/imports/jsm/preview", timezone="Mars/Olympus")
    assert response.status_code == 422


def test_simulate_next_day_moves_the_clock_and_creates_activity(client, sqm):
    before = client.get("/tickets?size=1", headers=sqm).json()["total"]
    result = client.post("/simulate/next-day", headers=sqm).json()
    assert result["demo_now"].startswith("2026-11-19T09:00")
    assert result["created"] > 5 and result["resolved"] > 0
    assert client.get("/tickets?size=1", headers=sqm).json()["total"] > before
    assert client.get("/demo/clock").json()["simulated_days"] == 1
    simulated = client.get("/tickets?q=Outlook search does not find&size=5", headers=sqm).json()["items"]
    assert simulated and simulated[0]["source"] == "simulated"


def test_recurring_issue_becomes_a_candidate_after_three_days(client, sqm):
    for _ in range(3):
        client.post("/simulate/next-day", headers=sqm)
    candidates = client.get("/problems/candidates", headers=sqm).json()
    assert any(c["plant_code"] == "ILL" and c["category"] == "Mailbox" for c in candidates)


def test_simulation_is_deterministic_and_reset_returns_to_start(client, sqm):
    first = client.post("/simulate/next-day", headers=sqm).json()
    reset = client.post("/demo/reset", headers=sqm).json()
    assert reset["demo_now"].startswith("2026-11-18T09:00")
    again = client.post("/simulate/next-day", headers=sqm).json()
    assert {k: first[k] for k in ("created", "resolved", "changes")} == {
        k: again[k] for k in ("created", "resolved", "changes")
    }
