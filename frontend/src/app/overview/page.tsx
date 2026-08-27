"use client";

// Home de Operações: responde "o que precisa de mim agora?" em uma tela —
// KPIs da planta, fila de alertas priorizada com ação inline e mini-planta.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BellOff, Check, ServerCrash } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { PlantMap } from "@/components/PlantMap";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { alertTypeLabel, severityLabel } from "@/lib/alertLabels";
import { acknowledgeAlert, getAlerts, getAssets } from "@/lib/api";
import { hasRole, useAuth } from "@/lib/auth";
import { useToasts } from "@/lib/toast";
import { usePageTitle } from "@/lib/usePageTitle";

const SEVERITY_RANK: Record<string, number> = { CRITICAL: 3, WARNING: 2, INFO: 1 };
const SEVERITY_VARIANT: Record<string, BadgeProps["variant"]> = {
  CRITICAL: "critical",
  WARNING: "warning",
  INFO: "default",
};
const STATUS_ORDER: Record<string, number> = {
  critical: 0,
  warning: 1,
  unknown: 2,
  ok: 3,
};

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${Math.round(seconds / 3600)} h`;
}

function StatCard({
  label,
  value,
  tone = "text-slate-100",
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <Card className="p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${tone}`}>{value}</p>
    </Card>
  );
}

export default function OverviewPage() {
  usePageTitle("Visão Geral");
  const queryClient = useQueryClient();
  const push = useToasts((state) => state.push);
  const role = useAuth((state) => state.role);
  const canAck = hasRole(role, "operator");

  const assetsQuery = useQuery({
    queryKey: ["assets", "", ""],
    queryFn: () => getAssets(),
    refetchInterval: 15000,
  });
  const alertsQuery = useQuery({
    queryKey: ["alerts", "overview"],
    queryFn: () => getAlerts({ onlyActive: true }),
    refetchInterval: 8000,
  });

  const ackMutation = useMutation({
    mutationFn: (id: string) => acknowledgeAlert(id, "Reconhecido pela visão geral"),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      push({ title: "Alerta reconhecido", severity: "info" });
    },
    onError: (error) =>
      push({
        title: "Falha ao reconhecer o alerta",
        description: error instanceof Error ? error.message : undefined,
        severity: "critical",
      }),
  });
  const ackingId = ackMutation.isPending ? ackMutation.variables : null;

  const assets = assetsQuery.data ?? [];
  const counts = {
    total: assets.length,
    ok: assets.filter((a) => a.status === "ok").length,
    warning: assets.filter((a) => a.status === "warning").length,
    critical: assets.filter((a) => a.status === "critical").length,
  };
  const alerts = [...(alertsQuery.data ?? [])].sort(
    (a, b) =>
      (SEVERITY_RANK[b.severity] ?? 0) - (SEVERITY_RANK[a.severity] ?? 0) ||
      +new Date(b.created_at) - +new Date(a.created_at),
  );
  const rankedAssets = [...assets].sort(
    (a, b) => (STATUS_ORDER[a.status] ?? 2) - (STATUS_ORDER[b.status] ?? 2),
  );

  return (
    <AppShell>
      <div className="mb-5">
        <h1 className="text-xl font-semibold text-slate-100">Visão Geral</h1>
        <p className="text-sm text-slate-400">
          Estado da planta em tempo real — priorize e aja a partir daqui.
        </p>
      </div>

      {/* KPIs */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Ativos monitorados" value={counts.total} />
        <StatCard label="Operacional" value={counts.ok} tone="text-emerald-400" />
        <StatCard label="Em atenção" value={counts.warning} tone="text-amber-400" />
        <StatCard
          label="Críticos"
          value={counts.critical}
          tone={counts.critical > 0 ? "text-red-400" : "text-slate-100"}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Fila de prioridades */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Fila de prioridades</CardTitle>
            <Link
              href="/alerts"
              className="text-xs text-cyan-400 hover:text-cyan-300"
            >
              Histórico de alertas →
            </Link>
          </CardHeader>
          <CardContent>
            {alertsQuery.isLoading && (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-14" />
                <Skeleton className="h-14" />
                <Skeleton className="h-14" />
              </div>
            )}
            {alertsQuery.isError && (
              <EmptyState
                icon={ServerCrash}
                title="Não foi possível carregar os alertas"
                action={
                  <Button variant="outline" onClick={() => void alertsQuery.refetch()}>
                    Tentar novamente
                  </Button>
                }
              />
            )}
            {alertsQuery.isSuccess && alerts.length === 0 && (
              <EmptyState
                icon={BellOff}
                title="Nenhum alerta ativo"
                description="Planta operando normalmente."
              />
            )}
            <ul className="flex flex-col gap-2">
              {alerts.slice(0, 8).map((alert) => (
                <li
                  key={alert.id}
                  className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2.5"
                >
                  <Badge variant={SEVERITY_VARIANT[alert.severity] ?? "default"}>
                    {severityLabel(alert.severity)}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-slate-200">{alert.message}</p>
                    <p className="text-xs text-slate-500">
                      {alertTypeLabel(alert.alert_type)} · {timeAgo(alert.created_at)} atrás
                    </p>
                  </div>
                  <Link
                    href={`/asset/${encodeURIComponent(alert.asset_tag)}`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-cyan-400 hover:text-cyan-300"
                  >
                    {alert.asset_tag}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                  <button
                    type="button"
                    onClick={() => ackMutation.mutate(alert.id)}
                    disabled={!canAck || ackingId === alert.id}
                    title={canAck ? "Reconhecer" : "Requer papel operador"}
                    className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-200 disabled:opacity-40"
                  >
                    <Check className="h-3.5 w-3.5" />
                    {ackingId === alert.id ? "..." : "Reconhecer"}
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* Coluna direita: mini-planta + ativos */}
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Planta</CardTitle>
            </CardHeader>
            <CardContent>
              <PlantMap assets={assets} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between pb-2">
              <CardTitle>Ativos</CardTitle>
              <Link href="/assets" className="text-xs text-cyan-400 hover:text-cyan-300">
                Ver todos →
              </Link>
            </CardHeader>
            <CardContent>
              {assetsQuery.isLoading && (
                <div className="flex flex-col gap-2">
                  <Skeleton className="h-9" />
                  <Skeleton className="h-9" />
                  <Skeleton className="h-9" />
                </div>
              )}
              <ul className="flex flex-col gap-1">
                {rankedAssets.slice(0, 6).map((asset) => (
                  <li key={asset.id}>
                    <Link
                      href={`/asset/${encodeURIComponent(asset.tag)}`}
                      className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 hover:bg-slate-800/60"
                    >
                      <span className="min-w-0">
                        <span className="text-sm font-medium text-slate-200">
                          {asset.tag}
                        </span>
                        <span className="ml-2 truncate text-xs text-slate-500">
                          {asset.name}
                        </span>
                      </span>
                      <StatusBadge status={asset.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
