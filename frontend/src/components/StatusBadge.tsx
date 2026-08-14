import { Badge } from "@/components/ui/badge";

// Chaves = status da API (não traduzir); valores = rótulo exibido.
const STATUS_LABELS: Record<string, string> = {
  ok: "Operacional",
  warning: "Atenção",
  critical: "Crítico",
  unknown: "Desconhecido",
};

type StatusVariant = "ok" | "warning" | "critical" | "unknown";

export function StatusBadge({ status }: { status: string }) {
  const variant: StatusVariant = (
    ["ok", "warning", "critical"].includes(status) ? status : "unknown"
  ) as StatusVariant;
  return <Badge variant={variant}>{STATUS_LABELS[status] ?? status}</Badge>;
}
