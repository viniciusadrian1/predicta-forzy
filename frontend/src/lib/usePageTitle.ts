"use client";

import { useEffect } from "react";

/** Define o título da aba ("X · Predicta"). Páginas são client components,
 *  então `export const metadata` não se aplica — o hook cobre estático e
 *  dinâmico (ex.: TAG do ativo). */
export function usePageTitle(title: string | undefined) {
  useEffect(() => {
    if (title) document.title = `${title} · Predicta`;
  }, [title]);
}
