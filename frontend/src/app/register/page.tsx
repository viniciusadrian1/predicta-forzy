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
              <p className={`mb-3 text-sm ${messageClass}`}>{result.message}</p>
              {/* Diagnostico da leitura. Fica DEPOIS dos campos e recolhido:
                  e ferramenta de apoio para quando o OCR falha, nao o
                  resultado. Antes vinha antes de tudo, aberto, com o texto cru
                  ocupando a tela inteira. */}
              {result.fields.length === 0 && (
                <p className="mb-4 rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-sm text-amber-300">
                  Nenhum campo foi reconhecido. Confira o diagnóstico da leitura
                  abaixo e, se necessário, preencha o cadastro manualmente.
                </p>
              )}
              <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                {result.fields.map((field) => (
                  <div key={field.field} className="min-w-0">
                    <dt className="text-xs text-slate-500">{field.label}</dt>
                    <dd className="truncate text-sm text-slate-200" title={field.value ?? undefined}>
                      {field.value ?? "--"}
                      {/* Confianca baixa em amarelo: o rascunho vai para o
                          cadastro, e um valor duvidoso precisa puxar o olho de
                          quem revisa em vez de passar como cinza discreto. */}
                      <span
                        className={`ml-1 text-xs ${
                          field.confidence < 0.5 ? "text-amber-400" : "text-slate-500"
                        }`}
                        title={
                          field.confidence < 0.5
                            ? "Confiança baixa — confira este campo na placa"
                            : undefined
                        }
                      >
                        {Math.round(field.confidence * 100)}%
                      </span>
                    </dd>
                  </div>
                ))}
              </dl>

              {/* Diagnostico da leitura, recolhido. */}
              {result.raw_text !== undefined && (
                <details className="group mt-5 border-t border-slate-800 pt-3">
                  <summary className="flex cursor-pointer list-none items-center gap-2 text-xs text-slate-500 transition-colors hover:text-slate-300">
                    <span className="transition-transform group-open:rotate-90">›</span>
                    Diagnóstico da leitura
                    <span className="text-slate-600">
                      · {result.raw_text.trim().length} caracteres lidos
                    </span>
                  </summary>
                  {result.raw_text.trim() ? (
                    <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-md bg-slate-950/70 p-3 font-mono text-[11px] leading-relaxed text-slate-400">
                      {result.raw_text}
                    </pre>
                  ) : (
                    <p className="mt-3 text-xs leading-relaxed text-slate-400">
                      O OCR não extraiu nenhum caractere desta imagem. Costuma ser
                      foco, ângulo muito inclinado, reflexo na placa metálica ou
                      texto pequeno demais no quadro — tente uma foto mais
                      frontal, aproximada e sem brilho direto.
                    </p>
                  )}
                </details>
              )}
              {showOpenAsset && (
                <Link
                  href={`/asset/${encodeURIComponent(resultTag)}`}
                  className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-cyan-400 hover:text-cyan-300"
                >
                  Abrir ativo {resultTag}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
