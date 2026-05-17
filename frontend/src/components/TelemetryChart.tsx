"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TelemetryPoint } from "@/types";

interface TelemetryChartProps {
  points: TelemetryPoint[];
  color?: string;
  unit?: string;
}

export function TelemetryChart({
  points,
  color = "#22d3ee",
  unit = "",
}: TelemetryChartProps) {
  const data = points.map((point) => ({
    label: new Date(point.time).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }),
    value: point.value,
  }));

  if (data.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center text-sm text-slate-500">
        Aguardando dados de telemetria...
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={288}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="label"
          stroke="#475569"
          tick={{ fontSize: 11 }}
          minTickGap={64}
        />
        <YAxis
          stroke="#475569"
          tick={{ fontSize: 11 }}
          width={60}
          domain={["auto", "auto"]}
          tickFormatter={(value: number) => `${value}${unit ? ` ${unit}` : ""}`}
        />
        <Tooltip
          contentStyle={{
            background: "#0f172a",
            border: "1px solid #1e293b",
            borderRadius: 8,
            color: "#e2e8f0",
          }}
          labelStyle={{ color: "#94a3b8" }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
