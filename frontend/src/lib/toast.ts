import { create } from "zustand";

export type ToastSeverity = "info" | "warning" | "critical";

export interface Toast {
  id: string;
  title: string;
  description?: string;
  severity: ToastSeverity;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
}

/** Store de notificacoes toast (efemeras, auto-dispensadas em 6 s). */
export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = Math.random().toString(36).slice(2);
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) }));
    }, 6000);
  },
  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}));
