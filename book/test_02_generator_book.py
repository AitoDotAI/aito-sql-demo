"""Book the generator's planted mechanisms — the demo's ground truth.

This is the test that matters most in the repo, and it touches no network.
The whole demo rests on one claim: five mechanisms were planted, and the
dashboard recovers four of them while correctly finding nothing in the fifth.
That claim is only checkable because the generator is seeded, so this books
the realised rates and fails if any of them drift.

If a weight in src/generate.py is tuned, this snapshot SHOULD change — review
the diff and regenerate:

    ./do test-book --update-snapshots
"""

import booktest as bt

from src.generate import COMMISSIONING, MECHANISMS, SERVICE_PLANS, build


def _rate(installs, churn, sites, products, pred):
    """Churn % and n over the installs matching `pred`."""
    hits = [churn[i["install_id"]] for i in installs if pred(i, sites, products)]
    return (100.0 * sum(hits) / len(hits), len(hits)) if hits else (float("nan"), 0)


def test_planted_mechanisms(t: bt.TestCaseRun):
    """Generate the world and book what was actually realised."""
    w = build()
    sites = {s["site_id"]: s for s in w.sites}
    products = {p["product_id"]: p for p in w.products}
    churn = {r["install"]: r["reordered"] == "false" for r in w.reorders}

    def rate(pred):
        return _rate(w.installs, churn, sites, products, pred)

    P = lambda i: products[i["product"]]
    S = lambda i: sites[i["site"]]

    t.h1("Planted mechanisms")
    t.tln("The ground truth the dashboard is measured against.")
    t.tln("")
    for k, v in MECHANISMS.items():
        t.iln(f"- **{k}** — {v}")
    t.tln("")

    base, n = rate(lambda i, *_: True)
    t.h2("Baseline")
    t.tln(f"churn {base:.1f}% over n={n}")
    t.tln("")

    t.h2("M1 — passive cooling x hot climate")
    t.tln("An interaction: neither ingredient should be dangerous alone.")
    cells = [
        ("passive + hot", lambda i, *_: P(i)["cooling"] == "passive" and S(i)["climate"] == "hot"),
        ("passive + not-hot", lambda i, *_: P(i)["cooling"] == "passive" and S(i)["climate"] != "hot"),
        ("not-passive + hot", lambda i, *_: P(i)["cooling"] != "passive" and S(i)["climate"] == "hot"),
        ("neither", lambda i, *_: P(i)["cooling"] != "passive" and S(i)["climate"] != "hot"),
    ]
    both = None
    for label, pred in cells:
        r, n = rate(pred)
        if label == "passive + hot":
            both = r
        t.iln(f"- {label}: **{r:.1f}%** (n={n})")
    singles = max(rate(cells[1][1])[0], rate(cells[2][1])[0])
    t.tln("")
    t.assertln("the interaction cell beats BOTH single ingredients by 20pp+",
               both - singles > 20.0)

    t.h2("M2 — consumer grade x 3-shift duty")
    for label, pred in [
        ("consumer + 3-shift", lambda i, *_: P(i)["grade"] == "consumer" and S(i)["shift_pattern"] == "3-shift"),
        ("consumer + other", lambda i, *_: P(i)["grade"] == "consumer" and S(i)["shift_pattern"] != "3-shift"),
        ("other + 3-shift", lambda i, *_: P(i)["grade"] != "consumer" and S(i)["shift_pattern"] == "3-shift"),
    ]:
        r, n = rate(pred)
        t.iln(f"- {label}: **{r:.1f}%** (n={n})")
    t.tln("")

    t.h2("M3 — the confound")
    t.tln("Must look guilty unconditionally and innocent once climate is held fixed.")
    camps = {c["campaign_id"]: c for c in w.campaigns}
    sess = {s["session_id"]: s for s in w.sessions}

    def channel(i):
        s = sess.get(i["session"])
        return camps[s["campaign"]]["channel"] if s else "?"

    me_all, n1 = rate(lambda i, *_: channel(i) == "distributor-ME")
    other_all, n2 = rate(lambda i, *_: channel(i) != "distributor-ME")
    me_hot, n3 = rate(lambda i, *_: channel(i) == "distributor-ME" and S(i)["climate"] == "hot")
    other_hot, n4 = rate(lambda i, *_: channel(i) != "distributor-ME" and S(i)["climate"] == "hot")
    t.iln(f"- distributor-ME, all sites: **{me_all:.1f}%** (n={n1})")
    t.iln(f"- other channels, all sites: **{other_all:.1f}%** (n={n2})")
    t.iln(f"- distributor-ME, hot only: **{me_hot:.1f}%** (n={n3})")
    t.iln(f"- other channels, hot only: **{other_hot:.1f}%** (n={n4})")
    t.tln("")
    t.assertln("looks guilty unconditionally (3pp+ worse)", me_all - other_all > 3.0)
    t.assertln("is exonerated once climate is fixed (within 4pp)", abs(me_hot - other_hot) < 4.0)

    t.h2("M4 — slow first response, and the tier that causes it")
    slow = {tk["install"] for tk in w.tickets if tk["first_response_h"] > 24}
    for label, pred in [
        ("had a slow response", lambda i, *_: i["install_id"] in slow),
        ("never slow", lambda i, *_: i["install_id"] not in slow),
        ("support_tier=pooled", lambda i, *_: i["support_tier"] == "pooled"),
        ("support_tier=dedicated", lambda i, *_: i["support_tier"] == "dedicated"),
    ]:
        r, n = rate(pred)
        t.iln(f"- {label}: **{r:.1f}%** (n={n})")
    t.tln("")

    t.h2("NEG — the card that must find nothing")
    spread = []
    for c in COMMISSIONING:
        r, n = rate(lambda i, cc=c, *_: i["commissioning"] == cc)
        spread.append(r)
        t.iln(f"- commissioning={c}: **{r:.1f}%** (n={n})")
    t.tln("")
    t.assertln("commissioning is flat (under 4pp across all three)",
               max(spread) - min(spread) < 4.0)

    t.h2("service_plan — a lever that DOES work, for contrast")
    plan = {}
    for p in SERVICE_PLANS:
        r, n = rate(lambda i, pp=p, *_: i["service_plan"] == pp)
        plan[p] = r
        t.iln(f"- service_plan={p}: **{r:.1f}%** (n={n})")
    t.tln("")
    t.assertln("premium beats none by 4pp+ — so the flat NEG card means something",
               plan["none"] - plan["premium"] > 4.0)

    t.h2("Row counts")
    for name in ("products", "customers", "sites", "campaigns", "sessions", "orders",
                 "installs", "tickets", "feedback", "events", "actions", "reorders", "analysis"):
        t.iln(f"- {name}: {len(getattr(w, name))}")
    t.tln("")
    t.assertln("the generator is deterministic under a fixed seed",
               [r["reordered"] for r in build().reorders] == [r["reordered"] for r in w.reorders])
