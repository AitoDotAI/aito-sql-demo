# aito-sql-demo — design

Status: **draft for review** (2026-08-16). Ticket `td-20260815095530460426`, owner `aito-sql-demo`.

The brief (Company-AI doc `dc-20260816193644027164`) says *why* this demo exists and sets the rules.
This file is *how*: the entity model, the link directions, and the exact SQL each screen runs. Where
the brief and this file disagree, the brief wins — this one only adds detail below it.

## The theme: a 360° view of the business

One question — *which acquisition channel produces customers who churn?* — is the spine. But the demo
is not one query; it is **the whole business in one database**, every stage of the chain carrying a KPI
and the lever that moves it:

```
   ads  →  website  →  conversion  →  purchase  →  install  →  support  →  feedback  →  churn
    │         │            │             │            │           │           │           │
  quote     lead        win rate      order        fault       resolved    detractors   reorder
   rate     rate                       value        rate        <24h         share        rate
```

Each stage is a **card** in the Segment-360 grammar: the KPI, the root causes ranked by lift, the
recommended levers, and the size of the prize if you pull the top one.

> **KPI · root causes (`relate`) · recommended levers (`recommend`) · pull the top lever → X% · Ypp better**

That grammar is the **front door**, not the demo. Two things separate it from the 360 dashboards that
already exist next door: every number on the card is a SQL statement you can read *and the card shows
it*, and the cards are the top rows of an exhaustively **generated** map rather than a hand-picked six —
behind which everything is clickable. See
[the explorer](#the-web-surface-a-navigable-cause-and-effect-explorer).

### Why 360° and not just the churn query

The churn question alone proves inference. The full chain proves the thing that is actually hard: the
cause of the last stage lives four hops back in the first. A dashboard per stage — one per tool in the
real stack — cannot see across the seams, which is exactly why the naive answer wins in real companies.
Six cards from one schema *is* the argument.

One caveat to keep honest, because a sharp reader will raise it: those five systems are separate because
five teams own them, not because a database could not hold them. Consolidating them is an ETL problem
and this demo generates its data pre-joined. So the claim to make is *"once it is in one schema, the
causes are one query away"* — never *"we solved your integration problem."*

## What is already built elsewhere — and what is actually new here

Checked against the eight sibling demos on 2026-08-16, because a demo that duplicates one of them is
not worth building.

| Thing | Already shipped in | Verdict |
|---|---|---|
| Six-KPI 360 dashboard with root causes, lever, `$why` per number | **`aito-agent-demo`** ("Segment 360", `_relate $on` + `_recommend`) | **not new** — a static 360 would be a re-skin |
| Churn prediction | `aito-ecommerce-demo` | not new |
| Industrial-machinery B2B domain | `aito-erp-demo` (Metsä Machinery tenant) | not new |
| `$why` renderers | `aito-erp-demo`, `-agent-`, `-accounting-` | not new |
| "No training. Add a row, the next prediction reflects it." | four READMEs verbatim | the *house* claim, not ours |
| Honest held-out measurement | `aito-hacker-news-demo` (AUC + top-decile lift on a **temporal** holdout) | not new — and their bar is higher than k-fold |
| **SQL / pgwire as the surface** | **nothing. Zero of eight.** | **this is the whole reason the lane exists** |

So the differentiator is not a capability, it is a **claim of a different kind**: not *Aito can predict
X* but *your existing tools work unchanged*. The audience is a developer evaluating an on-ramp, not a
buyer evaluating a feature.

And it means the static dashboard is the wrong web surface — it already exists next door. What does not
exist anywhere is the thing below.

## The web surface: a navigable cause-and-effect explorer

The static card grid is the *front door*, not the product. Behind it, every object in the business is
clickable, and clicking it asks the same four questions again in its context.

### Why this is possible here and nowhere else

Endless navigation normally requires pre-aggregating every cube, which is why dashboards die at the long
tail: a specific SKU, in one region, on 3-shift sites has no dashboard, because nobody built that slice.
Here **conditioning is just another `WHERE`, computed on click** — so every slice is a first-class
citizen, including the ones nobody anticipated. No cube, no pre-aggregation, no "this combination isn't
supported". That is a structural claim about the database, not a UI trick.

### The navigation model — four panels, one component

Every node — a product, a region, a channel, an event type, a ticket, **a token in a ticket** — renders
the same four panels:

| Panel | Question | Query |
|---|---|---|
| **What is this** | the object and its rows | `SELECT … WHERE <ctx>` |
| **What causes it** | it as the *outcome* | `relate(…, to => '<this> AND <ctx>')` |
| **What it causes** | it as *evidence*, against each downstream outcome | `relate(<downstream>, fields => '<this>', to => …)` |
| **What to do** | the lever, ranked | `recommend(…, goal => …, given => '<this> AND <ctx>')` |

One component parameterised by `(object, filter context)`. Every link in every panel opens another
instance of it. The app is therefore ~one component and four query shapes — the database does the work,
which is the same argument as the psql spine rather than a competing one.

The filter context accumulates as a breadcrumb (`hot climate → 3-shift → passive cooling`) and **the
breadcrumb *is* the `WHERE` clause**, so the current view can always print its own SQL. The URL is a
query.

### The interaction that carries the demo

Lift recomputes under the filter. So the viewer adds `climate = hot` to the breadcrumb and watches
`distributor-ME` collapse from ×1.91 to ×1.06 **themselves**. The refutation stops being a story we
narrate and becomes something the viewer performs — and disproving your own hypothesis by clicking is
far more convincing than being told.

### Filtering is unrestricted, because the engine tempers instead of lying

No minimum-`n` rule, no greyed-out cells, no refusals. Thin evidence does not produce a confident wrong
answer; **support-tempering (on by default) shrinks `$p` back toward the base rate**, and the
`calibration / support-tempering(auto)` node in `$why` reports exactly how much it shrank
(0.911 in `books/evaluation/AnalogyProbe`). Measured in-repo: on redundant weak features a plain naive
Bayes collapses to **~0.60 accuracy while Aito holds 0.920 at identical calibration** — query-time
decorrelation plus wide-feature grouping (`books/test/cases/ReexpVsAitoInferenceTest`).

So this becomes a **demo beat, not a caveat**: keep filtering until the slice is nearly empty and watch
`$p` decay gracefully with the tempering factor falling from ~1.0, instead of the confident nonsense a
hand-rolled classifier emits. *It degrades gracefully instead of lying* — with 0.92-vs-0.60 beside it,
already measured rather than asserted.

Surface `n` and the tempering value in every panel: free, and it makes the decay legible. Note
`relate()`'s `lift` is a frequency ratio, not a tempered probability — it ships `n` and `info` alongside,
so the same honesty is available, but the shrinkage story belongs to `predict`/`recommend`. Confirm on
live data (probe 11).

### Text is a navigable dimension, from day one

Free text is the flagship capability and the explorer is where it pays off, in both directions:

- **Forward — a token is a clickable cause.** The word `ambient` in a ticket body → detractor ×1.6 →
  no reorder ×1.8 in hot sites → and here is the lever. *A support ticket becomes a revenue forecast
  with an action*, across four systems, in five seconds. Probably the best single moment available.
- **Reverse — the vocabulary of churn.** Ask the outcome which *words* predict it and get the phrases
  customers use before they leave, ranked by lift. I have not seen that artifact anywhere.

**And no LLM in the loop.** Everyone now assumes text analysis means embeddings, RAG and a model. An LLM
summarises tickets; it cannot tell you that this phrase predicts non-reorder at 1.8× *conditioned on hot
climate*, joined to structured causes in one query, with exact arithmetic behind the number.

This half depends entirely on the analysed-text DDL gap (`td-20260816165937059483`): without
`text` → analysed `Text`, `@@` and every token-level relation are dead on SQL.

### The map behind the front door: exhaustive, not hand-picked

The six cards are the top rows of a **generated** table, not a curated selection. Because every
(field, outcome) pair is one query over a link path — no feature engineering, no model per outcome — the
full matrix can simply be enumerated in a loop. In a normal stack each cell is a join plus a
data-science project, so an N×M causal matrix is N×M projects; that cost difference *is* the moat.
**Not better inference — inference cheap enough to run exhaustively.**

This also kills the sharpest objection to the whole demo. Hand-picked cards invite *"you found
passive×hot because you knew where to look"* — a self-graded exam. A map produced by enumeration makes
the same finding a **discovery**, and the demo can show it arriving at the top of a ranked sweep.

Four artifacts fall out, in order of how legibly they sell:

1. **The spurious-signal audit** — marginal lift beside conditioned lift for every signal, ranked by the
   gap. *"These 12 numbers your teams optimise are confounded; these 7 survive."* "Cut the ME budget"
   would have been a real, expensive mistake.
2. **The incentive-conflict list** — levers that improve one stage's KPI while degrading a downstream
   outcome. A board artifact, and no single-stage tool can produce it.
3. **The lag map** — when each effect lands. Acquisition is bonused in Q1, churn arrives in Q4, so the
   org is *structurally* unable to see it.
4. **Prize × cost-of-lever** as a ranked Monday list, plus the map's holes — which say where you are not
   instrumented.

**The honest limit, and it belongs in the copy.** Conditioning on observed confounds is not causal
identification. What we can truthfully promise is exhaustive *screening*: surface every candidate cause,
flag which survive controlling for what was measured. That replaces an analyst's first two weeks, not
their judgement. Overclaiming causal inference is the fastest way to lose exactly the technical buyer
this demo is aimed at.

### Still the SQL demo

Nothing above weakens the spine; the psql session stays the artifact for the technical audience, and the
explorer prints the SQL of whatever it is showing. Two audiences, one query set, and the strongest
single proof remains the one the brief already names and ranks too low: **an unmodified third-party tool
(DuckDB `ATTACH`, Metabase) getting a prediction out of it.** That *demonstrates* "existing tools work
unchanged" rather than asserting it, and I would promote it from stretch to co-spine.

### Mockups

Both built on the repo's own tokens (`frontend/app/globals.css`) so they drop into the app unchanged.
Numbers are illustrative placeholders pending the generator; the shape is the proposal.

| File | What it shows |
|---|---|
| [`docs/mockup-explorer.html`](./mockup-explorer.html) | **the product** — one explorer node (`cooling = passive` under `climate = hot × 3-shift`): trail, context chips, the four panels, the text/token panel, the calibration-decay strip, the generated map, and the SQL behind the whole screen |
| [`docs/mockup.html`](./mockup.html) | **the front door** — the six-card grid the explorer opens from |

The explorer mockup deliberately shows the *hard* things in one screen: a token panel that only works if
analysed text lands, a lag column on the downstream outcomes, the naive lever ranked last and flat, and
the tempering factor decaying across three progressively thinner slices.

## Editable dashboards — fitting the demo to other data

Asked for 2026-08-31. Filed here rather than actioned, because it changes what the demo *is* and the
sequencing matters more than the code.

### Why this is cheaper than it sounds: the card grammar is already a template

Every card in *The six cards* is the same four statements with different bindings — the design just
never said so out loud:

```sql
-- 1. the KPI          P(outcome | slice)
SELECT * FROM predict('<FROM>', '<OUTCOME_COL>', where => '<SLICE>', why => true);
-- 2. the root causes  what moves it
SELECT * FROM relate('<FROM>', to => '<OUTCOME>', fields => '<EXPLANATORY>', k => 8);
-- 3. the levers       what you could change
SELECT * FROM recommend('<FROM>', '<LEVER_COL>', goal => '<GOOD_OUTCOME>', why => true, k => 5);
-- 4. the prize        the counterfactual
SELECT * FROM predict('<FROM>', '<OUTCOME_COL>', where => '<SLICE> AND <TOP_LEVER>');
```

So a card is a **five-slot binding**: `FROM`, `OUTCOME`, `EXPLANATORY`, `LEVER_COL`, `SLICE`. It is
already a config object; it is simply hard-coded today. Making it editable is exposing a parameterisation
that exists, not inventing one.

### The definition should be SQL text, not a config object that emits SQL

This is the load-bearing decision. A JSON card config with a query-builder UI is the obvious move and it
is the wrong one here:

- **The thesis is "everything is SQL".** A dashboard whose definition *is* SQL, editable as SQL, with the
  result rendering live beside it, is the strongest possible form of "you can do this yourself". A
  builder UI that hides the SQL argues the opposite of the demo's point.
- **It removes a whole surface.** No query builder, no expression language, no validation layer of our
  own — the engine validates, and the error is Aito's own error, which is now good enough to show the
  user (the alias error is a model of the genre).
- **It makes the repo artifacts the config.** `sql/03_cards.sql` *is* the dashboard. Edit the file, the
  dashboard changes; edit in the browser, you get SQL you can paste back into the file. The demo's
  source and its configuration are the same thing.

So: a card is a named block of SQL plus a thin binding header saying which returned column is the KPI,
which is the lift, which is the lever. Everything else is the query text.

### What the schema can tell us, and the one thing it cannot

Adapting to *other* data is mostly a schema-reading problem, and the surface for it landed this month —
`\df`, `\dn`, `information_schema`, and `REFERENCES` declaring real links. From the catalog we can derive:

| Question | Derivable? | How |
|---|---|---|
| What tables exist | yes | catalog |
| Which columns can `predict` target | yes | `varchar` = categorical; `text` is analysed and is *not* a predict target |
| Which fields are usable as evidence | yes | BFS forward over declared links from the `FROM` table — the same forward-only constraint described under *link direction* below, now enforced by construction instead of by hand |
| Which columns are temporal | yes | `timestamp` / `date`, plus their derived parts |
| **Which columns are levers** | **no** | — |

That last row is the whole configuration burden, and it is worth stating precisely because it is so
small. **A schema cannot know which columns are chosen and which are merely observed.** `cooling_type` is
a purchasing decision; `fault_reported` is an observation. Both are `varchar`. The events-vs-actions
distinction that this design is built on is *human knowledge*, and it is the one annotation a user must
supply — one flag per column, plus the outcome and its good direction.

Three annotations. Everything else falls out of the catalog. That is a good result and it should be said
in the copy: **the tool asks you the only question it cannot answer for itself.**

### The risk, stated plainly

A generic dashboard builder is a product, not a demo — and it would make this demo *worse* if it became
the front door. The persuasive thing here is the narrative: four planted mechanisms, three recovered, one
confound correctly left alone. A blank canvas with a table picker has no story, and a visitor who lands
on one leaves.

### The sequencing that gets both

1. **Ship the narrative as the default state.** Cards land pre-bound to the generated data, exactly as
   designed. Nothing about the first thirty seconds changes.
2. **Make every card editable in place.** The `▸ SQL` disclosure that already exists in the mockup becomes
   an editable textarea with a Run. Edit the slice, watch the lift move. This is a small change to a
   component that is already there, and it strengthens the existing demo rather than diluting it.
3. **Add "point this at your own schema" as a closing beat, not an opening one.** After the narrative has
   landed, offering to run the same four statements against the visitor's own database inverts the usual
   demo weakness — *"this only works on your toy data"* — into the proof. That is the moment the
   editability argues for the product instead of merely existing.
4. **Persist edits in the URL, not on the server.** An edited dashboard becomes a shareable link, which
   costs nothing, needs no accounts, and makes the editing feature spread the demo.

Steps 1–2 are the ones I would build. Step 3 is the one that would make this the strongest demo in the
set, and it is also the one that needs a real decision about scope, because it turns a demo into
something people will ask to use.

### Two open questions this raises

- **Does the exhaustive map (`sql/05_map.sql`) become the card generator?** It already enumerates
  (field × outcome) and ranks by lift. Ranked cells *are* candidate cards. If the map generates the
  candidates and the user annotates the levers, "fit it to my data" is mostly automatic — the six cards
  become the top six cells rather than a hand-written set. This is the most promising thread here and it
  costs nothing extra, since the map is already planned.
- **How much does a wrong lever annotation cost?** If a user marks an observed field as a lever, the
  recommend card will confidently propose changing something unchangeable. Worth deciding whether that
  is caught (hard), warned about, or simply the user's business.

## Entities

Four things the business has, per the 360 framing — **customers, products, events, actions** — plus the
context that makes causality physical, and the outcome.

| Entity | Table | What it is |
|---|---|---|
| **Customers** | `customers`, `sites` | who bought, and *where they deploy it* — a customer is not a row, it is a set of physical sites |
| **Products** | `products` | the catalog: what could be sold, with the engineering attributes that matter (`cooling`, `grade`, `duty_cycle_pct`) |
| **Events** | `events` | what *happened*, immutable, customer-side: `ad_click … lapse` |
| **Actions** | `actions` | what *we chose*, company-side: the lever space — SKU quoted, service plan, commissioning level, support tier |
| Context | `campaigns`, `sessions` | the acquisition side of the chain |
| Facts | `orders`, `installs`, `tickets`, `feedback` | the transactional spine |
| Outcome | `reorders` | did the customer come back — the label everything predicts |

**`events` vs `actions` is the distinction that makes this a causal model rather than a log.** An event
is something you observe and cannot change; an action is something you chose and could choose
differently. `relate()` runs over events to find what co-occurs with churn; `recommend()` runs over
actions, because only an action can be *pulled*. A card whose root cause is an event and whose lever is
an action is exactly the Segment-360 grammar, and the split is what makes "the lever that moves it"
well-defined instead of a wish.

### The one modelling constraint that shapes everything: link direction

`predict()`, `relate()` and `recommend()` walk **dotted link paths**, and a link path only goes in the
direction the foreign key points. There is no reverse traversal. Therefore:

> **The outcome table must be able to reach every explanatory field by following links forward.**

This inverts the naive schema. `reorders(customer → customers, …)` cannot reach the product that
overheated, because `orders` points *at* the customer, not the other way. So the outcome hangs off the
**install** — the deepest point of the chain — and everything else is reachable from there:

```
reorders.install.product.cooling          -- 3 hops   (M1, half of it)
reorders.install.site.climate             -- 3 hops   (M1, the other half)
reorders.install.session.campaign.channel -- 4 hops   (M3, the confound)
reorders.install.customer.industry        -- 3 hops
```

Four hops is the deepest path the narrative needs, and it is the one the money question runs on.
**Whether path resolution actually goes four deep is probe #1** — the brief flags it as unconfirmed, and
if it caps at two the schema has to flatten and the demo loses its best line.

## Schema — written as the SQL we want to write

Per the brief, this is the specification handed to the DDL ticket (`td-20260816165937059483`), not a
description of what runs today. Two constructs here do not exist yet and are the point:

- **`REFERENCES`** — links are not declarable in `CREATE TABLE`. Everything above depends on them.
- **`text` vs `varchar`** — `text` should mean *analysed* Text (tokenised, `@@`-searchable), `varchar`
  should mean String (categorical, exact-match, predictable). Today both map to String, so the ticket
  text beat and every `@@` query are dead.

```sql
CREATE TABLE products (
  product_id      varchar PRIMARY KEY,
  name            text NOT NULL,                    -- analysed: searchable
  family          varchar NOT NULL,
  grade           varchar NOT NULL,                 -- consumer | pro | industrial
  cooling         varchar NOT NULL,                 -- passive | active | liquid     ← M1
  load_rating_kg  integer NOT NULL,
  duty_cycle_pct  integer NOT NULL,
  ip_rating       varchar NOT NULL,
  price           numeric NOT NULL,
  launched        date    NOT NULL
);

CREATE TABLE customers (
  customer_id varchar PRIMARY KEY,
  name        varchar NOT NULL,
  industry    varchar NOT NULL,                     -- construction | food | logistics | mining
  size_band   varchar NOT NULL,
  country     varchar NOT NULL
);

CREATE TABLE sites (
  site_id       varchar PRIMARY KEY,
  customer      varchar NOT NULL REFERENCES customers(customer_id),
  climate       varchar NOT NULL,                   -- temperate | hot | arctic       ← M1
  dust_level    varchar NOT NULL,
  shift_pattern varchar NOT NULL,                   -- 1-shift | 2-shift | 3-shift    ← M2
  altitude_m    integer NOT NULL
);

CREATE TABLE campaigns (
  campaign_id   varchar PRIMARY KEY,
  channel       varchar NOT NULL,                   -- paid-social | search | trade-fair | distributor-ME | referral   ← M3
  region        varchar NOT NULL,
  message_angle varchar NOT NULL,
  spend         numeric NOT NULL
);

CREATE TABLE sessions (
  session_id   varchar PRIMARY KEY,
  campaign     varchar NOT NULL REFERENCES campaigns(campaign_id),
  customer     varchar          REFERENCES customers(customer_id),   -- NULL until identified
  landing_page varchar NOT NULL,
  device       varchar NOT NULL,
  ts           date    NOT NULL
);

CREATE TABLE orders (
  order_id varchar PRIMARY KEY,
  customer varchar NOT NULL REFERENCES customers(customer_id),
  session  varchar          REFERENCES sessions(session_id),         -- attribution
  product  varchar NOT NULL REFERENCES products(product_id),
  qty      integer NOT NULL,
  value    numeric NOT NULL,
  ts       date    NOT NULL
);

-- the hub: every explanatory field is reachable from here, and the outcome hangs off it
CREATE TABLE installs (
  install_id    varchar PRIMARY KEY,
  order_p       varchar NOT NULL REFERENCES orders(order_id),
  customer      varchar NOT NULL REFERENCES customers(customer_id),
  product       varchar NOT NULL REFERENCES products(product_id),
  site          varchar NOT NULL REFERENCES sites(site_id),
  session       varchar          REFERENCES sessions(session_id),
  commissioning varchar NOT NULL,                   -- self | guided | on-site        ← lever
  service_plan  varchar NOT NULL,                   -- none | standard | premium      ← lever
  support_tier  varchar NOT NULL,                   -- pooled | dedicated             ← lever (M4)
  ts            date    NOT NULL
);

CREATE TABLE tickets (
  ticket_id        varchar PRIMARY KEY,
  install          varchar NOT NULL REFERENCES installs(install_id),
  opened           date    NOT NULL,
  category         varchar NOT NULL,                -- overheat | wear | electrical | user-error
  body             text    NOT NULL,                -- analysed: "unit shuts down midday, ambient 44C"
  first_response_h integer NOT NULL,                --                                 ← M4
  resolved         boolean NOT NULL
);

CREATE TABLE feedback (
  feedback_id varchar PRIMARY KEY,
  install     varchar NOT NULL REFERENCES installs(install_id),
  score       integer NOT NULL,                     -- 1..5
  body        text    NOT NULL,                     -- analysed
  ts          date    NOT NULL
);

-- what happened (observed, not choosable)
CREATE TABLE events (
  event_id varchar PRIMARY KEY,
  customer varchar REFERENCES customers(customer_id),
  session  varchar REFERENCES sessions(session_id),
  install  varchar REFERENCES installs(install_id),
  type     varchar NOT NULL,   -- ad_click|page_view|spec_download|quote_request|purchase|
                               -- install|fault_report|ticket_open|feedback_given|reorder|lapse
  page     varchar,
  body     text,               -- analysed
  value    numeric,
  ts       date NOT NULL
);

-- what we chose (choosable → the lever space)
CREATE TABLE actions (
  action_id varchar PRIMARY KEY,
  customer  varchar NOT NULL REFERENCES customers(customer_id),
  install   varchar          REFERENCES installs(install_id),
  lever     varchar NOT NULL, -- sku_quoted | service_plan | commissioning | support_tier | outreach
  choice    varchar NOT NULL,
  ts        date    NOT NULL
);

-- the outcome, hanging off the install so every cause is reachable forward
CREATE TABLE reorders (
  reorder_id varchar PRIMARY KEY,
  install    varchar NOT NULL REFERENCES installs(install_id),
  period     varchar NOT NULL,                      -- '2026-Q1' …
  reordered  boolean NOT NULL                       -- ← the label
);
```

### The flat analysis table — forced by measurement, 2026-08-31

The normalised schema above is correct and it loads. It is **not sufficient**, and the reason was found
by running the demo's central query rather than by reasoning about it.

**`relate()` has no filter.** Its `to =>` (JSON: `where`) is the *target proposition*, not a slice. So
"relate cooling to churn **within hot-climate sites**" — the conditioning move that reveals M1's
interaction, and the demo's single most important beat — has no direct spelling. Worse, a conjunction is
silently reinterpreted: `to => 'reordered = false AND install.site.climate = ''hot'''` returns relations
against *each conjunct separately* (three rows for one, two for the other), not against the conjunction.

**A view is the only conditioning mechanism, and views cannot bake a link path.** Measured:

```sql
CREATE VIEW hot_reorders AS SELECT * FROM reorders WHERE install.site.climate = 'hot';
SELECT count(*) FROM hot_reorders;   -- 0.  Silently. (td-20260831214438282862)

CREATE VIEW v AS SELECT * FROM tickets WHERE category = 'overheat';
SELECT count(*) FROM v;              -- 1414, exactly matching the direct query
SELECT * FROM relate('v', to => 'resolved = false', …);  -- correct, n=1414
```

So views work and `relate`-over-a-view scopes correctly — but only on the view's **own plain columns**.

#### The consequence

`sql/02_flatten.sql` builds **`analysis`**: one row per install, every explanatory field flattened onto
it — `cooling`, `climate`, `grade`, `shift_pattern`, `channel`, `industry`, the lever columns, the
outcome, and derived ticket features (`had_thermal_fault`, `slow_first_response`). Then:

- **conditioning** is `CREATE VIEW analysis_hot AS SELECT * FROM analysis WHERE climate = 'hot'`
- **`patterns()`** works, because the fields it must co-mine are now columns of one table — this is the
  same workaround `td-20260823192630739057` needs, arriving for an independent reason
- every card's four statements run against `analysis` or a view of it

#### Say this out loud rather than hiding it

A demo built to showcase link paths ends up flattening them, and the honest framing matters more than the
convenience. What survives, and is still true:

- **The links do the work that cannot be done any other way.** `analysis` is *built* by traversing them —
  four hops deep, confirmed working (`install.session.campaign.channel` resolved 537 rows, matching the
  generator exactly). Without declared links there is no flattening step to run.
- **The flatten is nine lines of SQL, not a pipeline.** It is a `CREATE VIEW`/`CREATE TABLE AS` over
  declared joins, in the same psql session, with no external tool. That is a materially different claim
  from "you need a warehouse first" and the copy should make the distinction precisely.
- **What we cannot claim** is "point Aito at your normalised schema and ask questions". Today the honest
  version is: *load the normalised schema, flatten once, then ask questions.* When the two link-path
  tickets land, the flatten becomes optional and the stronger claim becomes true.

The flatten is also what the *editable dashboards* section needs anyway: a single wide table with typed
columns is exactly what a schema-reading card builder can offer choices from.

### Deliberate redundancy, stated up front

The lever columns appear **both** on `installs` (as columns) and in `actions` (as rows). That is not an
accident: `recommend()` ranks the values of *one column* toward a goal, so a lever must be a column on a
table that can reach the goal — an `actions` row cannot be a recommend target. The `actions` log exists
for the narrative (one customer's story, the audit trail of what we chose) and the columns exist so the
lever is recommendable. The generator writes both from one source of truth, so they cannot disagree.

If `recommend()` turns out to be able to target `actions.choice` conditioned on `actions.lever = 'x'`,
the redundancy can go — **probe #5**.

## The card grammar, in SQL

Every card is the same four statements. Taking the churn card as the worked example:

**1 — the KPI.** An ordinary aggregate. It is just a database.

```sql
SELECT reordered, count(*) FROM reorders GROUP BY reordered;
```

**2 — root causes.** What co-occurs with the bad outcome, ranked by lift.

```sql
SELECT * FROM relate('reorders', to => 'reordered = false', k => 8);
-- → related | lift | info | n
```

**3 — recommended levers.** What to *do*, ranked by the probability of the good outcome.

```sql
SELECT * FROM recommend('installs', 'product',
         goal  => 'reorders.reordered = true',
         given => 'site.climate = ''hot''',
         k     => 5);
-- → value | p
```

**4 — the size of the prize.** The same prediction under the current choice and under the lever.

```sql
SELECT predictions(reordered) FROM reorders
 WHERE install.site.climate = 'hot' AND install.product.cooling = 'passive' LIMIT 1;
SELECT predictions(reordered) FROM reorders
 WHERE install.site.climate = 'hot' AND install.product.cooling = 'active'  LIMIT 1;
```

`predict()` is a **per-row projection and cannot combine with `GROUP BY`**, so a card's headline number
is always an aggregate and the prize is always a per-row prediction with `LIMIT 1`. That is a real
constraint on the design, not a stylistic choice.

Views make each card cheap to define, because **an Aito view is a materialised collection you can
predict, relate, recommend and `@@`-search on** — not stored SELECT text:

```sql
CREATE VIEW hot_installs AS SELECT * FROM installs WHERE site.climate = 'hot';
```

(View definitions take **equality** filters only, which is all the cards need. Whether a view's baked
`WHERE` may use a *link path* like `site.climate` is **probe #4**; if not, the flag gets denormalised
onto `installs`.)

## The six cards

| # | Stage | KPI | Root causes (`relate`) | Levers (`recommend`) | Plants |
|---|---|---|---|---|---|
| 1 | ads → website | lead rate | `message_angle`, `device`, `landing_page` | message angle | — |
| 2 | website → conversion | win rate | `channel`, `industry`, `family` | SKU quoted | M3 shows up here first |
| 3 | purchase → install | fault rate 90d | **`cooling` × `climate`**, **`grade` × `shift_pattern`** | SKU, commissioning | **M1**, M2 |
| 4 | support | resolved <24h | `support_tier`, `category`, volume | support tier | M4 |
| 5 | feedback | detractor share | unresolved, slow first response, `category = overheat` | support tier, SKU swap | M4 → M1 |
| 6 | churn | reorder rate | naive: **`channel = distributor-ME`** | SKU with active cooling in hot sites | **M3 refuted by M1** |

Card 6 is the climax and it is deliberately *wrong first*: `relate()` returns `channel =
distributor-ME` at high lift, because it is true — that channel does sell into hot regions. The demo
then walks one link deeper and the channel's lift collapses once cooling × climate is conditioned on.
Same database, same grammar, one more hop.

Cards 3 and 6 are the same mechanism seen at two stages, which is the 360 argument in miniature: the
fault-rate card can *see* M1 because product and site sit right there; the churn card cannot, unless it
walks the links. In a real stack those two cards live in different tools.

## Honesty

We wrote the generator, so we know the ground truth. Every card that reports a lift prints the planted
coefficient beside the recovered one:

```
M1  passive cooling × hot climate → churn     planted 2.1×   recovered 2.0×   (4 hops, no feature engineering)
M3  distributor-ME channel → churn            planted 1.0×   recovered 1.9×   ← the confound, correctly innocent
```

`relate()` returns **lift** — association. The only reason we may talk about cause here is that the
causal structure is known by construction. The README says the data is synthetic *and* that its causal
structure is planted; no copy claims causal inference on real-world data.

## SQL surface asks — verified live, rechecked 2026-08-31

This lane is the forcing function for the SQL surface, so the design is written against the surface it
*wants*. The bar for an ask here: **the capability already exists in the v2 JSON API**, so this is a
front-end spelling, not new inference work — and it lands server-side first, keeping pg_infer a strict
subset of Aito (the rule in `td-20260815102712969820`).

**Most of the original asks have shipped.** Everything below is now measured against a live pgwire
session rather than read off the parser source. The connection:

```bash
psql "host=internal.aito.ai port=5432 dbname=aito-sql-demo user=aito password=$AITO_API_KEY"
```

Note `dbname` is the **database**, not the env — this is a multi-database server (`/db/<name>/`). An
unknown database is deliberately reported as `password authentication failed`, so that a reachable port
cannot be used to enumerate databases. `shell.nix` now derives it from the `/db/` path, because the
failure mode otherwise looks like a bad key and sends you debugging the wrong thing.

### Which build we are actually testing

`GET https://internal.aito.ai/version` → `6f2700e2`, built **2026-08-30T08:02Z**, on the **v2.7.0**
release line. (It ran `c0cac691b` / 2026-08-22 when this section was first written; the redeploy landed.)

Keep checking this. The host has drifted in *both* directions — it once ran ahead of the release and
described features shared did not have, and later fell two nightlies behind. `td-20260825200311333655`
tracks setting an actual policy. The practical rule for this lane: **probe, don't read.** A concrete
instance of that today — the notice-delivery fix (`c4fd2a1ae`, 2026-08-30 06:41Z) is *not* in the
deployed build (`6f2700e2`, merged 07:40Z, a different branch), so notices that master emits do not
arrive here yet.

**The time gap is closed, and it was the largest open dependency.** All of this now works on the
deployed build:

```sql
CREATE TABLE notes (id integer PRIMARY KEY, cust varchar REFERENCES cust(id), body text, ts timestamp);
SELECT id FROM notes WHERE ts > '2026-03-01T00:00:00Z';        -- ranges
SELECT id FROM notes WHERE ts > now() - interval '1 year';     -- relative windows
SELECT id, "ts.year", "ts.weekday" FROM notes;                 -- derived parts, as features
SELECT id, date_trunc('month', ts) FROM notes;                 -- buckets
```

So the explorer's **lag column has an implementation**, the journey can be shown as *sequence* rather
than only co-occurrence, and a temporal holdout for the honesty beat is expressible. This is the single
biggest change since the design was drafted, and it removes the reason the redeploy was a dependency.

### Shipped since the asks were filed — confirmed working

| Ask | Status | Evidence from the live session |
|---|---|---|
| DDL: `REFERENCES` declares a link | **shipped** | `CREATE TABLE notes (cust varchar REFERENCES cust(id), …)` accepted; `INNER JOIN` and dotted paths then both work |
| DDL: `text` analysed vs `varchar` categorical | **shipped** | `@@` matches on the `text` column; `relate` returns per-token `{"body":{"$has":"thermal"}}` |
| A4 `patterns(...)` | **shipped** | `patterns('cust', fields => 'seg, churn', k => 3)` → `{"$and":[{"seg":"construction"},{"churn":"true"}]}` |
| Constant `SELECT` | **fixed** | `SELECT 1 AS ok` → `1`. The doc/behaviour mismatch recorded earlier is closed. |
| The function registry | **shipped, visibly** | `sql-reference.md#signatures` is generated between `BEGIN/END GENERATED` markers "from the same declaration the parser builds its argument errors from". The errors prove it: `unknown relate argument 'why' (expected fields, to, or k)` enumerates the real signature. That is exactly the bar `td-20260817231645693031` set. |

So probe 6 (`relate` over a link path) and probe 9 (per-token `relate` on analysed text) — the two that
decided whether the text half of the explorer exists — both **pass**, in one statement:

```sql
SELECT * FROM relate('notes', to => 'cust.churn = ''true''', k => 5);
--          related             |  lift  |  info  |  n
-- {"body":{"$has":"thermal"}}  | 1.8400 | 0.3965 | 5.0
-- {"body":{"$has":"shutdown"}} | 1.3167 | 0.0664 | 5.0
```

Per-token lifts against a link-path condition. **The clickable-token panel is real.**

### Status of every ask — rechecked live 2026-08-31

Seven of the eleven items filed from this lane are delivered. Rechecked by probing, not by reading
tickets.

**Delivered and verified**

| Ask | Ticket | What the live session shows |
|---|---|---|
| N1 table aliases | `td-20260823192626893375` | `FROM t AS c` and `FROM t c` both work, on both sides of a JOIN. The shadowing question I asked them to settle was settled the Postgres way, and the error is a model of the kind: *"invalid reference to table 'rc_cust' — it is aliased as 'c', so qualify the column as 'c.id' (Postgres hides the table name once an alias is given)"* |
| N5 `pg_proc` | `td-20260823204928799552` | `\df` lists all 14 functions with argument types; `\dn` shows the `aito` schema. Shipped in the same PR as N1 (#1186) |
| N4 date/time | `td-20260823204851068152` | `timestamp`, ranges, `now() - interval`, derived parts, `date_trunc` — all live |
| A1b `why` on predictions | `td-20260816220020308261` | via the **hypothetical** form: `SELECT * FROM predict('t','col', where => '…', why => true)` returns the factor tree |
| DDL `REFERENCES` + analysed `text` | `td-20260816165937059483` | in review |
| Redeploy | `td-20260823205005630264` | done — v2.7.0 |
| Docs gaps ×3 | `td-20260823205040145864` | in review |

**Still open**

| Ask | Ticket | Priority | State |
|---|---|---|---|
| N3 strict-vs-flexible `CREATE TABLE` | `td-20260823204811553899` | 1 | **half fixed; a product decision is open, and my answer is filed on the ticket** |
| Per-row `$why` on the `predict()` projection | `td-20260827064609626680` | 2 | confirmed engine gap, split out of A1b |
| N2 `patterns` over link paths | `td-20260823192630739057` | 2 | engine-level, both surfaces |
| A2 `evaluate(...)` | `td-20260816220027057517` | 2 | not shipped |
| A3 `estimate(col)` | `td-20260816220033849021` | 2 | not shipped |

#### What A1b's resolution actually means for the card grammar

`why => true` landed on the **hypothetical** form — `FROM predict('cust','churn', where => …, why => true)`
— and *not* on the per-row projection `predict(col, why => true)`, which remains an engine gap
(`td-20260827064609626680`: the `$predict` select object accepts only `limit` and `basedOn`, so there is
nothing for the SQL argument to lower to).

That split maps onto this design better than it sounds, and the mapping is worth stating because it
decides which SQL each surface writes:

- **The six cards are hypotheticals.** Each card is *one* question with *one* `where` — "for hot-climate
  sites with passive cooling, what is P(churn)?" The table-function form is exactly that shape, and it
  explains itself. **The card grammar is unblocked.**
- **The explorer's row lists are per-row**, so a list of at-risk installs each with its own `?` still
  cannot explain itself. Design around it: explain the *slice* (one hypothetical call for the current
  breadcrumb), not each row. That is arguably the better interaction anyway — one explanation the user
  reads, rather than N explanations they don't.

#### N3 is now a product question, and the answer changes the schema

The core lane's diagnosis was better than my report. There is no resolver bug: SQL `CREATE TABLE`
produces a **flexible** collection, so an unknown field in a `WHERE` is semantically legitimate and
merely *warned* about — and the warning was being dropped on every SQL path. They fixed the delivery
(pgwire `NoticeResponse`, `warnings` in `_sql`) and escalated the real question: **should SQL
`CREATE TABLE` create a strict schema?**

My answer, filed on the ticket, is *yes*, with new evidence — the write side is flexible too:

```sql
CREATE TABLE cust (id varchar PRIMARY KEY, seg varchar, churn varchar);
INSERT INTO cust (id, seg, churn, undeclared_col) VALUES ('c9','retail','false','surprise');
-- INSERT 0 1. The column is created, is real, and is immediately filterable.
```

So a mistyped column in an `INSERT` silently **forks a column** — write `staus` once against a table
declaring `status` and the data splits, with no error at any point. A read-side typo costs a wrong
answer you might catch; a write-side typo costs split data you probably won't.

**Either way, the explorer validates facets against the schema in its own layer.** A click-to-filter UI
cannot be correct while trusting the backend to reject bad facets — warnings are dropped by most
clients, and an empty panel renders just as confidently as a full one. This is a design constraint here,
not a dependency on that ticket.

#### N2 — `patterns` cannot mine across a link path  ★ new, priority 2

Worth being exact about where this limit lives. Probed on both surfaces, same data, same instance:

```sql
SELECT * FROM patterns('notes', fields => 'body, cust.seg, cust.churn', k => 5);
  → relate $patterns: no such field 'cust.seg'
```
```json
{"from":"notes","relate":{"$patterns":["body","cust.seg"]}}
  → {"code":"request.invalid","message":"relate $patterns: no such field 'cust.seg'"}
```

**Identical error from JSON.** So this is *not* a SQL spelling gap — it is an engine limitation, and it
fails this section's stated bar. Filing it anyway, at priority 2 and labelled honestly as engine work,
because of what it costs: the headline pattern the front door is designed around is inherently
cross-table —

> 5 cases of `{customer.type: construction, feedback.text: {$has: thermal}, events.type: {$has:
> "fault-report"}, churn: true}` — 73× lift

— and today `$patterns` mines the columns of one table only.

Two consequences, both real now rather than hypothetical:

- **A workaround exists today: mine on a denormalised view.** `CREATE VIEW` is materialised and
  from-able, so a view flattening the fields we want to co-mine gives `patterns()` a single table. This
  costs the "no ETL" purity of the pitch, and should be said out loud in the copy rather than hidden —
  but it unblocks the front door without waiting on engine work.
- Two other observed behaviours are **not** bugs — checked against JSON before concluding. `lift` and
  `condition` come back `NULL` when no `where` is given (lift is only defined relative to a condition),
  and `patterns` with a `where` returned zero rows on a 5-row slice, which is a support threshold doing
  its job. Re-check both on the generated dataset before concluding anything from them.

#### A2 / A3 — unchanged asks

`evaluate(...)` and `estimate(col)` are both still absent (`unexpected '(' after the query`, and
`function 'estimate(…)' is not supported in a SELECT expression yet`). The arguments are unchanged and
stated in the tickets: A2 is the honesty beat (`base_accuracy` printed beside `accuracy`, held out, in
the same psql session), A3 turns percentage points into money. Both should be cheaper now than when
filed — the registry is precisely the mechanism for adding a function without hand-writing its errors.

### Parked, not asked for

- **Relevance ranking** (`ts_rank` → `$similarity`): largely answered by `aito.search`, which arrives
  with the redeploy. Re-evaluate then rather than asking now.
- **`config.ai` / `config.calibrate` via SQL**: tuning knobs; the demo should run on defaults, which is
  itself part of the claim.
- **`ORDER BY predict(col = v)`** (rank rows by per-row probability): would be perfect for an
  at-risk-installs list, but it is **engine-blocked**, not a spelling gap — `PredictionProposition2`
  needs a contextful examination that a plain `from` SELECT does not build (`td-20260815102712969820`).
  It fails this section's bar, so it is not asked for here.

## Probes — the full list

Each gets exact SQL, the exact error, and the SQLSTATE, and each break is filed as a core gap.
**Four are now closed against the live instance** — see the probe-status table under Findings for which,
and read this list as the specification each probe was run against.

1. **Link-path depth.** Does `reorders.install.session.campaign.channel` (4 hops) resolve in `SELECT`,
   in `WHERE`, and as a `predict()` target? Report the cap. *The narrative needs four.*
2. **`REFERENCES` in `CREATE TABLE`.** Expect a parse error; capture it verbatim for the DDL ticket.
   The schema above is that ticket's acceptance test.
3. **Analysed text.** Does `text` differ from `varchar`? Does `@@` work on a `CREATE TABLE`-created
   `text` column? Expected: no — both become String.
4. **View definitions over link paths.** `CREATE VIEW … WHERE site.climate = 'hot'`.
5. **`recommend()` targets.** Can the target column be a link (`'product'`), and can `goal` reference a
   *reverse* relation (`reorders.reordered = true` from `installs`)? If reverse goals do not work, the
   goal has to live on the fact table and `installs` carries `reordered` directly.
6. **`relate()` over link paths.** The comma-list is confirmed in the parser; what is unconfirmed is
   whether a *dotted path* entry (`install.product.cooling`) resolves against the JSON `relate` array
   on live data.
7. **Interaction discovery.** `relate()` ranks fields *individually* against a condition — it does not
   enumerate pairs. So the interaction is surfaced by **conditioning**: relate `cooling` to
   `reordered = false` across all sites (weak lift), then again with `site.climate = 'hot'` in the `to`
   condition (strong lift). The contrast between those two numbers *is* the interaction, and it is
   arguably a better demo beat than a pair falling out of a list, because the viewer watches the lift
   move. **Confirm the two lifts actually diverge on generated data — if they do not, the star
   mechanism does not land and the generator needs a stronger M1.** This remains the most
   story-critical probe.
8. **`avg(cast(bool AS int))`** for a one-line KPI, vs the safe `GROUP BY` two-row form.
9. **`relate()` over an analysed text column — per-token lifts.** Does
   `relate('tickets', fields => 'body', to => 'reordered = false')` return *token-level* relations
   (`ambient`, `44C`, `midday`) rather than one row for the whole field? This is the enabling capability
   for both text directions in the explorer — the clickable token and the vocabulary-of-churn artifact.
   **Check the v2 JSON side first**: if `_relate` already returns token relations, a SQL gap is a
   spelling ask that clears our bar; if JSON cannot do it either, it is a new engine feature and fails
   the bar, and the text half of the explorer needs rethinking.
10. **Per-click latency.** Time each of the four explorer panel queries at demo data volume, cold and
    warm. **~200 ms makes it an instrument; ~2 s makes it a report** — and that single number decides
    whether the explorer is the product shape or the exhaustive map has to be a batch job rendered
    static. Measure before building the frontend.
11. **Does `relate()`'s `lift` temper on thin evidence?** `predict`/`recommend` shrink `$p` via
    support-tempering, but `lift` is a frequency ratio. Filter to a deliberately tiny slice and see
    whether `lift` goes wild while `n` stays small (expected), and whether `info` behaves. Determines
    whether the explorer's relate panels need `n` shown prominently (probably yes) — not a blocker,
    since nothing is being restricted, but it shapes what the panel emphasises.
12. **Enumeration cost.** Time a full (field × outcome) sweep at demo volume — the exhaustive map is a
    loop over probe-6-shaped queries. Report total wall-clock and cell count, since that number is the
    "inference cheap enough to run exhaustively" claim, stated as a measurement rather than a boast.

## Findings so far

Everything below the first two bullets is now **measured on the live instance** (build `c0cac691b`,
2026-08-22) over pgwire, not inferred from source.

- ~~`psql` is not on PATH~~ — **fixed.** `shell.nix` provides `postgresql_17` (psql 17.10) and derives
  the whole `PG*` set from `AITO_API_URL` + `AITO_API_KEY`, so a bare `psql` in the dev shell connects.
- ~~**BLOCKER — pgwire port 5432 is not reachable**~~ — **RESOLVED 2026-08-23.**
  `td-20260816201324665971` (aito-azure) is done: the port is open and the listener is up. The demo's
  spine — one psql session against Aito — runs. Connectors (DuckDB, Metabase, `postgres_fdw`) are
  unblocked to the extent the alias gap (N1) allows.
- **`dbname` is the database, not the env, on this server.** `internal.aito.ai` is multi-database
  (`/db/<name>/`), so `dbname=aito-sql-demo`. Getting this wrong costs real time, because an unknown
  database is deliberately reported as `password authentication failed` — indistinguishable from a bad
  key, by design, so a reachable port cannot enumerate databases. `shell.nix` now derives it from the
  URL path. **Worth a line in the SQL guide's troubleshooting**, since everyone hits it once.
- ~~**Doc/behaviour mismatch:** constant `SELECT` rejected~~ — **fixed.** `SELECT 1 AS ok` → `1`. Since
  Postgres clients issue constant `SELECT`s as connect-time probes, this was on the connector path.
- **Probes 6 and 9 pass** — the two design forks. `relate()` resolves dotted link paths in the `to`
  condition, and returns **per-token** relations over an analysed `text` column
  (`{"body":{"$has":"thermal"}}`, lift 1.84). Both halves of the explorer's text panel are supported by
  the engine as it stands.
- **`patterns()` is live and works within one table** — `{"$and":[{"seg":"construction"},
  {"churn":"true"}]}` — but **cannot mine across a link path on either surface** (N2). The pattern-feed
  front door therefore needs a denormalised view, or engine work.
- **A `date` column cannot be range-filtered** (`td-20260823204851068152`). `WHERE d > '2026-03-01'` and
  `BETWEEN` both fail with `Unknown operation: $gt on field d`. `EXTRACT(MONTH FROM d) = 1` and
  `EXTRACT(ISODOW FROM d) = 6` *do* work, so calendar-aligned buckets are available and seasonality is
  expressible — but an arbitrary window is not, and neither is "the 90 days after each install".
  **Consequence for the design:** on the deployed build the journey can be shown as *co-occurrence* but
  not as *sequence*. The lag column has no implementation. That is what the redeploy
  (`td-20260823205005630264`) actually buys, and it is why that ticket exists.
  Related: `relate()` over a `date` column returns each distinct date as its own relation
  (`{"d":"2026-02-11"}`, lift 1.11) — near-unique values, so pure noise crowding the top-k. Dates should
  be related via their derived parts, not raw. **The schema should model time as parts from the start.**
- **An unknown field in a `WHERE` returns a silent empty result** (`td-20260823204811553899`) — and this
  one is a design constraint, not just a bug to wait on. `WHERE "totally_bogus" = 1` returns zero rows
  with no error, while the *same* unknown name in a `SELECT` list fails loudly (`no such field`). The
  docs promise loud failure in seven places, one of them verbatim: *"never a silent empty value."*
  **Consequence for the explorer:** the whole interaction model is a `WHERE` accumulated from clicked
  facets. One stale or mistyped facet empties the result set silently, and every lift and probability
  downstream is then computed over nothing — the UI would render a confident, well-formatted panel of
  zeros. **So the explorer must validate every facet against the schema before it builds the `WHERE`,
  and must distinguish "no rows match" from "that field does not exist" in its own layer.** Do not wait
  for the engine fix; a click-to-filter UI cannot be correct without that check regardless.
- **Table aliases are rejected entirely** (N1). Column aliases work. This is the finding with the most
  bearing on the demo's thesis and it is not in the docs.
- **`hitLinkPropositionLift`** appears in live `$why` trees on cross-table predictions and is **not in
  the documented factor-type table** (`inference-v2.md#why-factors`). Any renderer we write must handle
  it. Small docs gap, real rendering bug if missed.
- **The instance lags master by a week of SQL features** — `match`, `aito.search`, `aito.knn`,
  `date_trunc`, and the `timestamp` type are all on master and absent here. The explorer's lag column
  (`+41d → +274d`) depends on `timestamp`, so **the redeploy is a hard dependency of the design as
  drawn**, not a nice-to-have.
- **Support-tempering is measured, not just documented** — what makes unrestricted filtering in the
  explorer safe. `books/test/cases/ReexpVsAitoInferenceTest`: on redundant weak features a plain naive
  Bayes collapses to **~0.60 accuracy while Aito holds 0.920 at identical calibration (MXE 0.387)**,
  decorrelating at query time. And it is per-answer visible — the `calibration / support-tempering(auto)`
  node appears in `$why` with its value (0.911 in `books/evaluation/AnalogyProbe`). Use those numbers in
  the copy; they are in-repo measurements, not claims.
- The REST `_sql` endpoint takes **raw SQL as the request body** (`text/plain`), not a JSON envelope — a
  JSON body fails with `unexpected character '{' at position 0`. Worth a line in the docs.

### Probe status

Rechecked live 2026-08-31 on build `6f2700e2`.

| # | Probe | State |
|---|---|---|
| 1 | Link-path depth (4 hops) | **open** — 2 hops confirmed; needs the real schema |
| 2 | `REFERENCES` in `CREATE TABLE` | **passes** |
| 3 | `text` vs `varchar` analysed | **passes** |
| 4 | View definitions over link paths | **open** — also the N2 workaround, so run it early |
| 5 | `recommend()` targets / reverse goals | **partial** — `goal` + `given` work; reverse untested |
| 6 | `relate()` over link paths | **passes** |
| 7 | Interaction discovery by conditioning | **open** — needs generated data; still the most story-critical |
| 8 | `avg(cast(bool AS int))` KPI | **open** |
| 9 | Per-token `relate` on text | **passes** |
| 10 | Per-click latency | **open** — needs volume; decides instrument vs static report |
| 11 | Does `relate()`'s `lift` temper on thin evidence? | **open** |
| 12 | Enumeration cost of the full map | **open** |

Unchanged conclusion, now with the SQL surface no longer in the way: **7 and 10 are the two that fork
the design, and both need the generator first.** Every blocker that was external to this lane has
cleared. The critical path is entirely local work.

## Order of work

1. ~~**Probes 1–12** first~~ — **reordered.** Probes 2, 3, 6, 9 are closed against the live instance
   (see the table above), and probe 9 came back **yes**, so the text half of the explorer is confirmed.
   The probes still open — 1, 7, 10, 11, 12 — all need data that does not exist yet, so the generator
   now comes first. **Probe 10 (per-click latency) remains a design fork** and should run the moment
   there is volume to run it against: it decides whether the explorer is an instrument or the map ships
   as a static report.
2. **The generator**: entities, the four planted mechanisms, CSV out. Unblocked, pure data work — and
   now the critical path, since every remaining fork waits on it.
3. `sql/01_schema.sql` — the DDL above, verbatim, as the DDL ticket's acceptance test.
4. `sql/02_load.sql`, `sql/03_cards.sql`, `sql/04_the_climax.sql` — the four beats, JSON-free.
5. **`sql/05_map.sql`** — the exhaustive (field × outcome) sweep that generates the map the cards sit on
   top of. This is what makes the finding a discovery rather than a curated result, so it is not
   optional garnish; it comes before any frontend.
6. **The explorer** over the same files: four panels, one component, breadcrumb-as-`WHERE`, SQL always
   visible. Shape confirmed by probe 10.
7. **Federation** — DuckDB `ATTACH` / Metabase against the same instance. The brief files this under
   stretch; on the evidence it is the strongest single proof of the actual claim, and I would treat it as
   co-spine rather than optional.

~~Running alongside: redeploy the instance off master~~ — **done.** The instance runs v2.7.0
(`6f2700e2`), `timestamp` and its derived parts are live, and the lag column has an implementation.
Keep probing the build rather than reading the docs: the host has drifted both ahead of and behind the
release, and `td-20260825200311333655` is still open on setting a policy.

Two questions still open for Antti, both of which change what gets generated rather than how:
**synthetic vs a real public dataset with a genuine confound** (the synthetic caveat may cost more
credibility than the planted-truth trick buys), and whether a deliberate **negative result** — one card
where the lever is wrong or accuracy barely clears base rate — goes in. My view on the second is yes; it
is what makes every other number believable, and `aito-hacker-news-demo` already set that precedent.
