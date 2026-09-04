"use client";

/**
 * MotorViewer3D
 * =============
 * Visualizador 3D interativo de um motor elétrico genérico com marcadores de
 * PONTOS DE MEDIÇÃO posicionados fisicamente (mancais DE/NDE, carcaça).
 *
 * Adaptado da contribuição do time: aqui os marcadores são pontos fixos do
 * motor (não uma entidade "sensor" no banco) e o popup usa a telemetria do
 * PRÓPRIO ATIVO (getLatest(assetTag)). Geometria procedural, sem binário.
 *
 * Tecnologia: @react-three/fiber + @react-three/drei (já usados na planta 3D).
 * Importe com dynamic({ ssr: false }) — depende de WebGL.
 */

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { getLatest } from "@/lib/api";

// --- Geometria do motor genérico (unidades Three.js ~ metros) ---
const BODY_RADIUS = 0.38;
const BODY_LENGTH = 1.2;
const SHAFT_RADIUS = 0.06;
const SHAFT_OVERHANG = 0.32;
const FIN_COUNT = 9;
const FIN_TUBE_RADIUS = 0.025;
const TERMINAL_BOX_W = 0.3;
const TERMINAL_BOX_H = 0.18;
const TERMINAL_BOX_D = 0.22;

const STATUS_COLOR: Record<string, string> = {
  ok: "#22c55e",
  warning: "#f59e0b",
  critical: "#ef4444",
  unknown: "#64748b",
};

/** Ponto de medição no motor (posição normalizada 0-1). */
export interface MotorMarker {
  id: string;
  label: string;
  position_label?: string;
  position_distance_mm?: number;
  status: string;
  /** 0 = lado acoplamento (frente), 1 = traseira (ventilador). */
  pos3d_x: number;
  /** posição circunferencial: 0 = topo, 0.5 = base. */
  pos3d_z: number;
}

/** Pontos de medição padrão de um motor (mancais + carcaça), na cor do status. */
export function defaultMotorMarkers(status: string): MotorMarker[] {
  return [
    {
      id: "DE",
      label: "Mancal dianteiro (DE)",
      position_label: "Lado acoplamento",
      position_distance_mm: 40,
      status,
      pos3d_x: 0.12,
      pos3d_z: 0,
    },
    {
      id: "NDE",
      label: "Mancal traseiro (NDE)",
      position_label: "Lado ventilador",
      position_distance_mm: 210,
      status,
      pos3d_x: 0.88,
      pos3d_z: 0,
    },
    {
      id: "CARC",
      label: "Carcaça / enrolamento",
      position_label: "Topo da carcaça",
      status,
      pos3d_x: 0.5,
      pos3d_z: 0,
    },
  ];
}

function markerTo3D(marker: MotorMarker): [number, number, number] {
  const x = marker.pos3d_x * BODY_LENGTH - BODY_LENGTH / 2;
  const angle = marker.pos3d_z * Math.PI * 2 - Math.PI / 2; // -π/2 = topo
  const r = BODY_RADIUS + 0.06;
  return [x, Math.sin(angle) * r, Math.cos(angle) * r];
}

// --- Peças do motor ---
function MotorBody() {
  return (
    <mesh rotation={[0, 0, Math.PI / 2]} receiveShadow castShadow>
      <cylinderGeometry args={[BODY_RADIUS, BODY_RADIUS, BODY_LENGTH, 48]} />
      <meshStandardMaterial color="#4a5568" roughness={0.55} metalness={0.7} />
    </mesh>
  );
}

function MotorShaft() {
  return (
    <>
      <mesh
        position={[-(BODY_LENGTH / 2 + SHAFT_OVERHANG / 2), 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[SHAFT_RADIUS, SHAFT_RADIUS, SHAFT_OVERHANG, 24]} />
        <meshStandardMaterial color="#94a3b8" roughness={0.3} metalness={0.9} />
      </mesh>
      <mesh
        position={[BODY_LENGTH / 2 + SHAFT_OVERHANG / 4, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[SHAFT_RADIUS, SHAFT_RADIUS, SHAFT_OVERHANG / 2, 24]} />
        <meshStandardMaterial color="#94a3b8" roughness={0.3} metalness={0.9} />
      </mesh>
    </>
  );
}

function CoolingFins() {
  return (
    <>
      {Array.from({ length: FIN_COUNT }).map((_, i) => {
        const x = -BODY_LENGTH / 2 + (i / (FIN_COUNT - 1)) * BODY_LENGTH;
        return (
          <mesh key={i} position={[x, 0, 0]} castShadow>
            <torusGeometry args={[BODY_RADIUS + 0.015, FIN_TUBE_RADIUS, 12, 48]} />
            <meshStandardMaterial color="#2d3748" roughness={0.6} metalness={0.6} />
          </mesh>
        );
      })}
    </>
  );
}

function TerminalBox() {
  return (
    <mesh position={[0, BODY_RADIUS + TERMINAL_BOX_H / 2, 0]} castShadow>
      <boxGeometry args={[TERMINAL_BOX_W, TERMINAL_BOX_H, TERMINAL_BOX_D]} />
      <meshStandardMaterial color="#2d3748" roughness={0.5} metalness={0.6} />
    </mesh>
  );
}

function EndCap({ side }: { side: "front" | "back" }) {
  const x = side === "front" ? -BODY_LENGTH / 2 : BODY_LENGTH / 2;
  return (
    <mesh position={[x, 0, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
      <circleGeometry args={[BODY_RADIUS, 48]} />
      <meshStandardMaterial
        color="#374151"
        roughness={0.5}
        metalness={0.7}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

// --- Marcador de ponto de medição ---
interface MarkerMeshProps {
  marker: MotorMarker;
  assetTag: string;
  position: [number, number, number];
  isActive: boolean;
  isHovered: boolean;
  onClick: () => void;
  onHover: (v: boolean) => void;
}

function MarkerMesh({
  marker,
  assetTag,
  position,
  isActive,
  isHovered,
  onClick,
  onHover,
}: MarkerMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = STATUS_COLOR[marker.status] ?? STATUS_COLOR.unknown;
  const scale = isActive ? 1.5 : isHovered ? 1.25 : 1;

  useFrame(() => {
    if (!meshRef.current) return;
    if (marker.status === "critical" || marker.status === "warning") {
      const t = Date.now() / 600;
      meshRef.current.scale.setScalar(scale * (1 + Math.sin(t) * 0.12));
    } else {
      meshRef.current.scale.setScalar(scale);
    }
  });

  const showPopup = isHovered || isActive;
  // Telemetria do proprio ativo (dedupe por queryKey entre marcadores).
  const latestQuery = useQuery({
    queryKey: ["latest", assetTag],
    queryFn: () => getLatest(assetTag),
    refetchInterval: 4000,
    enabled: showPopup,
  });

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(true);
        }}
        onPointerOut={() => onHover(false)}
        castShadow
      >
        <sphereGeometry args={[0.07, 16, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isActive ? 0.8 : 0.4}
          roughness={0.2}
          metalness={0.3}
        />
      </mesh>

      <mesh position={[0, -0.04, 0]}>
        <cylinderGeometry args={[0.008, 0.008, 0.08, 8]} />
        <meshStandardMaterial color={color} opacity={0.6} transparent />
      </mesh>

      {showPopup && (
        <Html distanceFactor={4} position={[0, 0.18, 0]} center style={{ pointerEvents: "none" }}>
          <div
            style={{
              background: "rgba(15,23,42,0.97)",
              border: `1px solid ${color}44`,
              borderLeft: `3px solid ${color}`,
              borderRadius: 8,
              padding: "10px 14px",
              minWidth: 200,
              fontFamily: "system-ui, sans-serif",
              fontSize: 12,
              color: "#e2e8f0",
              boxShadow: `0 4px 24px ${color}22`,
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4, color }}>
              {marker.label}
            </div>
            <div style={{ color: "#64748b", fontSize: 11, marginBottom: 8 }}>
              {marker.position_label}
              {marker.position_distance_mm != null && (
                <span style={{ marginLeft: 6, color: "#94a3b8" }}>
                  · {marker.position_distance_mm} mm do acoplamento
                </span>
              )}
            </div>

            {latestQuery.isLoading && <div style={{ color: "#475569" }}>Carregando telemetria…</div>}

            {latestQuery.data?.readings.map((r) => {
              const isVibVel = r.variable === "Vibracao_Velocidade_RMS";
              const isVibAcc = r.variable === "Vibracao_Aceleracao_RMS";
              const isTemp = r.variable === "Temperatura";
              const priority = isVibVel || isVibAcc || isTemp;
              const valColor =
                isTemp && r.value > 95 ? "#ef4444" : isTemp && r.value > 80 ? "#f59e0b" : "#e2e8f0";
              return (
                <div
                  key={r.variable}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: "2px 0",
                    opacity: priority ? 1 : 0.65,
                    fontWeight: priority ? 600 : 400,
                  }}
                >
                  <span style={{ color: "#94a3b8" }}>
                    {isVibVel
                      ? "Vibração vel. RMS"
                      : isVibAcc
                        ? "Vibração acel. RMS"
                        : r.variable}
                  </span>
                  <span style={{ color: valColor }}>
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

// --- Cena 3D ---
function MotorScene({
  markers,
  assetTag,
  activeId,
  onSelect,
}: {
  markers: MotorMarker[];
  assetTag: string;
  activeId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const { gl } = useThree();

  const handleHover = useCallback(
    (id: string, v: boolean) => {
      gl.domElement.style.cursor = v ? "pointer" : "default";
      setHoveredId(v ? id : null);
    },
    [gl],
  );

  const placed = useMemo(
    () => markers.map((m) => ({ marker: m, pos: markerTo3D(m) })),
    [markers],
  );

  return (
    <>
      <PerspectiveCamera makeDefault position={[0, 1.4, 2.8]} fov={42} />
      <OrbitControls enablePan={false} minDistance={1.5} maxDistance={5} maxPolarAngle={Math.PI * 0.85} />

      <ambientLight intensity={0.45} />
      <directionalLight position={[3, 5, 3]} intensity={1.2} castShadow />
      <directionalLight position={[-3, 2, -2]} intensity={0.4} color="#93c5fd" />
      <pointLight position={[0, 2, 0]} intensity={0.3} color="#e2e8f0" />

      <group>
        <MotorBody />
        <CoolingFins />
        <MotorShaft />
        <TerminalBox />
        <EndCap side="front" />
        <EndCap side="back" />
      </group>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -BODY_RADIUS - 0.02, 0]} receiveShadow>
        <planeGeometry args={[8, 8]} />
        <shadowMaterial opacity={0.18} />
      </mesh>

      {placed.map(({ marker, pos }) => (
        <MarkerMesh
          key={marker.id}
          marker={marker}
          assetTag={assetTag}
          position={pos}
          isActive={activeId === marker.id}
          isHovered={hoveredId === marker.id}
          onClick={() => onSelect(activeId === marker.id ? null : marker.id)}
          onHover={(v) => handleHover(marker.id, v)}
        />
      ))}
    </>
  );
}

// --- Legenda lateral ---
function MarkerLegend({
  markers,
  activeId,
  onSelect,
}: {
  markers: MotorMarker[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5 text-xs">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
        Pontos de medição
      </p>
      {markers.map((m) => {
        const color = STATUS_COLOR[m.status] ?? STATUS_COLOR.unknown;
        const isActive = activeId === m.id;
        return (
          <button
            key={m.id}
            type="button"
            onClick={() => onSelect(m.id)}
            className="flex items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-slate-800"
            style={{ background: isActive ? "rgba(56,189,248,0.08)" : undefined }}
          >
            <span
              className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ background: color, boxShadow: `0 0 6px ${color}` }}
            />
            <span>
              <span className="block font-medium text-slate-300">{m.label}</span>
              {m.position_label && (
                <span className="block text-[10px] text-slate-600">{m.position_label}</span>
              )}
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
            <span className="text-slate-500 capitalize">
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
  );
}

export interface MotorViewer3DProps {
  /** Ativo cuja telemetria alimenta os popups dos marcadores. */
  assetTag: string;
  /** Status do ativo — colore os marcadores (ok/warning/critical/unknown). */
  status?: string;
  /** Pontos de medição; se omitido, usa os padrões (mancais + carcaça). */
  markers?: MotorMarker[];
}

export function MotorViewer3D({ assetTag, status = "unknown", markers }: MotorViewer3DProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const list = useMemo(() => markers ?? defaultMotorMarkers(status), [markers, status]);

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      <div
        className="relative flex-1 overflow-hidden rounded-xl border border-slate-800 bg-slate-950"
        style={{ minHeight: 340 }}
      >
        <Canvas shadows gl={{ antialias: true }}>
          <color attach="background" args={["#020617"]} />
          <fog attach="fog" args={["#020617", 6, 14]} />
          <MotorScene
            markers={list}
            assetTag={assetTag}
            activeId={activeId}
            onSelect={setActiveId}
          />
        </Canvas>

        <div className="pointer-events-none absolute bottom-3 left-0 right-0 flex justify-center">
          <span className="rounded-full bg-slate-900/80 px-3 py-1 text-[10px] text-slate-600">
            Arraste para girar · Scroll para zoom · Clique no ponto para a leitura
          </span>
        </div>
      </div>

      <div className="w-full lg:w-52">
        <MarkerLegend markers={list} activeId={activeId} onSelect={(id) => setActiveId(id)} />
        <p className="mt-3 text-[10px] text-slate-700">
          Modelo ilustrativo — os pontos representam mancais e carcaça; as leituras
          são a telemetria do ativo.
        </p>
      </div>
    </div>
  );
}
