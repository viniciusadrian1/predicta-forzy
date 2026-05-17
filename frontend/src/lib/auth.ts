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
    { name: "forzy-auth" },
  ),
);
