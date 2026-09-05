"""The six cards — each one four SQL statements, and nothing else.

The point of this file is that it is READABLE AS SQL. Every number the
dashboard shows comes from a statement here, verbatim, and the UI displays the
same text it ran. If a card's claim cannot be written as SQL, it does not ship.

A card is a five-slot binding — `table`, `outcome`, `explain`, `lever`, `slice`
— which is what makes the dashboard editable (see docs/design.md, "Editable
dashboards"): the grammar below is a template, and the cards are its arguments.

Everything runs through the read-only REST `_sql` endpoint, which takes RAW SQL
as the request body (not a JSON envelope — a JSON body fails with "unexpected
character '{' at position 0"). Writes and DDL are wire-protocol only, so they
live in src/load.py; nothing here writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The conditioning views. relate() takes no filter — its `to` is the target
# proposition, not a slice — so narrowing means querying a narrower table, and
# a view is the only way to make one. These are created by load.py.
VIEWS = {
    "hot_sites": "SELECT * FROM analysis WHERE climate = 'hot'",
    "temperate_sites": "SELECT * FROM analysis WHERE climate = 'temperate'",
    "three_shift": "SELECT * FROM analysis WHERE shift_pattern = '3-shift'",
    "consumer_grade": "SELECT * FROM analysis WHERE grade = 'consumer'",
}


def q(s: str) -> str:
    """Collapse a SQL literal to one line for display without changing it."""
    return " ".join(s.split())


@dataclass
class Card:
    key: str
    title: str
    unit: str
    question: str
    kpi: str                       # -> (value, p)
    causes: str                    # -> (related, lift, info, n)
    levers: str                    # -> (value, p[, why])
    baseline: str                  # -> (value, p)
    note: str = ""                 # the honest caveat, shown on the card
    mechanism: str = ""            # which planted mechanism this recovers
    conditioned: str | None = None # a second causes query, for the interaction beat
    conditioned_label: str = ""
    rank: int = 0
    # Which table each relate() runs against. Needed because group sizes have to
    # be counted against the SAME slice the lift was computed on — counting
    # `analysis` for a lift measured on `hot_sites` would put an honest-looking `n`
    # next to a number it does not describe.
    table: str = "analysis"
    conditioned_table: str | None = None


BASELINE = "SELECT value, p FROM predict('analysis','churned')"

CARDS: list[Card] = [
    Card(
        key="thermal",
        title="Passive cooling in hot climates",
        unit="installs",
        question="Why do hot-climate sites churn twice as often?",
        mechanism="M1",
        rank=1,
        kpi=q("""SELECT value, p FROM predict('analysis','churned',
                 where => 'cooling = ''passive'' AND climate = ''hot''')"""),
        causes=q("""SELECT * FROM relate('analysis', to => 'churned = ''true''',
                    fields => 'cooling, climate, had_thermal_fault', k => 6)"""),
        conditioned=q("""SELECT * FROM relate('hot_sites', to => 'churned = ''true''',
                         fields => 'cooling', k => 3)"""),
        conditioned_label="the same question, asked only of hot-climate sites",
        levers=q("""SELECT * FROM recommend('hot_sites','cooling',
                    goal => 'churned = ''false''', why => true, k => 3)"""),
        baseline=BASELINE,
        note="Neither ingredient is dangerous alone. Passive cooling reads ×1.56 over the whole "
             "book and ×1.08 inside temperate sites — it is the combination that bites, which is "
             "why ranking single fields by lift never finds it.",
        conditioned_table="hot_sites",
    ),
    Card(
        key="duty",
        title="Consumer grade on 3-shift duty",
        unit="installs",
        question="Which machines are being asked to do more than they are rated for?",
        mechanism="M2",
        rank=2,
        kpi=q("""SELECT value, p FROM predict('analysis','churned',
                 where => 'grade = ''consumer'' AND shift_pattern = ''3-shift''')"""),
        causes=q("""SELECT * FROM relate('analysis', to => 'churned = ''true''',
                    fields => 'grade, shift_pattern, duty_cycle_pct', k => 6)"""),
        conditioned=q("""SELECT * FROM relate('three_shift', to => 'churned = ''true''',
                         fields => 'grade', k => 3)"""),
        conditioned_label="the same question, asked only of 3-shift sites",
        levers=q("""SELECT * FROM recommend('three_shift','grade',
                    goal => 'churned = ''false''', why => true, k => 3)"""),
        baseline=BASELINE,
        note="A second interaction, and a cheaper fix than the first: the duty cycle is printed "
             "on the spec sheet, so this one is catchable at quote time.",
        conditioned_table="three_shift",
    ),
    Card(
        key="response",
        title="First response time",
        unit="installs",
        question="Does answering faster actually keep customers?",
        mechanism="M4",
        rank=3,
        kpi=q("""SELECT value, p FROM predict('analysis','churned',
                 where => 'slow_first_response = ''true''')"""),
        causes=q("""SELECT * FROM relate('analysis', to => 'churned = ''true''',
                    fields => 'slow_first_response, support_tier, ticket_count', k => 6)"""),
        levers=q("""SELECT * FROM recommend('analysis','support_tier',
                    goal => 'churned = ''false''', why => true, k => 3)"""),
        baseline=BASELINE,
        note="The only card whose lever is purely operational — no engineering change, no "
             "re-quote. It is also the one most likely to be confounded by deal size, since "
             "bigger deals get dedicated support anyway.",
    ),
    Card(
        key="channel",
        title="The channel that looks guilty",
        unit="installs",
        question="Should we cut spend on the distributor channel?",
        mechanism="M3",
        rank=4,
        kpi=q("""SELECT value, p FROM predict('analysis','churned',
                 where => 'channel = ''distributor-ME''')"""),
        causes=q("""SELECT * FROM relate('analysis', to => 'churned = ''true''',
                    fields => 'channel, region', k => 6)"""),
        conditioned=q("""SELECT * FROM relate('hot_sites', to => 'churned = ''true''',
                         fields => 'channel', k => 3)"""),
        conditioned_label="the same question, holding climate fixed — the channel vanishes",
        levers=q("""SELECT * FROM recommend('analysis','channel',
                    goal => 'churned = ''false''', why => true, k => 4)"""),
        baseline=BASELINE,
        note="ANSWER: no. The channel sells into the Middle East, the Middle East is hot, and hot "
             "is what churns. Hold climate fixed and distributor-ME leaves the top of the list "
             "entirely. Cutting it would have cost the revenue and fixed nothing.",
        conditioned_table="hot_sites",
    ),
    Card(
        key="commissioning",
        title="Commissioning level",
        unit="installs",
        question="Is on-site commissioning worth what it costs us?",
        mechanism="NEG",
        rank=5,
        kpi=q("""SELECT value, p FROM predict('analysis','churned',
                 where => 'commissioning = ''self''')"""),
        causes=q("""SELECT * FROM relate('analysis', to => 'churned = ''true''',
                    fields => 'commissioning', k => 3)"""),
        levers=q("""SELECT * FROM recommend('analysis','commissioning',
                    goal => 'churned = ''false''', k => 3)"""),
        baseline=BASELINE,
        note="THE CARD THAT FAILS, and it ships on purpose. The three commissioning levels sit "
             "within about two points of each other — there is no lever here. A dashboard where "
             "every card works is a dashboard nobody should trust; this is what an honest null "
             "looks like when you go looking for one.",
    ),
    Card(
        key="service",
        title="Service plan",
        unit="installs",
        question="Which plan should we push, and what is it worth?",
        mechanism="lever",
        rank=6,
        kpi=q("""SELECT value, p FROM predict('analysis','churned',
                 where => 'service_plan = ''none''')"""),
        causes=q("""SELECT * FROM relate('analysis', to => 'churned = ''true''',
                    fields => 'service_plan, order_value', k => 5)"""),
        levers=q("""SELECT * FROM recommend('analysis','service_plan',
                    goal => 'churned = ''false''', why => true, k => 3)"""),
        baseline=BASELINE,
        note="Read this one beside the commissioning card. Same shape of question, same query, "
             "and a real gap between the options — which is what makes the flat card next to it "
             "meaningful rather than a bug.",
    ),
]

CARDS_BY_KEY = {c.key: c for c in CARDS}
