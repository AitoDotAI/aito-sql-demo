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

export interface MapCell {
  slice: string;
  slice_field: string | null;
  slice_value: string | null;
  field: string;
  value: string;
  lift: number;
  info: number;
  n: number | null;
  /** the same cell's lift over the whole book, for the contrast */
  base_lift: number | null;
  movement: number;
  /** movement x info — the interaction score the table ranks on */
  signal: number;
  /** which of the six cards was written from this cell, if any */
  card?: string | null;
}

export interface MapResult {
  generated_ms: number;
  statements: number;
  cells: number;
  slices: string[];
  explanatory_fields: string[];
  excluded_fields: Record<string, string>;
  outcome: string;
  by_movement: MapCell[];
  by_lift: MapCell[];
  cards: { key: string; title: string; rank: number; mechanism: string }[];
}

export interface ExploreValue {
  value: string;
  n: number;
  /** churn rate within this value, counted from rows */
  rate: number;
  /** lift against the CURRENT slice, not the whole book */
  lift: number | null;
}

export interface ExploreDimension {
  field: string;
  values: ExploreValue[];
  /** widest gap between this field's values, in points */
  spread: number;
  sql: string;
}

export interface ExploreResult {
  facets: { field: string; value: string }[];
  where: string;
  n: number;
  churned_n: number;
  /** counted from the rows */
  observed: number | null;
  /** what predict() says — differs from `observed` when evidence is thin */
  predicted: number | null;
  dimensions: ExploreDimension[];
  lever: string;
  levers: { value: string; churn: number | null }[];
  lever_options: string[];
  sql: Record<string, string>;
}

export interface MinedPattern {
  terms: { field: string; value: string }[];
  n: number;
  /** how much more common this combination is among churned installs */
  lift: number | null;
  where: string;
  group: string;
  table: string;
  /** generated from the terms by grammatical slot, not hand-written */
  sentence: string;
  cases: Record<string, unknown>[];
}

export interface PatternsResult {
  statements: number;
  patterns: MinedPattern[];
  case_columns: string[];
  groups: string[];
}
