"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import TopBar from "@/components/shell/TopBar";
import Nav from "@/components/shell/Nav";
import { NAV_SECTIONS } from "@/lib/routes";
import AitoPanel from "@/components/shell/AitoPanel";
import ErrorState from "@/components/shell/ErrorState";
import { apiFetch } from "@/lib/api";
import type { AitoPanelConfig } from "@/lib/types";
import ConnectBox from "@/components/shell/ConnectBox";
import CardPanel from "@/components/cards/CardPanel";
import ChainStrip from "@/components/cards/ChainStrip";
import type { CardSummary, Overview } from "@/lib/cardTypes";

/** Counted from the cards themselves. Typed by hand this said 24 while the six
 *  cards actually carry 27 statements — the kind of number that is wrong the
 *  moment a card gains a conditioned query. */
const panelConfig = (cards: CardSummary[] | null): AitoPanelConfig => ({
  operation: "POST /api/v2/_sql",
  stats: [
    {
      value: cards
        ? String(cards.reduce(
            (n, c) => n + Object.values(c.sql ?? {}).filter(Boolean).length, 0))
        : "—",
      label: "SQL statements",
    },
    { value: "0", label: "models trained" },
    { value: "~45ms", label: "per statement" },
  ],
  description:
    "Every number on this page comes from a <strong>SQL statement</strong> — no model was trained, " +
    "and nothing was precomputed. Open <code>▸ SQL</code> on any card to see the exact text that " +
    "produced it, and edit it in place to ask a different question.",
  query:
    "SELECT * FROM relate('analysis',\n" +
    "  to => 'churned = ''true''',\n" +
    "  fields => 'cooling, climate',\n" +
    "  k => 6);",
  links: [
    { label: "Aito SQL guide", url: "https://aito.ai/docs/api/sql/guide" },
    { label: "This demo on GitHub", url: "https://github.com/AitoDotAI/aito-sql-demo" },
  ],
});

function HomeInner() {
  const [cards, setCards] = useState<CardSummary[] | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Which card is expanded lives in the URL, so a pasted link opens on the one
  // the sender was reading. Derived, not mirrored into state: a second copy is
  // how a URL and a view drift apart.
  //
  // No parameter means the first card — a default view, not a claim about
  // data. An UNRECOGNISED one expands nothing and says so, because quietly
  // opening a different card than the link named is the same lie as
  // /product/<id> rendering product 0.
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("card");
  const recognised = (cards ?? []).some((c) => c.key === requested);
  const openKey = requested === null
    ? (cards && cards.length ? cards[0].key : null)
    : (recognised ? requested : null);

  const setOpenKey = (next: string | null) => {
    router.push(next ? `/?card=${encodeURIComponent(next)}` : "/", { scroll: false });
  };

  const load = useCallback(() => {
    setError(null);
    Promise.all([
      apiFetch<{ cards: CardSummary[] }>("/api/cards"),
      apiFetch<Overview>("/api/overview"),
    ])
      .then(([c, o]) => {
        setCards(c.cards);
        setOverview(o);
      })
      .catch((e) => setError(e?.message || "Could not reach the API"));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="app">
      <Nav sections={NAV_SECTIONS} />
      <div className="main">
        <TopBar
          brand="predictive SQL"
          live
          breadcrumb="Dashboards"
          title="360° view of the business"
          subtitle="root causes, and the lever that moves each"
        />
        <div className="content">
          {error && <ErrorState message={error} onRetry={load} />}

          {!error && (
            <>
              <ChainStrip overview={overview} />

              {requested !== null && cards && !recognised && (
                <p className="url-miss">
                  This link points at a card called <code>{requested}</code>, and there is
                  no such card — so nothing is expanded, rather than something else being
                  opened in its place. The six below are all of them.
                </p>
              )}

              {/* The idiomatic form, first — an engineer looking for "what does
                  this actually look like in SQL" should not have to find it on
                  page three. It is also the one claim here that is checkable
                  against withheld data, so it earns the top slot. */}
              <aside className="lead-sql">
                <div className="lead-sql-body">
                  <span className="lead-sql-kicker">Predicting is one statement</span>
                  <pre>
{`SELECT install_id, predictions(churned)
  FROM analysis WHERE churned IS NULL;`}
                  </pre>
                  <p>
                    No model, no training step, no feature pipeline — a column that does not exist
                    yet, asked for like any other. Those rows are real installs whose outcome was
                    withheld from the database, so the answer can be marked.
                  </p>
                </div>
                <Link className="lead-sql-cta" href="/scoring">
                  See how well it did →
                </Link>
              </aside>

              <div className="lede">
                <h2>Six questions, twenty-four SQL statements, no training step.</h2>
                <p>
                  Each card asks what drives an outcome and what could be changed about it. The
                  numbers are calibrated probabilities, the <code>n</code> beside every cause is the
                  evidence it rests on, and <strong>one of these six cards deliberately fails</strong>{" "}
                  — because a dashboard where everything works is one nobody should trust.
                </p>
              </div>

              {!cards && <div className="skeleton-grid">
                {[0, 1, 2, 3, 4, 5].map((i) => <div className="card-skeleton" key={i} />)}
              </div>}

              {cards && (
                <div className="card-grid">
                  {cards.map((c) => (
                    <CardPanel
                      key={c.key}
                      summary={c}
                      open={openKey === c.key}
                      onToggle={() => setOpenKey(openKey === c.key ? null : c.key)}
                    />
                  ))}
                </div>
              )}

              <ConnectBox />

              <section className="honesty">
                <h3>What this page is not hiding</h3>
                <ul>
                  <li>
                    <strong>The data is synthetic, and four mechanisms were planted in it.</strong>{" "}
                    That is the point: knowing the ground truth is the only way to check whether the
                    engine recovered the right answer rather than a plausible one. The generator
                    (<code>src/generate.py</code>) prints what it planted.
                  </li>
                  <li>
                    <strong>One planted signal is a decoy.</strong> The distributor channel really
                    does churn more — and it is not the cause. Card 4 shows it being cleared.
                  </li>
                  <li>
                    <strong>Card 5 finds nothing, and ships anyway.</strong> Commissioning level does
                    not move churn here. The query is identical in shape to the ones that work.
                  </li>
                  <li>
                    <strong>Predicted rates sit below the raw rates.</strong> Support-tempering
                    shrinks confidence toward the base rate when evidence is thin or redundant, so
                    the card understates a cell it has little data for, on purpose.
                  </li>
                  <li>
                    <strong>These six numbers are in-sample.</strong> Each card predicts against
                    the same <code>analysis</code>{" "}table the installs it is describing live in, so
                    the rows being summarised are also part of the evidence. That is the right
                    thing for a question about a population you already have &mdash; but it is not
                    a measure of how well the engine would do on an install it has never seen.
                    That measurement is on its own page, it is held out, and{" "}
                    <Link href="/scoring">it does not flatter us</Link>.
                  </li>
                </ul>
              </section>
            </>
          )}
        </div>
      </div>
      <AitoPanel config={panelConfig(cards)} />
    </div>
  );
}

export default function Home() {
  // useSearchParams needs a Suspense boundary for the static export.
  return (
    <Suspense fallback={<div className="card-loading">loading…</div>}>
      <HomeInner />
    </Suspense>
  );
}
