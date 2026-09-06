"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import TopBar from "@/components/shell/TopBar";
import Nav from "@/components/shell/Nav";
import { ROUTES } from "@/lib/routes";
import AitoPanel from "@/components/shell/AitoPanel";
import ErrorState from "@/components/shell/ErrorState";
import { apiFetch } from "@/lib/api";
import type { AitoPanelConfig } from "@/lib/types";
import type { ExploreResult, ExploreDimension, ExploreValue } from "@/lib/cardTypes";

const PANEL_CONFIG: AitoPanelConfig = {
  operation: "predict + recommend + GROUP BY",
  stats: [
    { value: "∞", label: "slices" },
    { value: "~1s", label: "per click" },
    { value: "0", label: "precomputed" },
  ],
  description:
    "Every click narrows a <code>WHERE</code> and re-asks the whole question. Nothing here is " +
    "precomputed — the slice you are looking at may never have been queried before.",
  query:
    "SELECT value, p FROM predict('analysis',\n" +
    "  'churned',\n" +
    "  where => 'climate = ''hot''\n" +
    "            AND cooling = ''passive''');",
  links: [
    { label: "Aito SQL guide", url: "https://aito.ai/docs/api/sql/guide" },
    { label: "Source on GitHub", url: "https://github.com/AitoDotAI" },
  ],
};

function encode(facets: { field: string; value: string }[]) {
  return facets.map((f) => `${f.field}:${f.value}`).join(",");
}

/** A value chip. The lift is against THIS slice, so ×1.00 means "no different
 *  from where you already are" — which is the useful reading when navigating. */
function ValueChip({ v, onClick }: { v: ExploreValue; onClick: () => void }) {
  const up = (v.lift ?? 1) > 1.08;
  const down = (v.lift ?? 1) < 0.92;
  return (
    <button className={`chip ${up ? "chip-up" : down ? "chip-down" : ""}`} onClick={onClick}
            title={`narrow to ${v.value} — ${v.n} rows`}>
      <span className="chip-value">{v.value}</span>
      <span className="chip-rate">{v.rate}%</span>
      <span className="chip-n">n={v.n.toLocaleString()}</span>
      <span aria-hidden="true" className="chip-dir">{up ? "▲" : down ? "▼" : "▬"}</span>
    </button>
  );
}

function Dimension({ d, onPick }: { d: ExploreDimension; onPick: (f: string, v: string) => void }) {
  return (
    <section className="dim">
      <header className="dim-head">
        <h4>{d.field}</h4>
        <span className="dim-spread" title="widest gap between this field's values, in points">
          {d.spread}pp spread
        </span>
      </header>
      <div className="chips">
        {d.values.map((v) => (
          <ValueChip key={v.value} v={v} onClick={() => onPick(d.field, v.value)} />
        ))}
      </div>
    </section>
  );
}

function ExplorerInner() {
  const router = useRouter();
  const params = useSearchParams();
  const where = params.get("where") || "";
  const lever = params.get("lever") || "";

  const [data, setData] = useState<ExploreResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showSql, setShowSql] = useState(false);

  const load = useCallback(() => {
    setBusy(true);
    setError(null);
    const q = new URLSearchParams();
    if (where) q.set("where", where);
    if (lever) q.set("lever", lever);
    apiFetch<ExploreResult>(`/api/explore${q.toString() ? `?${q}` : ""}`)
      .then(setData)
      .catch((e) => setError(e?.message || "Could not reach the API"))
      .finally(() => setBusy(false));
  }, [where, lever]);

  useEffect(load, [load]);

  const go = (facets: { field: string; value: string }[], nextLever?: string) => {
    const q = new URLSearchParams();
    const w = encode(facets);
    if (w) q.set("where", w);
    if (nextLever ?? lever) q.set("lever", nextLever ?? lever);
    router.push(`/explore${q.toString() ? `?${q}` : ""}`);
  };

  const facets = data?.facets ?? [];
  const drill = (field: string, value: string) => go([...facets, { field, value }]);
  const dropAt = (i: number) => go(facets.slice(0, i));

  const gap = data && data.observed != null && data.predicted != null
    ? Math.abs(data.observed - data.predicted) : 0;

  return (
    <div className="app">
      <Nav routes={ROUTES} />
      <div className="main">
        <TopBar
          brand="predictive SQL"
          live
          breadcrumb="Dashboards"
          title="Explorer"
          subtitle="every value is a link to a narrower question"
        />
        <div className="content">
          {error && <ErrorState message={error} onRetry={load} />}

          {!error && (
            <>
              <nav className="trail" aria-label="current slice">
                <button className="trail-crumb trail-root" onClick={() => go([])}>
                  all installs
                </button>
                {facets.map((f, i) => (
                  <span key={`${f.field}:${f.value}`} className="trail-seg">
                    <span className="trail-sep" aria-hidden="true">›</span>
                    <button className="trail-crumb" onClick={() => dropAt(i + 1)}>
                      {f.field} = <strong>{f.value}</strong>
                    </button>
                  </span>
                ))}
                {facets.length > 0 && (
                  <button className="trail-clear" onClick={() => go([])}>clear</button>
                )}
              </nav>

              {data && (
                <div className="ex-hero">
                  <div className="ex-nums">
                    <div className="ex-num">
                      <span className="ex-v">{data.observed ?? "—"}%</span>
                      <span className="ex-l">churn, counted</span>
                    </div>
                    <div className="ex-num">
                      <span className="ex-v ex-v-pred">{data.predicted ?? "—"}%</span>
                      <span className="ex-l">churn, predicted</span>
                    </div>
                    <div className="ex-num">
                      <span className="ex-v ex-v-n">{data.n.toLocaleString()}</span>
                      <span className="ex-l">installs in this slice</span>
                    </div>
                  </div>
                  <p className={`ex-gap ${gap > 4 ? "ex-gap-wide" : ""}`}>
                    {gap > 4 ? (
                      <>
                        <strong>The two numbers disagree by {gap.toFixed(1)} points, and that is
                        the engine being careful.</strong>{" "}
                        {data.n.toLocaleString()} rows is thin for a slice this specific, so
                        support-tempering pulls the prediction back toward the base rate. Narrow
                        further and watch the gap widen.
                      </>
                    ) : (
                      <>
                        Counted and predicted agree to within {gap.toFixed(1)} points here — there
                        is enough evidence in this slice that the engine has no reason to hedge.
                        Keep narrowing and they will come apart.
                      </>
                    )}
                  </p>
                </div>
              )}

              {busy && !data && <div className="card-loading">asking…</div>}

              {data && (
                <div className="ex-grid">
                  <div className="ex-main">
                    <h3 className="ex-h">What divides this slice</h3>
                    <p className="ex-sub">
                      Ranked by spread — the field whose values differ most in churn rate comes
                      first, because that is the most informative next click. Percentages are
                      counted from the rows; <code>n</code> is how many.
                    </p>
                    {data.dimensions.length === 0 && (
                      <p className="muted">
                        Nothing left to split on — every remaining field has fewer than 12 rows per
                        value here. That is the honest end of this branch, not an error.
                      </p>
                    )}
                    {data.dimensions.map((d) => (
                      <Dimension key={d.field} d={d} onPick={drill} />
                    ))}
                  </div>

                  <aside className="ex-side">
                    <h3 className="ex-h">What to do about it</h3>
                    <p className="ex-sub">
                      <code>recommend()</code> ranked toward <em>not</em> churning, conditioned on
                      this exact slice.
                    </p>
                    <div className="lever-picker">
                      {data.lever_options.map((l) => (
                        <button key={l}
                                className={`lever-tab ${l === data.lever ? "lever-tab-on" : ""}`}
                                onClick={() => go(facets, l)}>
                          {l}
                        </button>
                      ))}
                    </div>
                    <ul className="lever-list">
                      {data.levers.map((l, i) => (
                        <li key={String(l.value)} className={`lever ${i === 0 ? "lever-best" : ""}`}>
                          <span className="lever-value">
                            {i === 0 && <span className="lever-star" aria-hidden="true">★</span>}
                            {String(l.value)}
                          </span>
                          <span className="lever-num">
                            {l.churn != null ? `${l.churn}% churn` : "—"}
                          </span>
                        </li>
                      ))}
                      {data.levers.length === 0 && (
                        <li className="muted">no lever available in this slice</li>
                      )}
                    </ul>

                    <button className="sql-toggle" onClick={() => setShowSql(!showSql)}
                            aria-expanded={showSql}>
                      {showSql ? "▾ the SQL behind this screen" : "▸ the SQL behind this screen"}
                    </button>
                    {showSql && (
                      <div className="ex-sql">
                        {Object.entries(data.sql).map(([k, v]) => (
                          <div key={k}>
                            <span className="ex-sql-k">{k}</span>
                            <pre>{v}</pre>
                          </div>
                        ))}
                        {data.dimensions[0] && (
                          <div>
                            <span className="ex-sql-k">each dimension (×{data.dimensions.length})</span>
                            <pre>{data.dimensions[0].sql}</pre>
                          </div>
                        )}
                      </div>
                    )}
                  </aside>
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <AitoPanel config={PANEL_CONFIG} />
    </div>
  );
}

export default function ExplorePage() {
  // useSearchParams needs a Suspense boundary for the static export.
  return (
    <Suspense fallback={<div className="card-loading">loading…</div>}>
      <ExplorerInner />
    </Suspense>
  );
}
