import { Card } from "@/components/ui/card";
import type { LatestReading } from "@/types";

const SENSOR_LABELS: Record<string, string> = {
  Tensao: "Tensao",
  Corrente: "Corrente",
  Temperatura: "Temperatura",
  Rotacao: "Rotacao",
  Vibracao_Velocidade_RMS: "Vibracao (velocidade)",
  Vibracao_Aceleracao_RMS: "Vibracao (aceleracao)",
};

const SENSOR_ORDER = [
  "Tensao",
  "Corrente",
  "Temperatura",
  "Rotacao",
  "Vibracao_Velocidade_RMS",
  "Vibracao_Aceleracao_RMS",
];

export function SensorStrip({ readings }: { readings: LatestReading[] }) {
  const byVariable = new Map(readings.map((reading) => [reading.variable, reading]));

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {SENSOR_ORDER.map((variable) => {
        const reading = byVariable.get(variable);
        return (
          <Card key={variable} className="p-3">
            <p className="text-xs text-slate-400">{SENSOR_LABELS[variable] ?? variable}</p>
            <p className="mt-1 text-lg font-semibold text-slate-100">
              {reading ? reading.value.toLocaleString("pt-BR") : "--"}
              <span className="ml-1 text-xs font-normal text-slate-500">
                {reading?.unit ?? ""}
              </span>
            </p>
          </Card>
        );
      })}
    </div>
  );
}
