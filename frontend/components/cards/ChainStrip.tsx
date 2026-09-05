"use client";

import type { Overview } from "@/lib/cardTypes";

/** The customer journey as one row. Five systems that are usually five
 *  databases, here as one schema — which is the reason the causes are one
 *  query away rather than one integration project away. */
const STEPS = [
  { label: "campaigns", key: null, glyph: "◎" },
  { label: "sessions", key: null, glyph: "◇" },
  { label: "orders", key: null, glyph: "◈" },
  { label: "installs", key: "installs", glyph: "▣" },
  { label: "tickets", key: "tickets", glyph: "▲" },
  { label: "reorder / churn", key: null, glyph: "●" },
];

export default function ChainStrip({ overview }: { overview: Overview | null }) {
  const base = overview?.base_churn;
  return (
    <div className="chain">
      <div className="chain-steps">
        {STEPS.map((s, i) => (
          <div className="chain-step" key={s.label}>
            <span className="chain-glyph" aria-hidden="true">{s.glyph}</span>
            <span className="chain-label">{s.label}</span>
            {s.key && overview?.counts?.[s.key] != null && (
              <span className="chain-count">
                {overview.counts[s.key]!.toLocaleString()}
              </span>
            )}
            {i < STEPS.length - 1 && <span className="chain-arrow" aria-hidden="true">→</span>}
          </div>
        ))}
      </div>
      <div className="chain-kpi">
        <span className="chain-kpi-label">book-wide churn</span>
        <span className="chain-kpi-value">{base != null ? `${base}%` : "—"}</span>
        <span className="chain-kpi-note">
          every card below is measured against this
        </span>
      </div>
    </div>
  );
}
