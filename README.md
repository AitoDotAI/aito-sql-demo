# aito-sql-demo — a 360° view of the business, in SQL

A machinery vendor's customer journey — ads → site → order → install → support → feedback →
churn — with the root cause of each outcome and the lever that moves it, computed by
[Aito](https://aito.ai) and asked **entirely in SQL** over the Postgres wire protocol.

No model is trained. Nothing is precomputed. Every number on the page is one SQL statement,
shown next to the number it produced and editable in place.

## Why this demo exists

Aito's sibling demos already show prediction, explanation, and a Segment-360 dashboard. The
thing none of them show is the surface: **your existing Postgres tools connect to Aito and
work unchanged.** So the constraint here is self-imposed and total — if a claim cannot be
written as SQL, it does not ship. The loader uses `COPY … FROM STDIN` over pgwire; the API
runs SELECTs against the read-only `/api/v2/_sql` endpoint; there is no Aito SDK call anywhere
in the request path.

## The honest part

The data is **synthetic and deliberately so**, because the demo's strongest claim needs a
ground truth to check against. `src/generate.py` plants five mechanisms and prints what it
planted, so you can compare what was buried with what the engine recovered:

| | mechanism | what the dashboard should do |
|---|---|---|
| **M1** | passive cooling × hot climate → thermal faults → churn | recover it — but only when conditioned; neither ingredient is dangerous alone |
| **M2** | consumer grade × 3-shift duty → wear → churn | recover it, same shape |
| **M3** | `distributor-ME` correlates with churn **only** via hot climate | **clear it.** The channel looks guilty at ×1.21 and vanishes once climate is held fixed |
| **M4** | slow first response → churn; `support_tier` causes the delay | recover it, and name the lever |
| **NEG** | commissioning level does nothing at all | **find nothing**, and say so |

Card 5 fails on purpose. A dashboard where all six cards work is one nobody should trust.

## Run it

```bash
./do install     # uv sync + npm install
python -m src.generate --out data     # writes 13 CSVs, prints the planted mechanisms
python -m src.load --drop             # COPY over pgwire into the Aito instance
./do dev                              # uvicorn :8800 + next dev :8801
```

`.env` needs `AITO_API_URL` and `AITO_API_KEY`. On a multi-database server the pgwire `dbname`
is the database from the URL path (`/db/<name>/`), **not** the environment — get it wrong and
the server says `password authentication failed`, deliberately, so a reachable port cannot be
used to enumerate databases. `shell.nix` derives it for you.

## Layout

| path | what |
|---|---|
| `src/generate.py` | the world, the planted mechanisms, and a report of what was realised |
| `src/load.py` | `COPY` over pgwire — nothing else |
| `sql/01_schema.sql` | 13 tables; `REFERENCES` declares the Aito links the cards traverse |
| `src/cards.py` | the six cards, each four SQL statements and nothing else |
| `src/app.py` | thin routes; every response carries the SQL that produced it |
| `docs/design.md` | the design, and every measured limit found building it |

## Reading the numbers

- **Lift** is always shown with a ▲/▼ glyph and the value. The status red and green in this
  design system sit at ΔE 2.7 under deuteranopia simulation — to a deuteranope they are the
  same colour — so colour is a redundant cue here, never the thing carrying the meaning.
- **`n` sits beside every lift.** A lift without the evidence count behind it is how
  dashboards mislead people.
- **Predicted rates sit below raw rates.** Support-tempering shrinks confidence toward the
  base rate on thin or redundant evidence, so a thinly-populated cell is understated on
  purpose. That is the engine being honest, not the demo hedging.
