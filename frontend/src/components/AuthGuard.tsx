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

  // Valida a sessão persistida logo na entrada: um token vencido faz o
  // backend responder 401, e o handler global de lib/api.ts desloga e manda
  // relogar. Sem isso o usuário só descobria a sessão morta ao abrir uma tela
  // protegida — e, antes do 401 existir, nem assim.
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
