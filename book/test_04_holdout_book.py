"""Book the held-out scoring — including the leak the page claims exists.

Two things need a net here, and the second is the unusual one.

  1. THE SCORE. Accuracy, base rate, decile lift, AUC. Assertions are on the
     claims the page makes out loud; the snapshot carries the numbers so drift
     reads as a diff rather than a failure. Note which way the accuracy
     assertion points: the page says accuracy LOSES to the base rate, so that
     is what is asserted. If a future engine wins, this test fails and the
     copy has to be rewritten — which is the correct outcome, because the page
     would then be lying in the modest direction.

  2. THE LEAK ITSELF, and its actual cause. Run the same statement against
     LABELLED rows and the prediction echoes the label at p = 0.9808 — the
     same value for every row. The first version of this test recorded that
     but described it wrongly, as the engine reading the target's own value
     back. It does not: it holds `churned` out when predicting `churned`, and
     says so in a warning. The echo is `reordered`, a perfect complement on
     the same row. The test now asserts the SIGNATURE that distinguishes the
     two — identical p across rows with different features, which a real
     prediction cannot produce.

  3. THE ENGINE'S OWN WARNING, and the unbiased number it points at. The
     held-out rows are still in the population the prediction is read from,
     so the score is optimistic; `select.predictions_in_sample` says so. That
     warning must reach the payload — swallowing it is how a page about
     honest measurement starts lying — and `evaluate()` must keep agreeing
     that accuracy does not beat the base rate.

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

    t.h2("What the engine says about the score")
    for w in r["warnings"]:
        t.iln(f"- `{w.get('code')}`: {w.get('message')}")
    t.tln("")
    codes = {w.get("code") for w in r["warnings"]}
    t.assertln("the in-sample warning reaches the payload rather than being swallowed",
               "select.predictions_in_sample" in codes)

    ev = r["evaluate"]
    t.h2("The unbiased estimate the warning points at")
    if ev:
        t.iln(f"- accuracy: {ev['accuracy']}% on {ev['test']} test rows "
              f"({ev['train']} train, n={ev['n']})")
        t.iln(f"- base rate: {ev['base_accuracy']}%")
        t.iln(f"- gain over base: {ev['gain']}pp")
    t.tln("")
    t.assertln("evaluate() is available and returned a figure", ev is not None)
    t.assertln("it reaches the SAME verdict as the holdout — accuracy does not "
               "beat the base rate",
               ev is not None and ev["accuracy"] <= ev["base_accuracy"])

    t.h2("The leak this page exists to avoid, and its real cause")
    t.tln("The same statement, against rows whose label IS present. The engine "
          "holds `churned` out; what it still sees is `reordered`.")
    t.tln("")
    rows = sql.query(
        "SELECT install_id, climate, cooling, churned, reordered, "
        "predictions(churned) FROM analysis WHERE churned IS NOT NULL LIMIT 6").rows
    echoes, ps = 0, []
    for row in rows:
        preds = json.loads(row["churned.$predictions"])
        top = max(preds, key=lambda x: x["p"])
        echoes += str(top["value"]).lower() == str(row["churned"]).lower()
        ps.append(top["p"])
        t.iln(f"- {row['install_id']} ({row['climate']}/{row['cooling']}): "
              f"churned={row['churned']}, reordered={row['reordered']} -> "
              f"{top['value']} at p={top['p']:.4f}")
    t.tln("")
    t.assertln("every labelled row's prediction agrees with its own label",
               echoes == len(rows))
    # The discriminating assertion. A genuine prediction varies with the
    # features; a complement column does not. If a future engine stops reading
    # `reordered`, these spread out and this fails — which is the signal to
    # rewrite the page, not to relax the test.
    t.assertln("at a probability IDENTICAL across rows with different climate "
               "and cooling — which no real prediction produces, and which is "
               "how we know the cause is the complement column",
               max(ps) - min(ps) < 1e-9)


def holdout_ids(sql: SqlClient) -> set[str]:
    return {r["install_id"]
            for r in sql.query("SELECT install_id FROM holdout_truth LIMIT 500").rows}
