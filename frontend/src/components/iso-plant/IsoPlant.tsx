"use client";

// Planta isometrica 3D (three.js / R3F). Cada ativo com coordenada vira uma
// maquina no chao de fabrica, posicionada por (position_x, position_y) ∈ [0,1].
// O motor "heroi" (o de maior potencia) usa o modelo real /models/motor.glb
// quando presente; caso contrario, uma malha procedural estilizada.
// Carregado dinamicamente (ssr: false) pela pagina da planta.

import { ContactShadows, Html, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { ArrowRight, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import {
  BEARING_A_U,
  BEARING_B_U,
  BENCH,
  BENCH_TAGS,
  axPos,
  bearingU,
  DEFAULT_BENCH_POINTS,
} from "@/lib/benchGeometry";
import type { Asset } from "@/types";

// -- dados de apoio ---------------------------------------------------------

const STATUS_COLOR: Record<string, string> = {
  ok: "#22c55e",
  warning: "#f59e0b",
  critical: "#ef4444",
  unknown: "#64748b",
};

const STATUS_LABEL: Record<string, string> = {
  ok: "Operacional",
  warning: "Atenção",
  critical: "Crítico",
  unknown: "Sem dados",
};

// Mundo (proporcao ~ da planta baixa 1000x640).
const WORLD_W = 30;
const WORLD_D = 18;
const MOTOR_GLB = "/models/motor.glb";

/** (x,y) normalizado -> coordenadas do chao (x, z). */
function toFloor(px: number | null, py: number | null): [number, number] {
  return [((px ?? 0.5) - 0.5) * WORLD_W, ((py ?? 0.5) - 0.5) * WORLD_D];
}

function statusColor(status: string): string {
  return STATUS_COLOR[status] ?? STATUS_COLOR.unknown;
}

// -- motor procedural (fallback / maquinas nao-heroi) -----------------------

function ProceduralMotor({ tint, spin }: { tint: string; spin: boolean }) {
  const fan = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (spin && fan.current) fan.current.rotation.x += delta * 3.2;
  });

  const body = useMemo(
    () => ({ color: new THREE.Color("#64748b").lerp(new THREE.Color(tint), 0.35) }),
    [tint],
  );
  const fins = useMemo(() => Array.from({ length: 12 }, (_, i) => (i / 12) * Math.PI * 2), []);

  return (
    <group>
      {/* base / pes */}
      <mesh position={[0, 0.08, 0]} castShadow receiveShadow>
        <boxGeometry args={[3.2, 0.16, 1.5]} />
        <meshStandardMaterial color="#334155" metalness={0.3} roughness={0.7} />
      </mesh>
      {/* carcaca (estator) com aletas */}
      <group position={[0, 0.95, 0]}>
        <mesh rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.8, 0.8, 2.2, 32]} />
          <meshStandardMaterial {...body} metalness={0.5} roughness={0.5} />
        </mesh>
        {fins.map((a) => (
          <group key={a} rotation={[a, 0, 0]}>
            <mesh position={[0, 0.88, 0]}>
              <boxGeometry args={[2.05, 0.16, 0.05]} />
              <meshStandardMaterial {...body} metalness={0.5} roughness={0.5} />
            </mesh>
          </group>
        ))}
        {/* eixo + flange (dianteira) */}
        <mesh position={[1.55, 0, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.13, 0.13, 1.0, 16]} />
          <meshStandardMaterial color="#cbd5e1" metalness={0.8} roughness={0.25} />
        </mesh>
        {/* ventoinha (traseira) */}
        <group ref={fan} position={[-1.35, 0, 0]}>
          <mesh rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.26, 0.26, 0.14, 16]} />
            <meshStandardMaterial {...body} />
          </mesh>
          {Array.from({ length: 6 }, (_, i) => (i / 6) * Math.PI * 2).map((a) => (
            <group key={a} rotation={[a, 0, 0]}>
              <mesh position={[0, 0.42, 0]}>
                <boxGeometry args={[0.08, 0.6, 0.18]} />
                <meshStandardMaterial {...body} />
              </mesh>
            </group>
          ))}
        </group>
        {/* caixa de ligacao */}
        <mesh position={[0.2, 0.95, 0]} castShadow>
          <boxGeometry args={[0.6, 0.42, 0.55]} />
          <meshStandardMaterial {...body} metalness={0.4} roughness={0.6} />
        </mesh>
      </group>
    </group>
  );
}

// -- motor real via glTF (quando /models/motor.glb existe) ------------------

function GlbMotor() {
  const { scene } = useGLTF(MOTOR_GLB);
  // Normaliza escala/posicao: encaixa numa altura alvo e apoia no chao.
  const model = useMemo(() => {
    const clone = scene.clone(true);
    const box = new THREE.Box3().setFromObject(clone);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);
    const scale = 2.4 / Math.max(size.y, 0.001);
    clone.scale.setScalar(scale);
    clone.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);
    clone.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
      }
    });
    return clone;
  }, [scene]);
  return <primitive object={model} />;
}

// -- uma maquina no chao ----------------------------------------------------

interface MachineProps {
  asset: Asset;
  hero: boolean;
  useGlb: boolean;
  selected: boolean;
  anySelected: boolean;
  onSelect: (tag: string) => void;
}

function Machine({ asset, hero, useGlb, selected, anySelected, onSelect }: MachineProps) {
  const [x, z] = toFloor(asset.position_x, asset.position_y);
  const color = statusColor(asset.status);
  const scale = hero ? 1 : 0.62;
  const dimmed = anySelected && !selected;

  return (
    <group
      position={[x, 0, z]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(asset.tag);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => (document.body.style.cursor = "auto")}
    >
      {/* corpo da maquina (escalado); a badge fica fora, em altura de mundo */}
      <group scale={scale}>
        {/* anel de status no piso */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
          <ringGeometry args={[1.85, 2.15, 48]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={selected ? 0.95 : dimmed ? 0.3 : 0.5}
            side={THREE.DoubleSide}
          />
        </mesh>
        {selected && (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
            <circleGeometry args={[1.85, 48]} />
            <meshBasicMaterial color={color} transparent opacity={0.1} />
          </mesh>
        )}

        {hero && useGlb ? (
          <Suspense fallback={<ProceduralMotor tint={color} spin={asset.status === "ok"} />}>
            <GlbMotor />
          </Suspense>
        ) : (
          <ProceduralMotor tint={color} spin={hero && asset.status === "ok"} />
        )}
      </group>

      {/* Badge com tamanho de tela fixo (sem distanceFactor, para nao inflar a
          mais proxima). Escondida quando este ativo esta selecionado - o card
          ja mostra os dados - e esmaecida quando outro esta selecionado. */}
      {!selected && (
        <Html position={[0, hero ? 3.8 : 2.7, 0]} center zIndexRange={[20, 0]}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onSelect(asset.tag);
            }}
            className="flex items-center gap-1.5 whitespace-nowrap rounded-full border bg-slate-900/85 px-2.5 py-1 text-[11px] font-medium text-slate-100 shadow-md backdrop-blur transition"
            style={{ borderColor: color, opacity: dimmed ? 0.35 : 1 }}
          >
            <span className="relative flex h-2 w-2">
              {asset.status === "critical" && (
                <span
                  className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-70"
                  style={{ backgroundColor: color }}
                />
              )}
              <span className="inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
            </span>
            <span className="font-semibold">{asset.tag}</span>
            <span style={{ color }}>{STATUS_LABEL[asset.status] ?? asset.status}</span>
          </button>
        </Html>
      )}
    </group>
  );
}


// -- bancada de bomba de teste (equipamento real da Forzy) ------------------
// MTR-F01 e MTR-F02 nao sao dois motores: sao os dois MANCAIS deste conjunto.
// Geometria nas medidas reais do CAD (@/lib/benchGeometry), escalada para o
// mundo isometrico.

/** Unidades de mundo por metro real. */
const BENCH_SCALE = 3.0;
/** Linha de centro do eixo (m). */
const BENCH_CL = 0.55;
const bx = (u: number) => axPos(u) * BENCH_SCALE;
const bs = (m: number) => m * BENCH_SCALE;

function BenchTube({
  u,
  r,
  len,
  color,
  y = BENCH_CL,
  roughness = 0.45,
}: {
  u: number;
  r: number;
  len: number;
  color: string;
  y?: number;
  roughness?: number;
}) {
  return (
    <mesh position={[bx(u), bs(y), 0]} rotation={[0, 0, Math.PI / 2]} castShadow receiveShadow>
      <cylinderGeometry args={[bs(r), bs(r), bs(len), 28]} />
      <meshStandardMaterial color={color} metalness={0.7} roughness={roughness} />
    </mesh>
  );
}

function BenchBlock({
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
    <mesh position={[bx(u), bs(y0 + h / 2), 0]} castShadow receiveShadow>
      <boxGeometry args={[bs(len), bs(h), bs(w)]} />
      <meshStandardMaterial color={color} metalness={0.45} roughness={0.6} />
    </mesh>
  );
}

/** O conjunto motor-bomba completo, em escala de mundo. */
function ProceduralBench({ spin }: { spin: boolean }) {
  const shaft = useRef<THREE.Mesh>(null);
  useFrame((_, delta) => {
    if (spin && shaft.current) shaft.current.rotation.y += delta * 2.4;
  });

  return (
    <group>
      {/* skid + placa de base */}
      <BenchBlock u={600} len={BENCH.skid.len} h={BENCH.skid.h} w={BENCH.skid.w} y0={0} color="#3f4855" />
      <BenchBlock
        u={600}
        len={BENCH.plate.len}
        h={BENCH.plate.h}
        w={BENCH.plate.w}
        y0={BENCH.plate.y0}
        color="#4b5563"
      />

      {/* bomba */}
      <BenchBlock
        u={BENCH.pumpBody.u}
        len={BENCH.pumpBody.len}
        h={BENCH.pumpBody.h}
        w={BENCH.pumpBody.w}
        y0={BENCH.pumpBody.y0}
        color="#2d3748"
      />
      <BenchTube u={BENCH.pumpVolute.u} r={BENCH.pumpVolute.r} len={BENCH.pumpVolute.len} color="#6b7280" />
      <BenchTube u={BENCH.pumpInlet.u} r={BENCH.pumpInlet.r} len={BENCH.pumpInlet.len} color="#8a94a3" />

      {/* suporte vertical + placa de instrumentacao */}
      <BenchBlock
        u={BENCH.stand.u}
        len={BENCH.stand.s}
        h={BENCH.stand.h}
        w={BENCH.stand.s}
        y0={BENCH.stand.y0}
        color="#8a94a3"
      />
      <BenchBlock
        u={BENCH.topPlate.u}
        len={BENCH.topPlate.s}
        h={BENCH.topPlate.h}
        w={BENCH.topPlate.s}
        y0={BENCH.topPlate.y0}
        color="#2d3748"
      />

      {/* acoplamento, eixo e os DOIS MANCAIS */}
      <BenchTube u={BENCH.coupling.u} r={BENCH.coupling.r} len={BENCH.coupling.len} color="#9aa4b2" />
      <group position={[bx(BENCH.shaft.u), bs(BENCH_CL), 0]} rotation={[0, 0, Math.PI / 2]}>
        <mesh ref={shaft} castShadow>
          <cylinderGeometry args={[bs(BENCH.shaft.r), bs(BENCH.shaft.r), bs(BENCH.shaft.len), 20]} />
          <meshStandardMaterial color="#cbd5e1" metalness={0.9} roughness={0.2} />
        </mesh>
      </group>
      <BenchTube u={BEARING_A_U} r={BENCH.bearing.r} len={BENCH.bearing.len} color="#1f2937" roughness={0.5} />
      <BenchTube u={BEARING_B_U} r={BENCH.bearing.r} len={BENCH.bearing.len} color="#1f2937" roughness={0.5} />

      {/* motor (azul, como o real) */}
      <BenchTube u={BENCH.motorCapFU} r={BENCH.motorCap.r} len={BENCH.motorCap.len} color="#28598f" />
      <BenchTube u={BENCH.motor.u} r={BENCH.motor.r} len={BENCH.motor.len} color="#2f6fb3" roughness={0.5} />
      <BenchTube u={BENCH.motorCapRU} r={BENCH.motorCap.r} len={BENCH.motorCap.len} color="#28598f" />
      <BenchBlock
        u={BENCH.motorFeet.u}
        len={BENCH.motorFeet.len}
        h={BENCH.motorFeet.h}
        w={BENCH.motorFeet.w}
        y0={BENCH.motorFeet.y0}
        color="#2d3748"
      />
    </group>
  );
}

/** A bancada no chao da planta, com um sensor clicavel sobre cada mancal. */
function BenchMachine({
  assets,
  selectedTag,
  anySelected,
  onSelect,
}: {
  assets: Asset[];
  selectedTag: string | null;
  anySelected: boolean;
  onSelect: (tag: string) => void;
}) {
  // Posicao do conjunto = media das coordenadas dos dois mancais.
  const px = assets.reduce((acc, a) => acc + (a.position_x ?? 0.5), 0) / assets.length;
  const py = assets.reduce((acc, a) => acc + (a.position_y ?? 0.5), 0) / assets.length;
  const [x, z] = toFloor(px, py);

  // Anel do conjunto = pior status entre os mancais.
  const rank = (st: string) => (st === "critical" ? 3 : st === "warning" ? 2 : st === "ok" ? 1 : 0);
  const worst = assets.reduce((w, a) => (rank(a.status) > rank(w) ? a.status : w), "unknown");
  const ringColor = statusColor(worst);
  const benchSelected = assets.some((a) => a.tag === selectedTag);
  const dimmed = anySelected && !benchSelected;

  return (
    <group position={[x, 0, z]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[2.4, 2.75, 56]} />
        <meshBasicMaterial
          color={ringColor}
          transparent
          opacity={benchSelected ? 0.95 : dimmed ? 0.3 : 0.5}
          side={THREE.DoubleSide}
        />
      </mesh>

      <ProceduralBench spin={worst !== "unknown"} />

      {/* um sensor clicavel sobre cada mancal */}
      {DEFAULT_BENCH_POINTS.map((point) => {
        const asset = assets.find((a) => a.tag === point.tag);
        if (!asset) return null;
        const color = statusColor(asset.status);
        const isSel = selectedTag === point.tag;
        const yTop = bs(BENCH_CL + BENCH.bearing.r + 0.05);
        return (
          <group key={point.tag} position={[bx(bearingU(point)), yTop, 0]}>
            <mesh
              onClick={(e) => {
                e.stopPropagation();
                onSelect(point.tag);
              }}
              onPointerOver={(e) => {
                e.stopPropagation();
                document.body.style.cursor = "pointer";
              }}
              onPointerOut={() => (document.body.style.cursor = "auto")}
              scale={isSel ? 1.5 : 1}
              castShadow
            >
              <sphereGeometry args={[0.16, 16, 16]} />
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={isSel ? 0.9 : 0.4}
                roughness={0.25}
              />
            </mesh>
            {!isSel && (
              // Os mancais distam so ~95 mm no real: separa os badges em X e Y
              // para nao se sobreporem na planta.
              <Html
                position={point.side === "bomba" ? [-0.75, 0.45, 0] : [0.75, 1.15, 0]}
                center
                zIndexRange={[20, 0]}
              >
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect(point.tag);
                  }}
                  className="flex items-center gap-1.5 whitespace-nowrap rounded-full border bg-slate-900/85 px-2 py-0.5 text-[10px] font-medium text-slate-100 shadow-md backdrop-blur transition"
                  style={{ borderColor: color, opacity: dimmed ? 0.35 : 1 }}
                >
                  <span className="inline-flex h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
                  <span className="font-semibold">{point.tag}</span>
                </button>
              </Html>
            )}
          </group>
        );
      })}

      {/* rotulo do conjunto */}
      <Html position={[0, bs(1.35), 0]} center zIndexRange={[20, 0]}>
        <div
          className="whitespace-nowrap rounded-full border border-slate-700 bg-slate-900/85 px-2.5 py-1 text-[11px] font-semibold text-slate-100 shadow-md backdrop-blur"
          style={{ opacity: dimmed ? 0.4 : 1 }}
        >
          Bancada de bomba de teste
          <span className="ml-1.5 font-normal text-slate-400">· 2 mancais</span>
        </div>
      </Html>
    </group>
  );
}

// -- cena -------------------------------------------------------------------

function Scene({
  assets,
  benchAssets,
  heroTag,
  useGlb,
  selectedTag,
  onSelect,
}: {
  assets: Asset[];
  benchAssets: Asset[];
  heroTag: string | null;
  useGlb: boolean;
  selectedTag: string | null;
  onSelect: (tag: string | null) => void;
}) {
  return (
    <>
      <color attach="background" args={["#020617"]} />
      <fog attach="fog" args={["#020617", 26, 52]} />
      <ambientLight intensity={0.55} />
      <hemisphereLight intensity={0.35} color="#38bdf8" groundColor="#0f172a" />
      <directionalLight position={[10, 16, 8]} intensity={1.3} castShadow shadow-mapSize={[1024, 1024]}>
        <orthographicCamera attach="shadow-camera" args={[-18, 18, 18, -18, 0.1, 60]} />
      </directionalLight>
      <directionalLight position={[-10, 6, -8]} intensity={0.3} color="#67e8f9" />

      {/* chao */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, 0, 0]}
        receiveShadow
        onPointerMissed={() => onSelect(null)}
      >
        <planeGeometry args={[WORLD_W + 8, WORLD_D + 8]} />
        <meshStandardMaterial color="#0b1220" metalness={0.2} roughness={0.9} />
      </mesh>
      <gridHelper
        args={[Math.max(WORLD_W, WORLD_D) + 8, 32, "#1e293b", "#0f1729"]}
        position={[0, 0.01, 0]}
      />
      <ContactShadows position={[0, 0.02, 0]} scale={WORLD_W + 8} blur={2.2} opacity={0.5} far={12} />

      {benchAssets.length > 0 && (
        <BenchMachine
          assets={benchAssets}
          selectedTag={selectedTag}
          anySelected={selectedTag !== null}
          onSelect={onSelect}
        />
      )}

      {assets.map((asset) => (
        <Machine
          key={asset.id}
          asset={asset}
          hero={asset.tag === heroTag}
          useGlb={useGlb}
          selected={asset.tag === selectedTag}
          anySelected={selectedTag !== null}
          onSelect={onSelect}
        />
      ))}

      <OrbitControls
        makeDefault
        enableDamping
        enablePan={false}
        target={[0, 0.8, 0]}
        minDistance={12}
        maxDistance={40}
        minPolarAngle={0.35}
        maxPolarAngle={1.15}
      />
    </>
  );
}

// -- card de detalhe (overlay HTML) -----------------------------------------

function DetailCard({ asset, onClose }: { asset: Asset; onClose: () => void }) {
  const router = useRouter();
  const color = statusColor(asset.status);
  const specs: Array<[string, string]> = [
    ["Fabricante", asset.manufacturer ?? "—"],
    ["Modelo", asset.model ?? "—"],
    ["Potência", asset.power_kw != null ? `${asset.power_kw} kW` : "—"],
    ["Rotação", asset.nominal_rpm != null ? `${asset.nominal_rpm} rpm` : "—"],
  ];

  return (
    <div className="absolute bottom-4 left-4 z-40 w-72 rounded-xl border border-slate-700 bg-slate-900/95 p-4 shadow-2xl backdrop-blur">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{asset.asset_type}</p>
          <h3 className="text-lg font-semibold text-slate-100">{asset.name ?? asset.tag}</h3>
          <p className="text-xs text-slate-400">{asset.tag}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar"
          className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2 rounded-lg px-2 py-1.5" style={{ backgroundColor: `${color}1a` }}>
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-sm font-medium" style={{ color }}>
          {STATUS_LABEL[asset.status] ?? asset.status}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
        {specs.map(([k, v]) => (
          <div key={k}>
            <dt className="text-xs text-slate-500">{k}</dt>
            <dd className="text-slate-200">{v}</dd>
          </div>
        ))}
      </dl>

      <button
        type="button"
        onClick={() => router.push(`/asset/${asset.tag}`)}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
      >
        Abrir ativo
        <ArrowRight className="h-4 w-4" />
      </button>
    </div>
  );
}

// -- componente principal ---------------------------------------------------

export default function IsoPlant({ assets }: { assets: Asset[] }) {
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [glbOk, setGlbOk] = useState(false);

  // Motor "heroi": maior potencia (empate -> primeiro). Recebe o modelo real.
  const placed = useMemo(
    () => assets.filter((a) => a.position_x !== null && a.position_y !== null),
    [assets],
  );
  // A bancada (MTR-F01/F02) e UM equipamento com dois mancais: renderizada uma
  // unica vez, fora do laco das demais maquinas.
  const benchAssets = useMemo(() => placed.filter((a) => BENCH_TAGS.includes(a.tag)), [placed]);
  const otherAssets = useMemo(() => placed.filter((a) => !BENCH_TAGS.includes(a.tag)), [placed]);

  const heroTag = useMemo(() => {
    const motors = otherAssets.filter((a) => a.asset_type === "motor");
    const pool = motors.length ? motors : otherAssets;
    if (!pool.length) return null;
    return pool.reduce((best, a) => ((a.power_kw ?? 0) > (best.power_kw ?? 0) ? a : best)).tag;
  }, [otherAssets]);

  // Detecta o .glb sem quebrar a cena quando ausente (HEAD honesto).
  useEffect(() => {
    let alive = true;
    fetch(MOTOR_GLB, { method: "HEAD" })
      .then((r) => alive && setGlbOk(r.ok && (r.headers.get("content-type")?.includes("model") ?? true)))
      .catch(() => alive && setGlbOk(false));
    return () => {
      alive = false;
    };
  }, []);

  const selected = placed.find((a) => a.tag === selectedTag) ?? null;

  return (
    <div className="relative h-[70vh] min-h-[520px] w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ position: [0, 18, 25], fov: 32 }}
      >
        <Scene
          assets={otherAssets}
          benchAssets={benchAssets}
          heroTag={heroTag}
          useGlb={glbOk}
          selectedTag={selectedTag}
          onSelect={setSelectedTag}
        />
      </Canvas>

      {/* legenda */}
      <div className="pointer-events-none absolute right-4 top-4 z-40 flex flex-col gap-1 rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-300 backdrop-blur">
        {(["ok", "warning", "critical", "unknown"] as const).map((s) => (
          <div key={s} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: STATUS_COLOR[s] }} />
            {STATUS_LABEL[s]}
          </div>
        ))}
      </div>

      {selected && <DetailCard asset={selected} onClose={() => setSelectedTag(null)} />}

      {placed.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
          Nenhum ativo posicionado nesta planta.
        </div>
      )}
    </div>
  );
}
