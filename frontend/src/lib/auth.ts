import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AuthToken } from "@/types";

interface AuthState {
  token: string | null;
  username: string | null;
  role: string | null;
  setAuth: (auth: AuthToken) => void;
  logout: () => void;
}

/** Store de autenticacao, persistido em localStorage. */
export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      role: null,
      setAuth: (auth) =>
        set({
          token: auth.access_token,
          username: auth.username,
          role: auth.role,
        }),
      logout: () => set({ token: null, username: null, role: null }),
    }),
    { name: "predicta-auth" },
  ),
);

// Hierarquia de papeis (poder de escrita) - espelho de backend/app/core/rbac.py.
// 'auditor' e transversal: nivel de escrita = viewer, mas com leitura ampla.
const ROLE_LEVEL: Record<string, number> = {
  viewer: 0,
  auditor: 0,
  operator: 1,
  engineer: 2,
  admin: 3,
};

/** Indica se `role` satisfaz o papel minimo `minimum` (null = viewer). */
export function hasRole(role: string | null, minimum: keyof typeof ROLE_LEVEL): boolean {
  return (ROLE_LEVEL[role ?? "viewer"] ?? 0) >= ROLE_LEVEL[minimum];
}

// Papeis com acesso de leitura a auditoria e governanca (nao-linear).
const AUDIT_ROLES = new Set(["auditor", "admin"]);

/** Auditor ou admin: enxerga a trilha de auditoria e a governanca. */
export function canSeeAudit(role: string | null): boolean {
  return AUDIT_ROLES.has(role ?? "");
}

/** Auditor: so-leitura com telemetria mascarada (minimizacao de dados). */
export function isAuditor(role: string | null): boolean {
  return role === "auditor";
}

// Rotulo do perfil de acesso (governanca) para cada papel interno.
const ROLE_LABEL: Record<string, string> = {
  viewer: "Visualizador",
  auditor: "Auditor de Segurança",
  operator: "Técnico de Operação",
  engineer: "Gestor de Planta",
  admin: "Administrador do Sistema",
};

/** Nome do perfil exibido ao usuário (ex.: engineer -> "Gestor de Planta"). */
export function roleLabel(role: string | null): string {
  return ROLE_LABEL[role ?? ""] ?? (role ?? "");
}

/** Gestor de Planta (engineer) ou Admin: pode validar cadastro gerado por IA. */
export function canValidate(role: string | null): boolean {
  return role === "engineer" || role === "admin";
}
