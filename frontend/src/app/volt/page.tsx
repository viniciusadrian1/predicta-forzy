"use client";

// Volt — assistente de manutenção (chatbot guiado) + ordens de serviço abertas.

import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { VoltChat } from "@/components/VoltChat";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getWorkOrders } from "@/lib/api";
import { hasRole, useAuth } from "@/lib/auth";
import { usePageTitle } from "@/lib/usePageTitle";

const PRIORITY_COLOR: Record<string, string> = {
  alta: "text-red-400",
  media: "text-amber-400",
  baixa: "text-slate-400",
};

function WorkOrders() {
  const role = useAuth((s) => s.role);
  const canView = hasRole(role, "operator");
  const ordersQuery = useQuery({
    queryKey: ["work-orders"],
    queryFn: () => getWorkOrders(),
    enabled: canView,
    refetchInterval: 15000,
  });

  if (!canView) {
    return (
      <p className="text-xs text-slate-500">
        As ordens de serviço abertas ficam visíveis para o papel operador ou superior.
      </p>
    );
  }

  const orders = ordersQuery.data ?? [];
  return (
    <div className="flex flex-col gap-2">
      {orders.length === 0 && (
        <p className="text-xs text-slate-500">Nenhuma ordem de serviço aberta ainda.</p>
      )}
      {orders.map((order) => (
        <div
          key={order.id}
          className="rounded-lg border border-slate-800 bg-slate-950/50 p-3"
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm text-slate-200">{order.number}</span>
            <span className={`text-xs font-medium ${PRIORITY_COLOR[order.priority] ?? "text-slate-400"}`}>
              {order.priority}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">{order.fault}</p>
          <p className="mt-0.5 text-[11px] text-slate-600">
            {order.asset_tag} · {order.symptom} · {Math.round(order.confidence * 100)}% ·{" "}
            {new Date(order.created_at).toLocaleString("pt-BR")}
          </p>
        </div>
      ))}
    </div>
  );
}

export default function VoltPage() {
  usePageTitle("Volt");
  return (
    <AppShell>
      <div className="mb-4">
        <h1 className="text-xl font-semibold text-slate-100">Volt — Assistente de Manutenção</h1>
        <p className="text-sm text-slate-400">
          Informe o código do ativo e o sintoma. O Volt lê os sensores, diagnostica e
          abre a ordem de serviço — encaminhando a um técnico quando necessário.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card className="h-[72vh] overflow-hidden p-0">
          <VoltChat />
        </Card>

        <Card className="h-fit">
          <CardHeader className="flex-row items-center gap-2 pb-2">
            <ClipboardList className="h-4 w-4 text-cyan-400" />
            <CardTitle>Ordens de serviço</CardTitle>
          </CardHeader>
          <CardContent>
            <WorkOrders />
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
