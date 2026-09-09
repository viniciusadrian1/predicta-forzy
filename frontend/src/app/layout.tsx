import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AlertWatcher } from "@/components/AlertWatcher";
import { AuthGuard } from "@/components/AuthGuard";
import { Toaster } from "@/components/Toaster";
import { VoltWidget } from "@/components/VoltWidget";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Predicta",
  description: "Monitoramento e manutenção preditiva de motores industriais",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen">
        <Providers>
          {/* O Volt fica ACIMA do slot de pagina. O AppShell e renderizado
              por CADA page.tsx, entao navegar desmontava o widget e levava
              junto a conversa e a requisicao em voo. Aqui ele e a mesma
              instancia enquanto so `children` troca.
              Dentro do AuthGuard de proposito: o guarda ja segura o render ate
              hidratar e devolve null sem sessao, entao o botao flutuante nao
              pisca durante o redirect para /login. */}
          <AuthGuard>
            {children}
            <VoltWidget />
          </AuthGuard>
          <AlertWatcher />
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
