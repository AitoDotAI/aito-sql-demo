"""Load the generated CSVs into Aito over the Postgres wire protocol.

Everything here goes through psql — no Aito SDK, no REST, no JSON. That is the
demo's whole claim, so the loader has to honour it too: if this file needed a
bespoke client, the pitch would be false.

`COPY … FROM STDIN` is the bulk path and is wire-protocol only (the REST `_sql`
endpoint is read-only). Load order follows the links: a REFERENCES target must
exist before the table pointing at it.

Usage:  python -m src.load [--data data/] [--drop]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Link order, not alphabetical: each table's REFERENCES targets precede it.
LOAD_ORDER = [
    "products", "customers", "sites", "campaigns", "sessions",
    "orders", "installs", "tickets", "feedback", "events", "actions", "reorders",
    "analysis",
]


def pg_env() -> dict[str, str]:
    """Derive the psql connection from the Aito instance, the way shell.nix does.

    On a MULTI-database server (`<host>/db/<name>/`) `dbname` selects the
    DATABASE. Get it wrong and the server answers "password authentication
    failed" — deliberately indistinguishable from a bad key, so that a
    reachable port cannot be used to enumerate databases. Deriving it beats
    guessing, because the error points at the one thing that is not wrong.
    """
    url = os.environ.get("AITO_API_URL", "")
    key = os.environ.get("AITO_API_KEY", "")
    if not url or not key:
        sys.exit("AITO_API_URL and AITO_API_KEY must be set (see .env)")
    host = urlparse(url).hostname or ""
    m = re.search(r"/db/([^/]+)", url)
    dbname = m.group(1) if m else os.environ.get("AITO_ENV", "aito")
    env = dict(os.environ)
    env.update({
        "PGHOST": os.environ.get("PGHOST", host),
        "PGPORT": os.environ.get("PGPORT", "5432"),
        "PGUSER": os.environ.get("PGUSER", "aito"),
        "PGDATABASE": os.environ.get("PGDATABASE", dbname),
        "PGPASSWORD": key,
    })
    return env


def psql(sql: str, env: dict[str, str], stdin: str | None = None) -> str:
    r = subprocess.run(
        ["psql", "-v", "ON_ERROR_STOP=1", "-c", sql] if stdin is None
        else ["psql", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=env, input=stdin, capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"psql failed on:\n  {sql[:200]}\n{r.stderr.strip()}")
    return r.stdout


def psql_file(path: Path, env: dict[str, str]) -> str:
    r = subprocess.run(
        ["psql", "-v", "ON_ERROR_STOP=1", "-f", str(path)],
        env=env, capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"psql failed on {path}:\n{r.stderr.strip()}")
    return r.stdout


# Views the demo needs. DDL is wire-protocol only (the REST `_sql` endpoint is
# read-only), so views are created here rather than by the app.
#
#   CARD_VIEWS   the four conditioning slices the six cards use.
#   MAP_VIEWS    one slice per value of each conditioning dimension, for the
#                exhaustive sweep in src/map.py. Generated rather than listed:
#                the map's whole claim is that nobody hand-picked the cells, so
#                hand-picking the slices would undercut it.
CARD_VIEWS = {
    "hot_sites": "SELECT * FROM analysis WHERE climate = 'hot'",
    "temperate_sites": "SELECT * FROM analysis WHERE climate = 'temperate'",
    "three_shift": "SELECT * FROM analysis WHERE shift_pattern = '3-shift'",
    "consumer_grade": "SELECT * FROM analysis WHERE grade = 'consumer'",
}

MAP_SLICE_DIMENSIONS = ["climate", "shift_pattern", "grade", "industry"]
MAP_MIN_SLICE_ROWS = 150


def _view_name(field: str, value: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in str(value)).strip("_").lower()
    return f"map_{field}_{safe}"


def create_views(env: dict[str, str]) -> int:
    """Create the card views and the map's slice views. Idempotent."""
    made = 0
    for name, select in CARD_VIEWS.items():
        psql(f"DROP VIEW IF EXISTS {name}", env)
        psql(f"CREATE VIEW {name} AS {select}", env)
        made += 1

    for dim in MAP_SLICE_DIMENSIONS:
        out = psql(f"SELECT {dim}, count(*) FROM analysis GROUP BY {dim}", env)
        for line in out.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 2 or not parts[1].isdigit():
                continue
            value, count = parts[0], int(parts[1])
            if count < MAP_MIN_SLICE_ROWS:
                continue          # too thin to carry a card
            name = _view_name(dim, value)
            psql(f"DROP VIEW IF EXISTS {name}", env)
            psql(f"CREATE VIEW {name} AS SELECT * FROM analysis "
                 f"WHERE {dim} = '{value}'", env)
            made += 1
    return made


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data", type=Path)
    ap.add_argument("--schema", default="sql/01_schema.sql", type=Path)
    ap.add_argument("--drop", action="store_true", help="drop the tables first")
    ap.add_argument("--views", action="store_true",
                    help="only (re)create the views, skip the load")
    args = ap.parse_args()
    env = pg_env()

    print(f"target: {env['PGHOST']}:{env['PGPORT']} db={env['PGDATABASE']}")

    if args.views:
        print(f"created {create_views(env)} views")
        return

    if args.drop:
        # Reverse link order: drop the referrers before what they reference.
        for t in reversed(LOAD_ORDER):
            psql(f"DROP TABLE IF EXISTS {t}", env)
        print(f"dropped {len(LOAD_ORDER)} tables")

    psql_file(args.schema, env)
    print(f"created schema from {args.schema}")

    total = 0
    for table in LOAD_ORDER:
        csv_path = args.data / f"{table}.csv"
        if not csv_path.exists():
            sys.exit(f"missing {csv_path} — run `python -m src.generate` first")
        text = csv_path.read_text(encoding="utf-8")
        n = text.count("\n") - 1
        psql(f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true)", env, stdin=text)
        total += n
        print(f"  {table:12} {n:>7} rows")

    print(f"\nloaded {total} rows")
    print(f"created {create_views(env)} views")
    print(psql("SELECT count(*) AS installs FROM installs", env).strip())


if __name__ == "__main__":
    main()
