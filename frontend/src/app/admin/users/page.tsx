"use client";

// Usuários: contas cadastradas e seus papéis (RBAC). Consome GET /users (admin).
// ponytail: somente leitura — criar/editar exige endpoints novos no backend.

import { useQuery } from "@tanstack/react-query";
import { ServerCrash, Users } from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listUsers } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

const ROLE_COLOR: Record<string, string> = {
  admin: "text-red-400 border-red-500/40",
  engineer: "text-cyan-400 border-cyan-500/40",
  operator: "text-amber-400 border-amber-500/40",
  viewer: "text-slate-400 border-slate-600",
};

export default function UsersPage() {
  usePageTitle("Usuários");
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: listUsers });

  return (
    <AppShell>
      <div className="mb-4 flex items-center gap-2">
        <Users className="h-5 w-5 text-cyan-400" />
        <h1 className="text-xl font-semibold text-slate-100">Usuários</h1>
        <span className="ml-auto text-sm text-slate-500">
          {usersQuery.data?.length ?? 0} conta(s)
        </span>
      </div>
      <p className="mb-4 text-sm text-slate-400">
        Contas cadastradas e seus papéis de acesso. As senhas são protegidas por
        hashing argon2 e nunca expostas.
      </p>

      {usersQuery.isLoading && <Skeleton className="h-48" />}

      {usersQuery.isError && (
        <EmptyState
          icon={ServerCrash}
          title="Não foi possível carregar os usuários"
          description="Verifique a conexão com a API e tente novamente."
          action={
            <Button variant="outline" onClick={() => void usersQuery.refetch()}>
              Tentar novamente
            </Button>
          }
        />
      )}

      {usersQuery.isSuccess && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2.5 font-medium">Usuário</th>
                  <th className="px-4 py-2.5 font-medium">Nome</th>
                  <th className="px-4 py-2.5 font-medium">Papel</th>
                  <th className="px-4 py-2.5 font-medium">Situação</th>
                  <th className="px-4 py-2.5 font-medium">Criado em</th>
                </tr>
              </thead>
              <tbody>
                {usersQuery.data.map((user) => (
                  <tr key={user.id} className="border-b border-slate-800/60">
                    <td className="px-4 py-2.5 font-medium text-slate-200">
                      {user.username}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400">{user.full_name ?? "--"}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs ${
                          ROLE_COLOR[user.role] ?? ROLE_COLOR.viewer
                        }`}
                      >
                        {user.role}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {user.is_active ? (
                        <span className="text-emerald-400">Ativo</span>
                      ) : (
                        <span className="text-slate-500">Inativo</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">
                      {new Date(user.created_at).toLocaleDateString("pt-BR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </AppShell>
  );
}
