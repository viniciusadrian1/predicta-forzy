"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, SearchX, ServerCrash } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { AssetHealth } from "@/components/AssetHealth";
import { ChatWidget } from "@/components/ChatWidget";
import { EmptyState } from "@/components/EmptyState";
import { NextAction } from "@/components/NextAction";
import { SensorPanel } from "@/components/SensorPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getAsset } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

interface AssetPageProps {
  params: { tag: string };
}

// `variable` são as chaves canônicas da telemetria (OPC-UA) — não traduzir.
// warn/crit espelham os limiares do avaliador de alertas (ISO 10816 / térmico).
const SENSORS = [
  { variable: "Tensao", label: "Tensão", unit: "V", color: "#38bdf8" },
  { variable: "Corrente", label: "Corrente", unit: "A", color: "#22d3ee" },
  {
    variable: "Temperatura",
    label: "Temperatura",
    unit: "C",
    color: "#f59e0b",
    warn: 80,
    crit: 95,
  },
  { variable: "Rotacao", label: "Rotação", unit: "RPM", color: "#a78bfa" },
  {
    variable: "Vibracao_Velocidade_RMS",
    label: "Vibração (velocidade)",
    unit: "mm/s",
    color: "#34d399",
    warn: 4.5,
    crit: 7.1,
  },
  {
    variable: "Vibracao_Aceleracao_RMS",
    label: "Vibração (aceleração)",
    unit: "g",
    color: "#f472b6",
  },
];

export default function AssetPage({ params }: AssetPageProps) {
  const { tag } = params;
  const router = useRouter();
  usePageTitle(tag);

  const assetQuery = useQuery({
    queryKey: ["asset", tag],
    queryFn: () => getAsset(tag),
  });
  const asset = assetQuery.data;
  const notFound =
    assetQuery.error instanceof ApiError && assetQuery.error.status === 404;

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/overview");
  };

  const specs: { label: string; value: string | number | null }[] = asset
    ? [
        { label: "Fabricante", value: asset.manufacturer },
        { label: "Modelo", value: asset.model },
        { label: "Número de série", value: asset.serial_number },
        { label: "Potência (kW)", value: asset.power_kw },
        { label: "Tensão (V)", value: asset.voltage_v },
        { label: "Corrente nominal (A)", value: asset.nominal_current_a },
        { label: "Rotação nominal (RPM)", value: asset.nominal_rpm },
        { label: "Ligação", value: asset.connection_type },
        { label: "Classe de isolamento", value: asset.insulation_class },
        { label: "Grau de proteção", value: asset.ip_rating },
      ]
    : [];

  return (
    <AppShell>
      <p className="mb-1 text-xs text-slate-500">
        <Link href="/assets" className="hover:text-slate-300">
          Ativos
        </Link>
        {" / "}
        <span className="text-slate-400">{tag}</span>
      </p>
      <button
        type="button"
        onClick={goBack}
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </button>

        {assetQuery.isLoading && (
          <>
            <Skeleton className="mb-6 h-9 w-72" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-32" />
              ))}
            </div>
          </>
        )}

        {assetQuery.isError &&
          (notFound ? (
            <EmptyState
              icon={SearchX}
              title={`Ativo "${tag}" não encontrado`}
              description="Verifique a TAG ou volte ao painel de ativos."
              action={
                <Button variant="outline" onClick={() => router.push("/overview")}>
                  Voltar para o painel
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={ServerCrash}
              title="API indisponível"
              description="Não foi possível carregar o ativo. Tente novamente."
              action={
                <Button variant="outline" onClick={() => void assetQuery.refetch()}>
                  Tentar novamente
                </Button>
              }
            />
          ))}

        {asset && (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold text-slate-100">{asset.tag}</h1>
              <StatusBadge status={asset.status} />
              <span className="text-slate-400">{asset.name}</span>
            </div>

            <NextAction tag={asset.tag} />

            <section className="mb-6">
              <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                Telemetria em tempo real
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {SENSORS.map((sensor) => (
                  <SensorPanel
                    key={sensor.variable}
                    tag={asset.tag}
                    variable={sensor.variable}
                    label={sensor.label}
                    unit={sensor.unit}
                    color={sensor.color}
                    warn={sensor.warn}
                    crit={sensor.crit}
                  />
                ))}
              </div>
            </section>

            <AssetHealth tag={asset.tag} />

            <Card>
              <CardHeader>
                <CardTitle>Especificações do ativo</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  {specs.map((row) => (
                    <div key={row.label} className="flex justify-between gap-4">
                      <dt className="text-slate-400">{row.label}</dt>
                      <dd className="text-right text-slate-200">{row.value ?? "--"}</dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>

            <ChatWidget assetTag={asset.tag} />
          </>
        )}
    </AppShell>
  );
}
