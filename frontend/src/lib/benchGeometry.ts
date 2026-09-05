/**
 * Bancada de bomba de teste da Forzy — geometria e pontos de medição.
 *
 * A malha 3D vem do CAD REAL: `ChallengeForzy-bomba-teste.stp` (AVEVA,
 * ISO-10303 AP203, mm) foi tesselado com OpenCascade e exportado para
 * `public/models/bomba-teste.glb` (17 sólidos, ~12k triângulos).
 *
 * As medidas abaixo foram extraídas da MALHA TESSELADA, não dos pontos de
 * controle das B-splines — estes ficam fora da superfície e inflavam os
 * diâmetros em ~55% (o motor "media" ⌀412 mm quando na verdade é ⌀265).
 *
 * Conjunto: 1200 (comprimento) × 500 (largura) × 817 (altura) mm, com a linha
 * de centro do eixo a 550 mm do piso do skid.
 *
 * MTR-F01 e MTR-F02 NÃO são dois motores: são os DOIS MANCAIS (⌀58 × 19 mm —
 * as únicas duas peças idênticas do conjunto) que flanqueiam o eixo central.
 * Um equipamento, dois pontos de medição IO-Link.
 */

/** Modelo tesselado a partir do STEP entregue pela Forzy. */
export const BENCH_GLB = "/models/bomba-teste.glb";

/** mm -> metros. */
export const mm = (v: number) => v / 1000;

/**
 * `u` = posição ao longo do eixo da máquina, em mm a partir da extremidade da
 * bomba (0..1200). Converte para a coordenada X local (metros, 0 = centro).
 */
export const axPos = (u: number) => (u - 600) / 1000;

/** Altura da linha de centro do eixo (m) — confirmada na malha. */
export const CENTERLINE = 0.55;

/** Extensão do conjunto (m), como exportado no GLB (já centrado em X/Z). */
export const BENCH_SIZE = { length: 1.2, height: 0.817, depth: 0.5 } as const;

/** Medidas reais por peça (m), medidas na malha tesselada. */
export const BENCH = {
  skid: { len: 1.2, h: 0.21, w: 0.5, u: 600, y0: 0 },
  plate: { len: 1.071, h: 0.086, w: 0.381, u: 600, y0: 0.21 },
  pumpInlet: { r: 0.0635, len: 0.018, u: 119.5 },
  pumpVolute: { r: 0.1475, len: 0.058, u: 214.5 },
  pumpBody: { len: 0.058, h: 0.34, w: 0.295, u: 214.5, y0: 0.21 },
  stand: { s: 0.034, h: 0.267, u: 214.5, y0: 0.5365 },
  topPlate: { s: 0.108, h: 0.014, u: 214.5, y0: 0.803 },
  coupling: { r: 0.043, len: 0.2, u: 343.3 },
  /** Os dois mancais — únicas peças idênticas do conjunto. */
  bearing: { r: 0.029, len: 0.019 },
  shaft: { r: 0.0095, len: 0.211, u: 548.6 },
  motor: { r: 0.1325, len: 0.3, u: 872.8 },
  motorCap: { r: 0.1325, len: 0.069 },
  motorCapFU: 688.3,
  motorCapRU: 1057.2,
  motorFeet: { len: 0.3, h: 0.34, w: 0.265, u: 872.8, y0: 0.21 },
} as const;

/** Posição (u, mm) de cada mancal no eixo. */
export const BEARING_A_U = 500.9; // lado bomba
export const BEARING_B_U = 596.3; // lado motor

/** Modelo do conjunto, conforme a montagem no CAD. */
export const BENCH_MODEL = "Bancada bomba de teste R11.06-2130-B01A";

/** Ponto de medição (mancal) mapeado a uma TAG de telemetria. */
export interface BenchPoint {
  tag: string;
  label: string;
  side: "bomba" | "motor";
}

export const DEFAULT_BENCH_POINTS: BenchPoint[] = [
  { tag: "MTR-F01", label: "Mancal lado bomba", side: "bomba" },
  { tag: "MTR-F02", label: "Mancal lado motor", side: "motor" },
];

/** TAGs que são pontos de medição da bancada (não motores independentes). */
export const BENCH_TAGS: readonly string[] = DEFAULT_BENCH_POINTS.map((p) => p.tag);

/** Posição no eixo do mancal correspondente a um ponto. */
export const bearingU = (p: BenchPoint) => (p.side === "bomba" ? BEARING_A_U : BEARING_B_U);

export const BENCH_STATUS_COLOR: Record<string, string> = {
  ok: "#22c55e",
  warning: "#f59e0b",
  critical: "#ef4444",
  unknown: "#64748b",
};
