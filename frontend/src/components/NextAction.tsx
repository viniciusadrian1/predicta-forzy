"use client";

// Bloco de decisão do ativo: estado + causa provável + próxima ação
// recomendada, composto a partir dos alertas ativos, limiares ISO 10816 e
// RUL — os mesmos critérios do avaliador de alertas do backend.

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  HelpCircle,
  OctagonAlert,
} from "lucide-react";
import Link from "next/link";

import { getAlerts, getLatest, getRul } from "@/lib/api";
import { cn } from "@/lib/utils";

// Espelho dos limiares do backend (alerts/evaluator.py).
const VIB_WARNING = 4.5;
const VIB_CRITICAL = 7.1;
const TEMP_WARNING = 80;
const TEMP_CRITICAL = 95;
const RUL_WARNING_DAYS = 45;
const RUL_CRITICAL_DAYS = 15;

type Tone = "critical" | "warning" | "ok" | "unknown";

interface Recommendation {
  tone: Tone;
  title: string;
  action: string;
}

const TONE_STYLES: Record<Tone, { border: string; icon: JSX.Element }> = {
  critical: {
    border: "border-l-red-500",
    icon: <OctagonAlert className="h-5 w-5 shrink-0 text-red-400" />,
  },
  warning: {
    border: "border-l-amber-500",
    icon: <CircleAlert className="h-5 w-5 shrink-0 text-amber-400" />,
  },
  ok: {
    border: "border-l-emerald-500",
    icon: <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />,
  },
  unknown: {
    border: "border-l-slate-600",
    icon: <HelpCircle className="h-5 w-5 shrink-0 text-slate-400" />,
  },
};

function fmt(value: number, digits = 1): string {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: digits });
}

function buildRecommendation(
  readings: Record<string, number>,
  hasMlAlert: boolean,
  rulDays: number | null,
): Recommendation {
  const vibration = readings.Vibracao_Velocidade_RMS;
  const temperature = readings.Temperatura;

  if (Object.keys(readings).length === 0) {
    return {
      tone: "unknown",
      title: "Sem telemetria recente",
      action:
        "Verifique a conexão do sensor e a alimentação do equipamento antes de qualquer análise.",
    };
  }
  if (vibration !== undefined && vibration >= VIB_CRITICAL) {
    return {
      tone: "critical",
      title: `Vibração crítica — ${fmt(vibration, 2)} mm/s (zona D · ISO 10816)`,
      action:
        "Programar parada do equipamento e inspecionar rolamentos, acoplamento e fixação. Operar nesta faixa acelera a degradação.",
    };
  }
  if (temperature !== undefined && temperature >= TEMP_CRITICAL) {
    return {
      tone: "critical",
      title: `Temperatura crítica — ${fmt(temperature)} °C`,
      action:
        "Reduzir carga imediatamente e verificar refrigeração, ventilação e sobrecorrente. Risco para o isolamento do enrolamento.",
    };
  }
  if (rulDays !== null && rulDays < RUL_CRITICAL_DAYS) {
    return {
      tone: "critical",
      title: `Vida útil estimada em ${fmt(rulDays, 0)} dias`,
      action:
        "Priorizar a troca do rolamento na próxima janela de manutenção — a tendência de vibração se aproxima do limite ISO.",
    };
  }
  if (vibration !== undefined && vibration >= VIB_WARNING) {
    return {
      tone: "warning",
      title: `Vibração elevada — ${fmt(vibration, 2)} mm/s (zona C · ISO 10816)`,
      action:
        "Planejar inspeção de balanceamento e alinhamento; acompanhar a tendência de perto nas próximas horas.",
    };
  }
  if (temperature !== undefined && temperature >= TEMP_WARNING) {
    return {
      tone: "warning",
      title: `Temperatura elevada — ${fmt(temperature)} °C`,
      action:
        "Verificar carga, ventilação e refrigeração do equipamento; acompanhar a evolução térmica.",
    };
  }
  if (rulDays !== null && rulDays < RUL_WARNING_DAYS) {
    return {
      tone: "warning",
      title: `Vida útil estimada em ${fmt(rulDays, 0)} dias`,
      action:
        "Planejar a substituição do rolamento na próxima parada programada e garantir peça em estoque.",
    };
  }
  if (hasMlAlert) {
    return {
      tone: "warning",
      title: "Desvio de padrão detectado pelos modelos",
      action:
        "O comportamento fugiu do baseline aprendido. Inspecionar o equipamento no próximo turno e validar com o assistente.",
    };
  }
  return {
    tone: "ok",
    title: "Nenhuma ação necessária",
    action: "Operação dentro dos parâmetros. Seguir o plano de manutenção preventiva.",
  };
}

/** Banner "Próxima ação" no topo da página do ativo. */
export function NextAction({ tag }: { tag: string }) {
  const latestQuery = useQuery({
    queryKey: ["latest", tag],
    queryFn: () => getLatest(tag),
    refetchInterval: 10000,
  });
  const alertsQuery = useQuery({
    queryKey: ["alerts", "active", tag],
    queryFn: () => getAlerts({ tag, onlyActive: true }),
    refetchInterval: 8000,
  });
  const rulQuery = useQuery({
    queryKey: ["ml-rul", tag],
    queryFn: () => getRul(tag),
    refetchInterval: 30000,
  });

  if (latestQuery.isPending) return null;

  const readings = Object.fromEntries(
    (latestQuery.data?.readings ?? []).map((r) => [r.variable, r.value]),
  );
  const activeAlerts = alertsQuery.data ?? [];
  const hasMlAlert = activeAlerts.some((alert) =>
    ["BASELINE_DEVIATION", "ANOMALY_DETECTED"].includes(alert.alert_type),
  );
  const rulDays = rulQuery.data?.available ? (rulQuery.data.rul_days ?? null) : null;

  const rec = buildRecommendation(readings, hasMlAlert, rulDays);
  const style = TONE_STYLES[rec.tone];

  return (
    <div
      className={cn(
        "mb-6 rounded-lg border border-l-4 border-slate-800 bg-slate-900/60 p-4",
        style.border,
      )}
    >
      <div className="flex items-start gap-3">
        {style.icon}
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
            Próxima ação
          </p>
          <p className="mt-0.5 font-medium text-slate-100">{rec.title}</p>
          <p className="mt-1 text-sm text-slate-400">{rec.action}</p>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-xs">
            {activeAlerts.length > 0 && (
              <Link
                href={`/alerts?tag=${encodeURIComponent(tag)}`}
                className="inline-flex items-center gap-1 font-medium text-cyan-400 hover:text-cyan-300"
              >
                {activeAlerts.length} alerta(s) ativo(s)
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            )}
            <span className="text-slate-600">
              Dúvidas? Pergunte ao assistente pelo botão flutuante.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
