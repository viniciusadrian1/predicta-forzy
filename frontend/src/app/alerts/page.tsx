"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BellOff, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { alertTypeLabel, severityLabel } from "@/lib/alertLabels";
import { acknowledgeAlert, getAlerts } from "@/lib/api";
import { hasRole, useAuth } from "@/lib/auth";
import { useToasts } from "@/lib/toast";
import { usePageTitle } from "@/lib/usePageTitle";

const SEVERITY_VARIANT: Record<string, BadgeProps["variant"]> = {
  CRITICAL: "critical",
  WARNING: "warning",
  INFO: "default",
};

const SEVERITY_OPTIONS = [
  { value: "", label: "Todas as severidades" },
  { value: "CRITICAL", label: "Crítico" },
  { value: "WARNING", label: "Atenção" },
  { value: "INFO", label: "Informativo" },
];

function AlertsPageInner() {
  usePageTitle("Alertas");
  const queryClient = useQueryClient();
  const push = useToasts((state) => state.push);
  const role = useAuth((state) => state.role);
  const canAck = hasRole(role, "operator");

  const searchParams = useSearchParams();
  const tagFilter = searchParams.get("tag") ?? "";

  const [severity, setSeverity] = useState("");
  // Tres visoes. Antes era so "apenas ativos" ligado por padrao: ao reconhecer
  // um alerta ele deixava de ser ativo e o card SUMIA da tela no mesmo segundo,
  // levando junto o comentario recem-escrito. "Reconhecidos" e onde esse
  // historico fica, separado do fechamento automatico da maquina.
  const [view, setView] = useState<"ativos" | "reconhecidos" | "todos">("ativos");
  const [comments, setComments] = useState<Record<string, string>>({});

  const alertsQuery = useQuery({
    queryKey: ["alerts", "page", severity, view, tagFilter],
    queryFn: () =>
      getAlerts({
        severity: severity || undefined,
        onlyActive: view === "ativos",
        acknowledgedBy: view === "reconhecidos" ? "humano" : undefined,
        tag: tagFilter || undefined,
        limit: view === "ativos" ? undefined : 500,
      }),
    refetchInterval: 8000,
  });

  const ackMutation = useMutation({
    mutationFn: (input: { id: string; comment: string }) =>
      acknowledgeAlert(input.id, input.comment),
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
  const ackingId = ackMutation.isPending ? ackMutation.variables?.id : null;

  return (
    <AppShell>
        <div className="mb-1 flex items-baseline justify-between">
          <h1 className="text-xl font-semibold text-slate-100">Alertas</h1>
          <span className="text-sm text-slate-400">
            {alertsQuery.data?.length ?? 0} alerta(s)
          </span>
        </div>
        <p className="mb-5 text-sm text-slate-400">
          Eventos gerados por regras de limite e pelos modelos de ML.
        </p>

        <div className="mb-5 flex flex-wrap items-center gap-3">
          <select
            aria-label="Filtrar por severidade"
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            className="h-10 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
          >
            {SEVERITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <div className="inline-flex overflow-hidden rounded-md border border-slate-700">
            {(
              [
                ["ativos", "Ativos"],
                ["reconhecidos", "Reconhecidos"],
                ["todos", "Todos"],
              ] as const
            ).map(([valor, rotulo]) => (
              <button
                key={valor}
                type="button"
                onClick={() => setView(valor)}
                className={`px-3 py-1.5 text-sm transition-colors ${
                  view === valor
                    ? "bg-cyan-500 font-medium text-slate-950"
                    : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                {rotulo}
              </button>
            ))}
          </div>
          {tagFilter && (
            <Link
              href="/alerts"
              className="inline-flex items-center gap-1.5 rounded-full border border-cyan-600/50 bg-cyan-950/50 px-3 py-1 text-xs text-cyan-300 hover:border-cyan-500"
            >
              Filtrando por {tagFilter}
              <X className="h-3.5 w-3.5" />
            </Link>
          )}
        </div>

        {alertsQuery.isLoading && <p className="text-slate-400">Carregando...</p>}

        {alertsQuery.isError && (
          <EmptyState
            icon={AlertTriangle}
            title="Não foi possível carregar os alertas"
            description="Verifique a conexão com a API e tente novamente."
            action={
              <Button variant="outline" onClick={() => void alertsQuery.refetch()}>
                Tentar novamente
              </Button>
            }
          />
        )}

        {alertsQuery.isSuccess && alertsQuery.data.length === 0 && (
          <EmptyState
            icon={BellOff}
            title="Nenhum alerta ativo"
            description="Tudo operando normalmente."
          />
        )}

        <div className="flex flex-col gap-3">
          {alertsQuery.data?.map((alert) => (
            <Card key={alert.id} className="p-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={SEVERITY_VARIANT[alert.severity] ?? "default"}>
                  {severityLabel(alert.severity)}
                </Badge>
                <span className="text-xs font-medium text-slate-400">
                  {alertTypeLabel(alert.alert_type)}
                </span>
                <Link
                  href={`/asset/${encodeURIComponent(alert.asset_tag)}`}
                  className="text-xs font-medium text-cyan-400 hover:text-cyan-300"
                >
                  {alert.asset_tag} →
                </Link>
                {/* Reincidencia: intermitencia e uma falha diferente de
                    degradacao continua, e sem isso as duas viravam a mesma
                    pilha de cards iguais. */}
                {alert.occurrence_count > 1 && (
                  <span
                    className="rounded-full border border-amber-700/60 bg-amber-950/40 px-2 py-0.5 text-[11px] font-medium text-amber-300"
                    title={
                      alert.last_seen_at
                        ? `Última ocorrência: ${new Date(alert.last_seen_at).toLocaleString("pt-BR")}`
                        : undefined
                    }
                  >
                    reincidiu {alert.occurrence_count}×
                  </span>
                )}
                <span className="ml-auto text-xs text-slate-500">
                  {new Date(alert.created_at).toLocaleString("pt-BR")}
                  {alert.occurrence_count > 1 && alert.last_seen_at && (
                    <>
                      {" · última "}
                      {new Date(alert.last_seen_at).toLocaleTimeString("pt-BR")}
                    </>
                  )}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-200">{alert.message}</p>

              {alert.acknowledged ? (
                <div className="mt-2 rounded-md border border-slate-800 bg-slate-950/50 px-3 py-2">
                  {alert.ack_by === "auto" ? (
                    <p className="text-xs text-slate-500">
                      Encerrado automaticamente — a condição normalizou
                      {alert.ack_at
                        ? ` em ${new Date(alert.ack_at).toLocaleString("pt-BR")}`
                        : ""}
                      .
                    </p>
                  ) : (
                    <>
                      <p className="text-xs text-slate-400">
                        <span className="font-medium text-slate-300">
                          Reconhecido por {alert.ack_by ?? "—"}
                        </span>
                        {/* ack_at existia no modelo, na API e no tipo, mas nunca
                            aparecia: dos tres dados pedidos, a hora do
                            reconhecimento simplesmente nao era exibida. */}
                        {alert.ack_at
                          ? ` · ${new Date(alert.ack_at).toLocaleString("pt-BR")}`
                          : ""}
                      </p>
                      {alert.ack_comment && (
                        <p className="mt-1 text-sm text-slate-200">
                          &ldquo;{alert.ack_comment}&rdquo;
                        </p>
                      )}
                    </>
                  )}
                </div>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  <Input
                    aria-label="Comentário do reconhecimento"
                    placeholder="Comentário (opcional)"
                    value={comments[alert.id] ?? ""}
                    onChange={(event) =>
                      setComments({ ...comments, [alert.id]: event.target.value })
                    }
                    className="max-w-xs"
                  />
                  <Button
                    size="sm"
                    onClick={() =>
                      ackMutation.mutate({
                        id: alert.id,
                        comment: comments[alert.id] ?? "",
                      })
                    }
                    disabled={!canAck || ackingId === alert.id}
                    title={canAck ? undefined : "Requer papel operador"}
                  >
                    {ackingId === alert.id ? "Reconhecendo..." : "Reconhecer"}
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
    </AppShell>
  );
}

export default function AlertsPage() {
  return (
    <Suspense fallback={null}>
      <AlertsPageInner />
    </Suspense>
  );
}
