/**
 * Medidas REAIS da bancada de bomba de teste da Forzy.
 *
 * Extraídas do CAD entregue pela Forzy (`ChallengeForzy-bomba-teste.stp`,
 * AVEVA / ISO-10303 AP203, unidades em mm). Fonte única: consumido tanto pelo
 * gêmeo 3D do ativo (PumpBenchViewer3D) quanto pela planta isométrica.
 *
 * Conjunto: 1200 (comprimento) × 500 (largura) × 817 (altura) mm, com a linha
 * de centro do eixo a 550 mm do piso do skid.
 *
 * MTR-F01 e MTR-F02 NÃO são dois motores: são os DOIS MANCAIS (⌀89,6 × 19,2 mm
 * — as únicas duas peças idênticas do conjunto) que flanqueiam o eixo central.
 * Um equipamento, dois pontos de medição IO-Link.
 */

/** mm -> metros. */
export const mm = (v: number) => v / 1000;

/**
 * `u` = posição ao longo do eixo da máquina, em mm a partir da extremidade da
 * bomba (0..1200). Converte para a coordenada X local (metros, 0 = centro).
 */
export const axPos = (u: number) => (u - 600) / 1000;

/** Altura da linha de centro do eixo (m). */
export const CENTERLINE = mm(550);

export const BENCH = {
  skid: { len: mm(1200), h: mm(210), w: mm(500), u: 600 },
  plate: { len: mm(1071), h: mm(85.9), w: mm(381), u: 600, y0: mm(210) },
  pumpVolute: { r: mm(459.1 / 2), len: mm(57.6), u: 214.5 },
  pumpBody: { len: mm(57.6), h: mm(340), w: mm(295.1), u: 214.5, y0: mm(210) },
  pumpInlet: { r: mm(197.6 / 2), len: mm(18), u: 119.5 },
  coupling: { r: mm(134.4 / 2), len: mm(200), u: 343.3 },
  shaft: { r: mm(29.9 / 2), len: mm(210.6), u: 548.6 },
  /** Os dois mancais — únicas peças idênticas do conjunto. */
  bearing: { r: mm(89.6 / 2), len: mm(19.2) },
  motor: { r: mm(412.1 / 2), len: mm(300), u: 872.8 },
  motorCap: { r: mm(412.1 / 2), len: mm(68.9) },
  /** Tampas/flanges do motor: dianteira (lado acoplamento) e traseira. */
  motorCapFU: 688.3,
  motorCapRU: 1057.2,
  motorFeet: { len: mm(300), h: mm(340), w: mm(264.9), u: 872.8, y0: mm(210) },
  stand: { s: mm(52.9), h: mm(267), u: 214.5, y0: mm(536) },
  topPlate: { s: mm(168), h: mm(14), u: 214.5, y0: mm(803) },
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
