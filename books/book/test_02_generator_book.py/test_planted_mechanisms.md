# Planted mechanisms

The ground truth the dashboard is measured against.

- **M1** — passive cooling × hot climate → thermal faults → churn   (INTERACTION)
- **M2** — consumer grade × 3-shift duty → wear faults → churn      (INTERACTION)
- **M3** — channel=distributor-ME correlates with churn ONLY via hot climate (CONFOUND, non-causal)
- **M4** — slow first response → churn; support_tier=pooled causes slow response (LEVER)
- **NEG** — commissioning (self/guided/on-site) has NO effect on churn (the honest negative)


## Baseline

churn 19.9% over n=3000


## M1 — passive cooling x hot climate

An interaction: neither ingredient should be dangerous alone.
- passive + hot: **45.2%** (n=431)
- passive + not-hot: **17.9%** (n=429)
- not-passive + hot: **16.1%** (n=1054)
- neither: **14.4%** (n=1086)

ok

## M2 — consumer grade x 3-shift duty

- consumer + 3-shift: **43.3%** (n=277)
- consumer + other: **24.0%** (n=559)
- other + 3-shift: **14.8%** (n=752)


## M3 — the confound

Must look guilty unconditionally and innocent once climate is held fixed.
- distributor-ME, all sites: **24.2%** (n=537)
- other channels, all sites: **19.0%** (n=2463)
- distributor-ME, hot only: **24.5%** (n=519)
- other channels, hot only: **24.6%** (n=966)

ok
ok

## M4 — slow first response, and the tier that causes it

- had a slow response: **39.7%** (n=774)
- never slow: **13.1%** (n=2226)
- support_tier=pooled: **25.4%** (n=1494)
- support_tier=dedicated: **14.5%** (n=1506)


## NEG — the card that must find nothing

- commissioning=self: **nan%** (n=0)
- commissioning=guided: **nan%** (n=0)
- commissioning=on-site: **nan%** (n=0)

ok

## service_plan — a lever that DOES work, for contrast

- service_plan=none: **nan%** (n=0)
- service_plan=standard: **nan%** (n=0)
- service_plan=premium: **nan%** (n=0)

ok

## Row counts

- products: 42
- customers: 520
- sites: 804
- campaigns: 21
- sessions: 3000
- orders: 3000
- installs: 3000
- tickets: 2841
- feedback: 1209
- events: 29438
- actions: 12000
- reorders: 3000
- analysis: 3000

ok
