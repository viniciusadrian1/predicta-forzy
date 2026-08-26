"use client";

// Selos de linhagem e painel de rastreabilidade do cadastro (governanca).

import { AlertTriangle, BadgeCheck, Cpu, PackageOpen } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Asset } from "@/types";

const REVIEW_THRESHOLD = 0.85;

/** Selo de linhagem do dado: VALIDADO / IA-GENERATED / REVISÃO NECESSÁRIA. */
export function LineageBadge({ asset }: { asset: Asset }) {
  const base =
    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium";

  if (asset.validated_by) {
    return (
      <span className={`${base} border-emerald-600/40 bg-emerald-950/30 text-emerald-300`}>
        <BadgeCheck className="h-3.5 w-3.5" />
        Validado por {asset.validated_by}
      </span>
    );
  }

  if (asset.data_origin === "ia_gerado") {
    const score = asset.ocr_confidence;
    const pct = score != null ? ` · ${Math.round(score * 100)}%` : "";
    if (score != null && score < REVIEW_THRESHOLD) {
      return (
        <span className={`${base} border-amber-600/40 bg-amber-950/30 text-amber-300`}>
          <AlertTriangle className="h-3.5 w-3.5" />
          Revisão necessária{pct}
        </span>
      );
    }
    return (
      <span className={`${base} border-cyan-600/40 bg-cyan-950/30 text-cyan-300`}>
        <Cpu className="h-3.5 w-3.5" />
        Gerado por IA{pct}
      </span>
    );
  }

  if (asset.data_origin === "importacao") {
    return (
      <span className={`${base} border-slate-700 bg-slate-800/60 text-slate-300`}>
        <PackageOpen className="h-3.5 w-3.5" />
        Importado
      </span>
    );
  }

  return (
    <span className={`${base} border-slate-700 bg-slate-800/60 text-slate-300`}>
      <BadgeCheck className="h-3.5 w-3.5" />
      Cadastro manual
    </span>
  );
}

function fmt(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}

/** Metadados de rastreabilidade exigidos pela governanca (cadastro do ativo). */
export function TraceabilityCard({ asset }: { asset: Asset }) {
  const rows: Array<[string, string]> = [
    ["Origem do dado", asset.data_origin],
    ["Data da foto/cadastro", fmt(asset.registration_photo_at)],
    ["Versão do OCR", asset.ocr_engine_version ?? "—"],
    [
      "Score de confiança",
      asset.ocr_confidence != null ? `${Math.round(asset.ocr_confidence * 100)}%` : "—",
    ],
    ["Responsável pela validação", asset.validated_by ?? "Pendente"],
    ["Fonte da imagem", asset.image_source ?? "—"],
    ["Condição visual", asset.visual_condition ?? "—"],
  ];
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 pb-2">
        <CardTitle>Rastreabilidade do cadastro</CardTitle>
        <LineageBadge asset={asset} />
      </CardHeader>
      <CardContent>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4">
              <dt className="text-slate-400">{label}</dt>
              <dd className="text-right text-slate-200">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
