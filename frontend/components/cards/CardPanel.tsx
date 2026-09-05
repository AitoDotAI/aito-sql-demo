"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Cause, CardDetail, CardSummary, Lever, SqlRunResult } from "@/lib/cardTypes";

/** Direction glyph + the number, ALWAYS — never colour alone.
 *
 *  The status red and green in this design system sit at ΔE 2.7 under deutan
 *  simulation (measured, not assumed): to a deuteranope they are the same
 *  colour. Colour here is a redundant cue on top of the glyph and the value,
 *  never the thing carrying the meaning.
 */
function Lift({ value }: { value: number | null }) {
  if (value == null) return <span className="lift lift-flat">—</span>;
  const up = value > 1.05;
  const down = value < 0.95;
  const cls = up ? "lift-up" : down ? "lift-down" : "lift-flat";
  const glyph = up ? "▲" : down ? "▼" : "▬";
  const label = up ? "above baseline" : down ? "below baseline" : "at baseline";
  return (
    <span className={`lift ${cls}`} title={label}>
      <span aria-hidden="true">{glyph}</span> ×{value.toFixed(2)}
      <span className="sr-only"> {label}</span>
    </span>
  );
}

/** Churn against the book-wide rate. One measure, one axis, a reference mark
 *  for the baseline — not a second scale. */
function Meter({ churn, base }: { churn: number | null; base: number | null }) {
  if (churn == null) return null;
  const max = Math.max(churn, base ?? 0) * 1.45 || 100;
  const w = Math.min(100, (churn / max) * 100);
  const bw = base != null ? Math.min(100, (base / max) * 100) : null;
  const bad = base != null && churn > base * 1.05;
  return (
    <div className="meter" role="img"
         aria-label={`churn ${churn}%, baseline ${base ?? "unknown"}%`}>
      <div className={`meter-fill ${bad ? "meter-bad" : "meter-ok"}`} style={{ width: `${w}%` }} />
      {bw != null && (
        <div className="meter-base" style={{ left: `${bw}%` }} title={`baseline ${base}%`} />
      )}
    </div>
  );
}

function CauseRow({ c }: { c: Cause }) {
  return (
    <li className="cause">
      <div className="cause-main">
        <span className="cause-field" title={c.field}>{c.field}</span>
        <span className="cause-value">{String(c.value)}</span>
      </div>
      <div className="cause-stats">
        {c.rate != null && <span className="cause-rate">{c.rate}% churn</span>}
        <Lift value={c.lift} />
        <span className="cause-n">n={c.n != null ? Math.round(c.n).toLocaleString() : "—"}</span>
      </div>
    </li>
  );
}

function LeverRow({ l, best }: { l: Lever; best: boolean }) {
  return (
    <li className={`lever ${best ? "lever-best" : ""}`}>
      <span className="lever-value">
        {best && <span className="lever-star" aria-hidden="true">★</span>}
        {String(l.value)}
      </span>
      <span className="lever-num">{l.churn != null ? `${l.churn}% churn` : "—"}</span>
    </li>
  );
}

export default function CardPanel({
  summary, open, onToggle,
}: { summary: CardSummary; open: boolean; onToggle: () => void }) {
  const [detail, setDetail] = useState<CardDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [showSql, setShowSql] = useState(false);
  const [draft, setDraft] = useState<string>("");
  const [runResult, setRunResult] = useState<SqlRunResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || detail || loading) return;
    setLoading(true);
    apiFetch<CardDetail>(`/api/cards/${summary.key}`)
      .then((d) => { setDetail(d); setDraft(d.sql.causes); })
      .catch(() => void 0)
      .finally(() => setLoading(false));
  }, [open, detail, loading, summary.key]);

  const runDraft = () => {
    setRunError(null);
    fetch("/api/sql", { method: "POST", body: draft })
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body?.detail?.message || "query failed");
        setRunResult(body);
      })
      .catch((e) => { setRunResult(null); setRunError(e.message); });
  };

  const isNull = summary.mechanism === "NEG";
  const levers = detail?.levers ?? [];
  const bestLever = levers.reduce<Lever | null>(
    (a, b) => (a == null || (b.p_good ?? 0) > (a.p_good ?? 0) ? b : a), null);

  return (
    <article className={`card ${open ? "card-open" : ""} ${isNull ? "card-null" : ""}`}>
      <header className="card-head">
        <div className="card-titles">
          <span className="card-rank">map #{summary.rank}</span>
          <h3>{summary.title}</h3>
        </div>
        <span className={`tag tag-${summary.mechanism.toLowerCase()}`}>{summary.mechanism}</span>
      </header>

      <p className="card-question">{summary.question}</p>

      <div className="card-hero">
        <div className="hero-num">
          <span className="hero-value">{summary.churn != null ? `${summary.churn}%` : "—"}</span>
          <span className="hero-unit">predicted churn</span>
        </div>
        <div className="hero-cmp">
          <Lift value={summary.lift} />
          <span className="hero-base">
            vs {summary.base_churn}% book-wide
          </span>
        </div>
      </div>
      <Meter churn={summary.churn} base={summary.base_churn} />

      <button className="card-toggle" onClick={onToggle} aria-expanded={open}>
        {open ? "▾ hide the working" : "▸ show causes, levers and the SQL"}
      </button>

      {open && (
        <div className="card-body">
          {loading && <div className="card-loading">running four statements…</div>}

          {detail && (
            <>
              <section>
                <h4>What relates to it</h4>
                <ul className="cause-list">
                  {detail.causes.map((c, i) => <CauseRow c={c} key={i} />)}
                </ul>
              </section>

              {detail.conditioned && (
                <section className="conditioned">
                  <h4>{detail.conditioned_label}</h4>
                  <ul className="cause-list">
                    {detail.conditioned.map((c, i) => <CauseRow c={c} key={i} />)}
                  </ul>
                </section>
              )}

              <section>
                <h4>What you could change</h4>
                {levers.length === 0 && <p className="muted">no lever returned</p>}
                <ul className="lever-list">
                  {levers.map((l, i) => (
                    <LeverRow l={l} key={i} best={bestLever === l && !isNull} />
                  ))}
                </ul>
              </section>

              <p className="card-note">{detail.note}</p>

              <button className="sql-toggle" onClick={() => setShowSql(!showSql)}
                      aria-expanded={showSql}>
                {showSql ? "▾ SQL" : "▸ SQL"}
              </button>

              {showSql && (
                <div className="sql-box">
                  <p className="sql-help">
                    This is the statement that produced the causes above. Edit it and run — the
                    card definition <em>is</em> SQL, so anything you can write here is a card.
                  </p>
                  <textarea value={draft} spellCheck={false}
                            onChange={(e) => setDraft(e.target.value)} rows={4} />
                  <div className="sql-actions">
                    <button className="btn btn-primary" onClick={runDraft}>Run</button>
                    <button className="btn btn-outline"
                            onClick={() => { setDraft(detail.sql.causes); setRunResult(null); setRunError(null); }}>
                      Reset
                    </button>
                    <span className="sql-ms">{detail.ms} ms for this card</span>
                  </div>
                  {runError && <pre className="sql-error">{runError}</pre>}
                  {runResult && (
                    <div className="sql-result">
                      <div className="sql-result-head">
                        {runResult.rows.length} rows · {runResult.ms} ms
                      </div>
                      <pre>{JSON.stringify(runResult.rows.slice(0, 5), null, 1)}</pre>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </article>
  );
}
