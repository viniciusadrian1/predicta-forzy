// Autoteste do formatador de RUL. Sem framework: `npm run check:rul`.
//
// Trava o bug que motivou o arquivo: o card "Proxima acao" mostrava "0 dias"
// (maximumFractionDigits: 0) enquanto o painel "Saude do ativo" mostrava "0.2
// dias" para o MESMO ativo.
import assert from "node:assert/strict";

import { rulDaysLabel, rulDeadlineLabel } from "../src/lib/rul.ts";

const CASOS: Array<[number, string, string]> = [
  [0.2, "0,2", "4,8 h"], // o caso relatado: nunca mais "0 dias"
  [0.24, "0,2", "5,8 h"],
  [0.02, "<0,1", "29 min"], // prazo real minusculo continua nao sendo zero
  [1, "1", "1 dia"],
  [1.5, "1,5", "1,5 dia"],
  [45, "45", "45 dias"],
  [180, "180", "180 dias"],
];

for (const [dias, painel, card] of CASOS) {
  assert.equal(rulDaysLabel(dias), painel, `painel para ${dias} dias`);
  assert.equal(rulDeadlineLabel(dias), card, `card para ${dias} dias`);
}

// Nenhum prazo positivo pode ser exibido como zero em qualquer das duas telas.
for (let dias = 0.001; dias < 200; dias *= 1.35) {
  assert.notEqual(rulDaysLabel(dias), "0", `${dias} dias virou "0" no painel`);
  assert.ok(!/^0\s/.test(rulDeadlineLabel(dias)), `${dias} dias virou "0" no card`);
}

console.log(`OK — ${CASOS.length} casos + varredura de 0,001 a 200 dias`);
