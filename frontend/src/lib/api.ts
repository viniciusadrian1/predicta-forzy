import { useAuth } from "@/lib/auth";
import type { Asset, AuthToken, LatestSnapshot, TelemetrySeries } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = process.env.NEXT_PUBLIC_API_V1_PREFIX ?? "/api/v1";

function apiUrl(path: string): string {
  return `${BASE_URL}${API_PREFIX}${path}`;
}

function authHeaders(): Record<string, string> {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // resposta sem corpo JSON
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function login(username: string, password: string): Promise<AuthToken> {
  const response = await fetch(apiUrl("/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return parse<AuthToken>(response);
}

export async function getAssets(): Promise<Asset[]> {
  return parse<Asset[]>(await fetch(apiUrl("/assets"), { cache: "no-store" }));
}

export async function getAsset(tag: string): Promise<Asset> {
  return parse<Asset>(
    await fetch(apiUrl(`/assets/${encodeURIComponent(tag)}`), { cache: "no-store" }),
  );
}

export interface CreateAssetInput {
  tag: string;
  name?: string;
  asset_type?: string;
  manufacturer?: string;
  model?: string;
}

export async function createAsset(input: CreateAssetInput): Promise<Asset> {
  const response = await fetch(apiUrl("/assets"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  return parse<Asset>(response);
}

export async function getTelemetry(
  tag: string,
  variable: string,
  limit = 600,
): Promise<TelemetrySeries> {
  const params = new URLSearchParams({ tag, variable, limit: String(limit) });
  return parse<TelemetrySeries>(
    await fetch(apiUrl(`/telemetry?${params.toString()}`), { cache: "no-store" }),
  );
}

export async function getLatest(tag: string): Promise<LatestSnapshot> {
  return parse<LatestSnapshot>(
    await fetch(apiUrl(`/telemetry/${encodeURIComponent(tag)}/latest`), {
      cache: "no-store",
    }),
  );
}
