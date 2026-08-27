"use client";

// Auditoria: trilha append-only de todas as operações (quem, o quê, quando).
// Consome GET /audit (requer papel admin — token enviado no header).

import { useQuery } from "@tanstack/react-query";
import { Boxes, ScrollText, ServerCrash } from "lucide-react";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getAuditLog, loadErrorDescription } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

const METHOD_COLOR: Record<string, string> = {
  POST: "text-emerald-400",
  PATCH: "text-amber-400",
  PUT: "text-amber-400",
  DELETE: "text-red-400",
};

function statusColor(code: number | null): string {
  if (code === null) return "text-slate-500";
  if (code >= 500) return "text-red-400";
  if (code >= 400) return "text-amber-400";
  return "text-emerald-400";
}

export default function AuditPage() {
  usePageTitle("Auditoria");
  const [filter, setFilter] = useState("");

  const auditQuery = useQuery({
    queryKey: ["audit"],
    queryFn: () => getAuditLog(200),
    refetchInterval: 20000,
  });

  const rows = useMemo(() => {
    const term = filter.trim().toLowerCase();
    const data = auditQuery.data ?? [];
    if (!term) return data;
    return data.filter(
      (e) =>
        e.actor.toLowerCase().includes(term) ||
        e.action.toLowerCase().includes(term) ||
        (e.path ?? "").toLowerCase().includes(term) ||
        e.resource_type.toLowerCase().includes(term),
    );
  }, [auditQuery.data, filter]);

  return (
    <AppShell>
      <div className="mb-4 flex items-center gap-2">
        <ScrollText className="h-5 w-5 text-cyan-400" />
        <h1 className="text-xl font-semibold text-slate-100">Auditoria</h1>
        <span className="ml-auto text-sm text-slate-500">
          {auditQuery.data?.length ?? 0} registro(s)
        </span>
      </div>
      <p className="mb-4 text-sm text-slate-400">
        Trilha append-only de todas as operações de escrita no sistema.
      </p>

      <Input
        aria-label="Filtrar auditoria"
        placeholder="Filtrar por ator, ação, recurso ou caminho..."
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        className="mb-4 max-w-md"
      />

      {auditQuery.isLoading && <Skeleton className="h-64" />}

      {auditQuery.isError && (
        <EmptyState
          icon={ServerCrash}
          title="Não foi possível carregar a auditoria"
          description={loadErrorDescription(auditQuery.error)}
          action={
            <Button variant="outline" onClick={() => void auditQuery.refetch()}>
              Tentar novamente
            </Button>
          }
        />
      )}

      {auditQuery.isSuccess && rows.length === 0 && (
        <EmptyState
          icon={Boxes}
          title={filter ? "Nenhum registro corresponde ao filtro" : "Sem registros de auditoria"}
        />
      )}

      {auditQuery.isSuccess && rows.length > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2.5 font-medium">Data/hora</th>
                  <th className="px-4 py-2.5 font-medium">Ator</th>
                  <th className="px-4 py-2.5 font-medium">Ação</th>
                  <th className="px-4 py-2.5 font-medium">Recurso</th>
                  <th className="px-4 py-2.5 font-medium">Caminho</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">IP</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((entry) => (
                  <tr key={entry.id} className="border-b border-slate-800/60">
                    <td className="whitespace-nowrap px-4 py-2 text-xs text-slate-400">
                      {new Date(entry.timestamp).toLocaleString("pt-BR")}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-200">{entry.actor}</td>
                    <td
                      className={`px-4 py-2 text-xs font-medium ${
                        METHOD_COLOR[entry.action] ?? "text-slate-300"
                      }`}
                    >
                      {entry.action}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">
                      {entry.resource_type}
                      {entry.resource_id ? `/${entry.resource_id}` : ""}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-500">
                      {entry.path ?? "--"}
                    </td>
                    <td className={`px-4 py-2 text-xs ${statusColor(entry.status_code)}`}>
                      {entry.status_code ?? "--"}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500">
                      {entry.ip_address ?? "--"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </AppShell>
  );
}
