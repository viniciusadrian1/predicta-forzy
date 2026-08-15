// Tipos compartilhados, espelhando os schemas da API.

export interface Asset {
  id: string;
  tag: string;
  asset_type: string;
  name: string | null;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  power_kw: number | null;
  voltage_v: number | null;
  nominal_current_a: number | null;
  nominal_rpm: number | null;
  connection_type: string | null;
  insulation_class: string | null;
  ip_rating: string | null;
  weight_kg: number | null;
  manufacture_date: string | null;
  plant_id: string | null;
  area_id: string | null;
  position_x: number | null;
  position_y: number | null;
  datasheet_url: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Plant {
  id: string;
  name: string;
  code: string;
  location: string | null;
  created_at: string;
  updated_at: string;
}

export interface TelemetryPoint {
  time: string;
  variable: string;
  value: number;
  unit: string;
  quality: number;
}

export interface TelemetrySeries {
  asset_tag: string;
  variable: string | null;
  count: number;
  points: TelemetryPoint[];
}

export interface LatestReading {
  variable: string;
  value: number;
  unit: string;
  quality: number;
  time: string;
}

export interface LatestSnapshot {
  asset_tag: string;
  readings: LatestReading[];
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  username: string;
  role: string;
}

export type AssetStatus = "ok" | "warning" | "critical" | "unknown";

// --- Hierarquia ---
export interface HierarchyAsset {
  id: string;
  tag: string;
  name: string | null;
  asset_type: string;
  status: string;
}

export interface HierarchyArea {
  id: string;
  name: string;
  code: string;
  assets: HierarchyAsset[];
}

export interface HierarchyPlant {
  id: string;
  name: string;
  code: string;
  areas: HierarchyArea[];
}

// --- Visao / OCR ---
export interface NameplateField {
  field: string;
  label: string;
  value: string | null;
  confidence: number;
}

export interface NameplateExtraction {
  filename: string | null;
  size_bytes: number;
  engine: string;
  raw_text: string;
  coverage: number;
  fields: NameplateField[];
  note: string;
}

// --- Automacao (RPA) ---
export interface AssetDraft {
  tag: string | null;
  manufacturer: string | null;
  model: string | null;
  power_kw: number | null;
  voltage_v: number | null;
  nominal_current_a: number | null;
  nominal_rpm: number | null;
  ip_rating: string | null;
  insulation_class: string | null;
}

export interface RpaResult {
  ocr_engine: string;
  ocr_coverage: number;
  fields: NameplateField[];
  draft: AssetDraft;
  duplicate: boolean;
  created: boolean;
  message: string;
}

// --- Machine Learning ---
export interface BaselinePrediction {
  ready: boolean;
  available: boolean;
  asset_tag: string | null;
  score: number | null;
  decision: string | null;
  model_version: string | null;
}

export interface AnomalyPrediction {
  ready: boolean;
  available: boolean;
  asset_tag: string | null;
  reconstruction_error: number | null;
  threshold: number | null;
  is_anomaly: boolean | null;
  model_version: string | null;
}

export interface RulEstimate {
  ready: boolean;
  available: boolean;
  asset_tag: string | null;
  rul_days: number | null;
  confidence_low_days: number | null;
  confidence_high_days: number | null;
  current_vibration: number | null;
  trend_mm_s_per_day: number | null;
  model_version: string | null;
  note: string | null;
}

// --- Alertas ---
export interface Alert {
  id: string;
  asset_tag: string;
  severity: string;
  alert_type: string;
  message: string;
  ml_score: number | null;
  created_at: string;
  acknowledged: boolean;
  ack_by: string | null;
  ack_at: string | null;
  ack_comment: string | null;
}

// --- RAG / Chat de troubleshooting ---
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatSource {
  document_id: string;
  document_title: string;
  snippet: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  mode: "anthropic" | "offline";
  sources: ChatSource[];
  asset_tag: string | null;
  used_asset_context: boolean;
}

export interface RagStatus {
  ready: boolean;
  indexed_chunks: number;
  documents: number;
  vector_backend: string;
  llm_mode: "anthropic" | "offline";
  embedding_dim: number;
}

// --- Governança / Administração ---
export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  method: string | null;
  path: string | null;
  status_code: number | null;
  ip_address: string | null;
}

export interface AccessRule {
  resource: string;
  methods: string[];
  min_role: string;
  description: string;
}

export interface AccessPolicy {
  roles: string[];
  rbac_enabled: boolean;
  rules: AccessRule[];
}

export interface DataAssetEntry {
  dataset: string;
  origin: string;
  classification: string;
  storage: string;
  retention: string;
  notes: string;
}

export interface DataLineage {
  document: string;
  classification_levels: string[];
  datasets: DataAssetEntry[];
}

export interface UserAccount {
  id: string;
  username: string;
  role: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface MlStatus {
  ready: boolean;
  model_version: string | null;
  trained_at: string | null;
  n_samples: number | null;
}
