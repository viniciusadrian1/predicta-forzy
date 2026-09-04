"use client";

/**
 * RoleMaturityLadder
 * ------------------
 * Diagrama visual dos 5 níveis de maturidade/acesso do Predicta.
 * Mostra a hierarquia RBAC de forma didática, com capacidades por papel
 * e destaque para o papel do usuário atual.
 *
 * Layout: trilhos horizontais empilhados.
 *  viewer → (auditor: transversal, tracejado) → operator → engineer → admin
 *
 * O auditor é exibido como um braço lateral, não linearmente acima do viewer,
 * pois possui o mesmo nível de escrita mas acesso de leitura transversal.
 */

import { cn } from "@/lib/utils";

interface RoleLevel {
  role: string;
  label: string;
  /** Hex para estilos inline. */
  hex: string;
  /** Descrição operacional em uma frase. */
  summary: string;
  /** Capacidades listadas no card. */
  capabilities: string[];
  /** Nível numérico na hierarquia linear (auditor = null = transversal). */
  level: number | null;
  transversal?: boolean;
}

const LEVELS: RoleLevel[] = [
  {
    role: "viewer",
    label: "Visualizador",
    hex: "#64748b",
    summary: "Observa o estado dos ativos sem modificar nada.",
    capabilities: [
      "Leitura do painel de visão geral",
      "Consulta de telemetria em tempo real",
      "Visualização do mapa de planta",
    ],
    level: 0,
  },
  {
    role: "auditor",
    label: "Auditor de Segurança",
    hex: "#a78bfa",
    summary: "Acesso transversal de leitura para conformidade e rastreabilidade.",
    capabilities: [
      "Leitura de logs de auditoria completos",
      "Visualização da linhagem de dados (LGPD)",
      "Telemetria mascarada (minimização de dados)",
      "Acesso à política de controle de acesso",
    ],
    level: null,
    transversal: true,
  },
  {
    role: "operator",
    label: "Técnico de Operação",
    hex: "#22d3ee",
    summary: "Responde a alertas e executa ações de manutenção de rotina.",
    capabilities: [
      "Tudo do Visualizador",
      "Confirmação e comentário de alertas",
      "Abertura de ordens de serviço via Volt",
      "Registro de ocorrências operacionais",
    ],
    level: 1,
  },
  {
    role: "engineer",
    label: "Gestor de Planta",
    hex: "#fbbf24",
    summary: "Configura ativos, modelos ML e define limiares de alarme.",
    capabilities: [
      "Tudo do Técnico",
      "Cadastro e edição de ativos e sensores",
      "Validação de cadastros gerados por IA",
      "Configuração de limiares (warn/critical)",
      "Acesso a dados de linhagem e rastreabilidade",
    ],
    level: 2,
  },
  {
    role: "admin",
    label: "Administrador do Sistema",
    hex: "#34d399",
    summary: "Controla usuários, permissões e a configuração global da plataforma.",
    capabilities: [
      "Tudo do Gestor",
      "Gestão de usuários e papéis",
      "Configuração de políticas RBAC",
      "Acesso irrestrito ao log de auditoria",
      "Controle de integrações e modelos ML",
    ],
    level: 3,
  },
];

// Apenas os níveis lineares (sem o auditor transversal), na ordem correta.
const LINEAR_LEVELS = LEVELS.filter((l) => !l.transversal);
const AUDITOR = LEVELS.find((l) => l.transversal)!;

interface RoleMaturityLadderProps {
  /** Papel do usuário atual — destaca o card correspondente. */
  currentRole?: string | null;
}

export function RoleMaturityLadder({ currentRole }: RoleMaturityLadderProps) {
  return (
    <div className="space-y-2">
      {/* Legenda */}
      <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-px w-6 bg-slate-600" />
          Hierarquia linear
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-px w-6 border-t border-dashed border-violet-500" />
          Papel transversal (auditoria)
        </span>
        {currentRole && (
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-white/80" />
            Seu papel atual
          </span>
        )}
      </div>

      <div className="relative">
        {/* Linha vertical de conexão dos níveis lineares */}
        <div
          className="absolute left-3 top-5 hidden w-px sm:block"
          style={{
            height: "calc(100% - 2.5rem)",
            background:
              "linear-gradient(to bottom, #475569 0%, #334155 60%, #1e293b 100%)",
          }}
        />

        <div className="space-y-2">
          {LINEAR_LEVELS.map((level, idx) => {
            const isActive = currentRole === level.role;
            const isAuditorInsertPoint = idx === 0; // auditor branches após viewer

            return (
              <div key={level.role}>
                {/* Card do nível linear */}
                <div className="relative flex items-start gap-3">
                  {/* Nó da linha vertical */}
                  <div
                    className="relative z-10 mt-4 hidden h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 sm:flex"
                    style={{
                      borderColor: isActive ? level.hex : "#334155",
                      backgroundColor: isActive ? level.hex + "22" : "#0f172a",
                    }}
                  >
                    <span className="text-[10px] font-bold" style={{ color: level.hex }}>
                      {level.level}
                    </span>
                  </div>

                  {/* Card de nível */}
                  <div
                    className={cn(
                      "flex-1 rounded-lg border-l-4 border border-slate-800 bg-slate-900/60 p-4 transition-all",
                      isActive && "ring-1 ring-white/10",
                    )}
                    style={{
                      borderLeftColor: level.hex,
                      boxShadow: isActive ? `0 0 0 1px ${level.hex}22` : undefined,
                    }}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-100" style={{ color: isActive ? level.hex : undefined }}>
                        {level.label}
                      </span>
                      <span className="font-mono text-[10px] text-slate-600">
                        {level.role}
                      </span>
                      {isActive && (
                        <span
                          className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                          style={{
                            backgroundColor: level.hex + "22",
                            color: level.hex,
                          }}
                        >
                          Seu papel
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{level.summary}</p>
                    <ul className="mt-2 space-y-0.5">
                      {level.capabilities.map((cap) => (
                        <li
                          key={cap}
                          className="flex items-start gap-1.5 text-xs text-slate-500"
                        >
                          <span className="mt-0.5 shrink-0" style={{ color: level.hex }}>
                            ·
                          </span>
                          {cap}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Braço transversal do auditor — inserido após o viewer (idx=0) */}
                {isAuditorInsertPoint && (
                  <div className="relative ml-9 mt-2 flex items-start gap-3">
                    {/* Linha tracejada horizontal de conexão */}
                    <div className="absolute -left-6 top-4 flex items-center">
                      <div className="h-px w-5 border-t border-dashed border-violet-700" />
                    </div>

                    {/* Nó auditor */}
                    <div
                      className="relative z-10 mt-2.5 hidden h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 border-dashed sm:flex"
                      style={{
                        borderColor:
                          currentRole === AUDITOR.role ? AUDITOR.hex : "#5b21b6",
                        backgroundColor:
                          currentRole === AUDITOR.role
                            ? AUDITOR.hex + "22"
                            : "#0f172a",
                      }}
                    >
                      <span
                        className="text-[8px] font-bold"
                        style={{ color: AUDITOR.hex }}
                      >
                        ★
                      </span>
                    </div>

                    {/* Card do auditor */}
                    <div
                      className={cn(
                        "flex-1 rounded-lg border-l-4 border border-dashed border-violet-900/60 bg-violet-950/20 p-3 transition-all",
                        currentRole === AUDITOR.role && "ring-1 ring-violet-500/20",
                      )}
                      style={{ borderLeftColor: AUDITOR.hex }}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className="font-semibold"
                          style={{
                            color:
                              currentRole === AUDITOR.role
                                ? AUDITOR.hex
                                : "#8b5cf6",
                          }}
                        >
                          {AUDITOR.label}
                        </span>
                        <span className="font-mono text-[10px] text-slate-600">
                          {AUDITOR.role}
                        </span>
                        <span className="rounded-full border border-violet-800 px-2 py-0.5 text-[10px] text-violet-400">
                          transversal
                        </span>
                        {currentRole === AUDITOR.role && (
                          <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-semibold text-violet-300">
                            Seu papel
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{AUDITOR.summary}</p>
                      <ul className="mt-2 space-y-0.5">
                        {AUDITOR.capabilities.map((cap) => (
                          <li
                            key={cap}
                            className="flex items-start gap-1.5 text-xs text-slate-600"
                          >
                            <span className="mt-0.5 shrink-0 text-violet-600">·</span>
                            {cap}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
