"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Header } from "@/components/Header";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { acknowledgeAlert, getAlerts } from "@/lib/api";

const SEVERITY_VARIANT: Record<string, BadgeProps["variant"]> = {
  CRITICAL: "critical",
  WARNING: "warning",
  INFO: "default",
};

const SEVERITY_OPTIONS = [
  { value: "", label: "Todas as severidades" },
  { value: "CRITICAL", label: "Critico" },
  { value: "WARNING", label: "Atencao" },
  { value: "INFO", label: "Informativo" },
];

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [severity, setSeverity] = useState("");
  const [onlyActive, setOnlyActive] = useState(true);
  const [comments, setComments] = useState<Record<string, string>>({});

  const alertsQuery = useQuery({
    queryKey: ["alerts", "page", severity, onlyActive],
    queryFn: () => getAlerts({ severity: severity || undefined, onlyActive }),
    refetchInterval: 8000,
  });

  const ackMutation = useMutation({
    mutationFn: (input: { id: string; comment: string }) =>
      acknowledgeAlert(input.id, input.comment),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });

  return (
    <div>
      <Header />
      <main className="mx-auto max-w-5xl px-6 py-8">
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
        </div>

        {alertsQuery.isLoading && <p className="text-slate-400">Carregando...</p>}
        {alertsQuery.data?.length === 0 && (
          <p className="text-slate-400">Nenhum alerta encontrado.</p>
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
                <span className="text-xs text-slate-500">{alert.asset_tag}</span>
                <span className="ml-auto text-xs text-slate-500">
                  {new Date(alert.created_at).toLocaleString("pt-BR")}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-200">{alert.message}</p>

              {alert.acknowledged ? (
                <p className="mt-2 text-xs text-slate-500">
                  Reconhecido por {alert.ack_by}
                  {alert.ack_comment ? ` - "${alert.ack_comment}"` : ""}
                </p>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  <Input
                    aria-label="Comentario do reconhecimento"
                    placeholder="Comentario (opcional)"
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
                    disabled={ackMutation.isPending}
                  >
                    Reconhecer
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
