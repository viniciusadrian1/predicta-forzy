"use client";

import { Camera } from "lucide-react";
import { useState } from "react";

import { Header } from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { registerFromImage } from "@/lib/api";
import type { RpaResult } from "@/types";

export default function RegisterPage() {
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

  return (
    <div>
      <Header />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <h1 className="mb-1 text-xl font-semibold text-slate-100">
          Cadastro por foto da placa
        </h1>
        <p className="mb-6 text-sm text-slate-400">
          Envie uma foto da placa de identificacao. O OCR extrai os dados e o
          fluxo de RPA pre-preenche o cadastro do ativo.
        </p>

        <Card className="mb-6">
          <CardContent className="flex flex-col gap-3 p-5">
            <span className="text-xs text-slate-400">Imagem da placa</span>
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => run(false)} disabled={loading}>
                <Camera className="h-4 w-4" />
                {loading ? "Processando..." : "Extrair dados (OCR)"}
              </Button>
              <Button variant="outline" onClick={() => run(true)} disabled={loading}>
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
              <dl className="grid gap-1.5 text-sm sm:grid-cols-2">
                {result.fields.map((field) => (
                  <div key={field.field} className="flex justify-between gap-3">
                    <dt className="text-slate-400">{field.label}</dt>
                    <dd className="text-slate-200">
                      {field.value ?? "--"}
                      <span className="ml-1 text-xs text-slate-500">
                        {Math.round(field.confidence * 100)}%
                      </span>
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
