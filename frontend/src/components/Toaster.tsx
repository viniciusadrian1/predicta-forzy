"use client";

import { X } from "lucide-react";
import { useRouter } from "next/navigation";

import { useToasts } from "@/lib/toast";
import { cn } from "@/lib/utils";

const TOAST_STYLES: Record<string, string> = {
  info: "border-cyan-600/40 bg-cyan-950/90",
  warning: "border-amber-600/40 bg-amber-950/90",
  critical: "border-red-600/40 bg-red-950/90",
};

/** Renderiza as notificações toast no canto inferior direito. */
export function Toaster() {
  const toasts = useToasts((state) => state.toasts);
  const dismiss = useToasts((state) => state.dismiss);
  const router = useRouter();

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2 lg:right-24"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          onClick={() => {
            if (toast.href) {
              router.push(toast.href);
              dismiss(toast.id);
            }
          }}
          className={cn(
            "flex items-start gap-2 rounded-lg border p-3 text-left shadow-lg",
            TOAST_STYLES[toast.severity],
            toast.href && "cursor-pointer hover:brightness-125",
          )}
        >
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-100">{toast.title}</p>
            {toast.description && (
              <p className="mt-0.5 text-xs text-slate-300">{toast.description}</p>
            )}
            {toast.href && (
              <p className="mt-1 text-xs text-cyan-400">Clique para abrir →</p>
            )}
          </div>
          <button
            type="button"
            aria-label="Dispensar notificação"
            onClick={(event) => {
              event.stopPropagation();
              dismiss(toast.id);
            }}
            className="text-slate-400 hover:text-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
