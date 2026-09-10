"use client";

import { useCallback, useEffect, useState } from "react";
import TopBar from "@/components/shell/TopBar";
import Nav from "@/components/shell/Nav";
import { NAV_SECTIONS } from "@/lib/routes";
import AitoPanel from "@/components/shell/AitoPanel";
import ErrorState from "@/components/shell/ErrorState";
import { apiFetch } from "@/lib/api";
import type { AitoPanelConfig } from "@/lib/types";
import CardPanel from "@/components/cards/CardPanel";
import ChainStrip from "@/components/cards/ChainStrip";
import type { CardSummary, Overview } from "@/lib/cardTypes";

const PANEL_CONFIG: AitoPanelConfig = {
  operation: "POST /api/v2/_sql",
  stats: [
    { value: "13", label: "tables" },
    { value: "0", label: "models trained" },
    { value: "~150ms", label: "per card" },
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
    { label: "Source on GitHub", url: "https://github.com/AitoDotAI" },
  ],
};

export default function Home() {
  const [cards, setCards] = useState<CardSummary[] | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openKey, setOpenKey] = useState<string | null>("thermal");

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
                </ul>
              </section>
            </>
          )}
        </div>
      </div>
      <AitoPanel config={PANEL_CONFIG} />
    </div>
  );
}
