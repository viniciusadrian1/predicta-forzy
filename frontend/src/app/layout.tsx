import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AlertWatcher } from "@/components/AlertWatcher";
import { Toaster } from "@/components/Toaster";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Forzy Digital Twin",
  description: "Monitoramento e manutencao preditiva de motores industriais",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen">
        <Providers>
          {children}
          <AlertWatcher />
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
