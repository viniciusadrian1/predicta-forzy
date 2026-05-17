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
