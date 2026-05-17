"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { AssetHealth } from "@/components/AssetHealth";
import { ChatWidget } from "@/components/ChatWidget";
import { Header } from "@/components/Header";
import { SensorPanel } from "@/components/SensorPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAsset } from "@/lib/api";

interface AssetPageProps {
  params: { tag: string };
}

const SENSORS = [
  { variable: "Tensao", label: "Tensao", unit: "V", color: "#38bdf8" },
  { variable: "Corrente", label: "Corrente", unit: "A", color: "#22d3ee" },
  { variable: "Temperatura", label: "Temperatura", unit: "C", color: "#f59e0b" },
  { variable: "Rotacao", label: "Rotacao", unit: "RPM", color: "#a78bfa" },
  {
    variable: "Vibracao_Velocidade_RMS",
    label: "Vibracao (velocidade)",
    unit: "mm/s",
    color: "#34d399",
  },
  {
    variable: "Vibracao_Aceleracao_RMS",
    label: "Vibracao (aceleracao)",
    unit: "g",
    color: "#f472b6",
  },
];

export default function AssetPage({ params }: AssetPageProps) {
  const { tag } = params;
  const assetQuery = useQuery({
    queryKey: ["asset", tag],
    queryFn: () => getAsset(tag),
  });
  const asset = assetQuery.data;

  const specs: { label: string; value: string | number | null }[] = asset
    ? [
        { label: "Fabricante", value: asset.manufacturer },
        { label: "Modelo", value: asset.model },
        { label: "Numero de serie", value: asset.serial_number },
        { label: "Potencia (kW)", value: asset.power_kw },
        { label: "Tensao (V)", value: asset.voltage_v },
        { label: "Corrente nominal (A)", value: asset.nominal_current_a },
        { label: "Rotacao nominal (RPM)", value: asset.nominal_rpm },
        { label: "Ligacao", value: asset.connection_type },
        { label: "Classe de isolamento", value: asset.insulation_class },
        { label: "Grau de protecao", value: asset.ip_rating },
      ]
    : [];

  return (
    <div>
      <Header />
      <main className="mx-auto max-w-[1536px] px-6 py-8 lg:px-8">
        <Link
          href="/dashboard"
          className="mb-4 inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar para o painel
        </Link>

        {assetQuery.isLoading && <p className="text-slate-400">Carregando ativo...</p>}
        {assetQuery.isError && (
          <p className="text-red-400">Ativo nao encontrado ou API indisponivel.</p>
        )}

        {asset && (
          <>
            <div className="mb-6 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold text-slate-100">{asset.tag}</h1>
              <StatusBadge status={asset.status} />
              <span className="text-slate-400">{asset.name}</span>
            </div>

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
                  />
                ))}
              </div>
            </section>

            <AssetHealth tag={asset.tag} />

            <Card>
              <CardHeader>
                <CardTitle>Especificacoes do ativo</CardTitle>
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
      </main>
    </div>
  );
}
