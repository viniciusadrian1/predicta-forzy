"use client";

// Chat guiado do Volt (assistente de manutenção): fluxo identificar ativo ->
// sintoma -> diagnóstico -> ordem de serviço ou handoff. Estado mantido no
// cliente e enviado a cada turno (backend stateless).

import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, CheckCircle2, Loader2, Send, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { voltGreeting, voltMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { VoltReply, VoltState } from "@/types";

interface Bubble {
  role: "bot" | "user";
  text: string;
  reply?: VoltReply; // anexos (diagnóstico/OS/handoff) na fala do bot
}

const PRIORITY_COLOR: Record<string, string> = {
  alta: "text-red-400",
  media: "text-amber-400",
  baixa: "text-slate-400",
};

function DiagnosisCard({ reply }: { reply: VoltReply }) {
  const wo = reply.work_order;
  const dx = reply.diagnosis;
  if (!wo || !dx) return null;
  return (
    <div className="mt-2 rounded-lg border border-emerald-600/40 bg-emerald-950/30 p-3">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        <span className="text-sm font-medium text-slate-100">Ordem de serviço aberta</span>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <dt className="text-slate-500">Número</dt>
        <dd className="font-mono text-slate-200">{wo.number}</dd>
        <dt className="text-slate-500">Diagnóstico</dt>
        <dd className="text-slate-200">{dx.fault}</dd>
        <dt className="text-slate-500">Confiança</dt>
        <dd className="text-slate-200">{Math.round(dx.confidence * 100)}%</dd>
        <dt className="text-slate-500">Prioridade</dt>
        <dd className={PRIORITY_COLOR[wo.priority] ?? "text-slate-200"}>{wo.priority}</dd>
      </dl>
      {dx.evidence && (
        <p className="mt-2 border-t border-slate-800 pt-2 text-[11px] text-slate-500">
          Evidência: {dx.evidence}
        </p>
      )}
    </div>
  );
}

function SourcesCard({ reply }: { reply: VoltReply }) {
  const sources = reply.sources ?? [];
  if (sources.length === 0) return null;
  return (
    <details className="mt-2 border-t border-slate-700 pt-2">
      <summary className="cursor-pointer text-xs text-slate-400">
        Fontes ({sources.length}) — base técnica
      </summary>
      <ul className="mt-2 space-y-2">
        {sources.map((source, index) => (
          <li key={index} className="text-xs text-slate-400">
            <span className="font-medium text-slate-300">{source.document_title}</span>
            <p className="mt-0.5 text-slate-500">{source.snippet}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}

function HandoffCard({ reply }: { reply: VoltReply }) {
  const h = reply.handoff;
  if (!h) return null;
  return (
    <div className="mt-2 rounded-lg border border-amber-600/40 bg-amber-950/30 p-3">
      <div className="flex items-center gap-2">
        <UserRound className="h-4 w-4 text-amber-400" />
        <span className="text-sm font-medium text-slate-100">
          Encaminhado para um técnico
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-400">Resumo entregue ao atendente:</p>
      <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        {h.asset_tag && (
          <>
            <dt className="text-slate-500">Ativo</dt>
            <dd className="text-slate-200">
              {h.asset_tag}
              {h.asset_name ? ` — ${h.asset_name}` : ""}
            </dd>
          </>
        )}
        {h.symptom && (
          <>
            <dt className="text-slate-500">Sintoma</dt>
            <dd className="text-slate-200">{h.symptom}</dd>
          </>
        )}
        {h.diagnosis && (
          <>
            <dt className="text-slate-500">Diagnóstico</dt>
            <dd className="text-slate-200">
              {h.diagnosis}
              {h.confidence !== null ? ` (${Math.round(h.confidence * 100)}%)` : ""}
            </dd>
          </>
        )}
        <dt className="text-slate-500">Ações</dt>
        <dd className="text-slate-200">{h.actions_taken}</dd>
        <dt className="text-slate-500">Motivo</dt>
        <dd className="text-slate-200">{h.reason}</dd>
      </dl>
    </div>
  );
}

export function VoltChat() {
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [state, setState] = useState<VoltState | null>(null);
  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Saudação inicial do Volt (capacidades ditas de cara).
  const greetingQuery = useQuery({ queryKey: ["volt-greeting"], queryFn: voltGreeting });
  useEffect(() => {
    if (greetingQuery.data && bubbles.length === 0) {
      setBubbles([{ role: "bot", text: greetingQuery.data.message }]);
      setState(greetingQuery.data.state);
    }
  }, [greetingQuery.data, bubbles.length]);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [bubbles]);

  const mutation = useMutation({
    // Envia o histórico (bolhas anteriores) para dar memória ao assistente.
    mutationFn: (text: string) =>
      voltMessage(
        text,
        state,
        bubbles.map((bubble) => ({ role: bubble.role, text: bubble.text })),
      ),
    onSuccess: (reply) => {
      setBubbles((prev) => [...prev, { role: "bot", text: reply.message, reply }]);
      setState(reply.state);
      setQuickReplies(reply.quick_replies);
    },
    onError: () =>
      setBubbles((prev) => [
        ...prev,
        { role: "bot", text: "Tive um problema para responder. Verifique a conexão e tente de novo." },
      ]),
  });

  const send = (text: string) => {
    const value = text.trim();
    if (!value || mutation.isPending) return;
    setBubbles((prev) => [...prev, { role: "user", text: value }]);
    setQuickReplies([]);
    setInput("");
    mutation.mutate(value);
  };

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {bubbles.map((bubble, index) => (
          <div
            key={index}
            className={cn(
              "flex gap-2",
              bubble.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            {bubble.role === "bot" && (
              <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/15 text-cyan-400">
                <Bot className="h-4 w-4" />
              </div>
            )}
            <div
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                bubble.role === "user"
                  ? "bg-cyan-500 text-slate-950"
                  : "bg-slate-800 text-slate-100",
              )}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{bubble.text}</p>
              {bubble.reply && <DiagnosisCard reply={bubble.reply} />}
              {bubble.reply && <HandoffCard reply={bubble.reply} />}
              {bubble.reply && <SourcesCard reply={bubble.reply} />}
            </div>
          </div>
        ))}
        {bubbles.length === 0 && greetingQuery.isLoading && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Volt está iniciando...
          </div>
        )}
        {bubbles.length === 0 && greetingQuery.isError && (
          <div className="flex flex-col items-start gap-2 rounded-lg bg-slate-800 px-3 py-2 text-sm text-slate-100">
            <p>Não consegui iniciar agora. Verifique a conexão.</p>
            <button
              type="button"
              onClick={() => greetingQuery.refetch()}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs text-cyan-300 hover:border-cyan-500 hover:text-cyan-200"
            >
              Tentar novamente
            </button>
          </div>
        )}
        {mutation.isPending && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Volt está preparando a resposta...
          </div>
        )}
      </div>

      {/* Quick replies (chips de sintoma / falar com humano) */}
      {quickReplies.length > 0 && (
        <div className="flex shrink-0 flex-wrap gap-2 border-t border-slate-800 px-4 pt-3">
          {quickReplies.map((qr) => (
            <button
              key={qr}
              type="button"
              onClick={() => send(qr)}
              className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-cyan-500 hover:text-cyan-300"
            >
              {qr}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(input);
        }}
        className="flex shrink-0 items-center gap-2 border-t border-slate-800 p-3"
      >
        <input
          aria-label="Mensagem para o Volt"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Código do ativo, sintoma ou uma pergunta técnica..."
          disabled={mutation.isPending}
          className="h-10 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={mutation.isPending || !input.trim()}
          aria-label="Enviar"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-cyan-500 text-slate-950 transition-colors hover:bg-cyan-400 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
