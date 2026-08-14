import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Estado vazio/erro padronizado: ícone + título + descrição + ação opcional. */
export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-slate-800 bg-slate-900/40 px-6 py-12 text-center">
      {Icon && <Icon className="mb-3 h-8 w-8 text-slate-600" />}
      <p className="text-sm font-medium text-slate-200">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-xs text-slate-500">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
