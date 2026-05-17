# Frontend — Predicta

Aplicação web em **Next.js 14** (App Router, TypeScript estrito).

## Páginas (Sprint 1)

| Rota | Descrição |
|---|---|
| `/login` | Autenticação (mock) |
| `/dashboard` | Lista de ativos cadastrados |
| `/asset/[tag]` | Detalhe do ativo + telemetria em tempo real |

## Desenvolvimento local

```bash
npm install
npm run dev
```

A aplicação espera a API em `NEXT_PUBLIC_API_URL` (padrão `http://localhost:8000`).

## Stack

- **Next.js 14** — App Router, Server/Client Components
- **TanStack Query** — estado de servidor e polling em tempo real
- **Zustand** — estado de autenticação no cliente
- **Recharts** — gráficos de séries temporais
- **Tailwind CSS** — estilização
- **react-hook-form + zod** — formulários validados
