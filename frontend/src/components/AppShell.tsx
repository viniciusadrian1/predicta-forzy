"use client";

// Casca unificada da aplicação: sidebar fixa (menu + hierarquia + usuário)
// em todas as páginas autenticadas, com variante mobile recolhível.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Bell,
  Bot,
  ChevronRight,
  Factory,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { getHierarchy } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

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

  if (hierarchyQuery.isLoading) {
    return (
      <div className="flex flex-col gap-2 px-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="ml-3 h-3 w-24" />
        <Skeleton className="ml-6 h-3 w-20" />
      </div>
    );
  }

  return (
    <div className="px-3 text-sm">
      {hierarchyQuery.data?.map((plant) => (
        <div key={plant.id} className="mb-2">
          <Link
            href={`/plant/${plant.id}`}
            className="flex items-center gap-1 font-medium text-slate-300 hover:text-cyan-400"
          >
            <ChevronRight className="h-3.5 w-3.5" />
            {plant.name}
          </Link>
          {plant.areas.map((area) => (
            <div key={area.id} className="ml-4 mt-1">
              <p className="text-xs text-slate-500">{area.name}</p>
              {area.assets.map((asset) => (
                <Link
                  key={asset.id}
                  href={`/asset/${asset.tag}`}
                  className="ml-2 flex items-center gap-1.5 py-0.5 text-slate-400 hover:text-cyan-400"
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
    </div>
  );
}

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  /** Prefixos de rota que marcam o item como ativo. */
  match: string[];
}

function useNav(): NavItem[] {
  // O item "Planta" leva à primeira planta cadastrada.
  const hierarchyQuery = useQuery({ queryKey: ["hierarchy"], queryFn: getHierarchy });
  const plantId = hierarchyQuery.data?.[0]?.id;
  return [
    { href: "/overview", label: "Visão Geral", icon: LayoutDashboard, match: ["/overview"] },
    { href: "/assets", label: "Ativos", icon: Package, match: ["/assets", "/asset/", "/register"] },
    ...(plantId
      ? [{ href: `/plant/${plantId}`, label: "Planta", icon: Factory, match: ["/plant"] }]
      : []),
    { href: "/alerts", label: "Alertas", icon: Bell, match: ["/alerts"] },
    { href: "/chat", label: "Assistente", icon: Bot, match: ["/chat"] },
  ];
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const nav = useNav();
  return (
    <nav className="flex flex-col gap-1 px-3">
      {nav.map((item) => {
        const active = item.match.some((prefix) => pathname.startsWith(prefix));
        return (
          <Link
            key={item.label}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
              active
                ? "bg-cyan-500/10 font-medium text-cyan-400"
                : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200",
            )}
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function UserBlock() {
  const username = useAuth((s) => s.username);
  const role = useAuth((s) => s.role);
  const logout = useAuth((s) => s.logout);
  const queryClient = useQueryClient();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const handleLogout = () => {
    logout();
    queryClient.clear();
    router.replace("/login");
  };

  if (!mounted || !username) return null;
  return (
    <div className="flex items-center justify-between gap-2 border-t border-slate-800 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm text-slate-300">{username}</p>
        <p className="text-xs text-slate-600">{role}</p>
      </div>
      <button
        type="button"
        onClick={handleLogout}
        title="Sair"
        aria-label="Sair"
        className="text-slate-500 hover:text-slate-200"
      >
        <LogOut className="h-4 w-4" />
      </button>
    </div>
  );
}

/** Layout de aplicação: sidebar fixa no desktop, topbar com menu no mobile. */
export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-dvh">
      {/* Sidebar desktop */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900/50 lg:flex">
        <Link
          href="/overview"
          className="flex items-center gap-2 px-4 py-4 font-semibold text-slate-100"
        >
          <Activity className="h-5 w-5 text-cyan-400" />
          Predicta
        </Link>
        <NavLinks />
        <p className="mt-5 px-6 text-[10px] font-medium uppercase tracking-wide text-slate-600">
          Hierarquia
        </p>
        <div className="mt-2 flex-1 overflow-y-auto pb-4">
          <HierarchyTree />
        </div>
        <UserBlock />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar mobile */}
        <header className="flex items-center justify-between border-b border-slate-800 bg-slate-900/50 px-4 py-3 lg:hidden">
          <Link href="/overview" className="flex items-center gap-2 font-semibold text-slate-100">
            <Activity className="h-5 w-5 text-cyan-400" />
            Predicta
          </Link>
          <button
            type="button"
            aria-label={mobileOpen ? "Fechar menu" : "Abrir menu"}
            onClick={() => setMobileOpen((open) => !open)}
            className="text-slate-300"
          >
            <Menu className="h-5 w-5" />
          </button>
        </header>
        {mobileOpen && (
          <div className="border-b border-slate-800 bg-slate-900/80 py-3 lg:hidden">
            <NavLinks onNavigate={() => setMobileOpen(false)} />
            <UserBlock />
          </div>
        )}

        <main className="mx-auto w-full max-w-[1536px] flex-1 px-6 py-8 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
