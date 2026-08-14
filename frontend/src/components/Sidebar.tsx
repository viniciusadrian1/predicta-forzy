"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { getHierarchy } from "@/lib/api";

const STATUS_DOT: Record<string, string> = {
  ok: "text-emerald-400",
  warning: "text-amber-400",
  critical: "text-red-400",
  unknown: "text-slate-500",
};

function HierarchyTree() {
  const hierarchyQuery = useQuery({
    queryKey: ["hierarchy"],
    queryFn: getHierarchy,
    refetchInterval: 15000,
  });

  return (
    <nav className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-sm">
      {hierarchyQuery.isLoading && (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="ml-4 h-3 w-28" />
          <Skeleton className="ml-7 h-3 w-24" />
          <Skeleton className="ml-7 h-3 w-20" />
        </div>
      )}
      {hierarchyQuery.data?.length === 0 && (
        <p className="text-slate-500">Sem plantas cadastradas.</p>
      )}
      {hierarchyQuery.data?.map((plant) => (
        <div key={plant.id} className="mb-2">
          <Link
            href={`/plant/${plant.id}`}
            className="flex items-center gap-1 font-medium text-slate-200 hover:text-cyan-400"
          >
            <ChevronRight className="h-3.5 w-3.5" />
            {plant.name}
          </Link>
          {plant.areas.map((area) => (
            <div key={area.id} className="ml-4 mt-1">
              <p className="text-xs text-slate-400">{area.name}</p>
              {area.assets.map((asset) => (
                <Link
                  key={asset.id}
                  href={`/asset/${asset.tag}`}
                  className="ml-3 flex items-center gap-1.5 py-0.5 text-slate-300 hover:text-cyan-400"
                >
                  <span className={STATUS_DOT[asset.status] ?? STATUS_DOT.unknown}>
                    &#9679;
                  </span>
                  {asset.tag}
                </Link>
              ))}
            </div>
          ))}
        </div>
      ))}
    </nav>
  );
}

/** Árvore de navegação Planta → Área → Ativo. */
export function Sidebar() {
  return (
    <aside className="w-full shrink-0 lg:w-60">
      {/* Mobile: recolhida num <details> nativo para não empurrar a lista. */}
      <details className="lg:hidden">
        <summary className="mb-2 cursor-pointer text-xs font-medium uppercase tracking-wide text-slate-500">
          Hierarquia
        </summary>
        <HierarchyTree />
      </details>
      <div className="hidden lg:block">
        <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Hierarquia
        </h2>
        <HierarchyTree />
      </div>
    </aside>
  );
}
