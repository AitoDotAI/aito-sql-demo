# Deploying this demo

Status as of 2026-09-12: **the repo and the platform entry are done. One thing
is left, and it needs a credential nobody has issued yet.**

## What is already in place

| | |
|---|---|
| GitHub repo | `AitoDotAI/aito-sql-demo`, public, `main` — `git ls-remote` resolves, which is the check the image build does |
| Platform entry | `aito-demo-server/demos.config.yaml` → `sql`, port 3009, `sql.aito.ai`, `enabled: true`, thumbnail placed. `validate-config.js` passes with 9 demos |
| Production shape | one uvicorn serves `/api/*` and the static export from `frontend/out/`; `/health` and `/api/health` both green |
| Lockfiles | `uv.lock` + `frontend/package-lock.json` committed, so `uv sync --frozen` and `npm ci` both work |

## The one blocker: the Aito database

Every live demo runs on `shared.aito.ai`. `aito-sql-demo` does not exist there
yet, and `AITO_SQL_API_URL` / `AITO_SQL_API_KEY` are not in
`aito-demo-server/.env.local`.

```bash
# 1. create the database on shared.aito.ai, then fill it — one command:
AITO_API_URL=https://shared.aito.ai/db/aito-sql-demo \
AITO_API_KEY=<read-write key>                        \
  ./do provision
```

`provision` generates the corpus, loads 61,875 rows over pgwire, creates the 17
views, precomputes the map, and verifies the result (3,000 installs, four card
views, ~20% baseline churn). It is idempotent — it drops and reloads.

```bash
# 2. add to aito-demo-server/.env.local AND Azure App Settings:
AITO_SQL_API_URL=https://shared.aito.ai/db/aito-sql-demo
AITO_SQL_API_KEY=<READ-ONLY key>        # not the one used above

# 3. deploy
cd ../aito-azure && ./do deploy-demos
```

### Why step 2 says READ-ONLY, emphatically

This demo exposes **`POST /api/sql`, which runs arbitrary user-supplied SELECTs
from the browser.** That is deliberate — the dashboard cards are editable, and
that is the feature.

It is safe today, and this was verified rather than assumed: `DROP`, `DELETE`,
`INSERT`, `CREATE` and `UPDATE` are all refused by the read-only REST `_sql`
endpoint with *"only a SELECT can be lowered to a query."* But that makes it
safe **by transport, not by credential** — anything that later routes a query
through psql instead inherits whatever the key can do. A read-only key makes
the credential enforce what the code currently only happens to.

The endpoint also caps statements at 4,000 characters, enforces one statement
per request, and uses a 15-second timeout.

## The numbers will probably move, and that is expected

`shared.aito.ai` runs **v2.8.3**. Everything in this repo was measured against
`internal.aito.ai`, which is on **2.8.2-dev** — behind, and specifically missing
three fixes that touch prediction:

| commit | what |
|---|---|
| `a4d066ad6` | `LBits.or`'s dense fast path assumed a shared segmentation — the changelog says this "could return a plausible wrong answer" and is "reachable from the predict path" |
| `5168fe5a0` | a candidate whose proposition the rep already knows keeps its real variable |
| `262ee0a78` | value membership derived in one place — six sites that disagreed |

So **every number in this demo was computed on a build missing a known
wrong-answer fix.** Expect the cards to shift on production. That is the fixes
landing, not a regression.

`book/test_03_engine_answers_book.py` exists for exactly this moment. It
asserts the STORY — M1's lift must rise under conditioning, M3 must be
exonerated, the NEG card must stay flat, the working lever must beat its
alternative — and snapshots the actual numbers so drift is a reviewable diff
rather than a silent change.

```bash
./do test-book            # after provisioning on shared: does the story hold?
./do test-book -a         # accept the new numbers once you have read the diff
```

If the assertions fail, the demo's narrative no longer matches the engine and
the copy needs revisiting before launch. If only the numbers move, accept them
and update the two figures hard-coded in prose: the M1 note in `src/cards.py`
and the methodology paragraph on the map page.

## Verifying a deploy

```bash
curl -s https://sql.aito.ai/health                 # 200, no Aito call
curl -s https://sql.aito.ai/api/health             # aito_connected: true
curl -s https://sql.aito.ai/api/cards | head -c 200
```

Then open it and check the four views load: `/`, `/map`, `/explore`, `/patterns`.

## Known gaps, deliberately shipped

- **No analytics.** `NEXT_PUBLIC_AMPLITUDE_KEY` / `NEXT_PUBLIC_GA4_MEASUREMENT_ID`
  are unset, so the demo reports no traffic. `frontend/lib/analytics.ts` is wired
  and will start working as soon as the keys are supplied.
- **`assets/teaser.png`** is generated and current, but the landing-page
  thumbnail is an app screenshot (matching the siblings) rather than the teaser.
- **The `/` view has not had the design pass** the other three got.
- **Mobile is verified by measurement, not by hand** — 390×844 shows no overflow
  and no sub-44px tap targets in the data navigation, but nobody has held it.
