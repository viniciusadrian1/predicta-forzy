"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Clock,
  HelpCircle,
  Loader2,
  ThumbsDown,
  WifiOff,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { alertTypeLabel } from "@/lib/alertLabels";
import {
  getAlerts,
  getRul,
  predictAnomaly,
  predictBaseline,
  predictFault,
  sendMlFeedback,
} from "@/lib/api";
import { useToasts } from "@/lib/toast";

const SEVERITY_BORDER: Record<string, string> = {
  CRITICAL: "#ef4444",
  WARNING: "#f59e0b",
  INFO: "#64748b",
};

// Rótulos PT das classes do classificador de falha (modelo simulado).
const FAULT_LABEL: Record<string, string> = {
  normal: "Operação normal",
  bearing_wear: "Desgaste de rolamento",
  unbalance: "Desbalanceamento",
  overload: "Sobrecarga",
  spike: "Pico transiente",
};

/** Seção "Saúde do ativo": baseline, anomalia, RUL e timeline de alertas. */
export function AssetHealth({ tag }: { tag: string }) {
  const push = useToasts((state) => state.push);
  const [reported, setReported] = useState(false);

  const baseline = useQuery({
    queryKey: ["ml-baseline", tag],
    queryFn: () => predictBaseline(tag),
    refetchInterval: 15000,
  });
  const anomaly = useQuery({
    queryKey: ["ml-anomaly", tag],
    queryFn: () => predictAnomaly(tag),
    refetchInterval: 15000,
  });
  const rul = useQuery({
    queryKey: ["ml-rul", tag],
    queryFn: () => getRul(tag),
    refetchInterval: 30000,
  });
  const fault = useQuery({
    queryKey: ["ml-fault", tag],
    queryFn: () => predictFault(tag),
    refetchInterval: 15000,
  });
  const alerts = useQuery({
    queryKey: ["alerts", tag],
    queryFn: () => getAlerts({ tag }),
    refetchInterval: 8000,
  });

  // Estado geral honesto: nunca "verde" sem dado positivo real.
  // Precedência: carregando -> sem conexão -> sem dados -> anômalo -> normal.
  const loading = baseline.isPending || anomaly.isPending;
  const offline = baseline.isError && anomaly.isError;
  const noData =
    baseline.data?.available === false && anomaly.data?.available === false;
  const isAnomalous =
    anomaly.data?.is_anomaly === true || baseline.data?.decision === "anomalo";

  const overall = loading
    ? {
        icon: <Loader2 className="h-5 w-5 animate-spin text-slate-400" />,
        text: "Verificando estado...",
      }
    : offline
      ? {
          icon: <WifiOff className="h-5 w-5 text-amber-400" />,
          text: "Estado desconhecido — sem conexão com a API",
        }
      : noData
        ? {
            icon: <HelpCircle className="h-5 w-5 text-slate-400" />,
            text: "Sem dados suficientes para avaliar",
          }
        : isAnomalous
          ? {
              icon: <Activity className="h-5 w-5 text-amber-400" />,
              text: "Atenção — desvio detectado",
            }
          : {
              icon: <Activity className="h-5 w-5 text-emerald-400" />,
              text: "Operação normal",
            };

  const rulDays = rul.data?.rul_days ?? null;
  const rulPercent =
    rulDays !== null ? Math.max(3, Math.min(100, (rulDays / 90) * 100)) : 100;
  const rulColor =
    rulDays !== null && rulDays < 15
      ? "bg-red-500"
      : rulDays !== null && rulDays < 45
        ? "bg-amber-500"
        : "bg-emerald-500";

  const reportIncorrect = async () => {
    try {
      await sendMlFeedback({
        asset_tag: tag,
        model: "anomaly",
        prediction: anomaly.data?.is_anomaly ? "anomalia" : "normal",
        is_correct: false,
      });
      setReported(true);
      push({
        title: "Feedback registrado",
        description: "Obrigado — a predição foi marcada para revisão.",
        severity: "info",
      });
    } catch (error) {
      push({
        title: "Falha ao enviar o feedback",
        description: error instanceof Error ? error.message : undefined,
        severity: "critical",
      });
    }
  };

  return (
    <section className="mb-6">
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        Saúde do ativo
      </h2>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-4">
          <div className="flex items-center gap-2">
            {overall.icon}
            <p className="font-medium text-slate-100">{overall.text}</p>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Baseline (Isolation Forest):{" "}
            {baseline.data?.available
              ? `${baseline.data.decision} — score ${baseline.data.score}`
              : "aguardando dados"}
          </p>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-cyan-400" />
            <p className="font-medium text-slate-100">Detecção de anomalia</p>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            {anomaly.data?.available
              ? anomaly.data.is_anomaly
                ? `Anomalia detectada (erro ${anomaly.data.reconstruction_error})`
                : `Sem anomalia (erro ${anomaly.data.reconstruction_error})`
              : "aguardando dados"}
          </p>
          <button
            type="button"
            onClick={reportIncorrect}
            disabled={reported}
            className="mt-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 disabled:opacity-50"
          >
            <ThumbsDown className="h-3.5 w-3.5" />
            {reported ? "Predição reportada" : "Reportar predição incorreta"}
          </button>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-violet-400" />
            <p className="font-medium text-slate-100">Vida útil (RUL)</p>
          </div>
          {rul.data?.available ? (
            rulDays !== null ? (
              <>
                <p className="mt-2 text-2xl font-semibold text-slate-100">
                  {rulDays}
                  <span className="ml-1 text-sm font-normal text-slate-500">dias</span>
                </p>
                <div className="mt-1 h-2 w-full rounded bg-slate-800">
                  <div
                    className={`h-2 rounded ${rulColor}`}
                    style={{ width: `${rulPercent}%` }}
                  />
                </div>
                {rul.data.confidence_low_days !== null && (
                  <p className="mt-1 text-xs text-slate-500">
                    Intervalo: {rul.data.confidence_low_days} —{" "}
                    {rul.data.confidence_high_days} dias
                  </p>
                )}
                {rul.data.note && (
                  <p className="mt-1 text-[11px] leading-snug text-slate-500">
                    {rul.data.note}
                  </p>
                )}
              </>
            ) : (
              <p className="mt-2 text-sm text-emerald-400">
                Vida útil longa — sem degradação mensurável
              </p>
            )
          ) : (
            <p className="mt-2 text-xs text-slate-400">Histórico insuficiente</p>
          )}
        </Card>
      </div>

      {fault.data?.available && fault.data.fault && (
        <Card className="mt-4 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-cyan-400" />
            <p className="font-medium text-slate-100">
              Classificação de falha: {FAULT_LABEL[fault.data.fault] ?? fault.data.fault}
            </p>
            <span className="rounded-full border border-amber-500/40 bg-amber-950/40 px-2 py-0.5 text-[11px] font-medium text-amber-300">
              simulado
            </span>
            {fault.data.confidence !== null && (
              <span className="text-xs text-slate-500">
                confiança {Math.round(fault.data.confidence * 100)}%
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Modelo treinado em dado simulado (motor de demonstração). Não aplicado
            aos motores reais até haver falha real rotulada.
          </p>
        </Card>
      )}

      <Card className="mt-4">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Alertas recentes</CardTitle>
          <Link
            href={`/alerts?tag=${encodeURIComponent(tag)}`}
            className="text-xs text-cyan-400 hover:text-cyan-300"
          >
            Ver todos →
          </Link>
        </CardHeader>
        <CardContent>
          {(alerts.data ?? []).length === 0 && (
            <p className="text-sm text-slate-400">Nenhum alerta para este ativo.</p>
          )}
          <ul className="flex flex-col gap-2">
            {(alerts.data ?? []).slice(0, 8).map((alert) => (
              <li key={alert.id}>
                <Link
                  href={`/alerts?tag=${encodeURIComponent(tag)}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 border-l-2 pl-3 text-sm hover:bg-slate-800/40"
                  style={{
                    borderColor: SEVERITY_BORDER[alert.severity] ?? "#64748b",
                  }}
                >
                  <span className="text-xs text-slate-500">
                    {new Date(alert.created_at).toLocaleString("pt-BR")}
                  </span>
                  <span className="text-xs font-medium text-slate-400">
                    {alertTypeLabel(alert.alert_type)}
                  </span>
                  <span className="text-slate-200">{alert.message}</span>
                </Link>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}
