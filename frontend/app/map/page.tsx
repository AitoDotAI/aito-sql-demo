"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TopBar from "@/components/shell/TopBar";
import Nav from "@/components/shell/Nav";
import { NAV_SECTIONS } from "@/lib/routes";
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

/** Lift over the whole book -> lift inside the slice, on one shared scale.
 *
 *  The data's job is "before -> after per item", which is a dumbbell. The
 *  connector's LENGTH is the movement, and movement is what the table ranks
 *  on — previously that was two numbers with a 12px arrow between them, so
 *  the one quantity the page is about was the one you had to compute in your
 *  head.
 *
 *  Both ends are labelled because they have to be: the light shade measures
 *  2.31:1 against this surface, and a contrast warning obliges visible labels
 *  rather than relying on the mark.
 */
function Dumbbell({ from, to, lo, hi }: { from: number; to: number; lo: number; hi: number }) {
  const pos = (v: number) => Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100));
  const a = pos(from);
  const b = pos(to);
  const left = Math.min(a, b);
  const width = Math.abs(b - a);
  const rose = to > from;
  // Anchor the end labels inward near the edges; a centred label at 0% or
  // 100% overhangs the track and is clipped by the cell.
  const label = (pct: number): React.CSSProperties =>
    pct < 12 ? { left: 0 }
    : pct > 88 ? { right: 0 }
    : { left: `${pct}%`, transform: "translateX(-50%)" };
  return (
    <div className="db" role="img"
         aria-label={`lift ${from.toFixed(2)} overall, ${to.toFixed(2)} inside this slice`}>
      <div className="db-axis" />
      <div className="db-ref" style={{ left: `${pos(1)}%` }} title="×1.00 — no effect" />
      <div className="db-conn" style={{ left: `${left}%`, width: `${width}%` }} />
      <div className="db-dot db-from" style={{ left: `${a}%` }} />
      <div className="db-dot db-to" style={{ left: `${b}%` }} />
      <span className="db-num" style={label(a)}>{from.toFixed(2)}</span>
      <span className="db-num db-num-to" style={label(b)}>
        {rose ? "▲" : "▼"}{to.toFixed(2)}
      </span>
    </div>
  );
}

function CellRow({ c, max, rank, lo, hi }:
                 { c: MapCell; max: number; rank: number; lo: number; hi: number }) {
  return (
    <tr className={c.card ? "cell-carded" : ""}>
      <td className="cell-rank">{rank}</td>
      <td>
        <span className="cell-field">{c.field}</span>
        <span className="cell-eq">=</span>
        <span className="cell-value">{c.value}</span>
      </td>
      <td className="cell-slice">{c.slice}</td>
      <td>
        {c.base_lift != null
          ? <Dumbbell from={c.base_lift} to={c.lift} lo={lo} hi={hi} />
          : <span className="cell-nocard">—</span>}
      </td>
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

  // One scale for every row, so connector lengths are comparable down the
  // column. Per-row scaling would make a small movement look like a large one.
  const lifts = cells.flatMap((c) => [c.lift, c.base_lift ?? c.lift]);
  const lo = lifts.length ? Math.min(0.9, ...lifts) : 0;
  const hi = lifts.length ? Math.max(1.1, ...lifts) : 2;

  // The finding, computed rather than asserted. Specifically the cells behind
  // the INTERACTION cards: taking "the first two carded cells" put M4 first,
  // which is a plain main effect, under a headline claiming interactions.
  const interactionKeys = new Set(
    (data?.cards ?? []).filter((c) => c.interaction).map((c) => c.key));
  const topCards = cells
    .map((c, i) => ({ ...c, rank: i + 1 }))
    .filter((c) => c.card && interactionKeys.has(c.card));

  return (
    <div className="app">
      <Nav sections={NAV_SECTIONS} />
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
                  finding because you went looking for it. So this sweeps every explanatory field
                  against every slice with the same <code>relate()</code> the cards use, and ranks
                  what comes back.
                </p>
              </div>

              {data && topCards.length > 0 && (
                <section className="finding">
                  <div className="finding-lead">
                    <h3>
                      Both planted interactions are in the top{" "}
                      {Math.max(...topCards.map((c) => c.rank))} of {data.cells}.
                    </h3>
                    <p>
                      Neither field is named anywhere in the sweep&rsquo;s configuration — it reads
                      every column against every slice. An interaction is the hard case, because it
                      is invisible until you condition; these two rose on their own.{" "}
                      {carded} of the top {cells.length} cells carry a card.
                    </p>
                  </div>
                  <div className="finding-cells">
                    {topCards.map((c) => (
                      <div className="finding-cell" key={c.card}>
                        <span className="finding-rank">rank #{c.rank} of {data.cells}</span>
                        <span className="finding-cell-name">{c.field} = {c.value}</span>
                        <span className="finding-cell-slice">
                          inside {c.slice} · ×{c.base_lift?.toFixed(2)} → ×{c.lift.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

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

              <details className="method">
                <summary>
                  <span>
                    <strong>Why the ranking is not just &ldquo;lift&rdquo;.</strong> An interaction
                    is invisible to lift alone — passive cooling reads ×1.56 across the whole book.
                  </span>
                </summary>
                <div className="method-body">
                  <p>
                    What gives an interaction away is that the lift <em>moves</em> when you
                    condition: ×1.81 inside hot sites, ×1.08 inside temperate ones. Each cell is
                    scored by how far its lift travelled, weighted by information gain — the bar in
                    the <code>signal</code> column.
                  </p>
                  <p>
                    The weighting is not decoration. Ranked on movement alone the top of this table
                    was <code>ticket_count=3 inside arctic</code>{" "}at 0.82 — a thin slice letting a
                    lift wander. Those noise cells carried <code>info</code>{" "}around 0.0002–0.003
                    while the planted interaction carried 0.056, so the engine&rsquo;s own
                    information measure separates them without a hand-tuned threshold, and without
                    dropping the noisy fields — which would have been the same curation this page
                    exists to avoid.
                  </p>
                </div>
              </details>

              {!data && <div className="card-loading">sweeping…</div>}

              {data && (
                <div className="map-table-wrap">
                  <table className="map-table">
                    <thead>
                      <tr>
                        <th>#</th><th>cell</th><th>inside</th>
                        <th>
                          lift: whole book → this slice
                          <span className="db-legend">
                            <span className="db-key">
                              <i className="db-swatch db-from" /> overall
                            </span>
                            <span className="db-key">
                              <i className="db-swatch db-to" /> in slice
                            </span>
                          </span>
                        </th>
                        <th>signal</th><th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {cells.map((c, i) => (
                        <CellRow key={i} c={c} max={max} rank={i + 1} lo={lo} hi={hi} />
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
