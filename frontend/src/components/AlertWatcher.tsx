"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { getAlerts } from "@/lib/api";
import { type ToastSeverity, useToasts } from "@/lib/toast";

function toSeverity(value: string): ToastSeverity {
  if (value === "CRITICAL") return "critical";
  if (value === "WARNING") return "warning";
  return "info";
}

/**
 * Observa os alertas ativos e dispara toasts para os novos.
 * Componente sem UI; renderizado uma vez no layout raiz.
 */
export function AlertWatcher() {
  const push = useToasts((state) => state.push);
  const seen = useRef<Set<string>>(new Set());
  const initialized = useRef(false);

  const { data } = useQuery({
    queryKey: ["alerts", "watch"],
    queryFn: () => getAlerts({ onlyActive: true }),
    refetchInterval: 10000,
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
        title: `${alert.severity}: ${alert.alert_type}`,
        description: alert.message,
        severity: toSeverity(alert.severity),
      });
    }
  }, [data, push]);

  return null;
}
