"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { getAlerts } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { type ToastSeverity, useToasts } from "@/lib/toast";

function toSeverity(value: string): ToastSeverity {
  if (value === "CRITICAL") return "critical";
  if (value === "WARNING") return "warning";
  return "info";
}

// Rótulos em português para o cabeçalho do toast (o backend usa códigos).
const SEVERITY_LABEL: Record<string, string> = {
  CRITICAL: "Crítico",
  WARNING: "Atenção",
};
const TYPE_LABEL: Record<string, string> = {
  THRESHOLD_EXCEEDED: "Limite excedido",
  THRESHOLD_APPROACHING: "Aproximando do limite",
  BASELINE_DEVIATION: "Desvio do padrão de operação",
  ANOMALY_DETECTED: "Anomalia de vibração",
  RUL_WARNING: "Vida útil (RUL)",
  CIRCUIT_BREAKER: "Dado não confiável",
};

/**
 * Observa os alertas ativos e dispara toasts para os novos.
 * Componente sem UI; renderizado uma vez no layout raiz.
 */
export function AlertWatcher() {
  const push = useToasts((state) => state.push);
  const token = useAuth((state) => state.token);
  const seen = useRef<Set<string>>(new Set());
  const initialized = useRef(false);

  const { data } = useQuery({
    queryKey: ["alerts", "watch"],
    queryFn: () => getAlerts({ onlyActive: true }),
    refetchInterval: 10000,
    // Silencioso sem sessão (senão a tela de login recebe toasts de alerta).
    enabled: !!token,
  });

  useEffect(() => {
    if (!data) return;
    if (!initialized.current) {
      data.forEach((alert) => seen.current.add(alert.id));
      initialized.current = true;
      return;
    }
    for (const alert of data) {
      if (seen.current.has(alert.id)) continue;
      seen.current.add(alert.id);
      push({
        title: `${SEVERITY_LABEL[alert.severity] ?? alert.severity} · ${
          TYPE_LABEL[alert.alert_type] ?? alert.alert_type
        }`,
        description: alert.message,
        severity: toSeverity(alert.severity),
        href: `/asset/${alert.asset_tag}`,
      });
    }
  }, [data, push]);

  return null;
}
