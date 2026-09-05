"use client";

// Widget flutuante global do Volt: botão no canto inferior direito, disponível
// em todas as telas. Oculto na própria página do Volt (evita redundância).

import { Wrench, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { VoltChat } from "@/components/VoltChat";

export function VoltWidget() {
  const [open, setOpen] = useState(false);
  // Monta o chat na 1a abertura e nunca desmonta: preserva a conversa ao
  // fechar/reabrir (sem refazer a saudacao). Antes o `open &&` desmontava tudo.
  const [mounted, setMounted] = useState(false);
  const pathname = usePathname();

  // Na página cheia do Volt (ou no login) o widget nao faz sentido.
  if (pathname.startsWith("/volt") || pathname.startsWith("/login")) return null;

  return (
    <>
      {mounted && (
        <div
          className={`fixed bottom-24 right-6 z-50 flex h-[min(560px,75dvh)] w-[min(400px,calc(100vw-3rem))] flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900 shadow-2xl ${
            open ? "" : "hidden"
          }`}
        >
          <div className="flex shrink-0 items-center justify-between border-b border-slate-800 px-4 py-3">
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4 text-cyan-400" />
              <div>
                <p className="text-sm font-semibold text-slate-100">Volt</p>
                <p className="text-xs text-slate-500">Assistente de manutenção</p>
              </div>
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
          {/* min-h-0 + flex-1: o chat ocupa o espaco RESTANTE (o header ja
              consumiu parte). Sem isso o h-full do chat pedia 100% da altura
              toda e o formulario transbordava para fora do painel, ficando
              inclicavel (os cliques caiam na pagina atras). */}
          <div className="min-h-0 flex-1">
            <VoltChat />
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() =>
          setOpen((value) => {
            if (!value) setMounted(true);
            return !value;
          })
        }
        aria-label={open ? "Fechar o Volt" : "Abrir o Volt"}
        title="Falar com o Volt"
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-cyan-500 text-slate-950 shadow-lg transition-colors hover:bg-cyan-400"
      >
        {open ? <X className="h-6 w-6" /> : <Wrench className="h-6 w-6" />}
      </button>
    </>
  );
}
