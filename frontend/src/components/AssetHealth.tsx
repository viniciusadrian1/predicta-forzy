"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, Clock, ThumbsDown } from "lucide-react";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getAlerts,
  getRul,
  predictAnomaly,
  predictBaseline,
  sendMlFeedback,
} from "@/lib/api";
import { useToasts } from "@/lib/toast";

const SEVERITY_BORDER: Record<string, string> = {
  CRITICAL: "#ef4444",
  WARNING: "#f59e0b",
  INFO: "#64748b",
};

/** Secao "Saude do ativo": baseline, anomalia, RUL e timeline de alertas. */
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
  const alerts = useQuery({
    queryKey: ["alerts", tag],
    queryFn: () => getAlerts({ tag }),
    refetchInterval: 8000,
  });

  const isAnomalous =
    anomaly.data?.is_anomaly === true || baseline.data?.decision === "anomalo";
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
    await sendMlFeedback({
      asset_tag: tag,
      model: "anomaly",
      prediction: anomaly.data?.is_anomaly ? "anomalia" : "normal",
      is_correct: false,
    });
    setReported(true);
    push({
      title: "Feedback registrado",
      description: "Obrigado - a predicao foi marcada para revisao.",
      severity: "info",
    });
  };

  return (
    <section className="mb-6">
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        Saude do ativo
      </h2>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-4">
          <div className="flex items-center gap-2">
            <Activity
              className={
                isAnomalous ? "h-5 w-5 text-amber-400" : "h-5 w-5 text-emerald-400"
              }
            />
            <p className="font-medium text-slate-100">
              {isAnomalous ? "Atencao - desvio detectado" : "Operacao normal"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Baseline (Isolation Forest):{" "}
            {baseline.data?.available
              ? `${baseline.data.decision} - score ${baseline.data.score}`
              : "aguardando dados"}
          </p>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-cyan-400" />
            <p className="font-medium text-slate-100">Deteccao de anomalia</p>
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
            {reported ? "Predicao reportada" : "Reportar predicao incorreta"}
          </button>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-violet-400" />
            <p className="font-medium text-slate-100">Vida util (RUL)</p>
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
                <p className="mt-1 text-xs text-slate-500">
                  Intervalo: {rul.data.confidence_low_days} -{" "}
                  {rul.data.confidence_high_days} dias
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm text-emerald-400">
                Vida util longa - sem degradacao mensuravel
              </p>
            )
          ) : (
            <p className="mt-2 text-xs text-slate-400">Historico insuficiente</p>
          )}
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Alertas recentes</CardTitle>
        </CardHeader>
        <CardContent>
          {(alerts.data ?? []).length === 0 && (
            <p className="text-sm text-slate-400">Nenhum alerta para este ativo.</p>
          )}
          <ul className="flex flex-col gap-2">
            {(alerts.data ?? []).slice(0, 8).map((alert) => (
              <li
                key={alert.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 border-l-2 pl-3 text-sm"
                style={{
                  borderColor: SEVERITY_BORDER[alert.severity] ?? "#64748b",
                }}
              >
                <span className="text-xs text-slate-500">
                  {new Date(alert.created_at).toLocaleString("pt-BR")}
                </span>
                <span className="text-xs font-medium text-slate-400">
                  {alert.alert_type}
                </span>
                <span className="text-slate-200">{alert.message}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </section>
  );
}
