"use client";

import { Bot, Loader2, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { streamChat } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatSource } from "@/types";

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  mode?: string;
}

const SUGGESTIONS = [
  "Qual o limite de vibração do motor?",
  "O que indica desgaste de rolamento?",
  "Como interpretar as zonas da ISO 10816?",
  "Qual o plano de manutenção recomendado?",
];

interface ChatPanelProps {
  /** Quando informado, o chat usa a telemetria/alertas/RUL do ativo como contexto. */
  assetTag?: string;
  className?: string;
}

/** Painel de chat reutilizavel: usado na pagina /chat e no widget flutuante. */
export function ChatPanel({ assetTag, className }: ChatPanelProps) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages]);

  async function send(question: string) {
    const text = question.trim();
    if (!text || streaming) return;
    setError(null);
    setInput("");

    const history = messages
      .filter((message) => message.content.trim())
      .map((message) => ({ role: message.role, content: message.content }));

    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);
    setStreaming(true);

    const patchLast = (patch: Partial<DisplayMessage>) =>
      setMessages((prev) => {
        const copy = [...prev];
        const index = copy.length - 1;
        copy[index] = { ...copy[index], ...patch };
        return copy;
      });

    try {
      await streamChat(
        { message: text, assetTag, history },
        {
          onSources: (sources, mode) => patchLast({ sources, mode }),
          onToken: (chunk) =>
            setMessages((prev) => {
              const copy = [...prev];
              const index = copy.length - 1;
              copy[index] = { ...copy[index], content: copy[index].content + chunk };
              return copy;
            }),
          onDone: (answer, mode) => patchLast({ content: answer, mode }),
        },
      );
    } catch {
      setError("Não foi possível falar com o assistente.");
      patchLast({
        content:
          "Desculpe, não consegui responder agora. Verifique se a API está disponível.",
      });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className={cn("flex flex-col", className)}>
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Sparkles className="mb-3 h-8 w-8 text-cyan-400" />
            <p className="text-sm font-medium text-slate-200">
              Assistente de troubleshooting
            </p>
            <p className="mt-1 max-w-xs text-xs text-slate-500">
              Pergunte sobre vibração, falhas, manutenção e a saúde dos motores. As
              respostas citam a documentação técnica.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void send(suggestion)}
                  className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 transition-colors hover:border-cyan-500 hover:text-cyan-300"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message, index) => (
          <div
            key={index}
            className={cn(
              "flex gap-2",
              message.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            {message.role === "assistant" && (
              <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/15 text-cyan-400">
                <Bot className="h-4 w-4" />
              </div>
            )}
            <div
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                message.role === "user"
                  ? "bg-cyan-500 text-slate-950"
                  : "bg-slate-800 text-slate-100",
              )}
            >
              {message.content ? (
                <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
              ) : (
                <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              )}
              {message.role === "assistant" &&
                message.sources &&
                message.sources.length > 0 && (
                  <details className="mt-2 border-t border-slate-700 pt-2">
                    <summary className="cursor-pointer text-xs text-slate-400">
                      Fontes ({message.sources.length})
                      {message.mode === "offline" && " - modo offline"}
                      {message.mode === "anthropic" && " - via Claude"}
                    </summary>
                    <ul className="mt-2 space-y-2">
                      {message.sources.map((source, sourceIndex) => (
                        <li key={sourceIndex} className="text-xs text-slate-400">
                          <span className="font-medium text-slate-300">
                            {source.document_title}
                          </span>
                          <p className="mt-0.5 text-slate-500">{source.snippet}</p>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
            </div>
          </div>
        ))}
      </div>

      {error && <p className="px-4 pb-1 text-xs text-red-400">{error}</p>}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void send(input);
        }}
        className="flex items-center gap-2 border-t border-slate-800 p-3"
      >
        <input
          aria-label="Mensagem para o assistente"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={
            assetTag ? `Pergunte sobre o ${assetTag}...` : "Faça uma pergunta..."
          }
          disabled={streaming}
          className="h-10 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={streaming || !input.trim()}
          aria-label="Enviar mensagem"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-cyan-500 text-slate-950 transition-colors hover:bg-cyan-400 disabled:opacity-50"
        >
          {streaming ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </form>
    </div>
  );
}
