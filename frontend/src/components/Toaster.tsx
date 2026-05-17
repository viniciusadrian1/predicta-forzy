"use client";

import { useToasts } from "@/lib/toast";
import { cn } from "@/lib/utils";

const TOAST_STYLES: Record<string, string> = {
  info: "border-cyan-600/40 bg-cyan-950/90",
  warning: "border-amber-600/40 bg-amber-950/90",
  critical: "border-red-600/40 bg-red-950/90",
};

/** Renderiza as notificacoes toast no canto inferior direito. */
export function Toaster() {
  const toasts = useToasts((state) => state.toasts);
  const dismiss = useToasts((state) => state.dismiss);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          type="button"
          onClick={() => dismiss(toast.id)}
          className={cn(
            "rounded-lg border p-3 text-left shadow-lg",
            TOAST_STYLES[toast.severity],
          )}
        >
          <p className="text-sm font-medium text-slate-100">{toast.title}</p>
          {toast.description && (
            <p className="mt-0.5 text-xs text-slate-300">{toast.description}</p>
          )}
        </button>
      ))}
    </div>
  );
}
