"""Score the held-out installs — the demo's honesty beat.

Everything else on this site asks the engine about a GROUP. This asks it about
a ROW, which is the form people actually mean when they say "predict", and the
form that is easiest to fake.

    SELECT install_id, predictions(churned) FROM analysis WHERE churned IS NULL

The `WHERE churned IS NULL` is the whole point. Run the same statement without
it, against labelled rows, and every prediction comes back agreeing with the
label at p = 0.98 — because the row's own outcome is part of the evidence the
engine conditions on. That is not a model being good, it is a lookup wearing a
model's clothes, and it is what this page originally showed (demo review,
2026-09-28). The generator now withholds the label on 8% of installs
(`src/generate.py`, `withhold_labels`) and parks the truth in `holdout_truth`,
which this module joins back ONLY to score.

What the scoring says is not flattering, and it ships anyway:

  * accuracy is BELOW the base rate. With 18% churn, "nobody churns" scores
    82%, and thresholding at p=0.5 scores less. Printing accuracy alone would
    have been the flattering choice and the dishonest one.
  * the ranking is what works — the riskiest decile churns ~2.5x as often as
    average, and AUC sits near 0.65. A retention team does not threshold at
    0.5, it works down a ranked list, so this is the number that matters.
  * the top of the range is overconfident: rows predicted ~0.80 churn ~0.48.

Caching, because this is not cheap: 240 rows cost ~7s, which is per-row
inference and not something to do while someone waits. Computed once on a
background thread at startup, same shape as the patterns cache.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from src.sql_client import SqlClient

# Kept in sync with generate.py's HOLDOUT_FRACTION x n_installs. Asked for
# explicitly because `predictions()` silently truncates to 10 rows when no
# LIMIT is given — no warning, no error, just a short answer that would have
# made this page score 10 installs and call it a holdout.
HOLDOUT_LIMIT = 500

# Shown in the table. Not the scoring set — that is all of them.
SAMPLE_ROWS = 8

SCORE_SQL = (
    "SELECT install_id, climate, cooling, grade, shift_pattern, had_thermal_fault, "
    f"predictions(churned) FROM analysis WHERE churned IS NULL LIMIT {HOLDOUT_LIMIT}"
)
TRUTH_SQL = f"SELECT install_id, churned FROM holdout_truth LIMIT {HOLDOUT_LIMIT}"

_CACHE: dict[str, Any] | None = None
_LOCK = threading.Lock()


def _p_true(raw: str | list | None) -> float | None:
    """P(churned = true) out of a $predictions cell.

    The cell arrives as a JSON STRING, not a list — one of the v2 response
    shapes the review flagged. Parse rather than assume, and tolerate it
    arriving already decoded if that changes.
    """
    if raw is None:
        return None
    ps = json.loads(raw) if isinstance(raw, str) else raw
    for p in ps:
        if str(p.get("value")).lower() == "true":
            return float(p["p"])
    for p in ps:
        if str(p.get("value")).lower() == "false":
            return 1.0 - float(p["p"])
    return None


def _auc(scored: list[tuple[float, bool]]) -> float | None:
    """Rank-based AUC. Ties count a half, which matters here: support-tempering
    puts many thin rows on exactly the same probability."""
    pos = [p for p, y in scored if y]
    neg = [p for p, y in scored if not y]
    if not pos or not neg:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def score(sql: SqlClient) -> dict[str, Any]:
    """Predict every held-out install, then join the withheld truth and score."""
    started = time.perf_counter()
    rows = sql.query(SCORE_SQL).rows
    truth = {r["install_id"]: str(r["churned"]).lower()
             for r in sql.query(TRUTH_SQL).rows}

    scored: list[tuple[float, bool]] = []
    sample: list[dict[str, Any]] = []
    hits = 0
    for r in rows:
        iid = r["install_id"]
        actual = truth.get(iid)
        p = _p_true(r.get("churned.$predictions"))
        if actual is None or p is None:
            continue
        y = actual == "true"
        scored.append((p, y))
        hits += (p >= 0.5) == y
        if len(sample) < SAMPLE_ROWS:
            sample.append({
                "install_id": iid,
                "climate": r.get("climate"), "cooling": r.get("cooling"),
                "grade": r.get("grade"), "shift_pattern": r.get("shift_pattern"),
                "had_thermal_fault": r.get("had_thermal_fault"),
                "p_churn": round(100 * p, 1),
                "actual": actual,
                "correct": (p >= 0.5) == y,
            })

    n = len(scored)
    if not n:
        return {"n": 0, "error": "no held-out rows — was the data regenerated?"}

    pos = sum(1 for _, y in scored if y)
    ranked = sorted(scored, key=lambda t: -t[0])
    d = max(1, n // 10)
    top_hits = sum(1 for _, y in ranked[:d] if y)

    bands = []
    for lo, hi in [(0.0, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 0.60), (0.60, 1.01)]:
        b = [(p, y) for p, y in scored if lo <= p < hi]
        if b:
            bands.append({
                "lo": round(100 * lo), "hi": round(100 * min(hi, 1.0)), "n": len(b),
                "predicted": round(100 * sum(p for p, _ in b) / len(b), 1),
                "actual": round(100 * sum(y for _, y in b) / len(b), 1),
            })

    return {
        "n": n,
        "churned": pos,
        "churn_rate": round(100 * pos / n, 1),
        "accuracy": round(100 * hits / n, 1),
        # The number accuracy has to beat. Printed beside it precisely because
        # this demo does NOT beat it.
        "base_accuracy": round(100 * max(pos, n - pos) / n, 1),
        "decile_n": d,
        "decile_hits": top_hits,
        "decile_rate": round(100 * top_hits / d, 1),
        "decile_lift": round((top_hits / d) / (pos / n), 2) if pos else None,
        "auc": round(a, 3) if (a := _auc(scored)) is not None else None,
        "bands": bands,
        "sample": sample,
        "sql": {"score": SCORE_SQL, "truth": TRUTH_SQL},
        "ms": round((time.perf_counter() - started) * 1000),
    }


def cached(sql: SqlClient) -> dict[str, Any]:
    """Single-flight cache. ~7s to compute, and it never changes between loads."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    with _LOCK:
        if _CACHE is None:
            _CACHE = score(sql)
    return _CACHE


def warm(sql: SqlClient) -> None:
    """Fill the cache off the request path. Never raises — see SqlClient.warm."""
    try:
        cached(sql)
    except Exception as e:                      # noqa: BLE001
        print(f"holdout warm-up failed (continuing): {e}")
