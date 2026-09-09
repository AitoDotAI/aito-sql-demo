"""FastAPI app for aito-sql-demo — a 360° view of the business, in SQL.

Every number this API returns comes from a SQL statement in src/cards.py, and
every response carries the SQL that produced it so the UI can show its working.
There is no query builder here on purpose: the demo's claim is that SQL is the
whole interface, and an API that quietly assembled queries would undercut it.

Conventions enforced by aito-demo-server (don't drift from these without
updating both the platform and the template in the same PR):

  - GET /health         : cheap liveness, no Aito call
  - GET /api/health     : readiness check, includes Aito connectivity
  - GET /api/schema     : pass-through to Aito's /schema (linked from AitoPanel)
  - GET /api/<...>      : your routes
  - app.mount("/", StaticFiles(directory="frontend/out", html=True))
                         : MUST be the last route registered. Serves the
                           Next.js static export from the same uvicorn process.

Replace the /api/example handler with your own routes. /health, /api/health,
and /api/schema can stay verbatim across demos.
"""

from __future__ import annotations

from pathlib import Path

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles

from src.aito_client import AitoClient, AitoError
from src.cards import CARDS, CARDS_BY_KEY, Card
from src.config import load_config
from src.sql_client import SqlClient, SqlError

config = load_config()
aito = AitoClient(config)
sql = SqlClient(config)

app = FastAPI(
    title="aito-sql-demo",
    description="A 360° view of the business — root causes and the lever that moves each, in SQL.",
    version="0.1.0",
)


# ── Middleware: surface Aito latency in response headers ─────────────
#
# The LatencyBadge in the frontend reads X-Aito-Ms / X-Aito-Calls /
# X-Aito-Ops set on every /api/* response. Reset the client's
# last_call before the route runs; pick it up after.

@app.middleware("http")
async def aito_latency_headers(request: Request, call_next):
    aito.last_call = None
    response: Response = await call_next(request)
    if aito.last_call:
        call = aito.last_call
        response.headers["X-Aito-Ms"] = f"{call.ms:.1f}"
        response.headers["X-Aito-Calls"] = "1"
        response.headers["X-Aito-Ops"] = f"{call.op}:{call.ms:.1f}"
    return response


# ── Health ────────────────────────────────────────────────────────

@app.get("/health")
def liveness():
    """Cheap liveness probe — does not touch Aito.

    The platform's nginx routes <demo>.aito.ai/health to this endpoint
    so external monitoring can target a specific demo. Keep it cheap.
    """
    return {"ok": True}


@app.get("/api/health")
def api_health():
    """Readiness. Checks the SQL surface, because that is what this demo uses —
    a green light from a REST path the app never calls would be a false one."""
    connected, detail = True, "ok"
    try:
        # NOT `SELECT 1`: a constant SELECT parses over pgwire but is refused
        # by the REST `_sql` endpoint ("expected 'FROM' but got end of input"),
        # so the two transports disagree on it. Use a real, cheap statement.
        sql.query("SELECT count(*) FROM analysis")
    except SqlError as e:
        connected, detail = False, str(e)[:200]
    return {
        "status": "ok" if connected else "degraded",
        "aito_url": sql.base_url,
        "aito_connected": connected,
        "detail": detail,
    }


@app.get("/api/schema")
def schema():
    """Pass-through to Aito's /schema. The AitoPanel "view live schema" link
    targets this endpoint, so users can verify what's actually in the DB."""
    try:
        return aito.get_schema()
    except AitoError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Example route — REPLACE THIS with your own /api/* routes ─────

def _pct(x: float | None) -> float | None:
    return None if x is None else round(100.0 * x, 1)


def _churn_from_predict(rows: list[dict]) -> float | None:
    """predict() returns the ranked distribution; we want P(churned = true).

    It returns the ARGMAX first, which for a healthy book is 'false' — so
    reading rows[0] would silently report the retention rate as the churn rate.
    Pick the row by its value instead.
    """
    for r in rows:
        if str(r.get("$value", r.get("value"))).lower() == "true":
            return r.get("$p", r.get("p"))
    for r in rows:
        if str(r.get("$value", r.get("value"))).lower() == "false":
            p = r.get("$p", r.get("p"))
            return None if p is None else 1.0 - p
    return None


@lru_cache(maxsize=256)
def _field_counts(table: str, field: str) -> tuple[tuple[str, int, int], ...]:
    """(value, rows, churned_rows) per value of `field` in `table`.

    Exists because `relate()` reports `n` as the size of the whole table, not
    of the group — and the group size is the number that keeps a lift honest.
    Until 2026-09 the REST `_sql` endpoint happened to leak the engine's `fs`
    block, which carried it; the transport-parity fix (correctly) trimmed the
    result to the documented `(related, lift, info, n)`, so it has to be asked
    for explicitly now.

    Memoised because the demo's data is static: the first card expansion pays
    two statements per field, every later one pays nothing.
    """
    totals, churned = {}, {}
    for row in _run(f"SELECT {field}, count(*) FROM {table} GROUP BY {field}").rows:
        vals = list(row.values())
        totals[str(vals[0])] = int(vals[-1])
    for row in _run(
        f"SELECT {field}, count(*) FROM {table} "
        f"WHERE churned = 'true' GROUP BY {field}"
    ).rows:
        vals = list(row.values())
        churned[str(vals[0])] = int(vals[-1])
    return tuple((v, n, churned.get(v, 0)) for v, n in totals.items())


def _causes(rows: list[dict], table: str) -> list[dict]:
    """Shape relate() output for the UI.

    `related` arrives as a JSON STRING over REST and as an object over pgwire,
    so parse defensively rather than binding to one transport's rendering.
    """
    out = []
    for r in rows:
        related = r.get("related") or {}
        if isinstance(related, str):
            try:
                related = json.loads(related)
            except ValueError:
                related = {"?": related}
        field, value = (list(related.items()) or [("?", "?")])[0]
        if isinstance(value, dict):          # e.g. {"$has": "thermal"} on a text column
            value = next(iter(value.values()), "?")
        value = str(value)

        n = rate = None
        try:
            for v, total, churned in _field_counts(table, field):
                if v == value:
                    n, rate = total, _pct(churned / total) if total else None
                    break
        except HTTPException:
            # A computed or link-path field may not be GROUP BY-able. Losing the
            # count is worth less than losing the row, so degrade rather than 500.
            pass

        out.append({
            "field": field, "value": value,
            "lift": r.get("lift"), "info": r.get("info"),
            "n": n, "rate": rate,
        })
    return out


def _levers(rows: list[dict]) -> list[dict]:
    # psql names these columns `value`/`p`; the REST `_sql` endpoint returns
    # `$value`/`$p` for the same statement. Accept both rather than binding to
    # one transport's spelling.
    out = []
    for r in rows:
        p = r.get("p", r.get("$p"))
        out.append({
            "value": r.get("value", r.get("$value")),
            "p_good": _pct(p),
            "churn": _pct(None if p is None else 1.0 - p),
            "why": r.get("why"),
        })
    return out


def _run(stmt: str):
    try:
        return sql.query(stmt)
    except SqlError as e:
        raise HTTPException(status_code=502, detail={"message": str(e), "sql": e.sql})


def _card_payload(card: Card, full: bool) -> dict:
    kpi = _run(card.kpi)
    base = _run(card.baseline)
    churn = _churn_from_predict(kpi.rows)
    base_churn = _churn_from_predict(base.rows)
    payload = {
        "key": card.key, "title": card.title, "unit": card.unit,
        "question": card.question, "note": card.note,
        "mechanism": card.mechanism, "rank": card.rank,
        "churn": _pct(churn), "base_churn": _pct(base_churn),
        "lift": round(churn / base_churn, 2) if churn and base_churn else None,
        "sql": {"kpi": card.kpi, "causes": card.causes, "levers": card.levers,
                "baseline": card.baseline, "conditioned": card.conditioned},
        "ms": round(kpi.ms + base.ms),
    }
    if not full:
        return payload

    causes = _run(card.causes)
    levers = _run(card.levers)
    payload["causes"] = _causes(causes.rows, card.table)
    payload["levers"] = _levers(levers.rows)
    payload["ms"] += round(causes.ms + levers.ms)
    if card.conditioned:
        cond = _run(card.conditioned)
        payload["conditioned"] = _causes(cond.rows, card.conditioned_table or card.table)
        payload["conditioned_label"] = card.conditioned_label
        payload["ms"] += round(cond.ms)
    return payload


@app.get("/api/cards")
def list_cards():
    """The six cards, headline numbers only — one round trip per card."""
    return {"cards": [_card_payload(c, full=False) for c in CARDS]}


@app.get("/api/cards/{key}")
def get_card(key: str):
    """One card, fully expanded: causes, levers, and the conditioned contrast."""
    card = CARDS_BY_KEY.get(key)
    if not card:
        raise HTTPException(status_code=404, detail=f"no such card '{key}'")
    return _card_payload(card, full=True)


# A public endpoint that runs user-supplied SQL needs a ceiling. Not for
# correctness — the read-only `_sql` endpoint refuses every write and DDL,
# verified with DROP/DELETE/INSERT/CREATE/UPDATE — but because an unbounded
# SELECT from the open internet is a cheap way to make the instance work hard.
SQL_MAX_CHARS = 4000
SQL_TIMEOUT_S = 15.0


@app.post("/api/sql")
async def run_sql(request: Request):
    """Run one read-only statement — this is what makes the cards editable.

    No allowlist and no SQL parsing of our own: the endpoint is backed by
    Aito's READ-ONLY `_sql`, which refuses DDL and writes itself. Validating in
    two places would mean two definitions of what is allowed, and the one that
    matters is the engine's. What we DO impose is a size and time ceiling,
    which is a resource question rather than a semantic one.
    """
    stmt = (await request.body()).decode("utf-8", errors="replace").strip()
    if not stmt:
        raise HTTPException(status_code=400, detail={"message": "empty statement"})
    if len(stmt) > SQL_MAX_CHARS:
        raise HTTPException(status_code=413, detail={
            "message": f"statement too long ({len(stmt)} chars, limit {SQL_MAX_CHARS})"})
    if ";" in stmt.rstrip().rstrip(";"):
        # One statement per request. The engine would reject a batch anyway;
        # saying so here is clearer than letting it come back as a parse error.
        raise HTTPException(status_code=400, detail={
            "message": "one statement per request (found a ';' mid-statement)"})

    try:
        result = sql.query(stmt, timeout=SQL_TIMEOUT_S)
    except SqlError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "sql": e.sql})
    # Pass warnings through. This is the channel that says "you filtered on a
    # column that does not exist" — without it an empty grid looks like an
    # honest no-match, which is the exact trap an editable SQL box sets.
    return {"sql": result.sql, "columns": result.columns,
            "rows": result.rows, "ms": round(result.ms),
            "warnings": result.warnings}


@app.get("/api/patterns")
def get_patterns():
    """Mined conjunctions, the rows behind each, and a generated sentence."""
    from src import patterns as pat

    try:
        return pat.mine(sql)
    except SqlError as e:
        raise HTTPException(status_code=502, detail={"message": str(e), "sql": e.sql})


@app.get("/api/explore")
def get_explore(where: str | None = None, lever: str | None = None):
    """One slice of the data, with every value a link to a deeper slice.

    `where` is a compact facet list — `climate:hot,cooling:passive` — rather
    than raw SQL, because these values arrive from clicks and an unknown field
    in a WHERE currently returns a silent empty result rather than an error
    (td-20260823204811553899). Validating the facets here is what stops a
    stale link rendering a confident page of zeros.
    """
    from src import explore as ex

    try:
        facets = ex.parse_facets(where)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"message": str(e)})
    try:
        return ex.explore(sql, facets, lever)
    except SqlError as e:
        raise HTTPException(status_code=502, detail={"message": str(e), "sql": e.sql})


@app.get("/api/map")
def get_map(refresh: bool = False):
    """The exhaustive sweep — every (field x value x slice) cell, ranked.

    Served from data/map.json by default because the sweep is a batch job, not
    a request: 18 statements and ~2.4s. `?refresh=true` recomputes it live,
    which is worth having because the honest version of the claim is 'run it
    yourself and see', not 'trust this file'.
    """
    from src import map as sweep

    path = Path(__file__).resolve().parent.parent / "data" / "map.json"
    if refresh or not path.exists():
        try:
            data = sweep.build_map(sql, verbose=False)
        except SqlError as e:
            raise HTTPException(status_code=502, detail={"message": str(e), "sql": e.sql})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    else:
        data = json.loads(path.read_text(encoding="utf-8"))

    # Mark the cells the six cards are built on, so the page can show that the
    # cards are the top of a generated ranking rather than a curated set.
    carded = {(c.mechanism, c.key): c for c in CARDS}
    claims = {
        ("cooling", "passive", "climate = hot"): "thermal",
        ("grade", "consumer", "shift_pattern = 3-shift"): "duty",
        ("slow_first_response", "true", None): "response",
        ("channel", "distributor-ME", None): "channel",
        ("commissioning", None, None): "commissioning",
        ("service_plan", None, None): "service",
    }
    for cell in data.get("by_movement", []) + data.get("by_lift", []):
        key = claims.get((cell["field"], cell["value"], cell["slice"]))
        if key is None:
            key = claims.get((cell["field"], cell["value"], None))
        if key is None:
            key = claims.get((cell["field"], None, None))
        cell["card"] = key
    data["cards"] = [{"key": c.key, "title": c.title, "rank": c.rank,
                      "mechanism": c.mechanism} for c in CARDS]
    return data


@app.get("/api/overview")
def overview():
    """The chain strip: the business as one row of numbers."""
    stmts = {
        "installs": "SELECT count(*) AS n FROM analysis",
        "customers": "SELECT count(*) AS n FROM customers",
        "tickets": "SELECT count(*) AS n FROM tickets",
        "events": "SELECT count(*) AS n FROM events",
    }
    counts = {}
    for name, stmt in stmts.items():
        rows = _run(stmt).rows
        # `count(*) AS n` comes back as `$count` — the alias is dropped on an
        # aggregate, though it is honoured on a plain column. Read the single
        # value out rather than binding to either spelling.
        counts[name] = next(iter(rows[0].values()), None) if rows else None
    base = _churn_from_predict(_run("SELECT value, p FROM predict('analysis','churned')").rows)
    return {"counts": counts, "base_churn": _pct(base),
            "aito_url": sql.base_url,
            "sql": stmts | {"base_churn": "SELECT value, p FROM predict('analysis','churned')"}}


# ── Static files — keep this last ─────────────────────────────────

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "out"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
