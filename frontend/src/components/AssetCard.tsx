import { Cpu } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { Card } from "@/components/ui/card";
import type { Asset } from "@/types";

export function AssetCard({
  asset,
  points = 0,
  status,
}: {
  asset: Asset;
  /** Quantos pontos de medicao este ativo agrupa (0 = mede a si proprio). */
  points?: number;
  /** Status efetivo (pior entre os pontos); default = o do proprio ativo. */
  status?: string;
}) {
  return (
    <Link href={`/asset/${asset.tag}`}>
      <Card className="h-full p-5 transition-colors hover:border-cyan-600/50">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-cyan-400" />
            <span className="text-lg font-semibold text-slate-100">{asset.tag}</span>
          </div>
          <StatusBadge status={status ?? asset.status} />
        </div>
        <p className="mt-2 text-sm text-slate-300">{asset.name ?? "Sem descrição"}</p>
        {points > 0 && (
          <p className="mt-1 inline-flex items-center gap-1 rounded-full border border-slate-700 px-2 py-0.5 text-[11px] text-slate-400">
            {points} pontos de medição
          </p>
        )}
        <p className="mt-1 text-xs text-slate-500">
          {[asset.manufacturer, asset.model].filter(Boolean).join(" — ") ||
            "Fabricante não informado"}
        </p>
        {asset.power_kw !== null && (
          <p className="mt-3 text-xs text-slate-400">
            {asset.power_kw} kW · {asset.voltage_v ?? "?"} V · {asset.nominal_rpm ?? "?"} RPM
          </p>
        )}
      </Card>
    </Link>
  );
}
