export type Scalar = string | number | boolean | null;
export interface Recipe {
  [key: string]: Scalar;
  name: string;
  graph_prompt: string;
  summary_prompt: string;
  answer_prompt: string;
  verify_prompt: string;
  pages: string;
  variant: string;
  currency: string;
  graph_enabled: boolean;
  summary_enabled: boolean;
}
export interface Configuration {
  id: string;
  name: string;
  revision: number;
  parent_id: string | null;
  hash: string;
  body: Recipe;
  created_at: string;
}
export interface FormField {
  id: string;
  path: string;
  question: string;
  value_schema: unknown;
}
export interface Dataset {
  id: string;
  revision: number;
  versions: { id: string; revision: number }[];
  source: {
    id: string;
    title: string;
    pages: number;
    sha256: string;
    scope: string;
    kind: string;
  };
  form: { fields: FormField[] };
  cases: {
    field_id: string;
    expected: unknown;
    split: string;
    reference_pages: number[];
  }[];
  reference_status: string;
}
export interface Stage {
  name: string;
  label: string;
  status: string;
  duration_ms: number | null;
  duration_is_partial?: boolean;
  duration_is_running?: boolean;
  history_ms?: number | null;
  source_run?: string;
  model_calls?: number;
  cached_operations?: number;
  api_cost?: number;
  machine_cost_estimate?: number | null;
  input_tokens?: number;
  output_tokens?: number;
  detail?: {
    reason?: string;
    error?: string;
    completed?: number;
    total?: number;
  };
}
export interface Metrics {
  stages: Stage[];
  wall_seconds: number | null;
  wall_seconds_upper_bound?: number | null;
  queue_seconds: number | null;
  total_seconds: number | null;
  api_cost: number;
  total_cost: number | null;
  machine_cost_estimate: number | null;
  currency: string;
  model_calls: number;
  cached_operations: number;
  mcp_calls: number;
  agent_rounds: number;
  input_tokens: number;
  output_tokens: number;
  usage_unknown_calls: number;
  timing_note: string;
}
export interface Citation {
  chunk_id: string;
  quote: string;
  page?: number;
}
export interface Answer {
  id: string;
  path: string;
  question: string;
  status: string;
  value: unknown;
  evidence: Citation[];
  reason: string;
  rounds: {
    round: number;
    query: string;
    retrieved_ids: string[];
    raw_answer?: unknown;
    validation_errors: string[];
    support_check?: unknown;
  }[];
}
export interface Score {
  field_id: string;
  annotated: boolean;
  correct: boolean | null;
  expected?: unknown;
  actual: unknown;
  status: string;
  reference_pages?: number[];
  reference_page_hit?: boolean | null;
}
export interface Evaluation {
  accuracy: number | null;
  coverage: number | null;
  field_count: number;
  annotated_count: number;
  fields: Score[];
  reference_status: string;
  scope_note: string;
}
export interface Run {
  id: string;
  batch_id: string;
  config_id: string;
  corpus_id: string;
  repetition: number;
  status: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  error: string | null;
  cancel_requested: number;
  retry_of: string | null;
  metrics: Metrics;
  request: {
    recipe: Recipe;
    field_ids: string[];
    input_hash: string;
    mode: string;
    split: string;
    form: Dataset["form"];
    source: Dataset["source"];
    cases: Dataset["cases"];
  };
  result: {
    evaluation: Evaluation | null;
    index: {
      index_name: string;
      graph_name: string;
      pages: number;
      chunks: number;
      facts: number;
      rejected_facts: number;
      selected_pages: number[];
    };
  } | null;
  fields?: Answer[];
  output?: unknown;
  events?: unknown[];
  provenance?: {
    implementation_changed_during_run?: boolean;
    [key: string]: unknown;
  } | null;
}
export interface Bootstrap {
  configurations: Configuration[];
  defaults: Recipe;
  datasets: Dataset[];
  models: { name: string; digest: string; capabilities: string[] }[];
  model_error: string | null;
  prototype: false;
}
export interface Plan {
  configuration_count: number;
  run_count: number;
  configurations: { recipe: Recipe; fields: Record<string, string[]> }[];
  notice: string;
}
export interface Comparison {
  reference: Run;
  candidate: Run;
  compatible: boolean;
  differences: Record<string, { reference: unknown; candidate: unknown }>;
  warning: string | null;
}
export interface Fact {
  subject: string;
  predicate: string;
  object: string;
  quote: string;
  chunk_id: string;
  page: number;
  date: string;
  speaker: string;
}
export interface Graph {
  facts: Fact[];
  total: number;
  rejected: number;
  version: string;
  offset: number;
  note?: string;
}
