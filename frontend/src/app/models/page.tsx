"use client";

// Modelos / IA: estado dos modelos de ML (baseline, anomalia, RUL) e retreino
// sob demanda. Consome GET /ml/status e POST /ml/train (engineer+).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cpu, RefreshCw, ServerCrash } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getMlStatus, trainModels } from "@/lib/api";
import { hasRole, useAuth } from "@/lib/auth";
import { useToasts } from "@/lib/toast";
import { usePageTitle } from "@/lib/usePageTitle";

const MODELS = [
  {
    name: "Baseline",
    algo: "Isolation Forest",
    desc: "Desvio do ponto de operação normal sobre os 6 sensores.",
  },
  {
    name: "Anomalia",
    algo: "Autoencoder (MLP)",
    desc: "Erro de reconstrução sobre janelas de vibração.",
  },
  {
    name: "RUL",
    algo: "Regressão linear",
    desc: "Tendência de vibração até o limite ISO 10816.",
  },
];

export default function ModelsPage() {
  usePageTitle("Modelos / IA");
  const queryClient = useQueryClient();
  const push = useToasts((state) => state.push);
  const role = useAuth((state) => state.role);
  const canTrain = hasRole(role, "engineer");

  const statusQuery = useQuery({
    queryKey: ["ml-status"],
    queryFn: getMlStatus,
    refetchInterval: 15000,
  });

  const trainMutation = useMutation({
    mutationFn: trainModels,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ml-status"] });
      push({ title: "Modelos retreinados", severity: "info" });
    },
    onError: (error) =>
      push({
        title: "Falha ao retreinar",
        description: error instanceof Error ? error.message : undefined,
        severity: "critical",
      }),
  });

  const status = statusQuery.data;

  return (
    <AppShell>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Cpu className="h-5 w-5 text-cyan-400" />
        <h1 className="text-xl font-semibold text-slate-100">Modelos / IA</h1>
        <Button
          className="ml-auto"
          onClick={() => trainMutation.mutate()}
          disabled={!canTrain || trainMutation.isPending}
          title={canTrain ? undefined : "Requer papel engenheiro"}
        >
          <RefreshCw
            className={`h-4 w-4 ${trainMutation.isPending ? "animate-spin" : ""}`}
          />
          {trainMutation.isPending ? "Retreinando..." : "Retreinar modelos"}
        </Button>
      </div>
      <p className="mb-5 text-sm text-slate-400">
        Modelos treinados sob demanda a partir da telemetria do TimescaleDB. As
        predições por ativo aparecem na seção &quot;Saúde do ativo&quot; de cada motor.
      </p>

      {statusQuery.isError && (
        <EmptyState
          icon={ServerCrash}
          title="Não foi possível carregar o estado dos modelos"
          action={
            <Button variant="outline" onClick={() => void statusQuery.refetch()}>
              Tentar novamente
            </Button>
          }
        />
      )}

      {/* Estado do bundle atual */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs text-slate-500">Estado</p>
          {statusQuery.isLoading ? (
            <Skeleton className="mt-1 h-7 w-24" />
          ) : (
            <p
              className={`mt-1 text-lg font-semibold ${
                status?.ready ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {status?.ready ? "Treinado" : "Aguardando dados"}
            </p>
          )}
        </Card>
        <Card className="p-4">
          <p className="text-xs text-slate-500">Versão</p>
          {statusQuery.isLoading ? (
            <Skeleton className="mt-1 h-7 w-24" />
          ) : (
            <p className="mt-1 truncate text-lg font-semibold text-slate-100">
              {status?.model_version ?? "--"}
            </p>
          )}
        </Card>
        <Card className="p-4">
          <p className="text-xs text-slate-500">Amostras de treino</p>
          {statusQuery.isLoading ? (
            <Skeleton className="mt-1 h-7 w-16" />
          ) : (
            <p className="mt-1 text-lg font-semibold tabular-nums text-slate-100">
              {status?.n_samples?.toLocaleString("pt-BR") ?? "--"}
            </p>
          )}
        </Card>
        <Card className="p-4">
          <p className="text-xs text-slate-500">Treinado em</p>
          {statusQuery.isLoading ? (
            <Skeleton className="mt-1 h-7 w-28" />
          ) : (
            <p className="mt-1 text-sm font-medium text-slate-100">
              {status?.trained_at
                ? new Date(status.trained_at).toLocaleString("pt-BR")
                : "--"}
            </p>
          )}
        </Card>
      </div>

      {/* Catálogo de modelos */}
      <div className="grid gap-4 md:grid-cols-3">
        {MODELS.map((model) => (
          <Card key={model.name}>
            <CardHeader>
              <CardTitle>{model.name}</CardTitle>
              <p className="text-xs text-cyan-400">{model.algo}</p>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-slate-400">{model.desc}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
