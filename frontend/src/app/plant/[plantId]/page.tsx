"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, MapPinOff, ServerCrash } from "lucide-react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { PlantMap } from "@/components/PlantMap";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { getAssets, getPlants, smartPdfUrl } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

interface PlantPageProps {
  params: { plantId: string };
}

export default function PlantPage({ params }: PlantPageProps) {
  const { plantId } = params;
  const router = useRouter();

  const plantsQuery = useQuery({
    queryKey: ["plants"],
    queryFn: getPlants,
    refetchInterval: 15000,
  });
  const assetsQuery = useQuery({
    queryKey: ["assets"],
    queryFn: () => getAssets(),
    refetchInterval: 15000,
  });

  const plant = plantsQuery.data?.find((item) => item.id === plantId);
  usePageTitle(plant ? `Planta — ${plant.name}` : "Planta");
  const assets = (assetsQuery.data ?? []).filter(
    (asset) => asset.plant_id === null || asset.plant_id === plantId,
  );

  // Id inexistente: a query resolveu mas nenhuma planta casa -> estado claro.
  if (plantsQuery.isSuccess && !plant) {
    return (
      <AppShell>
        <EmptyState
          icon={MapPinOff}
          title="Planta não encontrada"
          description="O identificador da planta não existe ou foi removido."
          action={
            <Button variant="outline" onClick={() => router.push("/overview")}>
              Voltar para a visão geral
            </Button>
          }
        />
      </AppShell>
    );
  }

  return (
    <AppShell>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-100">
              Planta baixa {plant ? `— ${plant.name}` : ""}
            </h1>
            <p className="text-sm text-slate-400">
              Clique em um equipamento para abrir o ativo monitorado.
            </p>
          </div>
          <a href={smartPdfUrl(plantId)} target="_blank" rel="noopener noreferrer">
            <Button variant="outline">
              <Download className="h-4 w-4" />
              PDF inteligente
            </Button>
          </a>
        </div>

        {assetsQuery.isError ? (
          <EmptyState
            icon={ServerCrash}
            title="Não foi possível carregar a planta"
            description="Verifique a conexão com a API e tente novamente."
            action={
              <Button variant="outline" onClick={() => void assetsQuery.refetch()}>
                Tentar novamente
              </Button>
            }
          />
        ) : (
          <Card>
            <CardContent className="p-4">
              <PlantMap assets={assets} />
            </CardContent>
          </Card>
        )}

        <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-400">
          <span>
            <span className="text-emerald-400">&#9679;</span> Operacional
          </span>
          <span>
            <span className="text-amber-400">&#9679;</span> Atenção
          </span>
          <span>
            <span className="text-red-400">&#9679;</span> Crítico
          </span>
          <span>
            <span className="text-slate-500">&#9679;</span> Desconhecido
          </span>
        </div>
    </AppShell>
  );
}
