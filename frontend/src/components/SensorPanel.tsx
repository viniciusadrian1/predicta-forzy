"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Download } from "lucide-react";
import { useEffect, useState } from "react";

import { TelemetryChart } from "@/components/TelemetryChart";
import { Card } from "@/components/ui/card";
import { getTelemetry, telemetryCsvUrl } from "@/lib/api";
import { isAuditor, useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { TelemetryPoint } from "@/types";

// Alem deste tempo sem leitura nova, a telemetria e considerada "SEM LEITURA".
const STALE_MS = 120_000;

const WINDOWS = [
  { key: "1h", label: "1h", hours: 1 },
  { key: "24h", label: "24h", hours: 24 },
  { key: "7d", label: "7d", hours: 24 * 7 },
  { key: "30d", label: "30d", hours: 24 * 30 },
];

function Sparkline({ points, color }: { points: TelemetryPoint[]; color: string }) {
  if (points.length < 2) {
    return <div className="mt-2 h-10" />;
  }
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 100;
  const height = 36;
  const path = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="mt-2 h-10 w-full"
      preserveAspectRatio="none"
    >
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

/** Tooltip inline (CSS puro) — esclarece o rótulo no hover do ícone ⓘ. */
function HintIcon({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex cursor-help items-center">
      <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full border border-slate-600 text-[9px] text-slate-500 group-hover:border-slate-400 group-hover:text-slate-300">
        i
      </span>
      <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1 hidden w-56 -translate-x-1/2 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[11px] leading-snug text-slate-300 shadow-lg group-hover:block">
        {text}
      </span>
    </span>
  );
}

interface SensorPanelProps {
  tag: string;
  variable: string;
  label: string;
  unit: string;
  color: string;
  /** Limiares de severidade — colorem a leitura (âmbar/vermelho) ao exceder. */
  warn?: number;
  crit?: number;
  /** Texto de esclarecimento opcional (ⓘ ao lado do rótulo). */
  hint?: string;
}

export function SensorPanel({
  tag,
  variable,
  label,
  unit,
  color,
  warn,
  crit,
  hint,
}: SensorPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [windowKey, setWindowKey] = useState("1h");
  const win = WINDOWS.find((item) => item.key === windowKey) ?? WINDOWS[0];

  const query = useQuery({
    queryKey: ["sensor", tag, variable, expanded, windowKey],
    queryFn: () => {
      if (!expanded) {
        return getTelemetry(tag, variable, { limit: 60 });
      }
      const to = new Date();
      const from = new Date(to.getTime() - win.hours * 3_600_000);
      return getTelemetry(tag, variable, {
        from: from.toISOString(),
        to: to.toISOString(),
        limit: 1000,
      });
    },
    refetchInterval: 4000,
  });

  const points = query.data?.points ?? [];
  const current = points.length > 0 ? points[points.length - 1] : null;

  // Governanca: o auditor ve a telemetria mascarada (minimizacao de dados);
  // o disclaimer de temporalidade (AO VIVO / SEM LEITURA) e visivel a todos.
  const role = useAuth((s) => s.role);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const masked = mounted && isAuditor(role);
  const stale =
    mounted && (!current || Date.now() - new Date(current.time).getTime() > STALE_MS);

  // Leitura colorida por severidade (padrão de sala de controle).
  const valueClass =
    current && crit !== undefined && current.value >= crit
      ? "text-red-400"
      : current && warn !== undefined && current.value >= warn
        ? "text-amber-400"
        : "text-slate-100";

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs text-slate-400">{label}</p>
            {hint && <HintIcon text={hint} />}
            {mounted &&
              (stale ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-red-950/40 px-1.5 py-0.5 text-[10px] font-medium text-red-400">
                  SEM LEITURA
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-950/40 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                  AO VIVO
                </span>
              ))}
          </div>
          <p className={`mt-1 text-2xl font-semibold tabular-nums ${valueClass}`}>
            {masked ? "***" : current ? current.value.toLocaleString("pt-BR") : "--"}
            <span className="ml-1 text-sm font-normal text-slate-500">{unit}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          className="text-slate-400 hover:text-slate-200"
          aria-label={expanded ? "Recolher" : "Expandir"}
        >
          {expanded ? (
            <ChevronUp className="h-5 w-5" />
          ) : (
            <ChevronDown className="h-5 w-5" />
          )}
        </button>
      </div>

      {!expanded &&
        (masked ? (
          <p className="mt-2 flex h-10 items-center text-xs text-slate-600">
            Telemetria mascarada (perfil auditor).
          </p>
        ) : (
          <Sparkline points={points} color={color} />
        ))}

      {expanded && (
        <div className="mt-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex gap-1">
              {WINDOWS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setWindowKey(item.key)}
                  className={cn(
                    "rounded px-2 py-1 text-xs transition-colors",
                    windowKey === item.key
                      ? "bg-cyan-500 text-slate-950"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <a
              href={telemetryCsvUrl(tag, variable)}
              download
              className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
            >
              <Download className="h-3.5 w-3.5" />
              CSV
            </a>
          </div>
          {masked ? (
            <p className="py-10 text-center text-sm text-slate-500">
              Histórico mascarado para o perfil auditor (minimização de dados).
            </p>
          ) : (
            <TelemetryChart points={points} unit={unit} color={color} warn={warn} crit={crit} />
          )}
        </div>
      )}
    </Card>
  );
}
