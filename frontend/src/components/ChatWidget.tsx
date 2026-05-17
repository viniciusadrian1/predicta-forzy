"use client";

import { MessageCircle, X } from "lucide-react";
import { useState } from "react";

import { ChatPanel } from "@/components/ChatPanel";

interface ChatWidgetProps {
  /** Ativo cujo contexto (telemetria, alertas, RUL) alimenta o chat. */
  assetTag?: string;
}

/** Widget de chat flutuante - botao no canto inferior direito + painel. */
export function ChatWidget({ assetTag }: ChatWidgetProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[520px] w-[min(380px,calc(100vw-3rem))] flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-slate-100">
                Assistente Predicta
              </p>
              <p className="text-xs text-slate-500">
                {assetTag ? `Troubleshooting - ${assetTag}` : "Troubleshooting"}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Fechar assistente"
              className="text-slate-400 hover:text-slate-200"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <ChatPanel assetTag={assetTag} className="flex-1 overflow-hidden" />
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? "Fechar assistente" : "Abrir assistente"}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-cyan-500 text-slate-950 shadow-lg transition-colors hover:bg-cyan-400"
      >
        {open ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>
    </>
  );
}
