// Agrupamento de ativo -> pontos de medição.
//
// Um ativo com `parent_tag` preenchido NÃO é um equipamento próprio: é um
// PONTO DE MEDIÇÃO de outro ativo. É o caso do conjunto motor-bomba da Forzy
// (MTR-F00), cujos dois mancais (MTR-F01 lado bomba, MTR-F02 lado motor) têm
// cada um seu sensor IO-Link, sua telemetria e seus modelos de ML — mas são
// um equipamento só.

import type { Asset } from "@/types";

/** Ativos que aparecem na lista: os pontos de medição ficam dentro do pai. */
export const rootAssets = (assets: Asset[]): Asset[] =>
  assets.filter((a) => !a.parent_tag);

/** Pontos de medição de um ativo (vazio quando ele mede a si próprio). */
export const pointsOf = (assets: Asset[], tag: string): Asset[] =>
  assets.filter((a) => a.parent_tag === tag);

const RANK: Record<string, number> = { unknown: 0, ok: 1, warning: 2, critical: 3 };

/**
 * Status exibido: o PIOR entre os pontos de medição. O ativo pai não tem
 * telemetria própria (quem mede são os pontos), então sem isso ele apareceria
 * eternamente como "sem dados".
 */
export function effectiveStatus(asset: Asset, points: Asset[]): string {
  if (points.length === 0) return asset.status;
  return points.reduce(
    (worst, p) => ((RANK[p.status] ?? 0) > (RANK[worst] ?? 0) ? p.status : worst),
    "unknown",
  );
}
