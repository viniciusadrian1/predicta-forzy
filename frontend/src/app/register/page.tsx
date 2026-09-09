"use client";

import { ArrowRight, Camera } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { registerFromImage } from "@/lib/api";
import { hasRole, useAuth } from "@/lib/auth";
import { usePageTitle } from "@/lib/usePageTitle";
import type { RpaResult } from "@/types";

// Ordem de exibicao dos campos de placa — a mesma sequencia usada na tela do
// ativo e nos manuais, para o tecnico ler sempre no mesmo lugar.
const ORDEM_DOS_CAMPOS = [
  "manufacturer",
  "model",
  "serial_number",
  "power_kw",
  "voltage_v",
  "nominal_current_a",
  "frequency_hz",
  "nominal_rpm",
  "insulation_class",
  "ip_rating",
  "service_factor",
  "power_factor",
];

export default function RegisterPage() {
  usePageTitle("Cadastro por foto");
  const role = useAuth((state) => state.role);
  const canOperate = hasRole(role, "operator");

  const [file, setFile] = useState<File | null>(null);
  const [tag, setTag] = useState("");
  const [result, setResult] = useState<RpaResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (autoCreate: boolean) => {
    if (!file) {
      setError("Selecione uma imagem da placa.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await registerFromImage(file, tag.trim(), autoCreate));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no processamento.");
    } finally {
      setLoading(false);
    }
  };

  const messageClass = result?.created
    ? "text-emerald-400"
    : result?.duplicate
      ? "text-amber-400"
      : "text-slate-300";

  const resultTag = result?.draft.tag ?? tag.trim();
  const showOpenAsset = Boolean(result && (result.created || result.duplicate) && resultTag);

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl">
        <p className="mb-2 text-xs text-slate-500">
          <Link href="/assets" className="hover:text-slate-300">
            Ativos
          </Link>
          {" / "}
          <span className="text-slate-400">Cadastro por foto</span>
        </p>
        <h1 className="mb-1 text-xl font-semibold text-slate-100">
          Cadastro por foto da placa
        </h1>
        <p className="mb-6 text-sm text-slate-400">
          Envie uma foto da placa de identificação. O OCR extrai os dados e o
          fluxo de RPA pré-preenche o cadastro do ativo.
        </p>

        <Card className="mb-6">
          <CardContent className="flex flex-col gap-3 p-5">
            <span className="text-xs text-slate-400">
              Imagem da placa (PNG ou JPG — foto legível da plaqueta)
            </span>
            <input
              type="file"
              accept="image/*"
              aria-label="Imagem da placa"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="text-sm text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-slate-200"
            />
            <span className="text-xs text-slate-400">TAG do ativo</span>
            <Input
              aria-label="TAG do ativo"
              placeholder="ex: MTR-003"
              value={tag}
              onChange={(event) => setTag(event.target.value)}
            />
            {error && <p className="text-sm text-red-400">{error}</p>}
            {!canOperate && (
              <p className="text-xs text-amber-400">
                Requer papel operador para extrair e cadastrar.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => run(false)} disabled={loading || !canOperate}>
                <Camera className="h-4 w-4" />
                {loading ? "Processando..." : "Extrair dados (OCR)"}
              </Button>
              <Button
                variant="outline"
                onClick={() => run(true)}
                disabled={loading || !canOperate}
              >
                Extrair e cadastrar
              </Button>
            </div>
          </CardContent>
        </Card>

        {result && (
          <Card>
            <CardHeader>
              <CardTitle>Resultado do OCR</CardTitle>
              <p className="text-sm text-slate-400">
                Motor de OCR: {result.ocr_engine} &middot; cobertura{" "}
                {Math.round(result.ocr_coverage * 100)}%
              </p>
            </CardHeader>
            <CardContent>
              <p className={`mb-4 text-sm ${messageClass}`}>{result.message}</p>

              {result.fields.length === 0 ? (
                <div className="rounded-md border border-amber-900/60 bg-amber-950/30 px-4 py-3">
                  <p className="text-sm font-medium text-amber-300">
                    Nenhum campo foi reconhecido nesta imagem.
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-amber-200/70">
                    Costuma ser foco, ângulo muito inclinado, reflexo na plaqueta
                    metálica ou texto pequeno demais no quadro. Tente uma foto mais
                    frontal, aproximada e sem brilho direto — ou preencha o cadastro
                    manualmente.
                  </p>
                </div>
              ) : (
                <>
                  {/* Campos como METRICAS, no mesmo padrao do resto do sistema:
                      rotulo pequeno acima, valor em destaque. Antes eram pares
                      soltos numa linha, e o texto cru do OCR vinha junto. */}
                  <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {ORDEM_DOS_CAMPOS.map((chave) => {
                      const campo = result.fields.find((f) => f.field === chave);
                      if (!campo?.value) return null;
                      const baixa = campo.confidence < 0.5;
                      return (
                        <div
                          key={chave}
                          className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2.5"
                        >
                          <dt className="truncate text-[11px] uppercase tracking-wide text-slate-500">
                            {campo.label}
                          </dt>
                          <dd
                            className="mt-0.5 truncate text-base font-semibold text-slate-100"
                            title={campo.value}
                          >
                            {campo.value}
                          </dd>
                          {/* Confianca baixa puxa o olho: o rascunho vai para o
                              cadastro, e ninguem desconfia do que ja veio
                              preenchido. */}
                          <dd
                            className={`mt-1 text-[10px] ${
                              baixa ? "text-amber-400" : "text-slate-600"
                            }`}
                          >
                            {baixa ? "confira na placa · " : ""}
                            {Math.round(campo.confidence * 100)}% de confiança
                          </dd>
                        </div>
                      );
                    })}
                  </dl>
                  {result.fields.some((f) => f.value && !ORDEM_DOS_CAMPOS.includes(f.field)) && (
                    <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {result.fields
                        .filter((f) => f.value && !ORDEM_DOS_CAMPOS.includes(f.field))
                        .map((campo) => (
                          <div
                            key={campo.field}
                            className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2.5"
                          >
                            <dt className="truncate text-[11px] uppercase tracking-wide text-slate-500">
                              {campo.label}
                            </dt>
                            <dd className="mt-0.5 truncate text-base font-semibold text-slate-100">
                              {campo.value}
                            </dd>
                          </div>
                        ))}
                    </dl>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
