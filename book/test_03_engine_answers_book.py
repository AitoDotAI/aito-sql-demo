"""Book the ENGINE's answers — the numbers the demo actually shows.

book/test_02 covers the generator: the ground truth we planted, computed
client-side. Nothing covered what the ENGINE says about it, and that is the
half that keeps moving — the Aito build under this demo has changed its answers
or its response shape three times, twice breaking the app in ways only a human
looking at a page would notice.

So this books the story, and it does it in two registers on purpose:

  * ASSERTIONS are on the NARRATIVE — M1's lift must rise under conditioning,
    M3 must be exonerated, the NEG card must stay flat. Those are the claims
    the demo makes out loud, and they must survive an engine upgrade.
  * The SNAPSHOT carries the actual numbers, so ordinary drift shows up as a
    reviewable diff rather than a failure. A prediction moving 37.4 -> 37.9 is
    information, not a bug.

That split matters right now: shared.aito.ai runs v2.8.3, which contains three
prediction fixes that internal (2.8.2-dev) does not — one of them for a bit
operation that "could return a plausible wrong answer" from the predict path.
So the numbers are EXPECTED to move on the production instance. When they do,
this test's diff is the record of what changed, and its assertions are the
guarantee that the story still holds.

Run against whichever instance .env points at:

    ./do test-book                 compare
    ./do test-book -a              accept new numbers after reviewing the diff
"""

import booktest as bt

from src.cards import CARDS
from src.config import load_config
from src.sql_client import SqlClient


def _p_true(rows, col_value="value", col_p="p"):
    """P(churned = true) from a predict result, whichever way it ranked.

    predict() returns the argmax first, which for a healthy book is 'false' —
    reading rows[0] would report the retention rate as the churn rate.
    """
    for r in rows:
        if str(r.get(col_value, r.get("$value"))).lower() == "true":
            return float(r.get(col_p, r.get("$p")))
    for r in rows:
        if str(r.get(col_value, r.get("$value"))).lower() == "false":
            return 1.0 - float(r.get(col_p, r.get("$p")))
    return float("nan")


def _lift(sql, table, field, value):
    """The lift of one (field = value) cell against churn, inside `table`."""
    import json
    stmt = (f"SELECT * FROM relate('{table}', to => 'churned = ''true''', "
            f"fields => '{field}', k => 6)")
    for row in sql.query(stmt).rows:
        rel = row.get("related")
        if isinstance(rel, str):
            try:
                rel = json.loads(rel)
            except ValueError:
                continue
        if isinstance(rel, dict) and str(rel.get(field)) == value:
            return float(row["lift"])
    return float("nan")


def test_engine_answers(t: bt.TestCaseRun):
    sql = SqlClient(load_config(), timeout=180.0)

    t.h1("What the engine says")
    t.tln(f"instance: `{sql.base_url}`")
    t.tln("")

    base = _p_true(sql.query("SELECT value, p FROM predict('analysis','churned')").rows)
    t.h2("Baseline")
    t.tln(f"book-wide churn: **{100 * base:.1f}%**")
    t.tln("")

    t.h2("The six cards")
    t.tln("Each card's headline number, as the dashboard prints it.")
    t.tln("")
    seen = {}
    for card in sorted(CARDS, key=lambda c: c.rank):
        p = _p_true(sql.query(card.kpi).rows)
        seen[card.key] = p
        t.iln(f"- **{card.rank}. {card.title}** ({card.mechanism}): "
              f"{100 * p:.1f}% churn, ×{p / base:.2f}")
    t.tln("")
    t.assertln("every card returned a probability", all(v == v for v in seen.values()))
    t.assertln("the three recovered mechanisms all read above the baseline",
               all(seen[k] > base for k in ("thermal", "duty", "response")))

    t.h2("M1 — the interaction only appears under conditioning")
    whole = _lift(sql, "analysis", "cooling", "passive")
    hot = _lift(sql, "hot_sites", "cooling", "passive")
    temperate = _lift(sql, "temperate_sites", "cooling", "passive")
    t.iln(f"- passive cooling, whole book: ×{whole:.2f}")
    t.iln(f"- passive cooling, inside hot sites: ×{hot:.2f}")
    t.iln(f"- passive cooling, inside temperate sites: ×{temperate:.2f}")
    t.tln("")
    t.assertln("conditioning on hot RAISES the lift", hot > whole)
    t.assertln("conditioning on temperate LOWERS it toward 1", temperate < whole)
    t.assertln("the hot/temperate contrast is the story, and it is wide",
               hot - temperate > 0.4)

    t.h2("M3 — the confound is exonerated by conditioning")
    me_all = _lift(sql, "analysis", "channel", "distributor-ME")
    me_hot = _lift(sql, "hot_sites", "channel", "distributor-ME")
    t.iln(f"- distributor-ME, whole book: ×{me_all:.2f}")
    t.iln(f"- distributor-ME, inside hot sites: ×{me_hot:.2f}"
          if me_hot == me_hot else
          "- distributor-ME, inside hot sites: **absent from the top 6**")
    t.tln("")
    t.assertln("it looks guilty unconditionally", me_all > 1.05)
    t.assertln("holding climate fixed clears it — it drops to ~1 or off the list",
               (me_hot != me_hot) or me_hot < 1.10)

    t.h2("NEG — the card that must keep finding nothing")
    rows = sql.query(
        "SELECT value, p FROM recommend('analysis','commissioning', "
        "goal => 'churned = ''false''', k => 3)").rows
    vals = [(str(r.get("value", r.get("$value"))),
             100 * (1 - float(r.get("p", r.get("$p"))))) for r in rows]
    for v, churn in vals:
        t.iln(f"- commissioning = {v}: {churn:.1f}% churn")
    spread = max(c for _, c in vals) - min(c for _, c in vals)
    t.tln("")
    t.tln(f"spread: {spread:.1f} points")
    t.assertln("commissioning stays flat — under 5 points across all three",
               spread < 5.0)

    t.h2("A lever that does work, for contrast")
    rows = sql.query(
        "SELECT value, p FROM recommend('analysis','support_tier', "
        "goal => 'churned = ''false''', k => 3)").rows
    tiers = {str(r.get("value", r.get("$value"))):
             100 * (1 - float(r.get("p", r.get("$p")))) for r in rows}
    for v, churn in tiers.items():
        t.iln(f"- support_tier = {v}: {churn:.1f}% churn")
    t.tln("")
    t.assertln("dedicated support beats pooled by 5+ points — so the flat NEG "
               "card next to it means something",
               tiers.get("pooled", 0) - tiers.get("dedicated", 100) > 5.0)
