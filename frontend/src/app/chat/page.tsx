"use client";

import { useQuery } from "@tanstack/react-query";

import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { Card } from "@/components/ui/card";
import { getRagStatus } from "@/lib/api";

export default function ChatPage() {
  const statusQuery = useQuery({
    queryKey: ["rag-status"],
    queryFn: getRagStatus,
    refetchOnWindowFocus: false,
  });
  const status = statusQuery.data;

  return (
    <div>
      <Header />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <h1 className="text-xl font-semibold text-slate-100">
          Assistente de Troubleshooting
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Chat com RAG sobre a documentacao tecnica dos motores. As respostas sao
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
      </main>
    </div>
  );
}
