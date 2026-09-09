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
