"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { Asset } from "@/types";

const STATUS_COLOR: Record<string, string> = {
  ok: "#22c55e",
  warning: "#f59e0b",
  critical: "#ef4444",
  unknown: "#64748b",
};

const STATUS_LABEL: Record<string, string> = {
  ok: "Operacional",
  warning: "Atencao",
  critical: "Critico",
  unknown: "Desconhecido",
};

/**
 * Planta baixa interativa: renderiza o SVG da planta e sobrepoe marcadores
 * clicaveis por ativo, posicionados pelas coordenadas vindas da API.
 */
export function PlantMap({ assets }: { assets: Asset[] }) {
  const router = useRouter();
  const [hovered, setHovered] = useState<string | null>(null);

  const markers = assets.filter(
    (asset) => asset.position_x !== null && asset.position_y !== null,
  );

  return (
    <svg
      viewBox="0 0 1000 640"
      className="w-full rounded-lg border border-slate-800 bg-slate-950"
      role="img"
      aria-label="Planta baixa interativa da Sala de Bombas"
    >
      <image href="/plant-layout.svg" x="0" y="0" width="1000" height="640" />

      {markers.map((asset) => {
        const cx = (asset.position_x ?? 0.5) * 1000;
        const cy = (asset.position_y ?? 0.5) * 640;
        const color = STATUS_COLOR[asset.status] ?? STATUS_COLOR.unknown;
        const label = STATUS_LABEL[asset.status] ?? asset.status;
        const isHovered = hovered === asset.tag;
        return (
          <g
            key={asset.id}
            data-asset-tag={asset.tag}
            style={{ cursor: "pointer" }}
            onClick={() => router.push(`/asset/${asset.tag}`)}
            onMouseEnter={() => setHovered(asset.tag)}
            onMouseLeave={() => setHovered(null)}
          >
            <title>{`${asset.tag} - ${label}`}</title>
            <circle
              cx={cx}
              cy={cy}
              r={isHovered ? 30 : 24}
              fill={color}
              fillOpacity="0.18"
              stroke={color}
              strokeWidth="2.5"
            />
            <circle cx={cx} cy={cy} r="9" fill={color} />
            <text
              x={cx}
              y={cy + 46}
              fill="#e2e8f0"
              fontSize="16"
              fontWeight="bold"
              textAnchor="middle"
            >
              {asset.tag}
            </text>
            {isHovered && (
              <g>
                <rect
                  x={cx + 16}
                  y={cy - 46}
                  width="210"
                  height="42"
                  rx="6"
                  fill="#0f172a"
                  stroke={color}
                  strokeWidth="1"
                />
                <text x={cx + 28} y={cy - 27} fill="#e2e8f0" fontSize="13">
                  {`${asset.tag} - ${asset.name ?? "Ativo"}`}
                </text>
                <text x={cx + 28} y={cy - 11} fill={color} fontSize="12">
                  {`Status: ${label}`}
                </text>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}
