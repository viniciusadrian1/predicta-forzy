"""Montagem dos prompts do assistente de troubleshooting."""

from __future__ import annotations

from app.modules.rag.retriever import RetrievedChunk

SYSTEM_PROMPT = (
    "Voce e o assistente de troubleshooting do Predicta, um gemeo digital de "
    "motores eletricos industriais. Ajude tecnicos de manutencao a interpretar "
    "a telemetria, os alertas e a documentacao tecnica do ativo.\n\n"
    "Regras:\n"
    "- Responda em portugues do Brasil, de forma objetiva e tecnica.\n"
    "- Baseie-se apenas no contexto fornecido (documentacao e dados do ativo). "
    "Se a informacao nao estiver no contexto, diga que nao sabe.\n"
    "- Nao invente valores, normas ou numeros de peca.\n"
    "- O assistente apoia a decisao; a intervencao de manutencao e sempre "
    "decidida e validada por uma pessoa. Recomende a verificacao humana.\n"
    "- Quando citar a documentacao, mencione o documento de origem."
)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Formata os trechos recuperados como bloco de contexto do prompt."""
    if not chunks:
        return "(Nenhum trecho relevante encontrado na base de conhecimento.)"
    blocks = [f"[Fonte: {chunk.document_title}]\n{chunk.text}" for chunk in chunks]
    return "\n\n".join(blocks)


def build_user_prompt(
    question: str, chunks: list[RetrievedChunk], asset_context: str | None
) -> str:
    """Monta o prompt do usuario com documentacao, dados do ativo e a pergunta."""
    sections = [
        "## Documentacao tecnica relevante",
        build_context_block(chunks),
    ]
    if asset_context:
        sections += ["\n## Dados em tempo real do ativo", asset_context]
    sections += ["\n## Pergunta do tecnico", question.strip()]
    return "\n".join(sections)
