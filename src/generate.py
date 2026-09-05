"""Generate the demo dataset — a machinery vendor's customer journey, with known mechanisms.

Everything here is synthetic and DELIBERATELY so: the demo's strongest beat is
"we planted four mechanisms, the engine recovered three and correctly stayed
quiet on the fourth", and that claim is only checkable when the ground truth is
written down. It is written down here, in `MECHANISMS`, and the module reports
what it actually realised so the planting can be verified before any SQL runs.

Determinism is a hard requirement, not a nicety: `tests/` snapshot the outputs,
and a demo that changes under you is not a demo. Hence one seeded `Random` and
no reliance on set/dict iteration order for any draw.

Usage:  python -m src.generate [--out data/] [--seed 20260831]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# The planted mechanisms — the ground truth the demo is measured against.
# --------------------------------------------------------------------------
#
# Two of these are INTERACTIONS (M1, M2): neither ingredient is harmful alone,
# and that is the point. A dashboard that ranks single fields by lift finds
# nothing; conditioning finds it immediately. M1 is the star because it is
# physical and a reader can feel it — passive cooling is fine until it is hot.
#
# M3 is a CONFOUND with no causal power at all. It is planted precisely so the
# demo can show the engine declining to recommend it once climate is held
# fixed. A demo where every signal is real proves nothing about the ones that
# are not.
#
# NEG is the deliberate negative result: a lever a reasonable person expects to
# matter, that here genuinely does not. It ships as a card that fails, because
# six cards that all work read as staged.

MECHANISMS = {
    "M1": "passive cooling × hot climate → thermal faults → churn   (INTERACTION)",
    "M2": "consumer grade × 3-shift duty → wear faults → churn      (INTERACTION)",
    "M3": "channel=distributor-ME correlates with churn ONLY via hot climate (CONFOUND, non-causal)",
    "M4": "slow first response → churn; support_tier=pooled causes slow response (LEVER)",
    "NEG": "commissioning (self/guided/on-site) has NO effect on churn (the honest negative)",
}

# Effect sizes, in log-odds on churn. Kept in one place so the planted truth is
# a table you can read, not arithmetic scattered through the generators.
BASE_CHURN_LOGIT = -2.15          # tuned so OVERALL churn lands near 21%
W_M1_INTERACTION = 1.35           # passive AND hot
W_M1_PASSIVE_ALONE = 0.05         # ~nothing: the whole point of an interaction
W_M1_HOT_ALONE = 0.10             # ~nothing on its own either
W_M2_INTERACTION = 0.95           # consumer AND 3-shift
W_M2_CONSUMER_ALONE = 0.08
W_M4_SLOW_RESPONSE = 0.85         # first_response_h > 24
W_SERVICE_PLAN_PREMIUM = -0.45    # a lever that genuinely works, modestly
W_SERVICE_PLAN_NONE = 0.25
W_COMMISSIONING = 0.0             # NEG — identically zero, deliberately

# How strongly distributor-ME over-sells into hot climates. This is the entire
# mechanism of M3: the channel never touches churn directly.
#
# Tuned UP from 0.62 after measuring: at 0.62 the channel's unconditional lift
# was only ×1.12, and a confound nobody would have accused in the first place
# makes for a limp exoneration. The beat needs the channel to look properly
# guilty on its own — then to go quiet the moment climate is held fixed.
M3_HOT_BIAS = 0.93                # P(hot site | distributor-ME) vs ~0.30 baseline
M3_ME_SHARE = 0.17                # share of deals arriving through the channel

SEED = 20260831

CLIMATES = ["temperate", "hot", "arctic"]
DUST = ["low", "medium", "high"]
SHIFTS = ["1-shift", "2-shift", "3-shift"]
INDUSTRIES = ["construction", "food", "logistics", "mining"]
SIZE_BANDS = ["small", "mid", "large"]
COUNTRIES = ["FI", "SE", "DE", "PL", "ES", "AE", "SA", "MA", "NO"]
HOT_COUNTRIES = {"AE", "SA", "MA", "ES"}
COOLING = ["passive", "active", "liquid"]
GRADES = ["consumer", "pro", "industrial"]
IP_RATINGS = ["IP54", "IP65", "IP66"]
CHANNELS = ["paid-social", "search", "trade-fair", "distributor-ME", "referral"]
REGIONS = ["nordics", "dach", "iberia", "middle-east", "benelux"]
ANGLES = ["uptime", "price", "durability", "service"]
LANDING = ["/products", "/pricing", "/case-studies", "/spec-sheets", "/contact"]
DEVICES = ["desktop", "mobile", "tablet"]
COMMISSIONING = ["self", "guided", "on-site"]
SERVICE_PLANS = ["none", "standard", "premium"]
SUPPORT_TIERS = ["pooled", "dedicated"]

START = dt.date(2024, 1, 8)
HORIZON_DAYS = 640


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@dataclass
class World:
    rng: random.Random
    products: list = field(default_factory=list)
    customers: list = field(default_factory=list)
    sites: list = field(default_factory=list)
    campaigns: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    orders: list = field(default_factory=list)
    installs: list = field(default_factory=list)
    tickets: list = field(default_factory=list)
    feedback: list = field(default_factory=list)
    events: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    reorders: list = field(default_factory=list)
    analysis: list = field(default_factory=list)


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------

FAMILIES = ["Lifter", "Conveyor", "Compactor", "Hoist", "Sorter", "Loader"]


def gen_products(w: World) -> None:
    """42 SKUs spanning the two engineering axes the mechanisms live on.

    `grade` and `cooling` are deliberately CROSSED rather than nested. The
    obvious catalog — consumer is always passive, industrial always liquid —
    makes grade a proxy for cooling, and then M2's card is really M1's card
    wearing a different label. Crossing them costs a few more SKUs and buys
    two mechanisms that can be told apart, which is the whole point of
    planting two.
    """
    rng = w.rng
    pid = 0
    for family in FAMILIES:
        for grade, cooling in [
            ("consumer", "passive"),
            ("consumer", "active"),
            ("pro", "passive"),
            ("pro", "active"),
            ("pro", "liquid"),
            ("industrial", "active"),
            ("industrial", "liquid"),
        ]:
            pid += 1
            # Duty cycle tracks grade — a consumer unit is not rated for 3-shift,
            # which is what makes M2 physically sensible rather than arbitrary.
            duty = {"consumer": 35, "pro": 65, "industrial": 90}[grade]
            price = {"consumer": 4200, "pro": 11500, "industrial": 26800}[grade]
            w.products.append({
                "product_id": f"P{pid:03d}",
                "name": f"{family} {grade.title()} {cooling.title()}-Cooled",
                "family": family,
                "grade": grade,
                "cooling": cooling,
                "load_rating_kg": {"consumer": 500, "pro": 1500, "industrial": 4000}[grade],
                "duty_cycle_pct": duty,
                "ip_rating": rng.choice(IP_RATINGS),
                "price": price + rng.randrange(-400, 400, 50),
                "launched": (START - dt.timedelta(days=rng.randrange(200, 1400))).isoformat(),
            })


def gen_campaigns(w: World) -> None:
    rng = w.rng
    for i, channel in enumerate(CHANNELS):
        for j, region in enumerate(REGIONS):
            # distributor-ME is a middle-east channel; that is *why* it correlates
            # with hot sites, and the reason the confound is innocent rather than sly.
            if channel == "distributor-ME" and region != "middle-east":
                continue
            w.campaigns.append({
                "campaign_id": f"C{i:02d}{j:02d}",
                "channel": channel,
                "region": region,
                "message_angle": rng.choice(ANGLES),
                "spend": rng.randrange(8000, 90000, 500),
            })


# --------------------------------------------------------------------------
# Customers, sites — where M1/M2's context lives
# --------------------------------------------------------------------------

def gen_customers_and_sites(w: World, n_customers: int) -> None:
    rng = w.rng
    for i in range(1, n_customers + 1):
        country = rng.choice(COUNTRIES)
        industry = rng.choice(INDUSTRIES)
        cid = f"K{i:04d}"
        w.customers.append({
            "customer_id": cid,
            "name": f"{industry.title()} {rng.choice(['Works', 'Group', 'AB', 'Oy', 'GmbH', 'SA'])} {i}",
            "industry": industry,
            "size_band": rng.choices(SIZE_BANDS, weights=[5, 3, 2])[0],
            "country": country,
        })
        for s in range(1, rng.choices([1, 2, 3], weights=[6, 3, 1])[0] + 1):
            # Climate follows geography, so "hot" is a physical fact about the
            # site rather than a label sprinkled at random.
            if country in HOT_COUNTRIES:
                climate = rng.choices(CLIMATES, weights=[25, 72, 3])[0]
            elif country in {"NO", "SE", "FI"}:
                climate = rng.choices(CLIMATES, weights=[70, 6, 24])[0]
            else:
                climate = rng.choices(CLIMATES, weights=[78, 18, 4])[0]
            # Mining and food run harder shifts. Again: physical, not arbitrary.
            shift_w = [5, 3, 2] if industry not in {"mining", "food"} else [2, 3, 5]
            w.sites.append({
                "site_id": f"S{i:04d}{s}",
                "customer": cid,
                "climate": climate,
                "dust_level": rng.choices(DUST, weights=[3, 4, 3])[0],
                "shift_pattern": rng.choices(SHIFTS, weights=shift_w)[0],
                "altitude_m": rng.randrange(0, 1800, 10),
            })


# --------------------------------------------------------------------------
# The acquisition chain, and M3
# --------------------------------------------------------------------------

def gen_sessions_orders_installs(w: World, n_installs: int) -> None:
    rng = w.rng
    sites_by_customer: dict[str, list] = {}
    for s in w.sites:
        sites_by_customer.setdefault(s["customer"], []).append(s)

    hot_sites = [s for s in w.sites if s["climate"] == "hot"]
    me_campaigns = [c for c in w.campaigns if c["channel"] == "distributor-ME"]
    other_campaigns = [c for c in w.campaigns if c["channel"] != "distributor-ME"]

    for i in range(1, n_installs + 1):
        # M3, planted here and nowhere else: distributor-ME deals land on hot
        # sites far more often than baseline. The channel itself carries no
        # churn weight anywhere in this file — grep for it and see.
        via_me = rng.random() < M3_ME_SHARE
        if via_me and hot_sites and rng.random() < M3_HOT_BIAS:
            site = rng.choice(hot_sites)
        else:
            site = rng.choice(w.sites)
        customer = site["customer"]
        campaign = rng.choice(me_campaigns if (via_me and me_campaigns) else other_campaigns)

        sess_id = f"E{i:05d}"
        sess_ts = START + dt.timedelta(days=rng.randrange(0, HORIZON_DAYS - 120))
        w.sessions.append({
            "session_id": sess_id,
            "campaign": campaign["campaign_id"],
            "customer": customer,
            "landing_page": rng.choice(LANDING),
            "device": rng.choices(DEVICES, weights=[6, 3, 1])[0],
            "ts": sess_ts.isoformat(),
        })

        product = rng.choice(w.products)
        order_ts = sess_ts + dt.timedelta(days=rng.randrange(3, 45))
        qty = rng.choices([1, 2, 3, 5], weights=[6, 3, 2, 1])[0]
        oid = f"O{i:05d}"
        w.orders.append({
            "order_id": oid,
            "customer": customer,
            "session": sess_id,
            "product": product["product_id"],
            "qty": qty,
            "value": round(product["price"] * qty, 2),
            "ts": order_ts.isoformat(),
        })

        install_ts = order_ts + dt.timedelta(days=rng.randrange(7, 60))
        # Levers. support_tier skews with deal size, which gives the M4 card a
        # real confound to survive rather than a clean two-way split.
        big = product["price"] * qty > 20000
        w.installs.append({
            "install_id": f"I{i:05d}",
            "order_p": oid,
            "customer": customer,
            "product": product["product_id"],
            "site": site["site_id"],
            "session": sess_id,
            "commissioning": rng.choice(COMMISSIONING),
            "service_plan": rng.choices(SERVICE_PLANS, weights=[3, 5, 2])[0],
            "support_tier": rng.choices(SUPPORT_TIERS, weights=[3, 7] if big else [7, 3])[0],
            "ts": install_ts.isoformat(),
        })


# --------------------------------------------------------------------------
# Tickets — where the mechanisms become observable, and where the text lives
# --------------------------------------------------------------------------

# Vocabulary is mechanism-specific on purpose: `relate()` over an analysed text
# column should surface "thermal"/"ambient"/"shutdown" against churn, which is
# the explorer's clickable-token panel. If every ticket said the same thing the
# text half of the demo would have nothing to find.
THERMAL_BODIES = [
    "unit shuts down midday, ambient 44C on the yard, thermal cutout trips repeatedly",
    "overheating during afternoon peak, thermal protection engaged, cooling fins caked",
    "thermal shutdown again at 41C ambient, passive cooling cannot keep up in summer",
    "machine stops when ambient climbs, thermal fault logged, restarts after cooling",
    "recurring overheat alarm, heat soak in the enclosure, thermal derate all afternoon",
]
WEAR_BODIES = [
    "bearing play after continuous running, wear on the drive belt, third shift usage",
    "excessive wear on rollers, unit running 24h, duty cycle far above rating",
    "drive wear and vibration, continuous three shift operation since install",
    "belt slippage and wear, machine never idles, wear parts replaced twice",
]
ELECTRICAL_BODIES = [
    "intermittent contactor fault, panel resets on its own, no pattern found",
    "control board error code 21, replaced the relay, fault cleared",
    "power supply dropout, breaker tripped once, wiring inspected and fine",
]
USER_BODIES = [
    "operator loaded above rated capacity, retrained the crew, no defect found",
    "wrong operating mode selected, user error, showed the team the correct sequence",
    "guard interlock left open, machine correctly refused to start, user error",
]
GOOD_FEEDBACK = [
    "runs well, uptime has been excellent since commissioning",
    "solid machine, support answered quickly when we asked",
    "no complaints, the line has kept pace all quarter",
    "reliable so far, operators like the controls",
]
BAD_FEEDBACK = [
    "too much downtime in hot weather, we lost a shift to it",
    "keeps overheating in summer, not what we were promised on uptime",
    "support took days to come back to us while the line was stopped",
    "wear parts go faster than expected at our duty cycle",
]


def gen_tickets_feedback(w: World) -> None:
    rng = w.rng
    sites = {s["site_id"]: s for s in w.sites}
    products = {p["product_id"]: p for p in w.products}
    tno = fno = 0

    for inst in w.installs:
        site = sites[inst["site"]]
        prod = products[inst["product"]]
        hot = site["climate"] == "hot"
        passive = prod["cooling"] == "passive"
        consumer = prod["grade"] == "consumer"
        three_shift = site["shift_pattern"] == "3-shift"

        # M1 and M2 express themselves as FAULTS first. Churn follows from the
        # experience, not directly from the spec sheet — which is what makes the
        # causal chain a chain rather than a single arrow.
        thermal_rate = 0.06 + (0.52 if (passive and hot) else 0.0) + (0.04 if hot else 0.0)
        wear_rate = 0.05 + (0.38 if (consumer and three_shift) else 0.0)

        n_thermal = sum(1 for _ in range(3) if rng.random() < thermal_rate)
        n_wear = sum(1 for _ in range(3) if rng.random() < wear_rate)
        n_other = sum(1 for _ in range(2) if rng.random() < 0.11)

        install_date = dt.date.fromisoformat(inst["ts"])
        pooled = inst["support_tier"] == "pooled"

        for kind, count in (("overheat", n_thermal), ("wear", n_wear), ("other", n_other)):
            for _ in range(count):
                tno += 1
                if kind == "overheat":
                    body, category = rng.choice(THERMAL_BODIES), "overheat"
                elif kind == "wear":
                    body, category = rng.choice(WEAR_BODIES), "wear"
                elif rng.random() < 0.5:
                    body, category = rng.choice(ELECTRICAL_BODIES), "electrical"
                else:
                    body, category = rng.choice(USER_BODIES), "user-error"

                # M4 is planted HERE: the tier causes the response time. The tier
                # is the lever; the response time is the mechanism it acts through.
                if pooled:
                    frh = rng.choices([4, 12, 30, 54, 96], weights=[2, 3, 4, 4, 2])[0]
                else:
                    frh = rng.choices([1, 3, 8, 18, 40], weights=[4, 4, 3, 2, 1])[0]

                w.tickets.append({
                    "ticket_id": f"T{tno:06d}",
                    "install": inst["install_id"],
                    "opened": (install_date + dt.timedelta(days=rng.randrange(20, 420))).isoformat(),
                    "category": category,
                    "body": body,
                    "first_response_h": frh,
                    "resolved": rng.random() < 0.88,
                })

        if rng.random() < 0.42:
            fno += 1
            unhappy = (n_thermal + n_wear) > 0 and rng.random() < 0.72
            w.feedback.append({
                "feedback_id": f"F{fno:06d}",
                "install": inst["install_id"],
                "score": rng.choices([1, 2, 3], weights=[3, 4, 3])[0] if unhappy
                else rng.choices([4, 5], weights=[4, 6])[0],
                "body": rng.choice(BAD_FEEDBACK if unhappy else GOOD_FEEDBACK),
                "ts": (install_date + dt.timedelta(days=rng.randrange(60, 500))).isoformat(),
            })


# --------------------------------------------------------------------------
# The outcome
# --------------------------------------------------------------------------

def gen_reorders(w: World) -> None:
    """The label. Churn is a function of the mechanisms and nothing else.

    Read this function as the ground truth: if a field is not referenced here,
    it does not cause churn, however strongly it may correlate with it. That is
    what makes M3 checkable and the NEG card honest.
    """
    rng = w.rng
    sites = {s["site_id"]: s for s in w.sites}
    products = {p["product_id"]: p for p in w.products}

    slow_by_install: dict[str, bool] = {}
    for t in w.tickets:
        if t["first_response_h"] > 24:
            slow_by_install[t["install"]] = True

    for i, inst in enumerate(w.installs, start=1):
        site = sites[inst["site"]]
        prod = products[inst["product"]]
        passive = prod["cooling"] == "passive"
        hot = site["climate"] == "hot"
        consumer = prod["grade"] == "consumer"
        three_shift = site["shift_pattern"] == "3-shift"

        z = BASE_CHURN_LOGIT
        if passive and hot:
            z += W_M1_INTERACTION
        else:
            z += W_M1_PASSIVE_ALONE if passive else 0.0
            z += W_M1_HOT_ALONE if hot else 0.0
        if consumer and three_shift:
            z += W_M2_INTERACTION
        elif consumer:
            z += W_M2_CONSUMER_ALONE
        if slow_by_install.get(inst["install_id"]):
            z += W_M4_SLOW_RESPONSE
        if inst["service_plan"] == "premium":
            z += W_SERVICE_PLAN_PREMIUM
        elif inst["service_plan"] == "none":
            z += W_SERVICE_PLAN_NONE
        z += W_COMMISSIONING  # NEG: identically zero, kept visible on purpose

        churned = rng.random() < logistic(z)
        install_date = dt.date.fromisoformat(inst["ts"])
        due = install_date + dt.timedelta(days=400)
        w.reorders.append({
            "reorder_id": f"R{i:05d}",
            "install": inst["install_id"],
            "period": f"{due.year}-Q{(due.month - 1) // 3 + 1}",
            "reordered": str(not churned).lower(),
        })


# --------------------------------------------------------------------------
# Events (observed) and actions (chosen)
# --------------------------------------------------------------------------

def gen_events_actions(w: World) -> None:
    rng = w.rng
    sessions = {s["session_id"]: s for s in w.sessions}
    reordered = {r["install"]: r["reordered"] == "true" for r in w.reorders}
    # Index by install first. The obvious inner scan over every ticket per
    # install is O(installs × tickets) — a hair over 9M iterations at demo
    # volume, and quadratic in whatever we raise it to.
    order_value = {o["order_id"]: o["value"] for o in w.orders}
    tickets_by_install: dict[str, list] = {}
    for t in w.tickets:
        tickets_by_install.setdefault(t["install"], []).append(t)
    feedback_by_install: dict[str, list] = {}
    for f in w.feedback:
        feedback_by_install.setdefault(f["install"], []).append(f)
    eno = ano = 0

    for inst in w.installs:
        sess = sessions.get(inst["session"])
        cust = inst["customer"]
        base = dt.date.fromisoformat(sess["ts"]) if sess else START

        def ev(kind, day_off, **kw):
            nonlocal eno
            eno += 1
            w.events.append({
                "event_id": f"V{eno:06d}",
                "customer": cust,
                "session": inst["session"] or "",
                "install": inst["install_id"],
                "type": kind,
                "page": kw.get("page", ""),
                "body": kw.get("body", ""),
                "value": kw.get("value", ""),
                "ts": (base + dt.timedelta(days=day_off)).isoformat(),
            })

        ev("ad_click", 0, page=sess["landing_page"] if sess else "/products")
        for k in range(rng.randrange(1, 4)):
            ev("page_view", 1 + k, page=rng.choice(LANDING))
        if rng.random() < 0.7:
            ev("spec_download", 4)
        ev("quote_request", 9)
        ev("purchase", 30, value=order_value[inst["order_p"]])
        ev("install", 60)

        for t in tickets_by_install.get(inst["install_id"], []):
            off = (dt.date.fromisoformat(t["opened"]) - base).days
            if t["category"] in ("overheat", "wear"):
                ev("fault_report", off, body=t["body"])
            ev("ticket_open", off, body=t["body"])
        for f in feedback_by_install.get(inst["install_id"], []):
            ev("feedback_given", (dt.date.fromisoformat(f["ts"]) - base).days, body=f["body"])

        ev("reorder" if reordered.get(inst["install_id"]) else "lapse", 460)

        # Actions mirror the lever columns on `installs` from one source of
        # truth, so the log and the recommendable columns cannot disagree.
        for lever, choice in (
            ("sku_quoted", inst["product"]),
            ("commissioning", inst["commissioning"]),
            ("service_plan", inst["service_plan"]),
            ("support_tier", inst["support_tier"]),
        ):
            ano += 1
            w.actions.append({
                "action_id": f"A{ano:06d}",
                "customer": cust,
                "install": inst["install_id"],
                "lever": lever,
                "choice": choice,
                "ts": inst["ts"],
            })


# --------------------------------------------------------------------------
# Verification — does the planted truth actually show up?
# --------------------------------------------------------------------------

def report(w: World) -> list[str]:
    """Report the realised contrasts. This is probe #7 answered at generation
    time: if M1's interaction does not separate here, no amount of SQL will
    find it later, and the weights above need changing before anything is loaded.
    """
    sites = {s["site_id"]: s for s in w.sites}
    products = {p["product_id"]: p for p in w.products}
    camps = {c["campaign_id"]: c for c in w.campaigns}
    sess = {s["session_id"]: s for s in w.sessions}
    churn = {r["install"]: r["reordered"] == "false" for r in w.reorders}

    def rate(pred):
        hits = [churn[i["install_id"]] for i in w.installs if pred(i)]
        return (100.0 * sum(hits) / len(hits), len(hits)) if hits else (float("nan"), 0)

    def P(i):
        return products[i["product"]]

    def S(i):
        return sites[i["site"]]

    out = ["", "=" * 78, "PLANTED MECHANISMS — realised rates", "=" * 78]
    for k, v in MECHANISMS.items():
        out.append(f"  {k:4} {v}")

    all_r, all_n = rate(lambda i: True)
    out += ["", f"baseline churn: {all_r:.1f}%  (n={all_n})", "",
            "M1  passive × hot — the interaction is the demo's star:"]
    for label, pred in [
        ("passive + hot   ", lambda i: P(i)["cooling"] == "passive" and S(i)["climate"] == "hot"),
        ("passive + not-hot", lambda i: P(i)["cooling"] == "passive" and S(i)["climate"] != "hot"),
        ("not-passive + hot", lambda i: P(i)["cooling"] != "passive" and S(i)["climate"] == "hot"),
        ("neither         ", lambda i: P(i)["cooling"] != "passive" and S(i)["climate"] != "hot"),
    ]:
        r, n = rate(pred)
        out.append(f"    {label}  {r:5.1f}%   n={n}")

    out += ["", "M2  consumer × 3-shift:"]
    for label, pred in [
        ("consumer + 3-shift ", lambda i: P(i)["grade"] == "consumer" and S(i)["shift_pattern"] == "3-shift"),
        ("consumer + other   ", lambda i: P(i)["grade"] == "consumer" and S(i)["shift_pattern"] != "3-shift"),
        ("other + 3-shift    ", lambda i: P(i)["grade"] != "consumer" and S(i)["shift_pattern"] == "3-shift"),
    ]:
        r, n = rate(pred)
        out.append(f"    {label}  {r:5.1f}%   n={n}")

    def channel(i):
        s = sess.get(i["session"])
        return camps[s["campaign"]]["channel"] if s else "?"

    out += ["", "M3  distributor-ME — must look guilty UNCONDITIONALLY and innocent GIVEN climate:"]
    r, n = rate(lambda i: channel(i) == "distributor-ME")
    out.append(f"    distributor-ME (all)          {r:5.1f}%   n={n}")
    r, n = rate(lambda i: channel(i) != "distributor-ME")
    out.append(f"    other channels (all)          {r:5.1f}%   n={n}")
    r, n = rate(lambda i: channel(i) == "distributor-ME" and S(i)["climate"] == "hot")
    out.append(f"    distributor-ME | hot          {r:5.1f}%   n={n}")
    r, n = rate(lambda i: channel(i) != "distributor-ME" and S(i)["climate"] == "hot")
    out.append(f"    other channels | hot          {r:5.1f}%   n={n}   <- should MATCH the line above")

    slow = {t["install"] for t in w.tickets if t["first_response_h"] > 24}
    out += ["", "M4  slow first response, and the tier that causes it:"]
    for label, pred in [
        ("had a slow response", lambda i: i["install_id"] in slow),
        ("never slow         ", lambda i: i["install_id"] not in slow),
        ("support=pooled     ", lambda i: i["support_tier"] == "pooled"),
        ("support=dedicated  ", lambda i: i["support_tier"] == "dedicated"),
    ]:
        r, n = rate(pred)
        out.append(f"    {label}  {r:5.1f}%   n={n}")

    out += ["", "NEG commissioning — the honest negative, all three should be flat:"]
    for c in COMMISSIONING:
        r, n = rate(lambda i, c=c: i["commissioning"] == c)
        out.append(f"    commissioning={c:9}  {r:5.1f}%   n={n}")

    out += ["", "service_plan — a lever that genuinely works (for contrast with NEG):"]
    for p in SERVICE_PLANS:
        r, n = rate(lambda i, p=p: i["service_plan"] == p)
        out.append(f"    service_plan={p:9}   {r:5.1f}%   n={n}")

    cats = Counter(t["category"] for t in w.tickets)
    out += ["", "-" * 78, "row counts:"]
    for name in TABLES:
        out.append(f"    {name:12} {len(getattr(w, name)):>7}")
    out.append(f"    ticket categories: {dict(cats)}")
    return out


def gen_analysis(w: World) -> None:
    """The flat analysis table — one row per install, every explanatory field on it.

    This exists because of a measured limitation, not a modelling preference,
    and it is worth being precise about which. `relate()` takes no filter (its
    `to` is the target proposition, not a slice), so conditioning — the move
    that reveals an interaction — has to come from the table being queried. The
    only in-database way to narrow a table is a VIEW, and a view can neither
    bake a link-path WHERE (it silently yields an empty view,
    td-20260831214438282862) nor project a link-path column (that one at least
    fails loud).

    Nor can the flattening itself be done in SQL: there is no `CREATE TABLE AS
    SELECT` and no `INSERT … SELECT`, so no statement derives one table from
    another across links. Hence it happens here, and ships as a 13th CSV
    alongside the normalised tables rather than being built server-side.

    The links are still what does the work — every column below is reached by
    traversing them — but the traversal runs in this process, not in Aito.
    """
    sites = {s["site_id"]: s for s in w.sites}
    products = {p["product_id"]: p for p in w.products}
    customers = {c["customer_id"]: c for c in w.customers}
    campaigns = {c["campaign_id"]: c for c in w.campaigns}
    sessions = {s["session_id"]: s for s in w.sessions}
    orders = {o["order_id"]: o for o in w.orders}
    churn = {r["install"]: r["reordered"] == "false" for r in w.reorders}

    thermal, slow, ticket_n = {}, {}, Counter()
    for t in w.tickets:
        ticket_n[t["install"]] += 1
        if t["category"] == "overheat":
            thermal[t["install"]] = True
        if t["first_response_h"] > 24:
            slow[t["install"]] = True
    scores: dict[str, list] = {}
    for f in w.feedback:
        scores.setdefault(f["install"], []).append(f["score"])

    for inst in w.installs:
        site = sites[inst["site"]]
        prod = products[inst["product"]]
        cust = customers[inst["customer"]]
        sess = sessions.get(inst["session"])
        camp = campaigns[sess["campaign"]] if sess else None
        order = orders[inst["order_p"]]
        iid = inst["install_id"]
        fb = scores.get(iid, [])
        w.analysis.append({
            "install_id": iid,
            # customer & site
            "industry": cust["industry"], "size_band": cust["size_band"],
            "country": cust["country"], "climate": site["climate"],
            "dust_level": site["dust_level"], "shift_pattern": site["shift_pattern"],
            # product
            "family": prod["family"], "grade": prod["grade"], "cooling": prod["cooling"],
            "ip_rating": prod["ip_rating"], "duty_cycle_pct": prod["duty_cycle_pct"],
            # acquisition
            "channel": camp["channel"] if camp else "unknown",
            "region": camp["region"] if camp else "unknown",
            "message_angle": camp["message_angle"] if camp else "unknown",
            "landing_page": sess["landing_page"] if sess else "unknown",
            "device": sess["device"] if sess else "unknown",
            # levers
            "commissioning": inst["commissioning"], "service_plan": inst["service_plan"],
            "support_tier": inst["support_tier"],
            # observed experience
            "had_thermal_fault": str(iid in thermal).lower(),
            "slow_first_response": str(iid in slow).lower(),
            "ticket_count": ticket_n[iid],
            "feedback_score": round(sum(fb) / len(fb)) if fb else "",
            "order_value": order["value"],
            "installed_on": inst["ts"],
            # the label, in both spellings the cards want
            "churned": str(churn.get(iid, False)).lower(),
            "reordered": str(not churn.get(iid, False)).lower(),
        })


TABLES = ["products", "customers", "sites", "campaigns", "sessions", "orders",
          "installs", "tickets", "feedback", "events", "actions", "reorders",
          "analysis"]


def write_csvs(w: World, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        rows = getattr(w, name)
        with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def build(seed: int = SEED, n_customers: int = 520, n_installs: int = 3000) -> World:
    w = World(rng=random.Random(seed))
    gen_products(w)
    gen_campaigns(w)
    gen_customers_and_sites(w, n_customers)
    gen_sessions_orders_installs(w, n_installs)
    gen_tickets_feedback(w)
    gen_reorders(w)
    gen_events_actions(w)
    gen_analysis(w)
    return w


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data", type=Path)
    ap.add_argument("--seed", default=SEED, type=int)
    ap.add_argument("--installs", default=3000, type=int)
    ap.add_argument("--customers", default=520, type=int)
    args = ap.parse_args()

    w = build(seed=args.seed, n_customers=args.customers, n_installs=args.installs)
    write_csvs(w, args.out)
    print("\n".join(report(w)))
    print(f"\nwrote {len(TABLES)} CSVs to {args.out}/")


if __name__ == "__main__":
    main()
