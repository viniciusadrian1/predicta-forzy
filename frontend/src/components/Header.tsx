"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Activity, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/dashboard", label: "Painel" },
  { href: "/alerts", label: "Alertas" },
  { href: "/chat", label: "Assistente" },
];

export function Header() {
  const username = useAuth((s) => s.username);
  const role = useAuth((s) => s.role);
  const logout = useAuth((s) => s.logout);
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const handleLogout = () => {
    logout();
    queryClient.clear();
    router.replace("/login");
  };

  return (
    <header className="border-b border-slate-800 bg-slate-900/50">
      <div className="mx-auto flex max-w-[1536px] items-center justify-between px-6 py-3 lg:px-8">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 font-semibold text-slate-100"
        >
          <Activity className="h-5 w-5 text-cyan-400" />
          Predicta
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname.startsWith(link.href) ? "page" : undefined}
              className={cn(
                "hover:text-slate-200",
                pathname.startsWith(link.href)
                  ? "font-medium text-cyan-400"
                  : "text-slate-400",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="text-sm">
          {mounted && username ? (
            <div className="flex items-center gap-3">
              <span className="hidden text-slate-400 sm:inline">
                {username}
                {role && <span className="text-slate-600"> · {role}</span>}
              </span>
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex items-center gap-1 text-slate-400 hover:text-slate-200"
              >
                <LogOut className="h-4 w-4" />
                Sair
              </button>
            </div>
          ) : (
            <Link href="/login" className="text-cyan-400 hover:text-cyan-300">
              Entrar
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
