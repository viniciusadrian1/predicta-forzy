// Rótulos em português dos alertas. O backend usa códigos (enums); a UI mostra
// texto legível. Fonte única, reusada em toasts, overview, alertas e saúde do ativo.

export const SEVERITY_LABEL: Record<string, string> = {
  CRITICAL: "Crítico",
  WARNING: "Atenção",
  INFO: "Aviso",
};

export const TYPE_LABEL: Record<string, string> = {
  THRESHOLD_EXCEEDED: "Limite excedido",
  THRESHOLD_APPROACHING: "Aproximando do limite",
  BASELINE_DEVIATION: "Desvio do padrão de operação",
  ANOMALY_DETECTED: "Anomalia de vibração",
  RUL_WARNING: "Vida útil (RUL)",
  CIRCUIT_BREAKER: "Dado não confiável",
};

/** Severidade legível; cai no próprio código se desconhecido. */
export const severityLabel = (severity: string): string =>
  SEVERITY_LABEL[severity] ?? severity;

/** Tipo de alerta legível; cai no próprio código se desconhecido. */
export const alertTypeLabel = (type: string): string => TYPE_LABEL[type] ?? type;
