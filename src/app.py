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
import os
import re
import threading
from urllib.parse import urlparse
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


def warm_on_startup() -> bool:
    """Whether to spend ~22 statements on Aito at boot.

    The warm-up is worth it in production, where a process starts once per
    deploy and the first visitor would otherwise pay ~7s of holdout scoring,
    ~9s of evaluate() and a 19-statement patterns mine — plus the DNS lookup
    that can stall for 5s. It is NOT worth it in a dev loop, where the same
    burst fires on every reload. Mine fired it a dozen times in an afternoon
    while shared was being investigated for load, which is how this got
    noticed.

    Default on, so deploys keep the behaviour they were tuned for. Set
    DEMO_WARM=0 to boot silent — the caches are lazy anyway (`holdout.cached`,
    the patterns cache), so skipping the warm-up moves the cost to the first
    request rather than losing it.
    """
    return os.environ.get("DEMO_WARM", "1").strip().lower() not in {"0", "false", "no", ""}


@app.on_event("startup")
def _warm_connection() -> None:
    """Resolve the host and open the pool before the first visitor waits.

    Mitigation, not a fix: the multi-second page loads reported in the demo
    review were DNS resolution timing out (5s and 8s multiples, glibc's default
    timeout:5), not slow SQL — the engine answers in ~1ms and the wire adds
    ~45ms. A pooled connection resolves once and then stops asking, so warming
    it here moves the expensive first lookup off the critical path.

    All of it on a daemon thread, nothing awaited — the same reasoning
    _warm_patterns gives below, and it applies to the connection warm-up too:
    the platform's readiness check hits /api/health, and the one statement that
    opens the pool is normally ~50ms but is precisely the call that can draw a
    5s DNS stall. Blocking the port bind on it would let the fault this warm-up
    exists to hide reappear as a deploy that looks unhealthy.

    Ordered deliberately: the pool first, then the holdout scoring, which is
    ~7s of per-row inference and wants a warm connection rather than opening
    its own.
    """
    if not warm_on_startup():
        print("DEMO_WARM=0 — not warming at startup; the first request pays instead")
        return

    def run() -> None:
        from src import holdout

        sql.warm()
        holdout.warm(sql)

    threading.Thread(target=run, name="warm-connection", daemon=True).start()


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
    """predictions() returns the ranked distribution; we want P(churned = true).

    It returns the ARGMAX first, which for a healthy book is 'false' — so
    reading rows[0] would silently report the retention rate as the churn rate.
    Pick the row by its value instead.

    The cards ask for `predictions(...)` rather than `predict(...)` precisely so
    that this function has a 'true' row to find. `predict()` returns the argmax
    ALONE, so a card showing 37.4% displayed a statement whose only row was
    ('false', 0.626) — the complement of the number above it. The reader who
    checked the SQL was the one who got misled, which is the wrong way round.
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


# Cached so the nav does not pay for a pattern mine on every page load. The
# counts are properties of a static dataset, so a per-process cache is honest
# rather than merely convenient.
_BADGE_CACHE: dict[str, int] = {}

# The mined patterns themselves, for the same reason: mining is 19 sequential
# statements to Aito, and the dataset is static — it changes only when
# `./do provision` reloads it — so a per-process cache is correct rather than a
# shortcut. `?refresh=true` re-mines, mirroring /api/map.
#
# On the size of the win, because the first measurement here was misread: this
# endpoint was timed at 13-16s per request and that was attributed to mining
# cost. It was not. It was DNS — resolution failures time out at glibc's
# default 5s, so 19 sequential statements meant 19 chances to draw a 5s stall.
# Re-measured when DNS is behaving, an uncached mine is ~1.3s. So the cache
# buys roughly 1s, not 15s. Still worth having for a page whose content cannot
# change between provisions, and the lock below still matters, but it is polish
# rather than a rescue.
_PATTERNS_CACHE: dict[str, object] = {}
_PATTERNS_LOCK = threading.Lock()

# The map sweep gets the same treatment, for the same reason and one more.
# `?refresh=true` is unauthenticated and recomputes 18 statements, so N
# concurrent refreshes were N concurrent sweeps: measured four simultaneous
# requests each taking ~2.8s, i.e. 72 statements to answer one page. Patterns
# was given a lock for exactly this; the map was not.
#
# The second reason is worse. The sweep OVERWRITES the file /map is served
# from, and `write_text` truncates before it writes — so an interleaved pair of
# writers, or a reader arriving mid-write, can leave or observe invalid JSON,
# after which every later /api/map fails on json.loads until someone gets a
# clean refresh through. A public endpoint should not be able to do that, so
# the write is now atomic (temp file + os.replace, which is a rename within the
# directory and therefore all-or-nothing).
_MAP_LOCK = threading.Lock()


@app.get("/api/nav/badges")
def nav_badges():
    """Counts for the sidebar. Cheap by construction: never runs a sweep or a
    mine of its own — it reports what is already known, and omits what is not,
    because a badge that appears only sometimes is worse than no badge."""
    out: dict[str, int] = {"cards": len(CARDS)}

    path = Path(__file__).resolve().parent.parent / "data" / "map.json"
    if "cells" in _BADGE_CACHE:
        out["cells"] = _BADGE_CACHE["cells"]
    elif path.exists():
        try:
            out["cells"] = _BADGE_CACHE.setdefault(
                "cells", int(json.loads(path.read_text(encoding="utf-8"))["cells"]))
        except Exception:
            pass
    if "patterns" in _BADGE_CACHE:
        out["patterns"] = _BADGE_CACHE["patterns"]
    # Only once the holdout cache has filled — see the docstring: a badge that
    # appears halfway through the first page load is worse than no badge.
    from src import holdout
    if holdout._CACHE is not None and holdout._CACHE.get("n"):
        out["holdout"] = holdout._CACHE["n"]
    return out


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


@app.get("/api/connect")
def connect_details():
    """What an engineer needs to open psql against this demo themselves.

    The key is deliberately NOT `AITO_API_KEY`. That one can write — this demo
    loads its data with it — and a demo page is a public place. A separate
    read-only key goes in `AITO_SQL_READONLY_KEY`, and until somebody sets it
    the box ships with a placeholder and tells the reader where to get one.
    That way publishing a credential stays an explicit act by a person rather
    than a side effect of deploying this route.
    """
    parsed = urlparse(config.aito_url)
    host = parsed.hostname or ""
    m = re.search(r"/db/([^/]+)", config.aito_url)
    database = m.group(1) if m else "aito"
    key = os.environ.get("AITO_SQL_READONLY_KEY", "")
    return {
        "host": host,
        "port": 5432,
        "database": database,
        "user": "aito",
        "key_published": bool(key),
        "key": key or "<your-read-only-key>",
        "psql": (f"PGPASSWORD={key or '<your-read-only-key>'} "
                 f"psql -h {host} -p 5432 -U aito -d {database}"),
        "url": config.aito_url,
        # The one statement worth running first.
        "try": "SELECT install_id, predictions(churned) FROM analysis WHERE churned IS NULL LIMIT 5;",
    }


@app.get("/api/scoring")
def get_scoring():
    """Row-level predictions on installs whose label was withheld, and the score.

    The demo's honesty beat, and the one route whose numbers are allowed to be
    unflattering — accuracy here sits BELOW the base rate. See src/holdout.py
    for why that is the honest thing to print rather than a bug to tune away.
    """
    from src import holdout

    try:
        return holdout.cached(sql)
    except SqlError as e:
        raise HTTPException(status_code=502,
                            detail={"message": str(e), "sql": e.sql})


@app.get("/api/patterns")
def get_patterns(refresh: bool = False):
    """Mined conjunctions, the rows behind each, and a generated sentence.

    Served from an in-process cache. The mine is 19 sequential statements and
    ~1.3s — see the note by _PATTERNS_CACHE for why the figure first recorded
    here (13-16s) was DNS stalls rather than mining cost.

    The lock makes it single-flight: without it, N visitors arriving on a cold
    process would each start their own 19-statement mine, which is how a slow
    endpoint becomes a thundering one.
    """
    from src import patterns as pat

    if not refresh and "result" in _PATTERNS_CACHE:
        return _PATTERNS_CACHE["result"]

    with _PATTERNS_LOCK:
        # Re-check inside the lock: whoever was ahead of us has filled it.
        if not refresh and "result" in _PATTERNS_CACHE:
            return _PATTERNS_CACHE["result"]
        try:
            result = pat.mine(sql)
        except SqlError as e:
            raise HTTPException(status_code=502, detail={"message": str(e), "sql": e.sql})
        _PATTERNS_CACHE["result"] = result
        _BADGE_CACHE["patterns"] = len(result["patterns"])
        return result


@app.on_event("startup")
def _warm_patterns() -> None:
    """Mine once in the background at startup, so the first visitor to
    /patterns does not pay for it.

    Deliberately a daemon thread rather than awaited: the platform's readiness
    check hits /api/health, and blocking startup on 19 Aito statements would
    make a deploy look unhealthy for a quarter of a minute. Failure is
    swallowed on purpose — a warm-up that cannot reach Aito must not stop the
    app from serving, and the route will simply mine on demand as before.
    """
    if not warm_on_startup():
        return

    def run() -> None:
        try:
            get_patterns()
        except Exception as e:                   # noqa: BLE001 — see docstring
            # Swallowed so the app still serves, but not silently: a warm-up
            # that cannot reach Aito otherwise looks exactly like one that
            # worked, and the only symptom is a slow first /patterns.
            print(f"patterns warm-up failed (continuing): {e}")

    threading.Thread(target=run, name="warm-patterns", daemon=True).start()


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


def _write_atomic(path: Path, text: str) -> None:
    """Replace `path` in one step, so no reader ever sees half a file.

    The temp file goes in the SAME directory on purpose: os.replace is atomic
    only within a filesystem, and /tmp is frequently a different one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


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
        with _MAP_LOCK:
            # Whoever was ahead of us has already rebuilt it; a refresh that
            # queued behind another refresh wants that result, not its own.
            if not refresh and path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                try:
                    data = sweep.build_map(sql, verbose=False)
                except SqlError as e:
                    raise HTTPException(status_code=502,
                                        detail={"message": str(e), "sql": e.sql})
                _write_atomic(path, json.dumps(data, indent=1))
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
                      "mechanism": c.mechanism, "interaction": c.interaction}
                     for c in CARDS]
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
