#!/usr/bin/env python3
"""Live smoke of the deployed SQL demo: every view, plus each card's own SQL, read-only.

    python scripts/live_smoke.py                       # https://sql.aito.ai
    python scripts/live_smoke.py --base http://localhost:8700

Fails when a view errors OR comes back hollow. Board td-20260929184223822327:
three handlers here turn a failed query into a quiet result (explore's
levers=[] on a failed recommend, patterns dropping a pattern whose count query
failed, a GROUP BY failure becoming n=None), and the map and patterns pages
are served from files and a startup cache, so a broken query could hide for a
long time. This asserts what a visitor sees is full.

Read-only: GETs, plus POST /api/sql with the SELECT drafts the cards
themselves offer. That endpoint is backed by Aito's read-only `_sql`, which
refuses writes and DDL. The demo's key is read-only too.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

LIVE_BASE = "https://sql.aito.ai"
SLOW_SECONDS = 20.0


def fetch(base: str, path: str, timeout: float, sql: str | None = None) -> Any:
    req = urllib.request.Request(base + path, data=None if sql is None else sql.encode(),
                                 method="POST" if sql is not None else "GET",
                                 headers={"user-agent": "sql-live-smoke", "content-type": "text/plain"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def check_health(body: dict) -> str:
    assert body.get("aito_connected") is True, f"Aito unreachable: {body}"
    return "Aito reachable"


def check_cards(body: dict) -> str:
    cards = body.get("cards") or []
    assert cards, "no cards"
    return f"{len(cards)} cards"


def check_overview(body: dict) -> str:
    counts = body.get("counts") or {}
    empty = [k for k, v in counts.items() if not v]
    assert counts and not empty, f"overview counts empty: {counts}"
    assert body.get("base_churn"), "no base churn"
    return ", ".join(f"{k} {v}" for k, v in counts.items())


def check_card(body: dict) -> str:
    """One insight card: its KPI, the causes behind it (each with a count), and
    the levers. A GROUP BY failure shows up as n=None; a failed recommend as []."""
    key = body.get("key")
    assert body.get("churn") is not None and body.get("base_churn") is not None, f"{key}: no KPI"
    causes = body.get("causes") or []
    assert causes, f"{key}: no causes"
    uncounted = [c.get("value") for c in causes if c.get("n") is None]
    assert not uncounted, f"{key}: causes without a count (a failed GROUP BY?): {uncounted}"
    assert body.get("levers"), f"{key}: no levers (a failed recommend reads as [])"
    return f"{key}: churn {body['churn']} vs {body['base_churn']}, {len(causes)} causes, {len(body['levers'])} levers"


def check_patterns(body: dict) -> str:
    patterns = body.get("patterns") or []
    assert patterns, "no patterns (a failed count query drops a pattern silently)"
    return f"{len(patterns)} patterns"


def check_explore(body: dict) -> str:
    assert body.get("dimensions"), "explore has no dimensions"
    assert body.get("levers"), "explore has no levers (a failed recommend reads as [])"
    assert body.get("predicted") is not None, "explore has no prediction"
    return f"n {body.get('n')}, predicted {body['predicted']}, {len(body['levers'])} levers"


def check_sql_rows(body: dict) -> str:
    rows = body.get("rows") if isinstance(body, dict) else None
    if rows is None and isinstance(body, dict):
        rows = body.get("hits") or body.get("data")
    assert rows, f"the statement returned no rows: {str(body)[:200]}"
    return f"{len(rows)} rows"


def check_kpi_matches_card(body: dict, churn: float) -> str:
    """The card's KPI statement must produce the card's number. 'Returns rows'
    can't tell a card from its complement: predict() yields only the argmax,
    which for a healthy book is `false` (p 0.618 under a card reading 38.2%),
    the bug aito-sql-demo #3 fixed. So: the `true` row's p must equal the card."""
    rows = body.get("rows") or []
    p = next((r.get("p") for r in rows if isinstance(r, dict) and str(r.get("value")).lower() == "true"), None)
    assert p is not None, f"KPI SQL has no 'true' row: predict() rather than predictions()? {rows}"
    assert abs(100 * p - churn) < 0.15, f"card shows {churn}% but its own SQL says {100 * p:.1f}%"
    return f"SQL says {100 * p:.1f}%, card {churn}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", default=LIVE_BASE)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    failures: list[tuple[str, str]] = []

    def step(name: str, run) -> Any:
        started = time.monotonic()
        try:
            body, summary = run()
            elapsed = time.monotonic() - started
            print(f"  {'SLOW' if elapsed > SLOW_SECONDS else 'ok  '}  {name:<28} {summary}  ({elapsed:.1f}s)")
            return body
        except Exception as exc:   # noqa: BLE001 -- record every failure and walk on (RemoteDisconnected,
            # ConnectionResetError and ssl.SSLError are OSErrors, not URLErrors)
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL  {name:<28} {type(exc).__name__}: {exc}  ({time.monotonic() - started:.1f}s)")
            return None

    def get(path, check):
        def run():
            body = fetch(args.base, path, args.timeout)
            return body, check(body)
        return run

    print(f"SQL demo live smoke — {args.base}\n")
    step("health", get("/api/health", check_health))
    step("overview", get("/api/overview", check_overview))
    cards = step("cards", get("/api/cards", check_cards))
    for card in (cards or {}).get("cards", []):
        key = card.get("key")
        detail = step(f"card {key}", get(f"/api/cards/{key}", check_card))
        kpi_sql = ((detail or {}).get("sql") or {}).get("kpi")
        if kpi_sql:
            # the card's own KPI statement, as a visitor would run it from the card,
            # must produce the number the card shows
            def run_card_sql(stmt=kpi_sql, churn=detail.get("churn")):
                body = fetch(args.base, "/api/sql", args.timeout, sql=stmt)
                return body, check_kpi_matches_card(body, churn)
            step(f"card {key} SQL", run_card_sql)
    step("patterns", get("/api/patterns", check_patterns))
    step("explore", get("/api/explore", check_explore))
    step("explore (hot, passive)", get("/api/explore?where=climate:hot,cooling:passive&lever=service_plan",
                                       check_explore))

    print()
    if failures:
        print(f"{len(failures)} checks FAILED:")
        for name, reason in failures:
            print(f"  {name}: {reason}")
        return 1
    print("Every view answered with content.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
