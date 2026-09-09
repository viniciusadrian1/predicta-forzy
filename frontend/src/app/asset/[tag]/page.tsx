"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, SearchX, ServerCrash } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { AssetHealth } from "@/components/AssetHealth";
import { EmptyState } from "@/components/EmptyState";
import { LineageBadge, TraceabilityCard } from "@/components/Governance";
import { NextAction } from "@/components/NextAction";
import { SensorPanel } from "@/components/SensorPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getAsset, getAssets, validateAsset } from "@/lib/api";
import { pointsOf } from "@/lib/assetGroup";
import { BENCH_SIZE } from "@/lib/benchGeometry";
import { canValidate, useAuth } from "@/lib/auth";
import { useToasts } from "@/lib/toast";
import { usePageTitle } from "@/lib/usePageTitle";

interface AssetPageProps {
  params: { tag: string };
}

// Modelos 3D (WebGL) carregados só no cliente.
const MotorViewer3D = dynamic(
  () => import("@/components/MotorViewer3D").then((m) => m.MotorViewer3D),
  { ssr: false, loading: () => <Skeleton className="h-80 w-full" /> },
);
const PumpBenchViewer3D = dynamic(
  () => import("@/components/PumpBenchViewer3D").then((m) => m.PumpBenchViewer3D),
  { ssr: false, loading: () => <Skeleton className="h-80 w-full" /> },
);

// MTR-F01/F02 NAO sao dois motores: sao os dois MANCAIS do mesmo conjunto
// motor-bomba da Forzy. Para eles mostramos a bancada real (CAD), com os dois
// pontos de medicao; para os demais ativos, o motor generico.
const BENCH_TAGS = ["MTR-F01", "MTR-F02"];

// `variable` são as chaves canônicas da telemetria (OPC-UA) — não traduzir.
// warn/crit espelham os limiares do avaliador de alertas (ISO 10816 / térmico).
type SensorConfig = {
  variable: string;
  label: string;
  unit: string;
  color: string;
  warn?: number;
  crit?: number;
  hint?: string;
};
// O sensor IO-Link dos mancais mede so vibracao (vel/acel) e temperatura.
// Tensao/Corrente/Rotacao nao existem nele — mostrar daria 'SEM LEITURA'.
const POINT_VARS = ["Vibracao_Velocidade_RMS", "Vibracao_Aceleracao_RMS", "Temperatura"];

const SENSORS: SensorConfig[] = [
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
  {
    variable: "Rotacao",
    label: "Rotação",
    unit: "RPM",
    color: "#a78bfa",
    hint: "Velocidade de rotação do eixo (RPM) — não confundir com a vibração da carcaça.",
  },
  {
    variable: "Vibracao_Velocidade_RMS",
    label: "Vibração (velocidade)",
    unit: "mm/s",
    color: "#34d399",
    warn: 4.5,
    crit: 7.1,
    hint: "Velocidade de vibração RMS da carcaça (ISO 10816) — mede oscilação, não a rotação do eixo.",
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

  const role = useAuth((s) => s.role);
  const pushToast = useToasts((s) => s.push);
  const queryClient = useQueryClient();
  const assetQuery = useQuery({
    queryKey: ["asset", tag],
    queryFn: () => getAsset(tag),
  });
  const asset = assetQuery.data;

  // Pontos de medicao deste ativo (ex.: os dois mancais do conjunto Forzy).
  const allAssetsQuery = useQuery({
    queryKey: ["assets"],
    queryFn: () => getAssets(),
    refetchInterval: 15000,
  });
  const points = pointsOf(allAssetsQuery.data ?? [], tag);
  const isGroup = points.length > 0;

  const validateMutation = useMutation({
    mutationFn: () => validateAsset(tag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["asset", tag] });
      pushToast({ title: "Cadastro validado", severity: "info" });
    },
    onError: () =>
      pushToast({
        title: "Não foi possível validar",
        description: "Tente novamente em instantes.",
        severity: "critical",
      }),
  });
  const showValidate =
    !!asset && canValidate(role) && asset.data_origin === "ia_gerado" && !asset.validated_by;
  const notFound =
    assetQuery.error instanceof ApiError && assetQuery.error.status === 404;

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/overview");
  };

  // Campos de PLACA (potencia, ligacao, classe de isolamento...) so existem
  // para um motor com placa lida. Num conjunto montado como a bancada da Forzy
  // eles nao se aplicam - mostrar "--" numa linha inaplicavel parece defeito.
  // Entao o conjunto lista o que de fato se sabe dele: o que veio do cadastro
  // e o que foi medido no CAD e na instrumentacao.
  const specs: { label: string; value: string | number | null }[] = !asset
    ? []
    : isGroup
      ? [
          { label: "Fabricante", value: asset.manufacturer },
          { label: "Modelo", value: asset.model },
          { label: "Tensão (V)", value: asset.voltage_v },
          { label: "Tipo", value: "Conjunto motor-bomba (bancada de teste)" },
          { label: "Pontos de medição", value: points.length },
          { label: "Instrumentação", value: "Sensor IO-Link por mancal" },
          {
            label: "Dimensões (mm)",
            value: `${BENCH_SIZE.length * 1000} × ${BENCH_SIZE.depth * 1000} × ${
              BENCH_SIZE.height * 1000
            }`,
          },
          { label: "Origem das dimensões", value: "Malha do CAD da Forzy" },
        ]
      : [
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
        ];

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
              <LineageBadge asset={asset} />
              {showValidate && (
                <Button
                  variant="outline"
                  onClick={() => validateMutation.mutate()}
                  disabled={validateMutation.isPending}
                  className="ml-auto"
                >
                  <BadgeCheck className="h-4 w-4" />
                  {validateMutation.isPending ? "Validando..." : "Validar cadastro"}
                </Button>
              )}
            </div>

            {isGroup ? (
              /* ---- Ativo que AGRUPA pontos de medicao (conjunto Forzy) ----
                 O pai nao tem telemetria propria: quem mede sao os mancais.
                 Entao mostramos os dois lado a lado, no mesmo equipamento. */
              <>
                <section className="mb-6">
                  <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                    Gêmeo 3D — bancada de bomba de teste
                  </h2>
                  <PumpBenchViewer3D />
                </section>

                <section className="mb-6">
                  <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
                    Telemetria por mancal
                  </h2>
                  <div className="grid gap-6 lg:grid-cols-2">
                    {points.map((point) => (
                      <div key={point.tag}>
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-slate-100">
                            {point.name ?? point.tag}
                          </span>
                          <span className="font-mono text-xs text-slate-500">{point.tag}</span>
                          <StatusBadge status={point.status} />
                        </div>
                        <NextAction tag={point.tag} />
                        <div className="grid gap-4 sm:grid-cols-2">
                          {SENSORS.filter((s) => POINT_VARS.includes(s.variable)).map(
                            (sensor) => (
                              <SensorPanel
                                key={sensor.variable}
                                tag={point.tag}
                                variable={sensor.variable}
                                label={sensor.label}
                                unit={sensor.unit}
                                color={sensor.color}
                                warn={sensor.warn}
                                crit={sensor.crit}
                                hint={sensor.hint}
                              />
                            ),
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {points.map((point) => (
                  <div key={point.tag}>
                    <p className="mb-1 text-xs text-slate-500">
                      {point.name ?? point.tag}{" "}
                      <span className="font-mono text-slate-600">({point.tag})</span>
                    </p>
                    <AssetHealth tag={point.tag} />
                  </div>
                ))}
              </>
            ) : (
              /* ---- Ativo simples: mede a si proprio ---- */
              <>
                <NextAction tag={asset.tag} />

                <section className="mb-6">
                  <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                    {BENCH_TAGS.includes(asset.tag)
                      ? "Gêmeo 3D — bancada de bomba de teste"
                      : "Modelo 3D do ativo"}
                  </h2>
                  {BENCH_TAGS.includes(asset.tag) ? (
                    <PumpBenchViewer3D activeTag={asset.tag} />
                  ) : (
                    <MotorViewer3D assetTag={asset.tag} status={asset.status} />
                  )}
                </section>

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
                        hint={sensor.hint}
                      />
                    ))}
                  </div>
                </section>

                <AssetHealth tag={asset.tag} />
              </>
            )}

            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Especificações do ativo</CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Mesmo padrao do cartao de rastreabilidade ao lado: rotulo
                      acima do valor. Com `justify-between` em duas colunas, um
                      valor longo encostava no rotulo da coluna seguinte. */}
                  <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                    {specs.map((row) => (
                      <div key={row.label} className="min-w-0">
                        <dt className="text-xs text-slate-500">{row.label}</dt>
                        <dd
                          className={`truncate text-sm ${
                            row.value == null ? "text-slate-500" : "text-slate-200"
                          }`}
                          title={row.value != null ? String(row.value) : undefined}
                        >
                          {row.value ?? "Não informado"}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </CardContent>
              </Card>

              <TraceabilityCard asset={asset} />
            </div>
          </>
        )}
    </AppShell>
  );
}
