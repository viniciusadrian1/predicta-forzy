"use client";

/**
 * PumpBenchViewer3D
 * =================
 * Gêmeo 3D da BANCADA DE BOMBA DE TESTE real da Forzy — não um motor genérico.
 *
 * Geometria reconstruída a partir do CAD entregue pela Forzy
 * (`ChallengeForzy-bomba-teste.stp`, AVEVA / AP203, unidades em mm).
 * O STEP é uma representação simplificada (17 sólidos, 63 faces em B-spline),
 * então reconstruímos por primitivas usando as MEDIDAS REAIS extraídas dele —
 * fica mais leve e mais legível que tesselar o B-rep.
 *
 * Conjunto real: 1200 (comprimento) × 500 (largura) × 817 (altura) mm,
 * linha de centro do eixo a 550 mm do piso do skid.
 *
 * PONTO-CHAVE DO MODELO DE DADOS: MTR-F01 e MTR-F02 NÃO são dois motores —
 * são os DOIS MANCAIS (⌀89,6 × 19,2 mm, as únicas duas peças idênticas do
 * conjunto) que flanqueiam o eixo central. Um equipamento, dois pontos de
 * medição. É isso que este visualizador comunica.
 */

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import * as THREE from "three";

import { getAssets, getLatest } from "@/lib/api";
import {
  BEARING_A_U,
  BEARING_B_U,
  BENCH,
  BENCH_STATUS_COLOR,
  CENTERLINE,
  DEFAULT_BENCH_POINTS,
  axPos as ax,
  mm,
  type BenchPoint,
} from "@/lib/benchGeometry";

// --------------------------------------------------------------------------
// Medidas reais do CAD Forzy — fonte única em `@/lib/benchGeometry`.
// Aliases locais para manter a leitura da cena curta.
// --------------------------------------------------------------------------
const SKID = BENCH.skid;
const PLATE = { ...BENCH.plate, y: BENCH.plate.y0 };
const PUMP_VOLUTE = BENCH.pumpVolute;
const PUMP_BODY = BENCH.pumpBody;
const PUMP_INLET = BENCH.pumpInlet;
const COUPLING = BENCH.coupling;
const SHAFT = BENCH.shaft;
const BEARING = BENCH.bearing;
const MOTOR = BENCH.motor;
const MOTOR_CAP = BENCH.motorCap;
const MOTOR_CAP_F_U = BENCH.motorCapFU;
const MOTOR_CAP_R_U = BENCH.motorCapRU;
const MOTOR_FEET = BENCH.motorFeet;
const STAND = BENCH.stand;
const TOP_PLATE = BENCH.topPlate;
const STATUS_COLOR = BENCH_STATUS_COLOR;

const STEEL = "#8a94a3";
const DARK = "#2d3748";
const MOTOR_BLUE = "#2f6fb3"; // o motor real é azul
const BEARING_C = "#1f2937";

export { DEFAULT_BENCH_POINTS };
export type { BenchPoint };

// --------------------------------------------------------------------------
// Primitivas (cilindro deitado ao longo de X)
// --------------------------------------------------------------------------
function Tube({
  u,
  r,
  len,
  y = CENTERLINE,
  color,
  metalness = 0.75,
  roughness = 0.45,
}: {
  u: number;
  r: number;
  len: number;
  y?: number;
  color: string;
  metalness?: number;
  roughness?: number;
}) {
  return (
    <mesh position={[ax(u), y, 0]} rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
      <cylinderGeometry args={[r, r, len, 40]} />
      <meshStandardMaterial color={color} metalness={metalness} roughness={roughness} />
    </mesh>
  );
}

function Block({
  u,
  len,
  h,
  w,
  y0,
  color,
}: {
  u: number;
  len: number;
  h: number;
  w: number;
  y0: number;
  color: string;
}) {
  return (
    <mesh position={[ax(u), y0 + h / 2, 0]} castShadow receiveShadow>
      <boxGeometry args={[len, h, w]} />
      <meshStandardMaterial color={color} metalness={0.5} roughness={0.6} />
    </mesh>
  );
}

// --------------------------------------------------------------------------
// Marcador de sensor sobre um mancal
// --------------------------------------------------------------------------
function BearingSensor({
  point,
  u,
  status,
  isActive,
  isHovered,
  onClick,
  onHover,
}: {
  point: BenchPoint;
  u: number;
  status: string;
  isActive: boolean;
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

  // O sensor fica no TOPO do mancal (como na bancada real).
  const yTop = CENTERLINE + BEARING.r + mm(30);

  return (
    <group position={[ax(u), yTop, 0]}>
      {/* Haste do sensor até o mancal */}
      <mesh position={[0, -mm(22), 0]}>
        <cylinderGeometry args={[mm(4), mm(4), mm(44), 10]} />
        <meshStandardMaterial color={color} transparent opacity={0.7} />
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
        scale={isActive ? 1.35 : isHovered ? 1.15 : 1}
        castShadow
      >
        <sphereGeometry args={[mm(26), 20, 20]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isActive ? 0.85 : 0.35}
          roughness={0.25}
          metalness={0.3}
        />
      </mesh>

      {show && (
        <Html distanceFactor={1.6} position={[0, mm(75), 0]} center style={{ pointerEvents: "none" }}>
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
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2, color }}>
              {point.label}
            </div>
            <div style={{ color: "#64748b", fontSize: 11, marginBottom: 8 }}>
              {point.tag} · sensor IO-Link
            </div>
            {latest.isLoading && <div style={{ color: "#475569" }}>Carregando…</div>}
            {latest.data?.readings.map((r) => {
              const isTemp = r.variable === "Temperatura";
              const isVel = r.variable === "Vibracao_Velocidade_RMS";
              const isAcc = r.variable === "Vibracao_Aceleracao_RMS";
              return (
                <div
                  key={r.variable}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 14,
                    padding: "2px 0",
                  }}
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
  onSelect,
}: {
  points: BenchPoint[];
  statusOf: (tag: string) => string;
  activeTag: string | null;
  onSelect: (tag: string) => void;
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

  // Leve rotação do eixo para dar vida (máquina girando). O cilindro tem eixo
  // local Y, então o grupo pai o deita e giramos o mesh em torno do próprio Y.
  const shaftRef = useRef<THREE.Mesh>(null);
  useFrame(() => {
    if (shaftRef.current) shaftRef.current.rotation.y += 0.02;
  });

  const uOf = (p: BenchPoint) => (p.side === "bomba" ? BEARING_A_U : BEARING_B_U);

  return (
    <>
      <PerspectiveCamera makeDefault position={[0.35, 0.95, 1.55]} fov={45} />
      <OrbitControls
        enablePan={false}
        target={[0, CENTERLINE * 0.85, 0]}
        minDistance={0.9}
        maxDistance={3.2}
        maxPolarAngle={Math.PI * 0.5}
      />

      <ambientLight intensity={0.5} />
      <directionalLight position={[1.5, 2.5, 1.5]} intensity={1.25} castShadow />
      <directionalLight position={[-1.5, 1.2, -1]} intensity={0.35} color="#93c5fd" />

      {/* --- Skid / base --- */}
      <Block u={600} len={SKID.len} h={SKID.h} w={SKID.w} y0={0} color="#3f4855" />
      <Block u={600} len={PLATE.len} h={PLATE.h} w={PLATE.w} y0={PLATE.y} color="#4b5563" />

      {/* --- Bomba --- */}
      <Block
        u={PUMP_BODY.u}
        len={PUMP_BODY.len}
        h={PUMP_BODY.h}
        w={PUMP_BODY.w}
        y0={PUMP_BODY.y0}
        color={DARK}
      />
      <Tube u={PUMP_VOLUTE.u} r={PUMP_VOLUTE.r} len={PUMP_VOLUTE.len} color="#6b7280" />
      <Tube u={PUMP_INLET.u} r={PUMP_INLET.r} len={PUMP_INLET.len} color={STEEL} />

      {/* Suporte vertical + placa superior (instrumentação) */}
      <Block u={STAND.u} len={STAND.s} h={STAND.h} w={STAND.s} y0={STAND.y0} color={STEEL} />
      <Block u={TOP_PLATE.u} len={TOP_PLATE.s} h={TOP_PLATE.h} w={TOP_PLATE.s} y0={TOP_PLATE.y0} color={DARK} />

      {/* --- Acoplamento / eixo / mancais --- */}
      <Tube u={COUPLING.u} r={COUPLING.r} len={COUPLING.len} color="#9aa4b2" roughness={0.35} />
      <group position={[ax(SHAFT.u), CENTERLINE, 0]} rotation={[0, 0, Math.PI / 2]}>
        <mesh ref={shaftRef} castShadow>
          <cylinderGeometry args={[SHAFT.r, SHAFT.r, SHAFT.len, 24]} />
          <meshStandardMaterial color="#cbd5e1" metalness={0.95} roughness={0.2} />
        </mesh>
      </group>
      <Tube u={BEARING_A_U} r={BEARING.r} len={BEARING.len} color={BEARING_C} roughness={0.5} />
      <Tube u={BEARING_B_U} r={BEARING.r} len={BEARING.len} color={BEARING_C} roughness={0.5} />

      {/* --- Motor (azul, como o real) --- */}
      <Tube u={MOTOR_CAP_F_U} r={MOTOR_CAP.r} len={MOTOR_CAP.len} color="#28598f" />
      <Tube u={MOTOR.u} r={MOTOR.r} len={MOTOR.len} color={MOTOR_BLUE} roughness={0.5} />
      <Tube u={MOTOR_CAP_R_U} r={MOTOR_CAP.r} len={MOTOR_CAP.len} color="#28598f" />
      <Block
        u={MOTOR_FEET.u}
        len={MOTOR_FEET.len}
        h={MOTOR_FEET.h}
        w={MOTOR_FEET.w}
        y0={MOTOR_FEET.y0}
        color={DARK}
      />

      {/* --- Sensores nos dois mancais --- */}
      {points.map((p) => (
        <BearingSensor
          key={p.tag}
          point={p}
          u={uOf(p)}
          status={statusOf(p.tag)}
          isActive={activeTag === p.tag}
          isHovered={hovered === p.tag}
          onClick={() => onSelect(p.tag)}
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
  const [selected, setSelected] = useState<string | null>(activeTag ?? null);

  // Status de cada mancal vem do próprio ativo correspondente.
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
            onSelect={(t) => setSelected((cur) => (cur === t ? null : t))}
          />
        </Canvas>

        <div className="pointer-events-none absolute left-3 top-3 rounded-md bg-slate-900/85 px-2.5 py-1.5">
          <p className="text-[11px] font-semibold text-slate-200">Bancada de bomba de teste</p>
          <p className="text-[10px] text-slate-500">
            Geometria do CAD Forzy · 1200 × 500 × 817 mm
          </p>
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
