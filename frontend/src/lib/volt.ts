import { create } from "zustand";

// Abertura do assistente compartilhada entre o widget flutuante e quem chama
// por ele de dentro da página (ex.: "Perguntar ao assistente" no card de
// próxima ação). Antes o estado era local do VoltWidget e o texto do card era
// só um <span> morto, mandando o usuário caçar o botão flutuante sozinho.

interface VoltState {
  open: boolean;
  /** TAG que motivou a abertura, para o chat já começar no ativo certo. */
  pendingTag: string | null;
  openFor: (tag?: string) => void;
  close: () => void;
  /** O chat consome a TAG uma única vez, para não repetir a cada reabertura. */
  consumeTag: () => string | null;
}

export const useVolt = create<VoltState>((set, get) => ({
  open: false,
  pendingTag: null,
  openFor: (tag) => set({ open: true, pendingTag: tag ?? null }),
  close: () => set({ open: false }),
  consumeTag: () => {
    const tag = get().pendingTag;
    if (tag !== null) set({ pendingTag: null });
    return tag;
  },
}));
