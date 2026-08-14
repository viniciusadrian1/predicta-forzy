"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, PackageOpen, Plus, Search, ServerCrash } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AssetCard } from "@/components/AssetCard";
import { EmptyState } from "@/components/EmptyState";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { type CreateAssetInput, createAsset, getAssets } from "@/lib/api";
import { hasRole, useAuth } from "@/lib/auth";
import { useToasts } from "@/lib/toast";
import { usePageTitle } from "@/lib/usePageTitle";

const EMPTY_FORM = { tag: "", name: "", manufacturer: "", model: "" };

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "ok", label: "Operacional" },
  { value: "warning", label: "Atenção" },
  { value: "critical", label: "Crítico" },
  { value: "unknown", label: "Desconhecido" },
];

export default function DashboardPage() {
  usePageTitle("Painel");
  const queryClient = useQueryClient();
  const router = useRouter();
  const push = useToasts((state) => state.push);
  const role = useAuth((state) => state.role);
  const canOperate = hasRole(role, "operator");

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  const assetsQuery = useQuery({
    queryKey: ["assets", search, statusFilter],
    queryFn: () =>
      getAssets({
        search: search.trim() || undefined,
        status: statusFilter || undefined,
      }),
    refetchInterval: 15000,
  });

  const mutation = useMutation({
    mutationFn: createAsset,
    onSuccess: (asset) => {
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      void queryClient.invalidateQueries({ queryKey: ["hierarchy"] });
      setShowForm(false);
      setForm(EMPTY_FORM);
      setFormError(null);
      push({ title: `Ativo ${asset.tag} criado`, severity: "info" });
      router.push(`/asset/${encodeURIComponent(asset.tag)}`);
    },
    onError: (error) =>
      setFormError(error instanceof Error ? error.message : "Erro ao cadastrar"),
  });

  const submit = () => {
    if (!form.tag.trim()) {
      setFormError("A TAG é obrigatória");
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
      <div className="mx-auto flex max-w-[1536px] flex-col gap-6 px-6 py-8 lg:flex-row lg:px-8">
        <Sidebar />
        <main className="flex-1">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-slate-100">
                Ativos monitorados
              </h1>
              <p className="text-sm text-slate-400">
                Motores e equipamentos com gêmeo digital ativo
              </p>
            </div>
            <div className="flex gap-2">
              <Link href="/register">
                <Button variant="outline" disabled={!canOperate}>
                  <Camera className="h-4 w-4" />
                  Cadastrar por foto
                </Button>
              </Link>
              <Button
                onClick={() => setShowForm((open) => !open)}
                disabled={!canOperate}
                title={canOperate ? undefined : "Requer papel operador"}
              >
                <Plus className="h-4 w-4" />
                Novo ativo
              </Button>
            </div>
          </div>

          <div className="mb-5 flex flex-wrap gap-3">
            <div className="relative min-w-[200px] flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <Input
                aria-label="Buscar ativos"
                placeholder="Buscar por TAG, fabricante ou modelo..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="pl-9"
              />
            </div>
            <select
              aria-label="Filtrar por status"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="h-10 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {showForm && (
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Cadastrar novo ativo</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Input
                    aria-label="TAG"
                    placeholder="TAG (ex: MTR-002)"
                    value={form.tag}
                    onChange={(event) => setForm({ ...form, tag: event.target.value })}
                  />
                  <Input
                    aria-label="Nome"
                    placeholder="Nome"
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                  />
                  <Input
                    aria-label="Fabricante"
                    placeholder="Fabricante"
                    value={form.manufacturer}
                    onChange={(event) =>
                      setForm({ ...form, manufacturer: event.target.value })
                    }
                  />
                  <Input
                    aria-label="Modelo"
                    placeholder="Modelo"
                    value={form.model}
                    onChange={(event) => setForm({ ...form, model: event.target.value })}
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
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, index) => (
                <Skeleton key={index} className="h-40" />
              ))}
            </div>
          )}

          {assetsQuery.isError && (
            <EmptyState
              icon={ServerCrash}
              title="Não foi possível carregar os ativos"
              description="Verifique a conexão com a API e tente novamente."
              action={
                <Button variant="outline" onClick={() => void assetsQuery.refetch()}>
                  Tentar novamente
                </Button>
              }
            />
          )}

          {assetsQuery.isSuccess && assetsQuery.data.length === 0 && (
            <EmptyState
              icon={PackageOpen}
              title="Nenhum ativo encontrado"
              description="Cadastre o primeiro equipamento para iniciar o monitoramento."
              action={
                canOperate ? (
                  <Button onClick={() => setShowForm(true)}>
                    <Plus className="h-4 w-4" />
                    Novo ativo
                  </Button>
                ) : undefined
              }
            />
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {assetsQuery.data?.map((asset) => (
              <AssetCard key={asset.id} asset={asset} />
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
