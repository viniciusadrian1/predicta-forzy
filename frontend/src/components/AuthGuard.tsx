"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { getMe } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const PUBLIC_ROUTES = new Set(["/login"]);

/**
 * Guard de sessão client-side: rotas protegidas exigem token.
 * O middleware do Next não lê localStorage, então a decisão acontece após a
 * hidratação do store persistido — antes disso não renderizamos nada, para
 * não haver flash de conteúdo autenticado nem mismatch de hidratação.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const token = useAuth((state) => state.token);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => setHydrated(true), []);

  const isPublic = PUBLIC_ROUTES.has(pathname);

  useEffect(() => {
    if (hydrated && !token && !isPublic) {
      router.replace("/login");
    }
  }, [hydrated, token, isPublic, router]);

  // Valida a sessão persistida; token expirado (15 min) dispara o handler
  // global de 401 em lib/api.ts, que desloga e redireciona com aviso.
  useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: hydrated && !!token,
    staleTime: Infinity,
    retry: false,
  });

  if (!hydrated) return null;
  if (!token && !isPublic) return null; // redirect em andamento, sem flash

  return <>{children}</>;
}
