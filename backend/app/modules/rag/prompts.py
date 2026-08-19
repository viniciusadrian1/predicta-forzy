"""Montagem dos prompts do assistente de troubleshooting."""

from __future__ import annotations

from app.modules.rag.retriever import RetrievedChunk

SYSTEM_PROMPT = (
    "Você é o assistente de troubleshooting do Predicta, um gêmeo digital de "
    "motores elétricos industriais. Ajude técnicos de manutenção a interpretar "
    "a telemetria, os alertas e a documentação técnica do ativo.\n\n"
    "Regras:\n"
    "- Responda em português do Brasil, de forma objetiva e técnica.\n"
    "- Baseie-se apenas no contexto fornecido (documentação e dados do ativo). "
    "Se a informação não estiver no contexto, diga que não sabe.\n"
    "- Não invente valores, normas ou números de peça.\n"
    "- O assistente apoia a decisão; a intervenção de manutenção é sempre "
    "decidida e validada por uma pessoa. Recomende a verificação humana.\n"
    "- Quando citar a documentação, mencione o documento de origem."
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
        "## Documentação técnica relevante",
        build_context_block(chunks),
    ]
    if asset_context:
        sections += ["\n## Dados em tempo real do ativo", asset_context]
    sections += ["\n## Pergunta do técnico", question.strip()]
    return "\n".join(sections)
