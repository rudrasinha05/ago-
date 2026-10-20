"""AGO continuous evidence radar: bounded RSS research, not an autonomous sales bot.

Launch from apps/backend with migrated local PostgreSQL:
 python ../../scripts/company_market_watch.py --tenant-id UUID --once
 python ../../scripts/company_market_watch.py --tenant-id UUID --interval-seconds 3600

Feeds are fixed HTTPS endpoints; untrusted article text is data, never agent
instructions. No linked article is fetched; no emails, posts or purchases occur.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import unescape
import json
import os
import re
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
from uuid import UUID, uuid4
import xml.etree.ElementTree as ET

import psycopg
from psycopg.rows import dict_row

from ago.governance import ApprovalRepository
from ago.local_ops import local_database

# Explicit sources: publication feed, technology news, peer-reviewed? arXiv is
# PREPRINT research, not peer-reviewed by default. Never treat it as validation.
FEEDS = (
    ("arxiv-cs-ai", "research", "https://rss.arxiv.org/rss/cs.AI"),
    ("hacker-news", "news", "https://news.ycombinator.com/rss"),
    ("guardian-tech", "article", "https://www.theguardian.com/technology/rss"),
)
MAX_BYTES = 1_000_000
MAX_ITEMS_PER_FEED = 70
MAX_SUMMARY = 700
MAX_NEW_NOMINATIONS_WEEKLY = 3
TERM_WEIGHTS = {
    "security": 9, "privacy": 8, "compliance": 12, "fraud": 12,
    "workflow": 8, "automation": 6, "billing": 12, "customer": 8,
    "accessibility": 10, "education": 7, "assessment": 10,
    "healthcare": 5, "small business": 14, "reliability": 9,
    "monitoring": 7, "invoice": 12, "admission": 12, "scheduling": 8,
    "cost": 6, "industry": 4, "tool": 3, "ai": 2,
}
CUSTOMERS = (
    (("school", "student", "education", "admission", "assessment"), "Educational institutions"),
    (("hospital", "healthcare", "patient", "clinic"), "Healthcare service providers"),
    (("retail", "small business", "customer", "merchant"), "Small businesses"),
    (("developer", "security", "software", "api"), "Software teams"),
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Source feed redirects are not trusted")


def _tag(node) -> str:
    return node.tag.split("}")[-1].lower()


def _child(node, name: str) -> str:
    for item in node:
        if _tag(item) == name:
            return "".join(item.itertext()).strip()
    return ""


def clean_text(value: str, limit: int) -> str:
    value = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()[:limit]


def normalized_url(value: str) -> str | None:
    try:
        p = urlsplit(value.strip())
        if p.scheme.lower() != "https" or not p.hostname or p.username or p.password:
            return None
        if p.port not in (None, 443):
            return None
        return urlunsplit(("https", p.netloc.lower(), p.path or "/", p.query, ""))
    except (ValueError, AttributeError):
        return None


def published_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if dt > datetime.now(timezone.utc):
        return None
    return dt.astimezone(timezone.utc)


def score_signal(title: str, excerpt: str, kind: str) -> tuple[int, str, str]:
    """Rule-based relevance, explicitly *not* a verified market-demand estimate."""
    text = (title + " " + excerpt[:300]).lower()
    found = [(term, weight) for term, weight in TERM_WEIGHTS.items()
             if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)]
    score = min(100, 9 + sum(weight for _, weight in found) + (5 if kind == "research" else 0))
    customer = next((segment for terms, segment in CUSTOMERS
                     if any(term in text for term in terms)), "Customer segment unvalidated")
    basis = "Keyword heuristic: " + (", ".join(term for term, _ in found) or "none")
    return score, basis, customer


def parse_feed(xml_data: bytes, source_name: str, source_kind: str) -> list[dict]:
    if len(xml_data) > MAX_BYTES or b"<!DOCTYPE" in xml_data.upper() or b"<!ENTITY" in xml_data.upper():
        raise ValueError("Untrusted or oversized feed XML")
    root = ET.fromstring(xml_data)
    items = [n for n in root.iter() if _tag(n) in ("item", "entry")]
    seen, records = set(), []
    for item in items[:MAX_ITEMS_PER_FEED]:
        title = clean_text(_child(item, "title"), 350)
        link = _child(item, "link")
        if not link:
            link = next((x.get("href", "") for x in item
                         if _tag(x) == "link" and x.get("href")), "")
        link = normalized_url(link)
        if len(title) < 8 or not link or link in seen:
            continue
        seen.add(link)
        excerpt = clean_text(_child(item, "description") or
                             _child(item, "summary") or _child(item, "content"), MAX_SUMMARY)
        date = published_date(_child(item, "pubdate") or
                              _child(item, "published") or _child(item, "updated"))
        score, basis, customer = score_signal(title, excerpt, source_kind)
        records.append(dict(source_name=source_name, source_kind=source_kind,
                            source_url=link, url_digest=sha256(link.encode()).hexdigest(),
                            title=title, excerpt=excerpt, published_at=date,
                            opportunity_score=score, score_basis=basis,
                            potential_customer=customer))
    return records


def retrieve_feed(url: str) -> bytes:
    if url not in {feed_url for _, _, feed_url in FEEDS}:
        raise ValueError("Source URL not allowlisted")
    req = Request(url, headers={"User-Agent": "AGO-Research-Radar/1.0 (RSS-only)",
                                "Accept": "application/rss+xml, application/atom+xml, application/xml"})
    with build_opener(NoRedirect()).open(req, timeout=12) as response:
        if response.status != 200:
            raise ValueError("Source HTTP status not successful")
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Source feed too large")
    return payload


def ingest(db, tenant_id: str, source: str, kind: str, url: str) -> dict:
    try:
        data = parse_feed(retrieve_feed(url), source, kind)
        with db.transaction():
            count = 0
            for item in data:
                row = db.execute("""
                    INSERT INTO ago_market_signals
                     (id,tenant_id,source_name,source_kind,source_url,url_digest,
                      title,excerpt,potential_customer,opportunity_score,
                      score_basis,published_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (tenant_id,url_digest) DO NOTHING RETURNING id
                """, (str(uuid4()), tenant_id, item["source_name"], item["source_kind"],
                      item["source_url"], item["url_digest"], item["title"], item["excerpt"],
                      item["potential_customer"], item["opportunity_score"],
                      item["score_basis"], item["published_at"])).fetchone()
                count += bool(row)
            db.execute("""INSERT INTO ago_growth_scan_runs
                (tenant_id,source_name,outcome,ingested_count)
                VALUES (%s,%s,'ok',%s)""", (tenant_id, source, count))
        return {"source": source, "status": "ok", "new_evidence": count}
    except (ET.ParseError, ValueError, OSError, TimeoutError, psycopg.Error) as exc:
        # No exception message: HTTP errors, credentials or feed contents are not audit data.
        with db.transaction():
            db.execute("""INSERT INTO ago_growth_scan_runs
                (tenant_id,source_name,outcome,error_class)
                VALUES (%s,%s,'degraded',%s)""", (tenant_id, source, type(exc).__name__))
        return {"source": source, "status": "degraded", "error_type": type(exc).__name__}


def nominate_for_founder_review(db, tenant_id: str) -> int:
    """CEO accountability + deterministic shortlist, *not* AI CEO independent judgement.

    A proposal is not a new approved project. The real founder must approve and
    plan/delegate before any execution; one weekly cap prevents notification spam.
    """
    with db.transaction():
        db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (tenant_id,))
        owner = db.execute("""
            SELECT id FROM ago_employees WHERE tenant_id=%s AND kind='ai' AND
              (lower(trim(coalesce(role_title,''))) IN ('ceo','chief executive officer')
               OR lower(trim(name))='ceo')
            ORDER BY id LIMIT 1
        """, (tenant_id,)).fetchone()
        if owner is None:
            return 0
        count = db.execute("""
            SELECT COUNT(*) AS total FROM ago_market_signals
            WHERE tenant_id=%s AND review_status='shortlisted'
              AND discovered_at >= date_trunc('week',now())
        """, (tenant_id,)).fetchone()["total"]
        quota = max(0, MAX_NEW_NOMINATIONS_WEEKLY - count)
        if quota == 0:
            return 0
        rows = db.execute("""
            SELECT id FROM ago_market_signals
            WHERE tenant_id=%s AND review_status='discovered'
              AND opportunity_score >= 55
              AND (published_at IS NULL OR published_at >= now()-interval '30 days')
            ORDER BY opportunity_score DESC,discovered_at DESC,id
            LIMIT %s FOR UPDATE SKIP LOCKED
        """, (tenant_id, quota)).fetchall()
        for row in rows:
            proposal = ApprovalRepository(db).propose(
                tenant_id=tenant_id,
                action="company:market-signal:" + str(row["id"]),
                requester_id=str(owner["id"]),
            )
            db.execute("""
                UPDATE ago_market_signals
                SET executive_owner_id=%s,review_status='shortlisted',approval_id=%s
                WHERE tenant_id=%s AND id=%s AND review_status='discovered'
            """, (owner["id"], proposal.request_id, tenant_id, row["id"]))
        return len(rows)


def prepare_marketing_drafts(db, tenant_id: str) -> int:
    """Only truthful drafts for active approved projects; no external posting."""
    with db.transaction():
        rows = db.execute("""
            SELECT i.id,i.title FROM ago_founder_intakes i
            JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
            WHERE i.tenant_id=%s AND p.status='active'
            ORDER BY i.created_at DESC LIMIT 50
        """, (tenant_id,)).fetchall()
        created = 0
        for project in rows:
            title = clean_text(project["title"], 220)
            if not title:
                continue
            for platform in ("linkedin", "x", "instagram", "facebook"):
                body = (f"Building in progress: {title}. We are evaluating needs, "
                        "accessibility and quality before any public release. "
                        "This is a development update, not a product launch or customer offer.")
                inserted = db.execute("""
                    INSERT INTO ago_marketing_drafts
                      (id,tenant_id,project_id,platform,draft_text)
                    VALUES (%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,project_id,platform)
                    DO NOTHING RETURNING id
                """, (str(uuid4()), tenant_id, project["id"], platform, body)).fetchone()
                created += bool(inserted)
        return created


def cycle(dsn: str, tenant_id: str) -> dict:
    with psycopg.connect(dsn, row_factory=dict_row, autocommit=True, connect_timeout=5) as db:
        results = [ingest(db, tenant_id, name, kind, url) for name, kind, url in FEEDS]
        nominated = nominate_for_founder_review(db, tenant_id)
        drafts = prepare_marketing_drafts(db, tenant_id)
        return {"sources": results, "nominated_for_founder": nominated,
                "marketing_drafts_created": drafts, "checked_at": datetime.now(timezone.utc).isoformat(),
                "published_posts": 0, "verified_revenue_inr": None}


def watch(dsn: str, tenant_id: str, once: bool, interval: int) -> int:
    while True:
        try:
            result = cycle(dsn, tenant_id)
            degraded = any(src["status"] == "degraded" for src in result["sources"])
            print(json.dumps({"status": "degraded" if degraded else "ok", **result},
                             sort_keys=True), flush=True)
        except (psycopg.Error, OSError) as exc:
            degraded = True
            print(json.dumps({"status": "degraded", "error_type": type(exc).__name__,
                              "checked_at": datetime.now(timezone.utc).isoformat()},
                             sort_keys=True), flush=True)
        if once:
            return 1 if degraded else 0
        time.sleep(min(interval, 60) if degraded else interval)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AGO continuous market signals (local only)")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    tenant_id = str(UUID(args.tenant_id))
    if not 900 <= args.interval_seconds <= 86400:
        parser.error("Market research interval must be between 900 and 86400 seconds")
    dsn = os.getenv("AGO_POSTGRES_DSN", "")
    if (os.getenv("AGO_ENVIRONMENT", "development") not in ("development", "test", "testing")
            or not local_database(dsn)):
        parser.error("Only local development/test PostgreSQL is supported")
    return watch(dsn, tenant_id, args.once, args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
