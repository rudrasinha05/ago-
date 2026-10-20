"""Real PostgreSQL evidence and tenant-bound visibility for ongoing company growth."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "company_market_watch.py"
SPEC = spec_from_file_location("company_market_watch_pg", SCRIPT)
market = module_from_spec(SPEC)
SPEC.loader.exec_module(market)

FEED = b"""<rss version="2.0"><channel>
<item><title>Small business invoice fraud security automation</title>
<link>https://example.org/report/market-need</link>
<description>Compliance and privacy workflow for customer billing</description>
<pubDate>Tue, 20 Oct 2026 12:00:00 GMT</pubDate>
</item></channel></rss>"""


def test_source_ingestion_ceo_ownership_founder_gate_and_tenant_isolation(case, monkeypatch):
    client, headers, info = case
    founder = headers["founder"]
    dep = department(client, founder)
    ceo = post(client, "/v1/organization/employees", founder, {
        "department_id": dep, "name": "CEO", "kind": "ai",
    })["id"]
    monkeypatch.setattr(market, "retrieve_feed", lambda url: FEED)
    uri = market.FEEDS[1][2]
    first = market.ingest(info["db"], info["tenant"], "hacker-news", "news", uri)
    repeated = market.ingest(info["db"], info["tenant"], "hacker-news", "news", uri)
    assert first["new_evidence"] == 1 and first["status"] == "ok"
    assert repeated["new_evidence"] == 0
    assert market.nominate_for_founder_review(info["db"], info["tenant"]) == 1
    assert market.nominate_for_founder_review(info["db"], info["tenant"]) == 0

    response = client.get("/v1/organization/company/market-intelligence", headers=founder)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["signal_total"] == 1
    item = data["signals"][0]
    assert item["review_status"] == "shortlisted"
    assert item["executive_owner_name"] == "CEO"
    assert item["source_url"] == "https://example.org/report/market-need"
    assert item["evidence_level"] == "unvalidated_signal"
    assert item["approval_status"] == "pending"
    assert data["claimed_verified_revenue"] is False

    inbox = client.get("/v1/organization/company/approvals", headers=founder).json()
    nominated = next(a for a in inbox if str(a["market_signal_id"]) == str(item["id"]))
    assert nominated["approval_type"] == "market_signal_review"
    assert nominated["market_signal_source"] == "hacker-news"
    assert nominated["market_signal_score"] >= 55
    assert str(nominated["requester_id"]) == ceo
    post(client, "/v1/governance/approvals/"+str(item["approval_id"])+"/decision",
         headers["reviewer"], {"approve": True, "reason": "I am not the founder"}, expected=403)

    from ago.bootstrap import bootstrap
    other, _ = bootstrap(info["db"], organization="Another growth tenant",
                         email="another-growth@example.test",
                         password="test-grow-password-12345")
    other_headers = info["login"]("another-growth@example.test",
                                   "test-grow-password-12345", other)
    isolated = client.get("/v1/organization/company/market-intelligence",
                          headers=other_headers)
    assert isolated.status_code == 200
    assert isolated.json()["signal_total"] == 0


def test_pageable_project_details_and_other_tenant_restriction(case):
    client, headers, info = case
    founder = headers["founder"]
    brief = "Build a well-tested education enquiry dashboard with verified business milestones"
    created = post(client, "/v1/organization/company/projects/start", founder, {
        "brief": brief, "operation_key": str(uuid4()),
    })
    detail = client.get("/v1/organization/company/projects/"+created["id"], headers=founder)
    assert detail.status_code == 200, detail.text
    project = detail.json()
    assert brief in project["brief"]
    assert project["status_label"] == "under_process"
    assert project["verified_market_release"] is False
    assert len(project["stages"]) == 5
    assert all(stage["task_status"] is None for stage in project["stages"])
    listing = client.get("/v1/organization/company/projects?limit=1&offset=0",headers=founder)
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == created["id"]
    assert client.get("/v1/organization/company/projects?limit=1&offset=1",
                      headers=founder).json() == []
    assert client.get("/v1/organization/company/projects/"+str(uuid4()),
                      headers=founder).status_code == 404
