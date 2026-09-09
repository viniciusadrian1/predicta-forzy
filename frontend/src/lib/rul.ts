// Formatacao da vida util restante (RUL).
//
// Existe para o card "Proxima acao" e o painel "Saude do ativo" nao poderem
// divergir: os dois liam `rul_days` e formatavam por conta propria, e o
// `maximumFractionDigits: 0` do card truncava 0,2 dia para "0 dias" enquanto o
// painel ao lado mostrava "0.2 dias" para o mesmo ativo.

/** Numero de dias como o painel de saude mostra (ate 1 casa, sem truncar). */
export function rulDaysLabel(days: number): string {
  // Uma vida util que existe nunca deve ser exibida como "0": arredondar para
  // zero um prazo real e a diferenca entre "troque hoje" e "ja era".
  if (days > 0 && days < 0.05) return "<0,1";
  return days.toLocaleString("pt-BR", {
    maximumFractionDigits: days < 10 ? 1 : 0,
  });
}

/**
 * Prazo por extenso, na unidade que faz sentido para a ordem de grandeza.
 *
 * Abaixo de um dia, "0,2 dia" nao ajuda ninguem a agir — quem vai parar a
 * maquina precisa ler "~5 horas".
 */
export function rulDeadlineLabel(days: number): string {
  if (days < 1) {
    const hours = days * 24;
    if (hours < 1) {
      const minutes = Math.max(1, Math.round(hours * 60));
      return `${minutes} min`;
    }
    return `${hours.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} h`;
  }
  return `${rulDaysLabel(days)} ${days < 2 ? "dia" : "dias"}`;
}
