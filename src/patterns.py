"""The pattern feed — conjunctions the engine mined, the rows behind them, and a sentence.

The shape asked for:

    5 cases of {cooling: passive, grade: consumer, churned: true} — 1.8x lift
      - case 1 …
      - case 2 …
    "There are 5 construction sites running consumer-grade machines on passive
     cooling in hot climates, and they churned."

Three things have to be true for that to be worth reading, and they are what
this module does:

  1. NOBODY CHOSE THE PATTERN. `patterns()` mines the conjunctions; the field
     list here is just "the columns worth looking at", not a hypothesis.
  2. THE CASES ARE REAL ROWS. Each pattern is turned back into a WHERE and the
     matching installs are fetched, so the claim is checkable by clicking.
  3. THE SENTENCE IS GENERATED FROM THE PATTERN, not written by hand. If the
     mining returns something different tomorrow, the prose changes with it.

A note on `lift`: `patterns()` returns it only when given a `where` — the
condition is what a lift is relative to. Mined without one, you get the
conjunction and its support and no lift, which is correct rather than missing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field

from src.sql_client import SqlClient, SqlError

TABLE = "analysis"
OUTCOME = "churned = 'true'"

# What to mine over. Grouped rather than thrown in together: mining all 20
# columns at once returns the same two dominant product facts every time, and
# the interesting conjunctions are the ones that cross a boundary — machine
# against site, or experience against outcome.
FIELD_GROUPS: list[tuple[str, str, list[str]]] = [
    ("machine × site", TABLE,
     ["cooling", "grade", "climate", "shift_pattern", "churned"]),
    ("experience × outcome", TABLE,
     ["had_thermal_fault", "slow_first_response", "support_tier", "churned"]),
    ("who bought it", TABLE,
     ["industry", "size_band", "grade", "churned"]),
    ("in hot climates", "hot_sites",
     ["cooling", "grade", "slow_first_response", "churned"]),
    ("on 3-shift duty", "three_shift",
     ["grade", "cooling", "had_thermal_fault", "churned"]),
]

# Verbalisation needs GRAMMAR, not a lookup. Concatenating per-column phrases
# produced "There are 190 installs of that overheated kept waiting on support on
# pooled support" — every fact present, unreadable as English. So each column is
# assigned a SLOT and the sentence is assembled per slot:
#
#   ADJECTIVE   attaches to the noun         consumer-grade, passive-cooled
#   PREP        a prepositional phrase       in hot climates, at mining companies
#   CLAUSE      a relative clause            that overheated, that waited on support
#   OUTCOME     the consequence              they did not come back
ADJECTIVE, PREP, CLAUSE, OUTCOME_SLOT = "adj", "prep", "clause", "outcome"

SLOTS: dict[str, tuple[str, dict | str]] = {
    "cooling":             (ADJECTIVE, "{v}-cooled"),
    "grade":               (ADJECTIVE, "{v}-grade"),
    "ip_rating":           (ADJECTIVE, "{v}-rated"),
    "climate":             (PREP, "in {v} climates"),
    "shift_pattern":       (PREP, "running {v}"),
    "industry":            (PREP, "at {v} companies"),
    "size_band":           (PREP, "at {v} customers"),
    "country":             (PREP, "in {v}"),
    "region":              (PREP, "in {v}"),
    "support_tier":        (PREP, "on {v} support"),
    "service_plan":        (PREP, "on a {v} plan"),
    "commissioning":       (PREP, "commissioned {v}"),
    "channel":             (PREP, "sold through {v}"),
    "had_thermal_fault":   (CLAUSE, {"true": "overheated", "false": "never overheated"}),
    "slow_first_response": (CLAUSE, {"true": "waited days for a reply",
                                     "false": "got a fast response"}),
    "churned":             (OUTCOME_SLOT, {"true": "did not come back",
                                           "false": "came back"}),
}


def _join(items: list[str]) -> str:
    """a, b and c"""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


@dataclass
class Pattern:
    terms: list[tuple[str, str]]
    n: int
    lift: float | None = None
    cases: list[dict] = dc_field(default_factory=list)
    group: str = ""
    table: str = TABLE

    @property
    def where(self) -> str:
        return " AND ".join(
            f"{f} = '{str(v).replace(chr(39), chr(39) * 2)}'" for f, v in self.terms)

    def sentence(self) -> str:
        """Verbalise the conjunction. Assembled from the terms by slot, so a
        different mining result produces different prose with no edit here."""
        adjs, preps, clauses, outcome = [], [], [], None
        for f, v in self.terms:
            slot, tmpl = SLOTS.get(f, (PREP, f"{f.replace('_', ' ')} {{v}}"))
            text = tmpl.get(str(v)) if isinstance(tmpl, dict) else tmpl.format(v=v)
            if text is None:
                continue
            if slot == ADJECTIVE:
                adjs.append(text)
            elif slot == PREP:
                preps.append(text)
            elif slot == CLAUSE:
                clauses.append(text)
            else:
                outcome = text

        noun = (", ".join(adjs) + " machines") if adjs else "installs"
        s = f"There are {self.n} {noun}"
        if preps:
            s += " " + " ".join(preps)
        if clauses:
            s += " that " + _join(clauses)
        if outcome:
            s += f", and they {outcome}"
        s += "."

        # The lift is measured against the `where` the mining used — churned =
        # true — so it says how much MORE COMMON this combination is among
        # installs that churned. "More likely than chance" would be a different
        # and false claim.
        if self.lift and self.lift > 1.15:
            s += f" That combination is {self.lift:.1f}x more common among installs that churned."
        elif self.lift and self.lift < 0.87:
            s += f" That combination is {1 / self.lift:.1f}x rarer among installs that churned."
        return s

    def as_dict(self) -> dict:
        return {
            "terms": [{"field": f, "value": v} for f, v in self.terms],
            "n": self.n, "lift": round(self.lift, 3) if self.lift else None,
            "where": self.where, "group": self.group, "table": self.table,
            "sentence": self.sentence(), "cases": self.cases,
        }


def _terms(raw) -> list[tuple[str, str]]:
    """Unpack a `{"$and":[{f:v}, …]}` proposition. Also accepts a bare {f:v}."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, dict):
        return []
    conj = raw.get("$and")
    items = conj if isinstance(conj, list) else [raw]
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for f, v in item.items():
            if isinstance(v, dict):        # {"$has": "thermal"} on a text column
                v = next(iter(v.values()), None)
            if v is not None:
                out.append((f, str(v)))
    return out


CASE_COLUMNS = ["install_id", "industry", "country", "climate", "shift_pattern",
                "grade", "cooling", "support_tier", "ticket_count", "churned"]


def mine(sql: SqlClient, k: int = 4, cases_per_pattern: int = 5) -> dict:
    patterns: list[Pattern] = []
    seen: set[str] = set()
    stmts = 0

    for group, table, fields in FIELD_GROUPS:
        # `where` is what makes a lift meaningful — it is the condition the lift
        # is measured against. Without it patterns() returns support only.
        stmt = (f"SELECT * FROM patterns('{table}', "
                f"fields => '{', '.join(fields)}', "
                f"where => '{OUTCOME.replace(chr(39), chr(39) * 2)}', k => {k})")
        try:
            rows = sql.query(stmt).rows
            stmts += 1
        except SqlError:
            continue

        for row in rows:
            terms = _terms(row.get("related"))
            if not terms:
                continue
            key = "|".join(sorted(f"{f}={v}" for f, v in terms))
            if key in seen:
                continue
            seen.add(key)
            lift = row.get("lift")
            patterns.append(Pattern(
                terms=terms, n=0, group=group, table=table,
                lift=float(lift) if lift is not None else None))

    # Turn each mined conjunction back into a WHERE: count it, and pull real
    # rows. This is the part that makes the claim checkable rather than assertive.
    for p in patterns:
        try:
            rows = sql.query(f"SELECT count(*) FROM {p.table} WHERE {p.where}").rows
            stmts += 1
            p.n = int(next(iter(rows[0].values()))) if rows else 0
            cols = ", ".join(CASE_COLUMNS)
            p.cases = sql.query(
                f"SELECT {cols} FROM {p.table} WHERE {p.where} LIMIT {cases_per_pattern}"
            ).rows
            stmts += 1
        except SqlError:
            p.n = 0

    patterns = [p for p in patterns if p.n > 0]
    # Biggest lift first, then support — a strong pattern nobody can check is
    # worth less than a strong pattern with rows behind it.
    patterns.sort(key=lambda p: ((p.lift or 0), p.n), reverse=True)

    return {
        "statements": stmts,
        "patterns": [p.as_dict() for p in patterns],
        "case_columns": CASE_COLUMNS,
        "groups": [g for g, _, _ in FIELD_GROUPS],
    }
