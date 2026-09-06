"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TopBar from "@/components/shell/TopBar";
import Nav from "@/components/shell/Nav";
import { ROUTES } from "@/lib/routes";
import AitoPanel from "@/components/shell/AitoPanel";
import ErrorState from "@/components/shell/ErrorState";
import { apiFetch } from "@/lib/api";
import type { AitoPanelConfig } from "@/lib/types";
import type { MapResult, MapCell } from "@/lib/cardTypes";

const PANEL_CONFIG: AitoPanelConfig = {
  operation: "relate() x 18",
  stats: [
    { value: "827", label: "cells" },
    { value: "18", label: "statements" },
    { value: "2.4s", label: "whole sweep" },
  ],
  description:
    "The map exists to answer one objection: <em>you found that because you went looking for it.</em> " +
    "This is every field crossed with every slice, swept by the same <code>relate()</code> the cards " +
    "use — and the cards turn out to be the top of it.",
  query:
    "SELECT * FROM relate('hot_sites',\n" +
    "  to     => 'churned = ''true''',\n" +
    "  fields => 'cooling, climate, grade, …',\n" +
    "  k => 60);",
  links: [
    { label: "Aito SQL guide", url: "https://aito.ai/docs/api/sql/guide" },
    { label: "Source on GitHub", url: "https://github.com/AitoDotAI" },
  ],
};

function Bar({ value, max }: { value: number; max: number }) {
  const w = Math.max(2, Math.min(100, (value / max) * 100));
  return <div className="sig-bar" style={{ width: `${w}%` }} />;
}

function CellRow({ c, max, rank }: { c: MapCell; max: number; rank: number }) {
  const up = c.lift > (c.base_lift ?? 1);
  return (
    <tr className={c.card ? "cell-carded" : ""}>
      <td className="cell-rank">{rank}</td>
      <td>
        <span className="cell-field">{c.field}</span>
        <span className="cell-eq">=</span>
        <span className="cell-value">{c.value}</span>
      </td>
      <td className="cell-slice">{c.slice}</td>
      <td className="cell-num">
        {c.base_lift != null ? `×${c.base_lift.toFixed(2)}` : "—"}
      </td>
      <td className="cell-num cell-arrow" aria-hidden="true">{up ? "→▲" : "→▼"}</td>
      <td className="cell-num cell-strong">×{c.lift.toFixed(2)}</td>
      <td className="cell-sig">
        <span className="sig-track"><Bar value={c.signal} max={max} /></span>
        <span className="cell-signum">{c.signal.toFixed(4)}</span>
      </td>
      <td>
        {c.card ? (
          <Link className="cell-card" href={`/#${c.card}`}>card →</Link>
        ) : (
          <span className="cell-nocard">—</span>
        )}
      </td>
    </tr>
  );
}

export default function MapPage() {
  const [data, setData] = useState<MapResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback((refresh = false) => {
    setError(null);
    if (refresh) setRefreshing(true);
    apiFetch<MapResult>(`/api/map${refresh ? "?refresh=true" : ""}`)
      .then(setData)
      .catch((e) => setError(e?.message || "Could not reach the API"))
      .finally(() => setRefreshing(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const cells = data?.by_movement ?? [];
  const max = cells.length ? cells[0].signal : 1;
  const carded = cells.filter((c) => c.card).length;

  return (
    <div className="app">
      <Nav routes={ROUTES} />
      <div className="main">
        <TopBar
          brand="predictive SQL"
          live
          breadcrumb="Dashboards"
          title="The map behind the cards"
          subtitle="every field × every slice, ranked — nobody picked these"
        />
        <div className="content">
          {error && <ErrorState message={error} onRetry={() => load()} />}

          {!error && (
            <>
              <div className="lede">
                <h2>The six cards are the top of this, not a selection from it.</h2>
                <p>
                  A good analyst&rsquo;s first objection to any dashboard is that you found the
                  finding because you went looking for it. So this sweeps{" "}
                  <strong>every explanatory field against every slice</strong> with the same{" "}
                  <code>relate()</code> the cards use, and ranks what comes back. The cards were
                  written from the top of this ranking &mdash; you can check that below, and you can
                  re-run the whole sweep yourself.
                </p>
              </div>

              {data && (
                <div className="map-stats">
                  <div className="map-stat">
                    <span className="map-stat-v">{data.cells}</span>
                    <span className="map-stat-l">cells swept</span>
                  </div>
                  <div className="map-stat">
                    <span className="map-stat-v">{data.statements}</span>
                    <span className="map-stat-l">SQL statements</span>
                  </div>
                  <div className="map-stat">
                    <span className="map-stat-v">{(data.generated_ms / 1000).toFixed(1)}s</span>
                    <span className="map-stat-l">to sweep all of it</span>
                  </div>
                  <div className="map-stat">
                    <span className="map-stat-v">{data.slices.length + 1}</span>
                    <span className="map-stat-l">slices (incl. the whole book)</span>
                  </div>
                  <button className="btn btn-outline map-refresh"
                          onClick={() => load(true)} disabled={refreshing}>
                    {refreshing ? "sweeping…" : "re-run the sweep"}
                  </button>
                </div>
              )}

              <section className="map-note">
                <h3>What is being ranked, and why it is not just &ldquo;lift&rdquo;</h3>
                <p>
                  <strong>An interaction is invisible to lift alone.</strong> Passive cooling reads
                  ×1.56 across the whole book, which is unremarkable and would never earn a card.
                  What gives it away is that the lift <em>moves</em> when you condition: ×1.81 inside
                  hot sites, ×1.08 inside temperate ones. So each cell is scored by how far its lift
                  travelled under conditioning, weighted by information gain.
                </p>
                <p className="map-note-sub">
                  The weighting is not decoration. Ranked on movement alone, the top of this table
                  was <code>ticket_count=3 inside arctic</code>{" "}at 0.82 &mdash; a thin slice letting a
                  lift wander. Every one of those noise cells carried <code>info</code>{" "}around
                  0.0002&ndash;0.003, while the planted interaction carried 0.056. Weighting by the
                  engine&rsquo;s own information measure separates them without a hand-tuned
                  threshold, and without dropping the noisy fields &mdash; which would have been the
                  same curation this page exists to avoid.
                </p>
              </section>

              {!data && <div className="card-loading">sweeping…</div>}

              {data && (
                <div className="map-table-wrap">
                  <table className="map-table">
                    <thead>
                      <tr>
                        <th>#</th><th>cell</th><th>inside</th>
                        <th>overall</th><th></th><th>in slice</th>
                        <th>signal</th><th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {cells.map((c, i) => (
                        <CellRow key={i} c={c} max={max} rank={i + 1} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {data && (
                <section className="honesty">
                  <h3>Reading this honestly</h3>
                  <ul>
                    <li>
                      <strong>{carded} of the top {cells.length} rows carry a card.</strong> That is
                      the claim: the cards came out of this ranking rather than out of a hunch.
                    </li>
                    <li>
                      <strong>Two rows say the same thing twice.</strong>{" "}
                      <code>grade=consumer</code> and <code>duty_cycle_pct=35</code> score
                      identically inside 3-shift because they are the same fact &mdash; the generator
                      sets duty cycle from grade. The map surfaces the redundancy rather than hiding
                      it, which is what you want a map to do about your own schema.
                    </li>
                    <li>
                      <strong>The sweep is one statement per slice, not per cell.</strong>{" "}
                      {data.cells} cells from {data.statements} statements. That is the whole reason
                      an exhaustive map is affordable here.
                    </li>
                    <li>
                      <strong>Numeric fields are related as categories.</strong>{" "}
                      <code>ticket_count</code> and <code>feedback_score</code> get one row per
                      distinct value, which is why they crowd the middle of the table. A real
                      deployment would bucket them.
                    </li>
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
      </div>
      <AitoPanel config={PANEL_CONFIG} />
    </div>
  );
}
