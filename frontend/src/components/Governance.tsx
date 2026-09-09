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

// Valores reais da coluna data_origin (assets/models.py): humano, importacao,
// ia_gerado. Chave errada aqui fazia a tela mostrar o valor cru ("humano").
const ORIGIN_LABEL: Record<string, string> = {
  humano: "Cadastro manual",
  importacao: "Importação de base existente",
  ia_gerado: "Extração por IA (foto da placa)",
};

/** Metadados de rastreabilidade exigidos pela governanca (cadastro do ativo). */
export function TraceabilityCard({ asset }: { asset: Asset }) {
  // Os campos de OCR so existem quando o ativo NASCEU de uma foto de placa.
  // "Score de confianca" aqui e a cobertura do OCR na placa — nada a ver com o
  // score do Isolation Forest em "Saude do ativo", que mede a vibracao de agora.
  const veioDeFoto = asset.data_origin === "ia_gerado";

  const rows: Array<[string, string | null]> = [
    ["Origem do dado", ORIGIN_LABEL[asset.data_origin] ?? asset.data_origin],
    ["Responsável pela validação", asset.validated_by ?? "Pendente"],
    ["Condição visual", asset.visual_condition ?? "Não avaliada"],
  ];
  if (veioDeFoto) {
    rows.push(
      ["Data da foto", fmt(asset.registration_photo_at)],
      ["Versão do OCR", asset.ocr_engine_version],
      [
        "Confiança do OCR",
        asset.ocr_confidence != null
          ? `${Math.round(asset.ocr_confidence * 100)}%`
          : null,
      ],
      ["Fonte da imagem", asset.image_source],
    );
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 pb-2">
        <CardTitle>Rastreabilidade do cadastro</CardTitle>
        <LineageBadge asset={asset} />
      </CardHeader>
      <CardContent>
        {/* Rotulo ACIMA do valor. Em duas colunas com `justify-between`, o valor
            de uma coluna encostava no rotulo da seguinte ("humano  Data da
            foto/cadastro") e os textos longos quebravam em 3 linhas, deixando as
            linhas de alturas diferentes. */}
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd
                className={`truncate text-sm ${
                  value ? "text-slate-200" : "text-slate-500"
                }`}
                title={value ?? undefined}
              >
                {value ?? "Não informado"}
              </dd>
            </div>
          ))}
        </dl>
        {!veioDeFoto && (
          // Uma nota, em vez de repetir "Não se aplica (sem leitura de placa)"
          // em quatro campos — era o que mais poluia o cartao.
          <p className="mt-4 border-t border-slate-800 pt-3 text-xs text-slate-500">
            Cadastro sem leitura de placa: não há versão de OCR, confiança de
            extração nem imagem de origem para este ativo.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
