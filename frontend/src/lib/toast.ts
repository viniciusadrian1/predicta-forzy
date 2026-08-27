import { create } from "zustand";

export type ToastSeverity = "info" | "warning" | "critical";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  severity: ToastSeverity;
  /** Destino opcional — o toast vira atalho clicável (ex.: /asset/MTR-001). */
  href?: string;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
}

// No máximo N toasts visíveis (novos empurram os antigos), auto-dispensados
// em alguns segundos - evita a pilha alta quando chegam vários alertas juntos.
const MAX_TOASTS = 4;
const TOAST_TTL_MS = 6000;

/** Store de notificações toast (efêmeras, empilhamento limitado). */
export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = Math.random().toString(36).slice(2);
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }].slice(-MAX_TOASTS),
    }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) }));
    }, TOAST_TTL_MS);
  },
  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}));
