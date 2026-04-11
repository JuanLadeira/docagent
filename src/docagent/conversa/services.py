"""
Fase 19 — ConversaService: cria, lista, persiste mensagens e gera títulos.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from docagent.conversa.models import Conversa, MensagemConversa, MensagemRole

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

_TITULO_PROMPT = (
    "Gere um título curto (máximo 6 palavras) para uma conversa que começa com:\n"
    '"{msg}"\n'
    "Responda APENAS com o título, sem aspas, sem pontuação final."
)


class ConversaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── CRUD básico ───────────────────────────────────────────────────────────

    async def criar(
        self,
        tenant_id: int,
        usuario_id: int,
        agente_id: int,
    ) -> Conversa:
        conversa = Conversa(
            tenant_id=tenant_id,
            usuario_id=usuario_id,
            agente_id=agente_id,
        )
        self.db.add(conversa)
        await self.db.flush()
        await self.db.commit()
        return conversa

    async def get_by_id(self, conversa_id: int, tenant_id: int) -> Conversa | None:
        result = await self.db.execute(
            select(Conversa).where(
                Conversa.id == conversa_id,
                Conversa.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def listar(
        self,
        usuario_id: int,
        tenant_id: int,
        agente_id: int | None,
        arquivada: bool,
        page: int,
        page_size: int,
    ) -> list[Conversa]:
        query = select(Conversa).where(
            Conversa.usuario_id == usuario_id,
            Conversa.tenant_id == tenant_id,
            Conversa.arquivada == arquivada,
        )
        if agente_id is not None:
            query = query.where(Conversa.agente_id == agente_id)

        query = query.order_by(Conversa.updated_at.desc())
        query = query.limit(page_size).offset((page - 1) * page_size)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ── Mensagens ─────────────────────────────────────────────────────────────

    async def salvar_mensagem(
        self,
        conversa_id: int,
        role: MensagemRole,
        conteudo: str,
        tool_name: str | None = None,
    ) -> MensagemConversa:
        mensagem = MensagemConversa(
            conversa_id=conversa_id,
            role=role.value,
            conteudo=conteudo,
            tool_name=tool_name,
        )
        self.db.add(mensagem)

        # Atualiza updated_at da conversa
        await self.db.execute(
            update(Conversa)
            .where(Conversa.id == conversa_id)
            .values(updated_at=datetime.utcnow())
        )

        await self.db.flush()
        await self.db.commit()
        return mensagem

    async def carregar_historico(self, conversa_id: int) -> list[BaseMessage]:
        result = await self.db.execute(
            select(MensagemConversa)
            .where(MensagemConversa.conversa_id == conversa_id)
            .order_by(MensagemConversa.created_at)
        )
        mensagens = result.scalars().all()
        return [_to_langchain_message(m) for m in mensagens]

    # ── Título automático ─────────────────────────────────────────────────────

    async def gerar_titulo(
        self,
        conversa_id: int,
        primeira_mensagem: str,
        llm: "BaseChatModel",
    ) -> None:
        prompt = _TITULO_PROMPT.format(msg=primeira_mensagem[:500])
        try:
            resposta = await llm.ainvoke(prompt)
            titulo = (resposta.content or "").strip()[:200]
        except Exception:
            titulo = primeira_mensagem[:80]

        await self.db.execute(
            update(Conversa)
            .where(Conversa.id == conversa_id)
            .values(titulo=titulo)
        )
        await self.db.commit()

    # ── Arquivo / restaurar ───────────────────────────────────────────────────

    async def arquivar(self, conversa_id: int, tenant_id: int) -> None:
        await self.db.execute(
            update(Conversa)
            .where(Conversa.id == conversa_id, Conversa.tenant_id == tenant_id)
            .values(arquivada=True)
        )
        await self.db.commit()

    async def restaurar(self, conversa_id: int, tenant_id: int) -> None:
        await self.db.execute(
            update(Conversa)
            .where(Conversa.id == conversa_id, Conversa.tenant_id == tenant_id)
            .values(arquivada=False)
        )
        await self.db.commit()

    # ── Contagem ──────────────────────────────────────────────────────────────

    async def contar_mensagens(self, conversa_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).where(MensagemConversa.conversa_id == conversa_id)
        )
        return result.scalar_one()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_langchain_message(m: MensagemConversa) -> BaseMessage:
    if m.role == MensagemRole.USER.value:
        return HumanMessage(content=m.conteudo)
    if m.role == MensagemRole.ASSISTANT.value:
        return AIMessage(content=m.conteudo)
    if m.role == MensagemRole.TOOL.value:
        return ToolMessage(content=m.conteudo, tool_call_id=m.tool_name or "tool")
    # SYSTEM e outros → HumanMessage com prefixo para não perder
    return HumanMessage(content=f"[{m.role}] {m.conteudo}")
