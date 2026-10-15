export type Locale = "tr" | "en";
export type Section = "overview" | "analysis" | "network" | "findings";
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
  preview: Record<string, string | number>[];
  metrics: { id: string; title: string; formula: string; note: string }[];
  graph: GraphData;
  answer: null | { status: string; text: string; reason: string; mode: string };
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
  };
  summary: AnalysisResult["summary"];
}
