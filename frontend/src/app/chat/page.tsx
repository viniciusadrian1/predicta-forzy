"use client";

import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/AppShell";
import { ChatPanel } from "@/components/ChatPanel";
import { Card } from "@/components/ui/card";
import { getRagStatus } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

export default function ChatPage() {
  usePageTitle("Assistente");
  const statusQuery = useQuery({
    queryKey: ["rag-status"],
    queryFn: getRagStatus,
    refetchOnWindowFocus: false,
  });
  const status = statusQuery.data;

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl">
        <h1 className="text-xl font-semibold text-slate-100">
          Assistente de Troubleshooting
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Chat com RAG sobre a documentação técnica dos motores. As respostas são
          fundamentadas nos manuais e podem usar a telemetria do ativo.
        </p>

        {status && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-slate-700 px-2.5 py-1 text-slate-400">
              {status.documents} documento(s)
            </span>
            <span className="rounded-full border border-slate-700 px-2.5 py-1 text-slate-400">
              {status.indexed_chunks} trechos indexados
            </span>
            <span className="rounded-full border border-slate-700 px-2.5 py-1 text-slate-400">
              LLM: {status.llm_mode === "anthropic" ? "Claude" : "modo offline"}
            </span>
          </div>
        )}

        <Card className="mt-5 h-[70vh] overflow-hidden p-0">
          <ChatPanel className="h-full" />
        </Card>
      </div>
    </AppShell>
  );
}
