"""Which predictor columns explain a holdout shift between Aito versions? Run on a LOCAL server only.

    AITO_API_URL=http://127.0.0.1:PORT AITO_API_KEY=... PGPORT=... uv run python scripts/holdout_cause.py [--out FILE]

Builds three copies of `analysis` on the target, differing only in which null-holding predictor columns they keep,
loads data/analysis.csv into each, and scores the held-out installs the way src/holdout.py does
(`predictions(churned) ... WHERE churned IS NULL`), against data/holdout_truth.csv:

    full        every column                      (what the demo does)
    no_fb       without feedback_score            (60% null)
    no_fb_reo   without feedback_score, reordered (feedback_score + the blanked label complement)

Run it on two engine versions; if `no_fb_reo` agrees across them while `full` does not, the shift comes from how the
engine treats those columns' nulls. Refuses a non-loopback target.
"""
import argparse
import csv
import io
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.holdout import _auc, _p_true  # noqa: E402
from src.load import psql, pg_env  # noqa: E402
from src.sql_client import SqlClient  # noqa: E402
from src.config import load_config  # noqa: E402

VARIANTS = {"full": [], "no_fb": ["feedback_score"], "no_fb_reo": ["feedback_score", "reordered"]}


def schema_for(drop: list[str], name: str) -> str:
    text = (ROOT / "sql/01_schema.sql").read_text()
    m = re.search(r"CREATE TABLE analysis \((.*?)\n\);", text, re.S)
    lines = []
    for ln in m.group(1).splitlines():
        s = ln.strip()
        if not s or s.startswith("--"):
            continue
        col = s.split()[0]
        if col in drop:
            continue
        lines.append(ln.rstrip().rstrip(","))
    return f"CREATE TABLE {name} (\n" + ",\n".join(lines) + "\n)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = load_config()
    if urlparse(cfg.aito_url).hostname not in ("127.0.0.1", "localhost", "::1"):
        sys.exit(f"refusing non-loopback target {cfg.aito_url}")
    env = pg_env()
    sql = SqlClient(cfg, timeout=300)
    rows = list(csv.DictReader((ROOT / "data/analysis.csv").open()))
    truth_rows = list(csv.DictReader((ROOT / "data/holdout_truth.csv").open()))
    truth = {r["install_id"]: r["churned"].lower() for r in truth_rows}
    out = {"server": None}
    for name, drop in VARIANTS.items():
        t = f"analysis_{name}"
        psql(f"DROP TABLE IF EXISTS {t}", env)
        psql(schema_for(drop, t), env)
        cols = [c for c in rows[0] if c not in drop]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            w.writerow([r[c] for c in cols])
        psql(f"COPY {t} FROM STDIN WITH (FORMAT csv, HEADER true)", env, stdin=buf.getvalue())
        res = sql.query(f"SELECT install_id, predictions(churned) FROM {t} WHERE churned IS NULL LIMIT 500").rows
        scored, hits, bins = [], 0, [0] * 5
        edges = [0.1, 0.2, 0.35, 0.6]
        for r in res:
            p = _p_true(r.get("churned.$predictions"))
            actual = truth.get(r["install_id"]) == "true"
            if p is None:
                continue
            scored.append((p, actual))
            hits += (p >= 0.5) == actual
            bins[sum(p >= e for e in edges)] += 1
        n = len(scored)
        out[name] = {"scored": n, "accuracy": round(hits / n, 4), "auc": round(_auc(scored), 4), "bin_counts": bins,
                     "mean_p": round(sum(p for p, _ in scored) / n, 5)}
        print(name, out[name])
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
