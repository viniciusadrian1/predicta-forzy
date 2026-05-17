"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Header } from "@/components/Header";
import { SensorStrip } from "@/components/SensorStrip";
import { StatusBadge } from "@/components/StatusBadge";
import { TelemetryChart } from "@/components/TelemetryChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAsset, getLatest, getTelemetry } from "@/lib/api";

interface AssetPageProps {
  params: { tag: string };
}

export default function AssetPage({ params }: AssetPageProps) {
  const { tag } = params;

  const assetQuery = useQuery({
    queryKey: ["asset", tag],
    queryFn: () => getAsset(tag),
  });
  const latestQuery = useQuery({
    queryKey: ["latest", tag],
    queryFn: () => getLatest(tag),
    refetchInterval: 2500,
  });
  const temperatureQuery = useQuery({
    queryKey: ["telemetry", tag, "Temperatura"],
    queryFn: () => getTelemetry(tag, "Temperatura", 600),
    refetchInterval: 3000,
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
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Link
          href="/dashboard"
          className="mb-4 inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar para o painel
        </Link>

        {assetQuery.isLoading && (
          <p className="text-slate-400">Carregando ativo...</p>
        )}
        {assetQuery.isError && (
          <p className="text-red-400">
            Ativo nao encontrado ou API indisponivel.
          </p>
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
                Leituras atuais
              </h2>
              <SensorStrip readings={latestQuery.data?.readings ?? []} />
            </section>

            <div className="grid gap-6 lg:grid-cols-3">
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Temperatura em tempo real</CardTitle>
                  <p className="text-sm text-slate-400">
                    Atualizacao automatica a cada 3 segundos
                  </p>
                </CardHeader>
                <CardContent>
                  <TelemetryChart
                    points={temperatureQuery.data?.points ?? []}
                    unit="C"
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Especificacoes</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="flex flex-col gap-2 text-sm">
                    {specs.map((row) => (
                      <div key={row.label} className="flex justify-between gap-4">
                        <dt className="text-slate-400">{row.label}</dt>
                        <dd className="text-right text-slate-200">
                          {row.value ?? "--"}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
