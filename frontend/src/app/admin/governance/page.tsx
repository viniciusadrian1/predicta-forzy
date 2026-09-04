"use client";

// Governança: matriz de controle de acesso (RBAC) + classificação de dados
// (LGPD). Consome /governance/access-policy e /governance/data-lineage.

import { useQuery } from "@tanstack/react-query";
import { ServerCrash, ShieldCheck } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { RoleMaturityLadder } from "@/components/RoleMaturityLadder";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getAccessPolicy, getDataLineage, loadErrorDescription } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePageTitle } from "@/lib/usePageTitle";

const CLASS_COLOR: Record<string, string> = {
  operacional: "text-emerald-400",
  pessoal: "text-amber-400",
  sensivel: "text-red-400",
};

const ROLE_ORDER: Record<string, number> = {
  viewer: 0,
  operator: 1,
  engineer: 2,
  admin: 3,
};

export default function GovernancePage() {
  usePageTitle("Governança");
  const policyQuery = useQuery({ queryKey: ["access-policy"], queryFn: getAccessPolicy });
  const lineageQuery = useQuery({ queryKey: ["data-lineage"], queryFn: getDataLineage });
  const role = useAuth((s) => s.role);

  return (
    <AppShell>
      <div className="mb-5 flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-cyan-400" />
        <h1 className="text-xl font-semibold text-slate-100">Governança</h1>
      </div>

      {/* Níveis de acesso e maturidade (didático) */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Níveis de acesso e maturidade</CardTitle>
        </CardHeader>
        <CardContent>
          <RoleMaturityLadder currentRole={role} />
        </CardContent>
      </Card>

      {/* Matriz RBAC */}
      <Card className="mb-6">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Controle de acesso (RBAC)</CardTitle>
          {policyQuery.data && (
            <span className="text-xs text-slate-500">
              {policyQuery.data.rbac_enabled ? "Aplicado" : "Desativado"} · papéis:{" "}
              {[...policyQuery.data.roles]
                .sort((a, b) => (ROLE_ORDER[a] ?? 0) - (ROLE_ORDER[b] ?? 0))
                .join(" < ")}
            </span>
          )}
        </CardHeader>
        <CardContent>
          {policyQuery.isLoading && <Skeleton className="h-40" />}
          {policyQuery.isError && (
            <EmptyState
              icon={ServerCrash}
              title="Não foi possível carregar a política de acesso"
              description={loadErrorDescription(policyQuery.error)}
              action={
                <Button variant="outline" onClick={() => void policyQuery.refetch()}>
                  Tentar novamente
                </Button>
              }
            />
          )}
          {policyQuery.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-4 font-medium">Recurso</th>
                    <th className="py-2 pr-4 font-medium">Métodos</th>
                    <th className="py-2 pr-4 font-medium">Papel mínimo</th>
                    <th className="py-2 font-medium">Descrição</th>
                  </tr>
                </thead>
                <tbody>
                  {policyQuery.data.rules.map((rule) => (
                    <tr key={rule.resource} className="border-b border-slate-800/60">
                      <td className="py-2 pr-4 font-mono text-xs text-slate-200">
                        {rule.resource}
                      </td>
                      <td className="py-2 pr-4 text-xs text-slate-400">
                        {rule.methods.join(", ")}
                      </td>
                      <td className="py-2 pr-4">
                        <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-cyan-400">
                          {rule.min_role}
                        </span>
                      </td>
                      <td className="py-2 text-xs text-slate-400">{rule.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Classificação de dados */}
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Classificação de dados (LGPD)</CardTitle>
          {lineageQuery.data && (
            <span className="text-xs text-slate-500">{lineageQuery.data.document}</span>
          )}
        </CardHeader>
        <CardContent>
          {lineageQuery.isLoading && <Skeleton className="h-40" />}
          {lineageQuery.isError && (
            <EmptyState
              icon={ServerCrash}
              title="Não foi possível carregar o catálogo de dados"
              description={loadErrorDescription(lineageQuery.error)}
              action={
                <Button variant="outline" onClick={() => void lineageQuery.refetch()}>
                  Tentar novamente
                </Button>
              }
            />
          )}
          {lineageQuery.data && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-4 font-medium">Dado</th>
                    <th className="py-2 pr-4 font-medium">Origem</th>
                    <th className="py-2 pr-4 font-medium">Classificação</th>
                    <th className="py-2 pr-4 font-medium">Armazenamento</th>
                    <th className="py-2 pr-4 font-medium">Retenção</th>
                    <th className="py-2 font-medium">Observações</th>
                  </tr>
                </thead>
                <tbody>
                  {lineageQuery.data.datasets.map((entry) => (
                    <tr key={entry.dataset} className="border-b border-slate-800/60">
                      <td className="py-2 pr-4 font-mono text-xs text-slate-200">
                        {entry.dataset}
                      </td>
                      <td className="py-2 pr-4 text-xs text-slate-400">{entry.origin}</td>
                      <td
                        className={`py-2 pr-4 text-xs font-medium ${
                          CLASS_COLOR[entry.classification] ?? "text-slate-400"
                        }`}
                      >
                        {entry.classification}
                      </td>
                      <td className="py-2 pr-4 text-xs text-slate-400">{entry.storage}</td>
                      <td className="py-2 pr-4 text-xs text-slate-400">
                        {entry.retention}
                      </td>
                      <td className="py-2 text-xs text-slate-500">{entry.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </AppShell>
  );
}
