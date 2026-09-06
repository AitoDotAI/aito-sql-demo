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
import type { PatternsResult, MinedPattern } from "@/lib/cardTypes";

const PANEL_CONFIG: AitoPanelConfig = {
  operation: "patterns(…)",
  stats: [
    { value: "5", label: "column groups" },
    { value: "0", label: "hypotheses" },
    { value: "100%", label: "cases checkable" },
  ],
  description:
    "<code>patterns()</code> mines conjunctions — combinations of values that co-occur more than " +
    "they should. Nothing here was hypothesised: the only input is which columns to look at.",
  query:
    "SELECT * FROM patterns('analysis',\n" +
    "  fields => 'cooling, grade, climate,\n" +
    "             shift_pattern, churned',\n" +
    "  where  => 'churned = ''true''',\n" +
    "  k => 4);",
  links: [
    { label: "Aito SQL guide", url: "https://aito.ai/docs/api/sql/guide" },
    { label: "Source on GitHub", url: "https://github.com/AitoDotAI" },
  ],
};

function Term({ field, value }: { field: string; value: string }) {
  return (
    <span className="term">
      <span className="term-f">{field}</span>
      <span className="term-eq">:</span>
      <span className="term-v">{value}</span>
    </span>
  );
}

function PatternCard({ p, cols }: { p: MinedPattern; cols: string[] }) {
  const [open, setOpen] = useState(false);
  const strong = (p.lift ?? 1) > 1.15;
  const exploreHref =
    "/explore?where=" +
    p.terms
      .filter((t) => t.field !== "churned")
      .map((t) => `${t.field}:${t.value}`)
      .join(",");

  return (
    <article className={`pat ${strong ? "pat-strong" : ""}`}>
      <header className="pat-head">
        <div className="pat-terms">
          {p.terms.map((t) => <Term key={t.field} {...t} />)}
        </div>
        <div className="pat-nums">
          {p.lift != null && (
            <span className={`lift ${strong ? "lift-up" : "lift-down"}`}>
              <span aria-hidden="true">{strong ? "▲" : "▼"}</span> ×{p.lift.toFixed(2)}
            </span>
          )}
          <span className="pat-n">{p.n.toLocaleString()} installs</span>
        </div>
      </header>

      <p className="pat-sentence">{p.sentence}</p>

      <div className="pat-actions">
        <button className="sql-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? `▾ hide the cases` : `▸ show ${p.cases.length} of these installs`}
        </button>
        <Link className="pat-explore" href={exploreHref}>open in explorer →</Link>
      </div>
      <code className="pat-where">WHERE {p.where}</code>

      {open && (
        <div className="pat-cases map-table-wrap">
          <table className="map-table">
            <thead>
              <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {p.cases.map((row, i) => (
                <tr key={i}>
                  {cols.map((c) => <td key={c}>{String(row[c] ?? "—")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

export default function PatternsPage() {
  const [data, setData] = useState<PatternsResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    apiFetch<PatternsResult>("/api/patterns")
      .then(setData)
      .catch((e) => setError(e?.message || "Could not reach the API"));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="app">
      <Nav routes={ROUTES} />
      <div className="main">
        <TopBar
          brand="predictive SQL"
          live
          breadcrumb="Dashboards"
          title="Patterns"
          subtitle="combinations the engine found, and the rows behind each"
        />
        <div className="content">
          {error && <ErrorState message={error} onRetry={load} />}

          {!error && (
            <>
              <div className="lede">
                <h2>Nobody proposed these combinations.</h2>
                <p>
                  A card answers a question you thought of. <code>patterns()</code> answers none
                  &mdash; it mines{" "}
                  <strong>conjunctions of values that co-occur more than they should</strong>, and
                  the only input is which columns to look at. Each one below is written back into a{" "}
                  <code>WHERE</code>, so the installs behind it are real rows you can open.
                </p>
              </div>

              {!data && <div className="card-loading">mining…</div>}

              {data && (
                <>
                  <div className="map-stats">
                    <div className="map-stat">
                      <span className="map-stat-v">{data.patterns.length}</span>
                      <span className="map-stat-l">patterns kept</span>
                    </div>
                    <div className="map-stat">
                      <span className="map-stat-v">{data.statements}</span>
                      <span className="map-stat-l">SQL statements</span>
                    </div>
                    <div className="map-stat">
                      <span className="map-stat-v">{data.groups.length}</span>
                      <span className="map-stat-l">column groups mined</span>
                    </div>
                  </div>

                  <div className="pat-list">
                    {data.patterns.map((p, i) => (
                      <PatternCard key={i} p={p} cols={data.case_columns} />
                    ))}
                  </div>

                  <section className="honesty">
                    <h3>How to read a lift here</h3>
                    <ul>
                      <li>
                        <strong>The lift is measured against churn, not against chance.</strong> The
                        mining runs with <code>where =&gt; &apos;churned = true&apos;</code>, so ×4.9
                        means <em>this combination is 4.9× more common among installs that
                        churned</em> &mdash; not that it is 4.9× more likely to occur.
                      </li>
                      <li>
                        <strong>A conjunction is not a cause.</strong> Several of these contain both
                        a machine fact and an outcome, which is co-occurrence. The{" "}
                        <Link href="/map">map</Link> is where that gets tested, by conditioning.
                      </li>
                      <li>
                        <strong>The sentences are generated, not written.</strong> Each is assembled
                        from the mined terms by grammatical slot, so if the mining returns something
                        else tomorrow the prose changes with it. That is also why they read a little
                        stiffly.
                      </li>
                      <li>
                        <strong>Patterns cannot yet cross a link.</strong> <code>$patterns</code>{" "}
                        mines the columns of one table, which is why this runs on the flat{" "}
                        <code>analysis</code> table rather than the normalised schema (filed as
                        td-20260823192630739057).
                      </li>
                    </ul>
                  </section>
                </>
              )}
            </>
          )}
        </div>
      </div>
      <AitoPanel config={PANEL_CONFIG} />
    </div>
  );
}
