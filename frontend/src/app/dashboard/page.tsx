"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { AssetCard } from "@/components/AssetCard";
import { Header } from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { type CreateAssetInput, createAsset, getAssets } from "@/lib/api";

const EMPTY_FORM = { tag: "", name: "", manufacturer: "", model: "" };

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const assetsQuery = useQuery({ queryKey: ["assets"], queryFn: getAssets });

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createAsset,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      setShowForm(false);
      setForm(EMPTY_FORM);
      setFormError(null);
    },
    onError: (error) =>
      setFormError(error instanceof Error ? error.message : "Erro ao cadastrar"),
  });

  const submit = () => {
    if (!form.tag.trim()) {
      setFormError("A TAG e obrigatoria");
      return;
    }
    const payload: CreateAssetInput = { tag: form.tag.trim() };
    if (form.name.trim()) payload.name = form.name.trim();
    if (form.manufacturer.trim()) payload.manufacturer = form.manufacturer.trim();
    if (form.model.trim()) payload.model = form.model.trim();
    mutation.mutate(payload);
  };

  return (
    <div>
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">Ativos monitorados</h1>
            <p className="text-sm text-slate-400">
              Motores e equipamentos com gemeo digital ativo
            </p>
          </div>
          <Button onClick={() => setShowForm((open) => !open)}>
            <Plus className="h-4 w-4" />
            Novo ativo
          </Button>
        </div>

        {showForm && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Cadastrar novo ativo</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Input
                  placeholder="TAG (ex: MTR-002)"
                  value={form.tag}
                  onChange={(e) => setForm({ ...form, tag: e.target.value })}
                />
                <Input
                  placeholder="Nome"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
                <Input
                  placeholder="Fabricante"
                  value={form.manufacturer}
                  onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
                />
                <Input
                  placeholder="Modelo"
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                />
              </div>
              {formError && <p className="mt-2 text-sm text-red-400">{formError}</p>}
              <div className="mt-3 flex gap-2">
                <Button onClick={submit} disabled={mutation.isPending}>
                  {mutation.isPending ? "Salvando..." : "Salvar"}
                </Button>
                <Button variant="outline" onClick={() => setShowForm(false)}>
                  Cancelar
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {assetsQuery.isLoading && (
          <p className="text-slate-400">Carregando ativos...</p>
        )}
        {assetsQuery.isError && (
          <p className="text-red-400">
            Nao foi possivel carregar os ativos. Verifique se a API esta no ar.
          </p>
        )}
        {assetsQuery.data?.length === 0 && (
          <p className="text-slate-400">
            Nenhum ativo cadastrado. Use &quot;Novo ativo&quot; para comecar.
          </p>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assetsQuery.data?.map((asset) => (
            <AssetCard key={asset.id} asset={asset} />
          ))}
        </div>
      </main>
    </div>
  );
}
