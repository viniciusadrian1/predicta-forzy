"use client";

/**
 * PumpBenchViewer3D
 * =================
 * Gêmeo 3D da BANCADA DE BOMBA DE TESTE real da Forzy — não um motor genérico.
 *
 * A malha é o CAD DELES: `ChallengeForzy-bomba-teste.stp` (AVEVA / AP203)
 * tesselado com OpenCascade e exportado como `/models/bomba-teste.glb`
 * (17 sólidos, ~12k triângulos), já em metros e no referencial do three.js.
 *
 * MTR-F01 e MTR-F02 NÃO são dois motores: são os DOIS MANCAIS (⌀58 × 19 mm,
 * as únicas duas peças idênticas do conjunto) que flanqueiam o eixo central.
 * Um equipamento, dois pontos de medição — é isso que este visualizador mostra.
 */

import { Html, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { useQuery } from "@tanstack/react-query";
import { Suspense, useCallback, useState } from "react";

import { BenchModel } from "@/components/BenchModel";
import { getAssets, getLatest } from "@/lib/api";
import {
  BENCH,
  BENCH_STATUS_COLOR as STATUS_COLOR,
  CENTERLINE,
  DEFAULT_BENCH_POINTS,
  axPos as ax,
  bearingU,
  mm,
  type BenchPoint,
} from "@/lib/benchGeometry";

export { DEFAULT_BENCH_POINTS };
export type { BenchPoint };

// --------------------------------------------------------------------------
// Marcador de sensor sobre um mancal
// --------------------------------------------------------------------------
function BearingSensor({
  point,
  status,
  isActive,
  isFocused,
  isHovered,
  onClick,
  onHover,
}: {
  point: BenchPoint;
  status: string;
  /** Selecionado por clique — abre o balao de leitura. */
  isActive: boolean;
  /** Mancal do ativo aberto — apenas destaca, sem abrir o balao. */
  isFocused: boolean;
  isHovered: boolean;
  onClick: () => void;
  onHover: (v: boolean) => void;
}) {
  const color = STATUS_COLOR[status] ?? STATUS_COLOR.unknown;
  const show = isActive || isHovered;

  const latest = useQuery({
    queryKey: ["latest", point.tag],
    queryFn: () => getLatest(point.tag),
    refetchInterval: 4000,
    enabled: show,
  });

  // O sensor fica no topo do mancal, como na bancada real.
  const yTop = CENTERLINE + BENCH.bearing.r + mm(22);

  return (
    <group position={[ax(bearingU(point)), yTop, 0]}>
      {/* Haste até o mancal */}
      <mesh position={[0, -mm(16), 0]}>
        <cylinderGeometry args={[mm(3), mm(3), mm(32), 10]} />
        <meshStandardMaterial color={color} transparent opacity={0.75} />
      </mesh>

      {/* Corpo do sensor (clicável) */}
      <mesh
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(true);
        }}
        onPointerOut={() => onHover(false)}
        scale={isActive || isFocused ? 1.35 : isHovered ? 1.15 : 1}
        castShadow
      >
        <sphereGeometry args={[mm(20), 20, 20]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isActive || isFocused ? 0.85 : 0.35}
          roughness={0.25}
          metalness={0.3}
        />
      </mesh>

      {show && (
        <Html distanceFactor={1.4} position={[0, mm(60), 0]} center style={{ pointerEvents: "none" }}>
          <div
            style={{
              background: "rgba(15,23,42,0.97)",
              border: `1px solid ${color}44`,
              borderLeft: `3px solid ${color}`,
              borderRadius: 8,
              padding: "10px 14px",
              minWidth: 210,
              fontFamily: "system-ui, sans-serif",
              fontSize: 12,
              color: "#e2e8f0",
              boxShadow: `0 4px 24px ${color}22`,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2, color }}>{point.label}</div>
            <div style={{ color: "#64748b", fontSize: 11, marginBottom: 8 }}>
              {point.tag} · sensor IO-Link
            </div>
            {latest.isLoading && <div style={{ color: "#475569" }}>Carregando…</div>}
            {latest.data?.readings.map((r) => {
              const isVel = r.variable === "Vibracao_Velocidade_RMS";
              const isAcc = r.variable === "Vibracao_Aceleracao_RMS";
              const isTemp = r.variable === "Temperatura";
              return (
                <div
                  key={r.variable}
                  style={{ display: "flex", justifyContent: "space-between", gap: 14, padding: "2px 0" }}
                >
                  <span style={{ color: "#94a3b8" }}>
                    {isVel
                      ? "Vibração vel. RMS"
                      : isAcc
                        ? "Vibração acel. RMS"
                        : isTemp
                          ? "Temperatura"
                          : r.variable}
                  </span>
                  <span style={{ color: "#e2e8f0", fontWeight: 600 }}>
                    {r.value.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} {r.unit}
                  </span>
                </div>
              );
            })}
          </div>
        </Html>
      )}
    </group>
  );
}

// --------------------------------------------------------------------------
// Cena
// --------------------------------------------------------------------------
function BenchScene({
  points,
  statusOf,
  activeTag,
  focusedTag,
  onSelect,
}: {
  points: BenchPoint[];
  statusOf: (tag: string) => string;
  activeTag: string | null;
  focusedTag: string | null;
  onSelect: (tag: string | null) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const { gl } = useThree();
  const hover = useCallback(
    (tag: string, v: boolean) => {
      gl.domElement.style.cursor = v ? "pointer" : "default";
      setHovered(v ? tag : null);
    },
    [gl],
  );

  return (
    <>
      <PerspectiveCamera makeDefault position={[0.6, 1.0, 1.7]} fov={42} />
      <OrbitControls
        enablePan={false}
        target={[0, CENTERLINE * 0.8, 0]}
        minDistance={0.8}
        maxDistance={3}
        maxPolarAngle={Math.PI * 0.5}
      />

      <ambientLight intensity={0.55} />
      <directionalLight position={[1.5, 2.5, 1.5]} intensity={1.2} castShadow />
      <directionalLight position={[-1.5, 1.2, -1]} intensity={0.35} color="#93c5fd" />

      {/* Malha do CAD real */}
      <Suspense fallback={null}>
        <BenchModel />
      </Suspense>

      {/* Sensores nos dois mancais */}
      {points.map((p) => (
        <BearingSensor
          key={p.tag}
          point={p}
          status={statusOf(p.tag)}
          isActive={activeTag === p.tag}
          isFocused={focusedTag === p.tag}
          isHovered={hovered === p.tag}
          onClick={() => onSelect(activeTag === p.tag ? null : p.tag)}
          onHover={(v) => hover(p.tag, v)}
        />
      ))}

      {/* Piso / sombra */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.001, 0]} receiveShadow>
        <planeGeometry args={[6, 6]} />
        <shadowMaterial opacity={0.22} />
      </mesh>
    </>
  );
}

// --------------------------------------------------------------------------
// Componente principal
// --------------------------------------------------------------------------
export interface PumpBenchViewer3DProps {
  /** TAG em foco (o ativo aberto) — destaca o mancal correspondente. */
  activeTag?: string;
  /** Pontos de medição; padrão = os dois mancais da bancada Forzy. */
  points?: BenchPoint[];
}

export function PumpBenchViewer3D({ activeTag, points = DEFAULT_BENCH_POINTS }: PumpBenchViewer3DProps) {
  // O mancal do ativo aberto fica destacado, mas o balao so abre no
  // hover/clique — senao ele tapa o modelo assim que a pagina carrega.
  const [selected, setSelected] = useState<string | null>(null);

  const assetsQuery = useQuery({
    queryKey: ["assets"],
    queryFn: () => getAssets(),
    refetchInterval: 15000,
  });
  const statusOf = useCallback(
    (tag: string) => assetsQuery.data?.find((a) => a.tag === tag)?.status ?? "unknown",
    [assetsQuery.data],
  );

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div
        className="relative flex-1 overflow-hidden rounded-xl border border-slate-800 bg-slate-950"
        style={{ minHeight: 380 }}
      >
        <Canvas shadows gl={{ antialias: true }}>
          <color attach="background" args={["#020617"]} />
          <BenchScene
            points={points}
            statusOf={statusOf}
            activeTag={selected}
            focusedTag={activeTag ?? null}
            onSelect={setSelected}
          />
        </Canvas>

        <div className="pointer-events-none absolute left-3 top-3 rounded-md bg-slate-900/85 px-2.5 py-1.5">
          <p className="text-[11px] font-semibold text-slate-200">Bancada de bomba de teste</p>
          <p className="text-[10px] text-slate-500">Malha do CAD da Forzy · 1200 × 500 × 817 mm</p>
        </div>

        <div className="pointer-events-none absolute bottom-3 left-0 right-0 flex justify-center">
          <span className="rounded-full bg-slate-900/80 px-3 py-1 text-[10px] text-slate-500">
            Arraste para girar · Scroll para zoom · Clique no sensor para a leitura
          </span>
        </div>
      </div>

      {/* Legenda */}
      <div className="w-full lg:w-56">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
          Pontos de medição
        </p>
        <p className="mb-2 text-[11px] leading-snug text-slate-500">
          Um único conjunto motor-bomba com <b className="text-slate-400">dois mancais</b> — cada um
          com seu sensor IO-Link.
        </p>
        {points.map((p) => {
          const color = STATUS_COLOR[statusOf(p.tag)] ?? STATUS_COLOR.unknown;
          const isActive = selected === p.tag;
          return (
            <button
              key={p.tag}
              type="button"
              onClick={() => setSelected((cur) => (cur === p.tag ? null : p.tag))}
              className="mb-1 flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-slate-800"
              style={{ background: isActive ? "rgba(56,189,248,0.08)" : undefined }}
            >
              <span
                className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: color, boxShadow: `0 0 6px ${color}` }}
              />
              <span>
                <span className="block font-medium text-slate-300">{p.label}</span>
                <span className="block font-mono text-[10px] text-slate-600">{p.tag}</span>
              </span>
            </button>
          );
        })}

        <div className="mt-3 border-t border-slate-800 pt-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
            Status
          </p>
          {(["ok", "warning", "critical", "unknown"] as const).map((s) => (
            <div key={s} className="flex items-center gap-2 py-0.5">
              <span className="h-2 w-2 rounded-full" style={{ background: STATUS_COLOR[s] }} />
              <span className="text-xs text-slate-500">
                {s === "ok"
                  ? "Normal"
                  : s === "warning"
                    ? "Atenção"
                    : s === "critical"
                      ? "Crítico"
                      : "Desconhecido"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
