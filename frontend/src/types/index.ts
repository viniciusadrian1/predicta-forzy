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
