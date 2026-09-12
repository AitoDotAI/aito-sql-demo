# What the engine says

instance: `https://internal.aito.ai/db/aito-sql-demo`


## Baseline

book-wide churn: **20.0%**


## The six cards

Each card's headline number, as the dashboard prints it.

- **1. Passive cooling in hot climates** (M1): 37.4% churn, ×1.87
- **2. Consumer grade on 3-shift duty** (M2): 33.4% churn, ×1.68
- **3. First response time** (M4): 39.5% churn, ×1.98
- **4. The channel that looks guilty** (M3): 24.1% churn, ×1.21
- **5. Commissioning level** (NEG): 20.0% churn, ×1.00
- **6. Service plan** (lever): 22.2% churn, ×1.11

ok
ok

## M1 — the interaction only appears under conditioning

- passive cooling, whole book: ×1.56
- passive cooling, inside hot sites: ×1.81
- passive cooling, inside temperate sites: ×1.08

ok
ok
ok

## M3 — the confound is exonerated by conditioning

- distributor-ME, whole book: ×1.12
- distributor-ME, inside hot sites: ×1.00

ok
ok

## NEG — the card that must keep finding nothing

- commissioning = on-site: 18.8% churn
- commissioning = self: 20.0% churn
- commissioning = guided: 21.2% churn

spread: 2.3 points
ok

## A lever that does work, for contrast

- support_tier = dedicated: 14.6% churn
- support_tier = pooled: 25.4% churn

ok
