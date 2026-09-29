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
import type { Scoring, ScoringBand, ScoringSample } from "@/lib/cardTypes";

const PANEL_CONFIG: AitoPanelConfig = {
  operation: "predictions(col) per row",
  stats: [
    { value: "240", label: "installs scored" },
    { value: "0", label: "labels seen" },
    { value: "1", label: "SQL statement" },
  ],
  description:
    "One statement scores every install whose outcome was withheld. Run it without the " +
    "<code>WHERE</code> and every row comes back at p&nbsp;=&nbsp;0.9808 &mdash; not because the " +
    "engine reads the target back (it holds that out), but because <code>reordered</code> is a " +
    "perfect complement sitting on the same row.",
  query:
    "SELECT install_id,\n" +
    "       predictions(churned)\n" +
    "  FROM analysis\n" +
    " WHERE churned IS NULL;",
  links: [
    { label: "Aito SQL guide", url: "https://aito.ai/docs/api/sql/guide" },
    { label: "This demo on GitHub", url: "https://github.com/AitoDotAI/aito-sql-demo" },
  ],
};

/** Predicted vs actual for one probability band, as a dumbbell.
 *
 *  Two states of the same measure per item is the dumbbell's case, and the
 *  distance IS the finding here — the bars would make five pairs the reader
 *  has to subtract by eye. The axis is fixed 0–100% so a band that is badly
 *  off looks badly off, rather than being rescaled into looking fine. */
function CalibrationRow({ b }: { b: ScoringBand }) {
  const lo = Math.min(b.predicted, b.actual);
  const hi = Math.max(b.predicted, b.actual);
  const over = b.predicted > b.actual;
  return (
    <tr>
      <th scope="row">
        <span className="cal-band">{b.lo}–{b.hi}%</span>
        <span className="cal-n">n={b.n}</span>
      </th>
      <td>
        <div className="db" role="img"
             aria-label={`predicted ${b.predicted}%, actually churned ${b.actual}%`}>
          <div className="db-axis" />
          <div className="db-conn" style={{ left: `${lo}%`, width: `${hi - lo}%` }} />
          <div className="db-dot db-from" style={{ left: `${b.predicted}%` }} />
          <div className="db-dot db-to" style={{ left: `${b.actual}%` }} />
        </div>
      </td>
      <td className="cal-nums">
        <span className="cal-pred">{b.predicted}%</span>
        <span className="cal-arrow" aria-hidden="true">→</span>
        <span className="cal-act">{b.actual}%</span>
        <span className={`cal-gap ${over ? "cal-over" : "cal-under"}`}>
          {over ? "over" : "under"} by {Math.abs(b.predicted - b.actual).toFixed(1)}pp
        </span>
      </td>
    </tr>
  );
}

function SampleTable({ rows }: { rows: ScoringSample[] }) {
  return (
    <div className="map-table-wrap">
      <table className="map-table sc-table">
        <thead>
          <tr>
            <th>install</th><th>climate</th><th>cooling</th><th>grade</th>
            <th>thermal fault</th><th className="num">P(churn)</th>
            <th>actually</th><th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.install_id}>
              <td className="mono">{r.install_id}</td>
              <td>{r.climate}</td>
              <td>{r.cooling}</td>
              <td>{r.grade}</td>
              <td>{r.had_thermal_fault}</td>
              <td className="num sc-p">{r.p_churn}%</td>
              <td className={r.actual === "true" ? "sc-churned" : "sc-kept"}>
                {r.actual === "true" ? "churned" : "stayed"}
              </td>
              <td className={r.correct ? "sc-ok" : "sc-miss"}>
                {r.correct ? "✓" : "✗"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ScoringPage() {
  const [data, setData] = useState<Scoring | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    apiFetch<Scoring>("/api/scoring")
      .then(setData)
      .catch((e) => setError(e?.message || "Could not reach the API"));
  }, []);

  useEffect(load, [load]);

  const beatsBase = data ? data.accuracy > data.base_accuracy : false;

  return (
    <div className="app">
      <Nav sections={NAV_SECTIONS} />
      <div className="main">
        <TopBar
          brand="predictive SQL"
          live
          breadcrumb="Check the working"
          title="Does it actually work?"
          subtitle="scored on installs whose outcome was withheld"
        />
        <div className="content">
          {error && <ErrorState message={error} onRetry={load} />}

          {!error && (
            <>
              <div className="lede">
                <h2>One statement, on rows whose outcome was withheld.</h2>
                <p>
                  Everything else on this site asks about a <em>group</em>. This asks about a{" "}
                  <strong>row</strong>{" "}— the form people mean when they say &ldquo;predict&rdquo;,
                  and the one that is easiest to fake. The generator withholds the outcome on 8% of
                  installs and parks the truth in a separate table; the query below cannot see it.
                </p>
              </div>

              <pre className="sc-hero-sql">
{`SELECT install_id, predictions(churned)
  FROM analysis
 WHERE `}<span className="sc-hl">churned IS NULL</span>{`;`}
              </pre>
              <p className="sc-hero-note">
                Drop that <code>WHERE</code> and every prediction comes back agreeing with the
                label at <code>p&nbsp;=&nbsp;0.9808</code> &mdash; the <em>same</em>{" "}number for
                every row, whatever its climate, cooling or grade. That is a lookup wearing a
                model&rsquo;s clothes, and it is what this page showed until someone checked.
                The cause is worth naming precisely, because we first got it wrong: the engine
                does <strong>not</strong> read the target&rsquo;s own value back &mdash; it holds{" "}
                <code>churned</code> out when predicting <code>churned</code>. The leak was{" "}
                <code>reordered</code>, a perfect complement sitting on the same row, which is why
                the generator blanks both.
              </p>

              {!data && <div className="card-loading">scoring…</div>}

              {data && data.n > 0 && (
                <>
                  <SampleTable rows={data.sample} />
                  <p className="sc-caption">
                    Eight of {data.n} scored installs. {data.churned} of them really did churn
                    ({data.churn_rate}%).
                  </p>

                  <section className="sc-score">
                    <h3 className="ex-h">The scorecard, including the part that looks bad</h3>
                    <div className="sc-grid">
                      <div className={`sc-stat ${beatsBase ? "" : "sc-stat-bad"}`}>
                        <span className="sc-v">{data.accuracy}%</span>
                        <span className="sc-l">accuracy</span>
                        <span className="sc-sub">
                          against an {data.base_accuracy}% base rate
                        </span>
                      </div>
                      <div className="sc-stat sc-stat-good">
                        <span className="sc-v">×{data.decile_lift}</span>
                        <span className="sc-l">top-decile lift</span>
                        <span className="sc-sub">
                          {data.decile_hits} of the {data.decile_n} riskiest churned
                          ({data.decile_rate}%)
                        </span>
                      </div>
                      <div className="sc-stat sc-stat-good">
                        <span className="sc-v">{data.auc}</span>
                        <span className="sc-l">AUC</span>
                        <span className="sc-sub">0.5 is a coin toss, 1.0 is perfect</span>
                      </div>
                    </div>

                    <p className={`sc-verdict ${beatsBase ? "" : "sc-verdict-bad"}`}>
                      <strong>
                        Accuracy is {beatsBase ? "above" : "below"} the base rate, and we are
                        printing it anyway.
                      </strong>{" "}
                      With churn at {data.churn_rate}%, a model that says &ldquo;nobody
                      churns&rdquo; scores {data.base_accuracy}%. Thresholding at 0.5 scores{" "}
                      {data.accuracy}%, which is worse. Accuracy is simply the wrong question for
                      an imbalanced outcome — and it is the number a demo would normally quietly
                      drop. What the engine <em>does</em> do is <strong>rank</strong>: work down
                      the riskiest decile and you find churn at {data.decile_rate}% against{" "}
                      {data.churn_rate}% overall. That is ×{data.decile_lift}, and it is what a
                      retention team actually uses, because nobody calls a threshold — they call a
                      list.
                    </p>
                  </section>

                  {(data.warnings?.length || data.evaluate) && (
                    <section className="sc-warn">
                      <h3 className="ex-h">What the engine says about this number</h3>
                      {data.warnings?.map((w, i) => (
                        <div className="sc-warn-box" key={i}>
                          <code className="sc-warn-code">{w.code}</code>
                          <p>{w.message}</p>
                        </div>
                      ))}
                      <p className="sc-warn-note">
                        It is right, and it is worth stating plainly rather than burying: the
                        withheld installs are still <em>in</em> <code>analysis</code>. Their
                        outcome is gone, but their other columns still count toward the
                        co-occurrence statistics every prediction is read from &mdash; so the
                        scorecard above is <strong>optimistic</strong>. A demo page is exactly
                        where that gets swallowed, so here is the unbiased version instead.
                      </p>
                      {data.evaluate && (
                        <>
                          <div className="sc-ev">
                            <div className="sc-ev-cell">
                              <span className="sc-ev-v">{data.evaluate.accuracy}%</span>
                              <span className="sc-ev-l">accuracy, held out properly</span>
                            </div>
                            <div className="sc-ev-cell">
                              <span className="sc-ev-v">{data.evaluate.base_accuracy}%</span>
                              <span className="sc-ev-l">base rate</span>
                            </div>
                            <div className="sc-ev-cell">
                              <span className={`sc-ev-v ${data.evaluate.gain < 0 ? "sc-ev-neg" : ""}`}>
                                {data.evaluate.gain > 0 ? "+" : ""}{data.evaluate.gain}pp
                              </span>
                              <span className="sc-ev-l">gain over base</span>
                            </div>
                            <div className="sc-ev-cell">
                              <span className="sc-ev-v">{data.evaluate.test}</span>
                              <span className="sc-ev-l">test rows, {data.evaluate.train} train</span>
                            </div>
                          </div>
                          <pre className="sc-ev-sql">{data.sql.evaluate}</pre>
                          <p className="sc-warn-note">
                            <code>evaluate()</code>{" "}splits train from test for real &mdash; the test
                            rows are held out of the <em>population</em>, not just of their own
                            prediction. It reaches the same verdict by a cleaner route:{" "}
                            <strong>the model does not beat the base rate</strong>. Both numbers are
                            here because they disagree in the third significant figure and agree on
                            everything that matters, and because the one to trust is this one.
                          </p>
                        </>
                      )}
                    </section>
                  )}

                  <section className="sc-cal">
                    <h3 className="ex-h">Is the probability honest?</h3>
                    <p className="ex-sub">
                      Installs grouped by what the engine predicted, against how many really
                      churned. Where the two dots meet, the probability means what it says.
                    </p>
                    <table className="cal-table">
                      <caption className="sr-only">
                        Predicted churn probability against observed churn rate, by band
                      </caption>
                      <tbody>
                        {data.bands.map((b) => <CalibrationRow key={b.lo} b={b} />)}
                        {/* Ticks live in the table so they line up with the
                            track itself rather than with the section. */}
                        <tr className="cal-scale-row" aria-hidden="true">
                          <td />
                          <td>
                            <div className="cal-scale">
                              <span>0%</span><span>25%</span><span>50%</span>
                              <span>75%</span><span>100%</span>
                            </div>
                          </td>
                          <td />
                        </tr>
                      </tbody>
                    </table>
                    <div className="db-legend">
                      <span className="db-key">
                        <span className="db-swatch db-from" /> predicted
                      </span>
                      <span className="db-key">
                        <span className="db-swatch db-to" /> actually churned
                      </span>
                    </div>
                    <p className="sc-caption">
                      The low bands hold up. The confident end does not: installs called ~80%
                      churn at about half that. The ranking is trustworthy well before the
                      absolute number is, which is the ordinary shape of a model on thin evidence
                      and not something this page is going to tune away.
                    </p>
                  </section>

                  <section className="honesty">
                    <h3>How this is set up</h3>
                    <ul>
                      <li>
                        <strong>The held-out rows are in the same table &mdash; which is both
                        the point and the limitation.</strong> They sit in <code>analysis</code>{" "}
                        with every feature and no outcome, exactly the shape of an install
                        commissioned this morning. But they are still in the population the
                        prediction is read from, so the scorecard flatters itself; that is what the
                        engine&rsquo;s warning above says, and why <code>evaluate()</code> is shown
                        beside it.
                      </li>
                      <li>
                        <strong>Both spellings of the label were blanked.</strong>{" "}
                        <code>reordered</code> is <code>churned</code>&rsquo;s complement, so
                        leaving it would have handed over the answer through the back door and
                        this page would be showing 100%.
                      </li>
                      <li>
                        <strong>Nothing was retrained.</strong>{" "}The withheld rows were never
                        &ldquo;learned&rdquo;; they are scored by the same statements the rest of
                        the site runs, against the same table.
                      </li>
                      <li>
                        <strong>240 rows is a small holdout.</strong> At this size the accuracy
                        figure carries roughly ±5 points, so read the ranking metrics before the
                        point estimates. The fraction is set in{" "}
                        <code>src/generate.py</code> (<code>HOLDOUT_FRACTION</code>).
                      </li>
                      <li>
                        <strong>This took {(data.ms / 1000).toFixed(1)}s to compute</strong> — per-row
                        inference, unlike the aggregate queries behind{" "}
                        <Link href="/">the cards</Link>, which answer in ~45ms. It is cached at
                        startup rather than run while you wait.
                      </li>
                    </ul>
                  </section>
                </>
              )}

              {data && data.n === 0 && (
                <ErrorState
                  message="No held-out rows found — the database predates the holdout cohort. Re-run `python -m src.generate` and `python -m src.load --drop`."
                  onRetry={load}
                />
              )}
            </>
          )}
        </div>
      </div>
      <AitoPanel config={PANEL_CONFIG} />
    </div>
  );
}
