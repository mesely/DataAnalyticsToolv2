export type Locale = "tr" | "en";
export type Section = "overview" | "chart" | "decision" | "findings";
/** Tabs inside the two studios (v3 G8). */
export type ChartTab = "chart" | "network" | "temporal" | "sql";
export type DecisionTab = "ask" | "brief" | "model";
export interface Dataset {
  id: string;
  title: string;
  rows: number;
  orders: number;
  products: number;
  columns: number;
  countries: string[];
  start: string;
  end: string;
  sha256: string;
  currency: string;
  definition: string;
  quality: Record<string, number>;
  schema: { name: string; type: string; nullable: boolean }[];
  source: {
    kind: string;
    publisher: string;
    url?: string;
    license: string;
    description?: string;
  };
}
export interface Filters {
  start?: string;
  end?: string;
  country?: string;
  /** v3 AW-21: metric definition; absent = retail-v1 (every positive, non-cancelled line). */
  definition?: "retail-v1" | "retail-v2";
}
export interface GraphNode {
  id: string;
  label: string;
  pence: number;
  orders: number;
  degree: number;
  brokerage: number;
  community: number;
  x: number;
  y: number;
}
export interface GraphData {
  nodes: GraphNode[];
  edges: { source: string; target: string; weight: number }[];
  mode: string;
  note: string;
  communities: number;
  components: number;
  source_method: string;
  include_service?: boolean;
}
/** v3 G2: an answer about the relationship network (analysis/network_qa.py). */
export interface NetworkAnswer {
  question: string;
  plan: { query: string; k: number; product: string | null; month: string | null };
  planner: "local" | "model";
  status: "answered" | "refused";
  answer: string;
  highlight: { nodes: string[]; edges: [string, string][] };
  routing?: RoutingReceipt;
}
/** v3 G6: which planner ran for a task and why (analysis/llm_routing.py `receipt`). */
export interface RoutingReceipt {
  task: string;
  method: "local" | "model" | "local_then_model";
  used: "local" | "model";
  why?: string | null;
  local_accuracy?: number | null;
  model_accuracy?: number | null;
  n?: number | null;
  measured_at?: string | null;
  unavailable?: string;
  fallback?: string | null;
}
/** v3 G5: what gross sales leaves out, what product views leave out, and how complete the edge months are. */
export interface ScopeInfo {
  include_service: boolean;
  service: {
    lines: number;
    pence: number;
    groups: { kind: string; label: string; lines: number; pence: number; codes: { code: string; label: string; lines: number; pence: number }[] }[];
  };
  exclusions: { reason: string; rows: number; pence: number }[] | null;
  raw_rows?: number;
  excluded_rows?: number;
  periods: { edge: "first" | "last" | "only"; month: string; date: string; covered_days: number; month_days: number; partial: boolean }[];
  /** v3 AW-21: the active definition and how the totals relate inside the current filters. */
  definition?: "retail-v1" | "retail-v2";
  reconciliation?: {
    retail_v1: { lines: number; pence: number };
    retail_v2: { lines: number; pence: number };
    merchandise: { lines: number; pence: number };
    kinds: Record<string, { lines: number; pence: number }>;
    v2_excluded_kinds: string[];
  };
}
export interface AnalysisResult {
  run_id: string;
  dataset: Dataset;
  filters: Filters;
  summary: {
    rows: number;
    orders: number;
    units: number;
    gross_pence: number;
    gross_sales: number;
    aov: number;
    products: number;
  };
  series: { period: string; pence: number; orders: number }[];
  countries: { label: string; pence: number; orders: number }[];
  products: {
    product_id: string;
    label: string;
    pence: number;
    units: number;
  }[];
  scope?: ScopeInfo;
  preview: Record<string, string | number>[];
  metrics: { id: string; title: string; formula: string; note: string }[];
  graph: GraphData;
  answer: null | {
    status: string;
    text: string;
    reason: string;
    mode: string;
    /** AW-24 pipeline: the decided intent and how it was decided. */
    intent?: string;
    pipeline?: { version: string; intent: string; intent_method?: string; intent_used?: string; confidence?: number; definition?: string; fallback?: string };
    /** knowledge and limitation answers: the context cards quoted (analysis/knowledge/context-cards.json). */
    citations?: { id: string; title: string; source?: string }[];
    network?: { highlight: { nodes: string[]; edges: string[][] } };
  };
  evidence: {
    recipe_version: string;
    dataset_sha256: string;
    output_sha256: string;
    metric_version: string;
    currency: string;
    sql: string;
    parameters: unknown[];
    duration_ms: number;
    policy: string;
  };
  planner?: { status: string; intent?: string; http_status?: number; error_code?: string };
  routing?: RoutingReceipt;
  provider: { connected: boolean; note: string; model?: string };
}
export interface SavedRun {
  run_id: string;
  title: string;
  saved: boolean;
  archived_at?: string | null;
  created_at: string;
  recipe: {
    dataset: string;
    filters: Filters;
    question: string;
    graph_mode: string;
    min_shared: number;
    include_service?: boolean;
  };
  summary: AnalysisResult["summary"];
}

/** AW-16 Chart Studio contract (specs/analyst-workspace-phase12.md §2). */
export interface ChartSpec {
  version: 1;
  metric: "gross_sales" | "orders" | "units" | "aov";
  dimension: "month" | "week" | "weekday" | "country" | "product" | "country_group";
  chart: "line" | "area" | "bar";
  /** v3 AW-19 (additive): reference group and membership date of a country_group chart. */
  group?: "nato" | "eu" | "eurozone" | "g7" | "oecd" | "continent";
  group_as_of?: "transaction" | "period_end" | "today";
  start?: string | null;
  end?: string | null;
  countries: string[];
  /** AW-16 amendment A1 (additive): catalog countries left out of the chart. */
  exclude_countries?: string[];
  split_by_country: boolean;
  top_n: number;
  statistic: "none" | "ci95" | "moving_average" | "trend" | "control_band";
  window: number;
  sort: "natural" | "value_desc" | "value_asc";
  /** v3 AW-20 (additive): money transform — currency at the order's date, constant prices, gold, index. */
  transform?: ChartTransform;
}
export interface ChartTransform {
  currency: "GBP" | "TRY" | "USD" | "EUR";
  fx: "transaction" | "latest";
  real: string | null;
  unit: "money" | "gold_g" | "gold_oz";
  index: boolean;
  compare: boolean;
}
export type ChartUnit = "GBP" | "TRY" | "USD" | "EUR" | "g" | "oz" | "index" | "count";
export interface ChartPoint {
  x: string;
  series?: string | null;
  value: number;
  lower?: number | null;
  upper?: number | null;
  n?: number | null;
  partial?: boolean;
  /** country_group charts: the bucket's part of the scope (0–1). */
  share?: number | null;
  /** transformed charts: the same row in GBP, before the transform. */
  gbp?: number | null;
}
export interface ChartResult {
  spec: ChartSpec;
  planner: {
    source: "model" | "local";
    status: string;
    changes: { field: string; from: unknown; to: unknown }[];
    note?: string;
    suggestions?: string[];
    routing?: RoutingReceipt;
  };
  title: string;
  subtitle: string;
  unit: ChartUnit;
  data: ChartPoint[];
  overlays: {
    moving_average?: { window: number; points: { x: string; value: number; series: string }[] };
    trend?: { slope: number; intercept: number; r2: number; p_value: number; n: number; line: { x: string; value: number }[] };
    control?: { mean: number; sd: number; lower: number; upper: number; n: number; outside: string[] };
  };
  statements: { type: "fact" | "calculation" | "inference" | "limitation"; text: string; evidence?: string[] }[];
  sql: string;
  params: unknown[];
  warnings: string[];
  output_sha256: string;
  /** country_group charts: which country fell in which bucket, at which date, from which reference table. */
  groups?: {
    group: string;
    label: string;
    as_of: string;
    as_of_rule: "transaction" | "period_end" | "today";
    card: { source: string; version: string; sha256: string };
    countries: {
      country: string;
      display: string;
      bucket: string;
      bucket_label: string;
      iso3: string | null;
      note: string | null;
      pence: number;
      /** AW-22: membership ranges inside the period when it is read on each order's date. */
      spans?: { bucket: string; bucket_label: string; from: string; to: string }[];
    }[];
  };
  /** transformed charts: every reference value used, with its source (analysis/transforms.py). */
  transform?: {
    label: string;
    text: string;
    currency: string;
    fx: string;
    base_month: string | null;
    days_carried_forward?: number;
    rate?: { quote: string; per: string; min: number; max: number; mean: number };
    cpi?: { area: string; base_month: string; base_value: number; base_rule: string };
    gold?: { unit: string; min: number; max: number };
    sources: { id: string; title: string; publisher: string; url: string; licence: string; retrieved_at: string; sha256: string; series: string[]; version: string }[];
  };
}
/** AW-16 developer code export (§1). */
export interface CodeExportResult {
  format: "bundle" | "python" | "sql";
  filename: string;
  content_type: string;
  base64: string;
  bytes: number;
  sha256: string;
  data_included: boolean;
  files: { path: string; bytes: number; sha256: string }[];
  preview: Partial<Record<"README.md" | "analysis.py" | "analysis.sql", string>>;
}
