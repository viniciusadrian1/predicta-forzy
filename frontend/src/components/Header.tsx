"use client";

import { Activity, LogOut } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";

export function Header() {
  const username = useAuth((s) => s.username);
  const logout = useAuth((s) => s.logout);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

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
          <Link href="/dashboard" className="text-slate-400 hover:text-slate-200">
            Painel
          </Link>
          <Link href="/alerts" className="text-slate-400 hover:text-slate-200">
            Alertas
          </Link>
          <Link href="/chat" className="text-slate-400 hover:text-slate-200">
            Assistente
          </Link>
        </nav>
        <div className="text-sm">
          {mounted && username ? (
            <div className="flex items-center gap-3">
              <span className="text-slate-400">{username}</span>
              <button
                type="button"
                onClick={logout}
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
