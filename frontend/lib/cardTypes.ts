export interface Cause {
  field: string;
  value: string;
  lift: number | null;
  info: number | null;
  n: number | null;
  /** churn rate WITHIN this group, as a percentage */
  rate: number | null;
  /** the book-wide rate, for comparison */
  base_rate: number | null;
}

export interface Lever {
  value: string;
  /** P(good outcome), as a percentage */
  p_good: number | null;
  /** the complement — what the card actually talks about */
  churn: number | null;
  why?: unknown;
}

export interface CardSql {
  kpi: string;
  causes: string;
  levers: string;
  baseline: string;
  conditioned: string | null;
}

export interface CardSummary {
  key: string;
  title: string;
  unit: string;
  question: string;
  note: string;
  /** which planted mechanism this card recovers: M1..M4, NEG, or "lever" */
  mechanism: string;
  rank: number;
  churn: number | null;
  base_churn: number | null;
  lift: number | null;
  sql: CardSql;
  ms: number;
}

export interface CardDetail extends CardSummary {
  causes: Cause[];
  levers: Lever[];
  conditioned?: Cause[];
  conditioned_label?: string;
}

export interface Overview {
  counts: Record<string, number | null>;
  base_churn: number | null;
  aito_url: string;
  sql: Record<string, string>;
}

export interface SqlRunResult {
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  ms: number;
}
