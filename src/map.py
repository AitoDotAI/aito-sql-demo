"""The exhaustive map — every (field × value × slice) cell, swept and ranked.

This exists to answer one objection, and it is the objection a good analyst
raises first: *you found passive-cooling-in-hot-climates because you went
looking for it.* Six hand-written cards cannot refute that. A sweep can — if
the six cards turn out to be the top six cells of a map nobody curated, the
finding is a discovery rather than a decoration.

It also does something the cards cannot: it FINDS INTERACTIONS AUTOMATICALLY.
`relate()` ranks fields individually, so an interaction is invisible to it —
passive cooling reads ×1.56 over the whole book, which is unremarkable. What
gives it away is that the lift MOVES when you condition: ×1.81 inside hot
sites, ×1.08 inside temperate ones. So the map runs the same sweep once per
slice and ranks cells by how far the lift travelled. The planted interactions
should rise to the top on their own.

Cost is the whole point of the exercise, so it is measured and reported: one
relate() per slice, not one per cell.

Usage:  python -m src.map [--out data/map.json]
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.config import load_config
from src.sql_client import SqlClient, SqlError

# The columns worth relating to the outcome. Deliberately NOT every column:
# install_id is a key (every value unique, so every lift is noise), and the two
# label spellings would relate to themselves perfectly and tell you nothing.
EXPLANATORY = [
    "industry", "size_band", "country", "climate", "dust_level", "shift_pattern",
    "family", "grade", "cooling", "ip_rating", "duty_cycle_pct",
    "channel", "region", "message_angle", "landing_page", "device",
    "commissioning", "service_plan", "support_tier",
    "had_thermal_fault", "slow_first_response", "ticket_count", "feedback_score",
]

EXCLUDED = {
    "install_id": "primary key — every value unique, so every lift is noise",
    "churned": "the outcome itself",
    "reordered": "the outcome, spelled the other way",
    "order_value": "continuous and near-unique; relates as a category and swamps the top-k",
    "installed_on": "a date relates as a category — same problem",
}

# The conditioning dimensions. Each value becomes a view, and the sweep runs
# again inside it. Kept to context the business cannot change (where the
# machine lives, what it is, who bought it) — conditioning on a LEVER would
# mean asking 'what causes churn among people we already helped', which is a
# different and much less useful question.
SLICE_DIMENSIONS = ["climate", "shift_pattern", "grade", "industry"]

OUTCOME = "churned = 'true'"


def sq(condition: str) -> str:
    """Escape a condition for embedding in a SQL string literal.

    `to => '...'` is itself a quoted string, so the quotes inside the condition
    have to be doubled: churned = 'true' becomes churned = ''true''. Forgetting
    this fails as "expected a literal value but got end of input", which points
    at the end of the statement rather than at the quote that broke it.
    """
    return condition.replace("'", "''")


@dataclass
class Cell:
    slice_name: str
    slice_field: str | None
    slice_value: str | None
    field: str
    value: str
    lift: float
    info: float
    n: int | None = None
    base_lift: float | None = None      # the same cell's lift over the whole book

    @property
    def movement(self) -> float:
        """How far the lift travelled when the slice was applied.

        A main effect has the same lift everywhere and scores ~0; an
        interaction only bites inside its slice and moves.
        """
        if self.base_lift is None or self.base_lift <= 0:
            return 0.0
        return abs(self.lift - self.base_lift)

    @property
    def signal(self) -> float:
        """Movement weighted by information gain — the actual interaction score.

        Movement ALONE does not work, and the failure is instructive: the first
        run of this sweep put `ticket_count=3 inside arctic` at the top with
        movement 0.82, because a thin slice lets a lift wander freely. Every one
        of those noise cells carried info 0.0002-0.003, while the planted
        interaction `grade=consumer inside 3-shift` carried info 0.056 — a
        20-200x gap.

        `info` is the engine's own information-gain measure and is already
        support-aware, so multiplying by it folds in 'how much evidence is
        behind this' without inventing a second, hand-tuned support rule. The
        alternative — dropping ticket_count and feedback_score from the field
        list — would be exactly the hand-picking this map exists to avoid.
        """
        return self.movement * self.info

    def as_dict(self) -> dict:
        return {
            "slice": self.slice_name, "slice_field": self.slice_field,
            "slice_value": self.slice_value,
            "field": self.field, "value": self.value,
            "lift": round(self.lift, 4), "info": round(self.info, 6),
            "n": self.n, "base_lift": round(self.base_lift, 4) if self.base_lift else None,
            "movement": round(self.movement, 4),
            "signal": round(self.signal, 6),
        }


def _view_name(field: str, value: str) -> str:
    """A readable view name. The demo argues its SQL is readable, so `hot_sites`
    beats `a_hot` and `v_3` beats neither."""
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_").lower()
    return f"map_{field}_{safe}"


def parse_related(raw) -> tuple[str, str]:
    """`related` is a JSON string over REST and an object over pgwire."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return "?", str(raw)
    if not isinstance(raw, dict) or not raw:
        return "?", "?"
    f, v = next(iter(raw.items()))
    if isinstance(v, dict):                 # {"$has": "thermal"} on a text column
        v = next(iter(v.values()), "?")
    return f, str(v)


def sweep_one(sql: SqlClient, table: str, k: int) -> list[tuple[str, str, float, float]]:
    """One relate() over every explanatory field at once.

    The cost claim rests on this: the map is one statement per SLICE, not one
    per cell. `relate` already accepts a comma-separated field list.
    """
    stmt = (f"SELECT * FROM relate('{table}', to => '{sq(OUTCOME)}', "
            f"fields => '{', '.join(EXPLANATORY)}', k => {k})")
    out = []
    for row in sql.query(stmt).rows:
        f, v = parse_related(row.get("related"))
        lift, info = row.get("lift"), row.get("info")
        if lift is None:
            continue
        out.append((f, v, float(lift), float(info or 0.0)))
    return out


def build_map(sql: SqlClient, k: int = 60, verbose: bool = True) -> dict:
    started = time.perf_counter()
    stmts = 0

    # 1. the base sweep — every field over the whole book
    base_rows = sweep_one(sql, "analysis", k)
    stmts += 1
    base_lift = {(f, v): lift for f, v, lift, _ in base_rows}
    cells = [Cell("all installs", None, None, f, v, lift, info, base_lift=lift)
             for f, v, lift, info in base_rows]
    if verbose:
        print(f"  base sweep: {len(base_rows)} cells")

    # 2. the values each conditioning dimension takes
    slices: list[tuple[str, str]] = []
    for dim in SLICE_DIMENSIONS:
        rows = sql.query(f"SELECT {dim}, count(*) FROM analysis GROUP BY {dim}").rows
        stmts += 1
        for row in rows:
            vals = list(row.values())
            value, count = str(vals[0]), int(vals[-1])
            if count >= 150:      # below this a slice is too thin to be worth a card
                slices.append((dim, value))

    # 3. a view per slice, then the same sweep inside it
    for dim, value in slices:
        view = _view_name(dim, value)
        try:
            sql.query(f"SELECT count(*) FROM {view}")
        except SqlError:
            # Views are DDL and DDL is wire-protocol only, so the read-only REST
            # client cannot create them. src/load.py does, from MAP_VIEWS below.
            if verbose:
                print(f"  ! missing view {view} — run `python -m src.load --views` first")
            continue
        rows = sweep_one(sql, view, k)
        stmts += 1
        for f, v, lift, info in rows:
            if f == dim:          # relating a slice to the field that defines it
                continue
            cells.append(Cell(f"{dim} = {value}", dim, value, f, v, lift, info,
                              base_lift=base_lift.get((f, v))))
        if verbose:
            print(f"  {view}: {len(rows)} cells")

    elapsed = (time.perf_counter() - started) * 1000.0
    ranked = sorted(cells, key=lambda c: c.signal, reverse=True)
    by_lift = sorted(cells, key=lambda c: abs(c.lift - 1.0), reverse=True)

    return {
        "generated_ms": round(elapsed),
        "statements": stmts,
        "cells": len(cells),
        "slices": [f"{d} = {v}" for d, v in slices],
        "explanatory_fields": EXPLANATORY,
        "excluded_fields": EXCLUDED,
        "outcome": OUTCOME,
        # ranked by movement x info — the interactions
        "by_movement": [c.as_dict() for c in ranked[:40]],
        # ranked by raw distance from 1.0 — the plain main effects
        "by_lift": [c.as_dict() for c in by_lift[:40]],
    }


def map_views() -> dict[str, str]:
    """The views the sweep needs, as {name: SELECT}. src/load.py creates these."""
    return {}   # filled at load time from the data; see src/load.py


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=Path("data/map.json"), type=Path)
    ap.add_argument("--k", default=60, type=int)
    args = ap.parse_args()

    sql = SqlClient(load_config(), timeout=120.0)
    print("sweeping…")
    result = build_map(sql, k=args.k)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")

    print(f"\n{result['cells']} cells from {result['statements']} statements "
          f"in {result['generated_ms']} ms")
    print(f"wrote {args.out}")
    print("\nTop 12 by SIGNAL (movement x info) — the interaction detector:")
    for c in result["by_movement"][:12]:
        base = f"x{c['base_lift']:.2f} overall" if c["base_lift"] else "no base"
        print(f"  {c['signal']:.4f}  {c['field']}={c['value']:<16} "
              f"x{c['lift']:<5.2f} in [{c['slice']:<24}] ({base})")


if __name__ == "__main__":
    main()
