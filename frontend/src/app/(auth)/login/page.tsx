"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { login } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const loginSchema = z.object({
  username: z.string().min(1, "Informe o usuario"),
  password: z.string().min(1, "Informe a senha"),
});

type LoginValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuth((s) => s.setAuth);
  const [serverError, setServerError] = useState<string | null>(null);

  const { register, handleSubmit, formState } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "admin", password: "admin123" },
  });

  const onSubmit = async (values: LoginValues) => {
    setServerError(null);
    try {
      const token = await login(values.username, values.password);
      setAuth(token);
      router.push("/dashboard");
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
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="flex flex-col gap-3"
            noValidate
          >
            <div>
              <label htmlFor="username" className="text-xs text-slate-400">
                Usuario
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
            <p className="text-center text-xs text-slate-500">
              Demonstracao: admin / admin123
            </p>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
