import { useAuth } from "@/lib/auth";
import type {
  AccessPolicy,
  Alert,
  AnomalyPrediction,
  Asset,
  AuditEntry,
  AuthToken,
  BaselinePrediction,
  ChatMessage,
  ChatSource,
  DataLineage,
  HierarchyPlant,
  LatestSnapshot,
  MlStatus,
  NameplateExtraction,
  Plant,
  RagStatus,
  RpaResult,
  RulEstimate,
  TelemetrySeries,
  UserAccount,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_PREFIX = process.env.NEXT_PUBLIC_API_V1_PREFIX ?? "/api/v1";

export function apiUrl(path: string): string {
  return `${BASE_URL}${API_PREFIX}${path}`;
}

function authHeaders(): Record<string, string> {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Erro de API com o status HTTP — permite distinguir 401/404/500 na UI. */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
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
    // Sessão expirada: derruba o estado local e volta ao login. A condição
    // de token evita loop no próprio login (senha errada também retorna 401).
    if (response.status === 401 && useAuth.getState().token) {
      useAuth.getState().logout();
      window.location.assign("/login?expired=1");
    }
    throw new ApiError(detail, response.status);
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

/** Valida a sessão persistida contra a API (token expirado cai no 401 global). */
export async function getMe(): Promise<{ username: string; role: string }> {
  return parse(
    await fetch(apiUrl("/auth/me"), { headers: authHeaders(), cache: "no-store" }),
  );
}

export interface AssetFilters {
  search?: string;
  status?: string;
  assetType?: string;
}

export async function getAssets(filters: AssetFilters = {}): Promise<Asset[]> {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.status) params.set("status", filters.status);
  if (filters.assetType) params.set("asset_type", filters.assetType);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return parse<Asset[]>(await fetch(apiUrl(`/assets${suffix}`), { cache: "no-store" }));
}

export async function getAsset(tag: string): Promise<Asset> {
  return parse<Asset>(
    await fetch(apiUrl(`/assets/${encodeURIComponent(tag)}`), { cache: "no-store" }),
  );
}

export async function getPlants(): Promise<Plant[]> {
  return parse<Plant[]>(await fetch(apiUrl("/plants"), { cache: "no-store" }));
}

export async function getHierarchy(): Promise<HierarchyPlant[]> {
  return parse<HierarchyPlant[]>(
    await fetch(apiUrl("/hierarchy"), { cache: "no-store" }),
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

export interface TelemetryQuery {
  limit?: number;
  from?: string;
  to?: string;
}

export async function getTelemetry(
  tag: string,
  variable: string,
  query: TelemetryQuery = {},
): Promise<TelemetrySeries> {
  const params = new URLSearchParams({ tag, variable });
  if (query.limit) params.set("limit", String(query.limit));
  if (query.from) params.set("from", query.from);
  if (query.to) params.set("to", query.to);
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

export async function extractFromImage(file: File): Promise<NameplateExtraction> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(apiUrl("/assets/extract-from-image"), {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  return parse<NameplateExtraction>(response);
}

export async function registerFromImage(
  file: File,
  tag: string,
  autoCreate: boolean,
): Promise<RpaResult> {
  const form = new FormData();
  form.append("file", file);
  if (tag) form.append("tag", tag);
  form.append("auto_create", String(autoCreate));
  const response = await fetch(apiUrl("/automation/register-from-image"), {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  return parse<RpaResult>(response);
}

export function smartPdfUrl(plantId: string): string {
  return apiUrl(`/plants/${encodeURIComponent(plantId)}/smart-pdf`);
}

export function telemetryCsvUrl(tag: string, variable?: string): string {
  const suffix = variable ? `?variable=${encodeURIComponent(variable)}` : "";
  return apiUrl(`/telemetry/${encodeURIComponent(tag)}/export${suffix}`);
}

// --- Alertas ---
export async function getAlerts(
  params: { tag?: string; severity?: string; onlyActive?: boolean } = {},
): Promise<Alert[]> {
  const query = new URLSearchParams();
  if (params.tag) query.set("tag", params.tag);
  if (params.severity) query.set("severity", params.severity);
  if (params.onlyActive) query.set("only_active", "true");
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return parse<Alert[]>(await fetch(apiUrl(`/alerts${suffix}`), { cache: "no-store" }));
}

export async function acknowledgeAlert(id: string, comment: string): Promise<Alert> {
  const response = await fetch(apiUrl(`/alerts/${id}/ack`), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ comment: comment || null }),
  });
  return parse<Alert>(response);
}

// --- Machine Learning ---
export async function predictBaseline(tag: string): Promise<BaselinePrediction> {
  const response = await fetch(apiUrl("/ml/baseline/predict"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_tag: tag }),
  });
  return parse<BaselinePrediction>(response);
}

export async function predictAnomaly(tag: string): Promise<AnomalyPrediction> {
  const response = await fetch(apiUrl("/ml/anomaly/predict"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_tag: tag }),
  });
  return parse<AnomalyPrediction>(response);
}

export async function getRul(tag: string): Promise<RulEstimate> {
  return parse<RulEstimate>(
    await fetch(apiUrl(`/ml/rul/${encodeURIComponent(tag)}`), { cache: "no-store" }),
  );
}

export interface MlFeedbackInput {
  asset_tag: string;
  model: string;
  prediction: string;
  is_correct: boolean;
  comment?: string;
}

export async function sendMlFeedback(
  input: MlFeedbackInput,
): Promise<{ recorded: boolean; message: string }> {
  const response = await fetch(apiUrl("/ml/feedback"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  return parse<{ recorded: boolean; message: string }>(response);
}

// --- RAG / Chat de troubleshooting ---
export async function getRagStatus(): Promise<RagStatus> {
  return parse<RagStatus>(await fetch(apiUrl("/rag/status"), { cache: "no-store" }));
}

export interface ChatStreamHandlers {
  onSources?: (sources: ChatSource[], mode: string, usedAssetContext: boolean) => void;
  onToken?: (text: string) => void;
  onDone?: (answer: string, mode: string) => void;
}

export interface ChatStreamInput {
  message: string;
  assetTag?: string | null;
  history?: ChatMessage[];
}

/**
 * Consome o endpoint SSE de chat (POST /rag/chat/stream), repassando os
 * eventos `sources`, `token` e `done` para os handlers fornecidos.
 */
export async function streamChat(
  input: ChatStreamInput,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const response = await fetch(apiUrl("/rag/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      message: input.message,
      asset_tag: input.assetTag ?? null,
      history: input.history ?? [],
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error("Falha ao conectar com o assistente");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const payload = JSON.parse(data) as Record<string, unknown>;
      if (event === "sources") {
        handlers.onSources?.(
          (payload.sources as ChatSource[]) ?? [],
          String(payload.mode ?? "offline"),
          Boolean(payload.used_asset_context),
        );
      } else if (event === "token") {
        handlers.onToken?.(String(payload.text ?? ""));
      } else if (event === "done") {
        handlers.onDone?.(String(payload.answer ?? ""), String(payload.mode ?? "offline"));
      }
    }
  }
}

// --- Governança / Administração ---
export async function getAuditLog(limit = 100): Promise<AuditEntry[]> {
  return parse<AuditEntry[]>(
    await fetch(apiUrl(`/audit?limit=${limit}`), {
      headers: authHeaders(),
      cache: "no-store",
    }),
  );
}

export async function getAccessPolicy(): Promise<AccessPolicy> {
  return parse<AccessPolicy>(
    await fetch(apiUrl("/governance/access-policy"), { cache: "no-store" }),
  );
}

export async function getDataLineage(): Promise<DataLineage> {
  return parse<DataLineage>(
    await fetch(apiUrl("/governance/data-lineage"), {
      headers: authHeaders(),
      cache: "no-store",
    }),
  );
}

export async function listUsers(): Promise<UserAccount[]> {
  return parse<UserAccount[]>(
    await fetch(apiUrl("/users"), { headers: authHeaders(), cache: "no-store" }),
  );
}

// --- Modelos / IA ---
export async function getMlStatus(): Promise<MlStatus> {
  return parse<MlStatus>(await fetch(apiUrl("/ml/status"), { cache: "no-store" }));
}

export async function trainModels(): Promise<MlStatus> {
  return parse<MlStatus>(
    await fetch(apiUrl("/ml/train"), { method: "POST", headers: authHeaders() }),
  );
}
