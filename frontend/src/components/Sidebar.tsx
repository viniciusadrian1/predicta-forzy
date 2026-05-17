"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { getHierarchy } from "@/lib/api";

const STATUS_DOT: Record<string, string> = {
  ok: "text-emerald-400",
  warning: "text-amber-400",
  critical: "text-red-400",
  unknown: "text-slate-500",
};

/** Arvore de navegacao Planta -> Area -> Ativo. */
export function Sidebar() {
  const hierarchyQuery = useQuery({
    queryKey: ["hierarchy"],
    queryFn: getHierarchy,
  });

  return (
    <aside className="w-60 shrink-0">
      <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        Hierarquia
      </h2>
      <nav className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-sm">
        {hierarchyQuery.isLoading && <p className="text-slate-500">Carregando...</p>}
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
    </aside>
  );
}
