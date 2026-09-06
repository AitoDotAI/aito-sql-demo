"""The explorer — one slice, four panels, and every value a link to a deeper slice.

The design constraint that shapes this whole file: **`relate()` takes no
filter.** Its `to` is the target proposition, not a slice, so the cards get
their conditioning from VIEWS — and a view is DDL, which the read-only app
cannot create for a slice the user just invented by clicking.

So the explorer is built from the three things that DO condition on an
arbitrary WHERE, all verified against the live engine:

    predict('analysis','churned', where => '<slice>')          the calibrated number
    recommend('analysis','<lever>', goal => …, given => '<slice>')   the levers
    SELECT <field>, count(*) FROM analysis WHERE <slice> GROUP BY <field>   the rates

That split is worth showing rather than hiding, and the UI does show it: the
headline is what the ENGINE PREDICTS, the rows underneath are what the DATA
COUNTS. When they disagree — and on a thin slice they will — that gap is
support-tempering being honest, not a bug.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from src.sql_client import SqlClient, SqlError

TABLE = "analysis"
OUTCOME_COL = "churned"
OUTCOME_TRUE = "true"

# Fields offered as navigation. Ordered roughly by how a person would think
# about the business — context, then machine, then acquisition, then the levers
# — rather than alphabetically or by the order they sit in the table.
NAVIGABLE = [
    "climate", "shift_pattern", "dust_level", "industry", "size_band", "country",
    "grade", "cooling", "family", "ip_rating",
    "channel", "region", "message_angle", "device",
    "commissioning", "service_plan", "support_tier",
    "had_thermal_fault", "slow_first_response",
]

# Columns a business could actually choose differently. recommend() only makes
# sense pointed at one of these: ranking values of `climate` would propose
# moving the customer's factory.
LEVERS = ["cooling", "grade", "service_plan", "support_tier", "commissioning"]

# A filter is a list of (field, value). Values come from the data, but they
# still reach SQL as literals, so both halves are validated: the field against
# the known column list, the value by escaping quotes.
_VALUE_OK = re.compile(r"^[A-Za-z0-9 _.\-/+]{1,64}$")


@dataclass(frozen=True)
class Facet:
    field: str
    value: str

    def sql(self) -> str:
        return f"{self.field} = '{self.value.replace(chr(39), chr(39) * 2)}'"


def parse_facets(raw: str | None) -> list[Facet]:
    """Parse `climate:hot,cooling:passive` into validated facets.

    Unknown FIELDS are rejected rather than passed through, and the reason is
    not injection (the read-only endpoint refuses writes anyway) — it is that an
    unknown field in a WHERE currently returns a SILENT EMPTY RESULT rather than
    an error (td-20260823204811553899). A typo'd facet would render a confident
    page of zeros. Validating here is the only thing standing between a
    click-to-filter UI and a confidently wrong answer.
    """
    if not raw:
        return []
    known = set(NAVIGABLE) | set(LEVERS)
    out: list[Facet] = []
    for part in raw.split(","):
        if ":" not in part:
            continue
        field, _, value = part.partition(":")
        field, value = field.strip(), value.strip()
        if field not in known:
            raise ValueError(f"unknown field '{field}'")
        if not _VALUE_OK.match(value):
            raise ValueError(f"invalid value for '{field}'")
        out.append(Facet(field, value))
    return out


def where_sql(facets: list[Facet]) -> str:
    return " AND ".join(f.sql() for f in facets)


def _sq(s: str) -> str:
    """Escape a condition for nesting inside a SQL string literal."""
    return s.replace("'", "''")


def _counts(sql: SqlClient, field: str, where: str) -> tuple[str, dict, dict]:
    """(field, {value: rows}, {value: churned_rows}) inside the slice."""
    base = f" WHERE {where}" if where else ""
    churn = (f" WHERE {where} AND {OUTCOME_COL} = '{OUTCOME_TRUE}'"
             if where else f" WHERE {OUTCOME_COL} = '{OUTCOME_TRUE}'")
    totals, churned = {}, {}
    for row in sql.query(f"SELECT {field}, count(*) FROM {TABLE}{base} GROUP BY {field}").rows:
        v = list(row.values())
        totals[str(v[0])] = int(v[-1])
    for row in sql.query(f"SELECT {field}, count(*) FROM {TABLE}{churn} GROUP BY {field}").rows:
        v = list(row.values())
        churned[str(v[0])] = int(v[-1])
    return field, totals, churned


def explore(sql: SqlClient, facets: list[Facet], lever: str | None = None) -> dict:
    where = where_sql(facets)
    used = {f.field for f in facets}
    fields = [f for f in NAVIGABLE if f not in used]

    # The slice's own size and churn rate — everything below is relative to these.
    n_stmt = f"SELECT count(*) FROM {TABLE}" + (f" WHERE {where}" if where else "")
    n_rows = sql.query(n_stmt).rows
    n = int(next(iter(n_rows[0].values()))) if n_rows else 0

    c_stmt = (f"SELECT count(*) FROM {TABLE} WHERE "
              + (f"{where} AND " if where else "")
              + f"{OUTCOME_COL} = '{OUTCOME_TRUE}'")
    c_rows = sql.query(c_stmt).rows
    churned_n = int(next(iter(c_rows[0].values()))) if c_rows else 0
    observed = (churned_n / n) if n else None

    # What the ENGINE says, which is a different question from what the rows say.
    pred_stmt = (f"SELECT value, p FROM predict('{TABLE}','{OUTCOME_COL}'"
                 + (f", where => '{_sq(where)}'" if where else "") + ")")
    predicted = None
    for row in sql.query(pred_stmt).rows:
        v = str(row.get("value", row.get("$value"))).lower()
        p = row.get("p", row.get("$p"))
        if v == OUTCOME_TRUE and p is not None:
            predicted = float(p)
        elif v == "false" and p is not None and predicted is None:
            predicted = 1.0 - float(p)

    # Per-field breakdowns, in parallel. Sequentially this is ~2 statements x 17
    # fields at ~130ms = 4s, which would make the explorer a report. Fanned out
    # it lands near the slowest single pair.
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda f: _counts(sql, f, where), fields))

    dimensions = []
    for field, totals, churned in results:
        values = []
        for value, rows in sorted(totals.items(), key=lambda kv: -kv[1]):
            if rows < 12:            # too thin to offer as a next click
                continue
            rate = churned.get(value, 0) / rows
            values.append({
                "value": value, "n": rows,
                "rate": round(100.0 * rate, 1),
                # Lift against THIS slice, not against the whole book — the
                # question the panel answers is "what varies in here".
                "lift": round(rate / observed, 3) if observed else None,
            })
        if len(values) < 2:          # nothing to compare, so nothing to show
            continue
        spread = max(v["rate"] for v in values) - min(v["rate"] for v in values)
        dimensions.append({
            "field": field, "values": values, "spread": round(spread, 1),
            "sql": f"SELECT {field}, count(*) FROM {TABLE}"
                   + (f" WHERE {where}" if where else "") + f" GROUP BY {field}",
        })
    # Widest spread first: the dimension that most divides this slice is the
    # most interesting next click.
    dimensions.sort(key=lambda d: d["spread"], reverse=True)

    # Levers, ranked toward NOT churning, conditioned on the slice.
    lever = lever if lever in LEVERS else next(
        (l for l in LEVERS if l not in used), LEVERS[0])
    lever_stmt = (f"SELECT value, p FROM recommend('{TABLE}','{lever}', "
                  f"goal => '{OUTCOME_COL} = ''false'''"
                  + (f", given => '{_sq(where)}'" if where else "") + ", k => 5)")
    levers = []
    try:
        for row in sql.query(lever_stmt).rows:
            p = row.get("p", row.get("$p"))
            levers.append({
                "value": row.get("value", row.get("$value")),
                "churn": round(100.0 * (1.0 - float(p)), 1) if p is not None else None,
            })
    except SqlError:
        levers = []

    return {
        "facets": [{"field": f.field, "value": f.value} for f in facets],
        "where": where,
        "n": n,
        "churned_n": churned_n,
        "observed": round(100.0 * observed, 1) if observed is not None else None,
        "predicted": round(100.0 * predicted, 1) if predicted is not None else None,
        "dimensions": dimensions[:8],
        "lever": lever,
        "levers": levers,
        "lever_options": [l for l in LEVERS if l not in used],
        "sql": {
            "n": n_stmt, "predict": pred_stmt, "levers": lever_stmt,
        },
    }
