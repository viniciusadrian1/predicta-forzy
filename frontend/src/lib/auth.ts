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

// Hierarquia de papeis - espelho de backend/app/core/rbac.py.
const ROLE_LEVEL: Record<string, number> = {
  viewer: 0,
  operator: 1,
  engineer: 2,
  admin: 3,
};

/** Indica se `role` satisfaz o papel minimo `minimum` (null = viewer). */
export function hasRole(role: string | null, minimum: keyof typeof ROLE_LEVEL): boolean {
  return (ROLE_LEVEL[role ?? "viewer"] ?? 0) >= ROLE_LEVEL[minimum];
}
