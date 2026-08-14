"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BellOff, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { Header } from "@/components/Header";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
  const [onlyActive, setOnlyActive] = useState(true);
  const [comments, setComments] = useState<Record<string, string>>({});

  const alertsQuery = useQuery({
    queryKey: ["alerts", "page", severity, onlyActive, tagFilter],
    queryFn: () =>
      getAlerts({
        severity: severity || undefined,
        onlyActive,
        tag: tagFilter || undefined,
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
    <div>
      <Header />
      <main className="mx-auto max-w-[1536px] px-6 py-8 lg:px-8">
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
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={onlyActive}
              onChange={(event) => setOnlyActive(event.target.checked)}
            />
            Apenas ativos
          </label>
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
                  {alert.severity}
                </Badge>
                <span className="text-xs font-medium text-slate-400">
                  {alert.alert_type}
                </span>
                <Link
                  href={`/asset/${encodeURIComponent(alert.asset_tag)}`}
                  className="text-xs font-medium text-cyan-400 hover:text-cyan-300"
                >
                  {alert.asset_tag} →
                </Link>
                <span className="ml-auto text-xs text-slate-500">
                  {new Date(alert.created_at).toLocaleString("pt-BR")}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-200">{alert.message}</p>

              {alert.acknowledged ? (
                <p className="mt-2 text-xs text-slate-500">
                  Reconhecido por {alert.ack_by}
                  {alert.ack_comment ? ` — "${alert.ack_comment}"` : ""}
                </p>
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
      </main>
    </div>
  );
}

export default function AlertsPage() {
  return (
    <Suspense fallback={null}>
      <AlertsPageInner />
    </Suspense>
  );
}
