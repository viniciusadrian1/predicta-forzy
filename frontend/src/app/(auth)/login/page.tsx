"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { login } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const loginSchema = z.object({
  username: z.string().min(1, "Informe o usuário"),
  password: z.string().min(1, "Informe a senha"),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuth((s) => s.setAuth);
  const token = useAuth((s) => s.token);
  const [serverError, setServerError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);

  // ?expired=1 vem do handler global de 401 (sessão de 15 min vencida).
  // Lido via window para não exigir <Suspense> de useSearchParams no build.
  useEffect(() => {
    setExpired(new URLSearchParams(window.location.search).has("expired"));
  }, []);

  // Já autenticado -> direto ao painel.
  useEffect(() => {
    if (token) router.replace("/overview");
  }, [token, router]);

  const { register, handleSubmit, formState } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (values: LoginValues) => {
    setServerError(null);
    try {
      const auth = await login(values.username, values.password);
      setAuth(auth);
      router.push("/overview");
    } catch (error) {
      setServerError(error instanceof Error ? error.message : "Falha no login");
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-lg">Predicta</CardTitle>
          <p className="text-sm text-slate-400">
            Acesse o painel de monitoramento de ativos
          </p>
        </CardHeader>
        <CardContent>
          {expired && (
            <p className="mb-3 rounded-md border border-amber-600/40 bg-amber-950/50 px-3 py-2 text-xs text-amber-300">
              Sessão expirada — entre novamente.
            </p>
          )}
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="flex flex-col gap-3"
            noValidate
          >
            <div>
              <label htmlFor="username" className="text-xs text-slate-400">
                Usuário
              </label>
              <Input id="username" autoComplete="username" {...register("username")} />
              {formState.errors.username && (
                <p className="mt-1 text-xs text-red-400">
                  {formState.errors.username.message}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="password" className="text-xs text-slate-400">
                Senha
              </label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...register("password")}
              />
              {formState.errors.password && (
                <p className="mt-1 text-xs text-red-400">
                  {formState.errors.password.message}
                </p>
              )}
            </div>
            {serverError && <p className="text-sm text-red-400">{serverError}</p>}
            <Button type="submit" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Entrando..." : "Entrar"}
            </Button>
            <p className="text-center text-xs text-slate-600">
              Ambiente de demonstração — admin · gestor · operador · auditor · viewer (senha:
              usuário + 123)
            </p>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
