"""Book the held-out scoring — including the leak the page claims exists.

Two things need a net here, and the second is the unusual one.

  1. THE SCORE. Accuracy, base rate, decile lift, AUC. Assertions are on the
     claims the page makes out loud; the snapshot carries the numbers so drift
     reads as a diff rather than a failure. Note which way the accuracy
     assertion points: the page says accuracy LOSES to the base rate, so that
     is what is asserted. If a future engine wins, this test fails and the
     copy has to be rewritten — which is the correct outcome, because the page
     would then be lying in the modest direction.

  2. THE LEAK ITSELF. The whole page is built on a measured fact: run the same
     statement against LABELLED rows and the prediction echoes the label at
     p ~ 0.98, whatever the features. That is an engine behaviour, not ours,
     and if it changes the page's central explanation becomes false while
     every number on it still looks fine. So it is asserted directly.

Run:  ./do test-book          compare
      ./do test-book -a       accept new numbers after reviewing the diff
"""

import json

import booktest as bt

from src import holdout
from src.config import load_config
from src.sql_client import SqlClient


def test_holdout_scoring(t: bt.TestCaseRun):
    sql = SqlClient(load_config(), timeout=300.0)

    t.h1("Scoring installs the engine was never told about")
    t.tln(f"instance: `{sql.base_url}`")
    t.tln("")

    r = holdout.score(sql)

    t.h2("The cohort")
    t.iln(f"- held-out installs scored: {r['n']}")
    t.iln(f"- of which actually churned: {r['churned']} ({r['churn_rate']}%)")
    t.tln("")
    t.assertln("every held-out row got a prediction AND matched a truth row",
               r["n"] > 0 and r["n"] == len(holdout_ids(sql)))
    t.assertln("the holdout is big enough to say anything at all", r["n"] >= 100)

    t.h2("The score")
    t.iln(f"- accuracy: {r['accuracy']}%")
    t.iln(f"- base rate (always predict the majority): {r['base_accuracy']}%")
    t.iln(f"- top-decile lift: x{r['decile_lift']} "
          f"({r['decile_hits']}/{r['decile_n']} churned, {r['decile_rate']}%)")
    t.iln(f"- AUC: {r['auc']}")
    t.tln("")
    # Pointed deliberately at the unflattering claim — see the module docstring.
    t.assertln("accuracy LOSES to the base rate, which is what the page says",
               r["accuracy"] < r["base_accuracy"])
    t.assertln("but the ranking works — the riskiest decile churns well above base",
               r["decile_lift"] is not None and r["decile_lift"] > 1.5)
    t.assertln("and AUC is meaningfully better than a coin toss",
               r["auc"] is not None and r["auc"] > 0.55)

    t.h2("Calibration")
    for b in r["bands"]:
        t.iln(f"- p in [{b['lo']}%, {b['hi']}%): n={b['n']}, "
              f"predicted {b['predicted']}%, actually churned {b['actual']}%")
    t.tln("")
    low = [b for b in r["bands"] if b["hi"] <= 20]
    t.assertln("the low bands are roughly honest — within 10 points",
               all(abs(b["predicted"] - b["actual"]) < 10 for b in low))

    t.h2("The leak this page exists to avoid")
    t.tln("The same statement, against rows whose label IS present.")
    t.tln("")
    rows = sql.query(
        "SELECT install_id, churned, predictions(churned) FROM analysis "
        "WHERE churned IS NOT NULL LIMIT 6").rows
    echoes, ps = 0, []
    for row in rows:
        preds = json.loads(row["churned.$predictions"])
        top = max(preds, key=lambda x: x["p"])
        echoes += str(top["value"]).lower() == str(row["churned"]).lower()
        ps.append(top["p"])
        t.iln(f"- {row['install_id']}: label={row['churned']}, "
              f"top prediction={top['value']} at p={top['p']:.4f}")
    t.tln("")
    t.assertln("every labelled row's prediction agrees with its own label",
               echoes == len(rows))
    t.assertln("...and does so at a near-identical, near-certain probability — "
               "which is the signature of an echo rather than a prediction",
               min(ps) > 0.90)


def holdout_ids(sql: SqlClient) -> set[str]:
    return {r["install_id"]
            for r in sql.query("SELECT install_id FROM holdout_truth LIMIT 500").rows}
