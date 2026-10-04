export type Lang = "bn" | "hi" | "en";
export type Verdict = "OK" | "CAREFUL" | "NOT_OK" | "UNCHECKED";
export type Box = [number, number, number, number];

export interface Quality {
  blur_score: number;
  brightness: number;
  width: number;
  height: number;
  issues: string[];
  retake: boolean;
}

export interface SessionView {
  session_id: string;
  quality: Quality | null;
  ocr: { mean_conf?: number | null; n_lines?: number; deskew_deg?: number; source?: string; user_corrected?: boolean };
  image: { width: number; height: number } | null;
  lines: { id: number; text: string; conf: number | null; low_conf: boolean }[];
  clauses: { id: number; label: string; text: string; box: Box | null; low_conf: boolean; categories: string[]; selected: boolean }[];
  pii_counts: Record<string, number>;
}

export interface RuleView {
  id: string;
  name: string;
  plain: string;
  severity: Verdict;
}

export interface StatuteView {
  id: string;
  name: string;
  plain_summary: string;
  source_url: string;
  source_hint?: string;
  last_verified: string | null;
  verified_by?: string | null;
}

export interface Card {
  pending?: boolean;
  clause_id: number;
  label: string;
  original_text: string;
  box: Box | null;
  line_boxes: Box[];
  low_conf: boolean;
  conf: number | null;
  categories: string[];
  verdict: Verdict;
  verdict_source?: string;
  rule_ids: string[];
  rule_ids_from_code?: string[];
  rules: RuleView[];
  statutes: StatuteView[];
  category?: string;
  reason_en?: string;
  fair_rewrite_en?: string;
  riders_en?: string[];
  thinking?: string | null;
  engine?: string;
  loc_engine?: string;
  plain_explanation?: string;
  why_it_matters?: string;
  questions_to_ask?: string[];
  ask_to_change?: string;
}

export interface Step {
  key: string;
  text: string;
  values: Record<string, number | string>;
}

export interface Money {
  principal: number;
  upfront_fees: number;
  cash_in_hand: number;
  installment: number;
  num_installments: number;
  frequency: string;
  balloon: number;
  total_repayment: number;
  extra_cost: number;
  periodic_rate_pct: number;
  apr_pct: number;
  effective_annual_pct: number;
  stated_rate_pct: number | null;
  stated_rate_period: string | null;
  stated_annual_pct: number | null;
  installment_source: string;
  steps: Step[];
  warnings: string[];
}

export interface Terms {
  doc_type: string;
  principal: number | null;
  upfront_fees: number | null;
  upfront_fee_pct: number | null;
  installment: number | null;
  num_installments: number | null;
  frequency: string | null;
  balloon: number | null;
  stated_rate_pct: number | null;
  stated_rate_period: string | null;
  rate_type: string;
  monthly_rent: number | null;
  security_deposit: number | null;
  apr_disclosed: boolean;
}

export interface DocHit extends RuleView {
  detail: Record<string, number>;
  statutes: StatuteView[];
  questions: string[];
  rider_en: string;
  ask_to_change: string;
  attached: boolean;
}

export interface Result {
  session_id: string;
  lang: Lang;
  engine: "gemma" | "fallback";
  image: { width: number; height: number } | null;
  cards: Card[];
  money: Money | null;
  money_error: string | null;
  terms: Terms | null;
  terms_source: string | null;
  doc_hits: DocHit[];
  summary: { question: string; clause_id: number | null }[];
  help: { id: string; name: string; contact: string; source_url: string; last_verified: string | null }[];
  timings: Record<string, number>;
}

export type StreamEvent =
  | { type: "start"; engine: string; model: string }
  | { type: "progress"; stage: string; i: number; n: number; label: string }
  | { type: "clause"; clause_id: number; verdict: Verdict }
  | { type: "partial"; result: Result }
  | { type: "done"; result: Result }
  | { type: "error"; message: string };
