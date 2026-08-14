import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AlertWatcher } from "@/components/AlertWatcher";
import { AuthGuard } from "@/components/AuthGuard";
import { Toaster } from "@/components/Toaster";

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
          <AuthGuard>{children}</AuthGuard>
          <AlertWatcher />
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
