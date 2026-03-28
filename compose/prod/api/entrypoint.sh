#!/bin/bash
set -e

echo "[entrypoint] Rodando migrações Alembic..."
uv run alembic upgrade head
echo "[entrypoint] Migrações aplicadas."

echo "[entrypoint] Executando seed de dados iniciais..."

uv run python -c "
import asyncio, sys
sys.path.insert(0, '/app/src')
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from docagent.database import Base
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.telegram.models import TelegramInstancia  # noqa
from docagent.whatsapp.models import WhatsappInstancia  # noqa
from docagent.atendimento.models import Atendimento, MensagemAtendimento, Contato  # noqa
from docagent.mcp_server.models import McpServer, McpTool  # noqa
from docagent.agente.models import Agente, Documento  # noqa
from docagent.auth.security import get_password_hash
from docagent.settings import Settings

settings = Settings()
username = settings.ADMIN_DEFAULT_USERNAME
password = settings.ADMIN_DEFAULT_PASSWORD

async def main():
    engine = create_async_engine(settings.DOCAGENT_DB_URL)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(Usuario).where(Usuario.username == username))
            existing = result.scalar_one_or_none()
            if existing:
                print(f'[entrypoint] Usuário {username!r} já existe, pulando seed de usuário.')
            else:
                tenant = Tenant(nome='Admin Tenant', descricao='Tenant padrão')
                session.add(tenant)
                await session.flush()

                user = Usuario(
                    username=username,
                    email=f'{username}@docagent.com',
                    password=get_password_hash(password),
                    nome='Administrador',
                    ativo=True,
                    role=UsuarioRole.OWNER,
                    tenant_id=tenant.id,
                )
                session.add(user)
                await session.flush()
                print(f'[entrypoint] Usuário {username!r} criado (tenant_id={tenant.id}).')

    # Seed agentes padrão se não existir nenhum
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(Agente))
            if not result.scalars().first():
                agentes_padrao = [
                    Agente(
                        nome='Analista de Documentos',
                        descricao='Especializado em analisar PDFs carregados pelo usuário.',
                        skill_names=['rag_search', 'web_search'],
                        ativo=True,
                    ),
                    Agente(
                        nome='Pesquisador Web',
                        descricao='Busca informações atuais na internet sem depender de documentos.',
                        skill_names=['web_search'],
                        ativo=True,
                    ),
                ]
                for a in agentes_padrao:
                    session.add(a)
                print('[entrypoint] Agentes padrão criados.')

    # Seed servidores MCP de exemplo se não existir nenhum
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(McpServer))
            if not result.scalars().first():
                servidores_exemplo = [
                    McpServer(
                        nome='Fetch',
                        descricao='Busca e converte o conteúdo de qualquer URL para texto. Requer uvx (uv).',
                        command='uvx',
                        args=['mcp-server-fetch'],
                        env={},
                        ativo=False,
                    ),
                    McpServer(
                        nome='Memory',
                        descricao='Grafo de conhecimento persistente: o agente pode salvar e recuperar fatos entre conversas. Requer Node.js.',
                        command='npx',
                        args=['-y', '@modelcontextprotocol/server-memory'],
                        env={},
                        ativo=False,
                    ),
                    McpServer(
                        nome='Time',
                        descricao='Fornece data/hora atual e conversão de fusos horários. Requer Node.js.',
                        command='npx',
                        args=['-y', '@modelcontextprotocol/server-time'],
                        env={},
                        ativo=False,
                    ),
                    McpServer(
                        nome='Puppeteer',
                        descricao='Automação de browser real: navega páginas, clica, extrai conteúdo e tira screenshots. Requer Node.js e Chromium.',
                        command='npx',
                        args=['-y', '@modelcontextprotocol/server-puppeteer'],
                        env={},
                        ativo=False,
                    ),
                    McpServer(
                        nome='Clima (Open-Meteo)',
                        descricao='Previsão do tempo em tempo real para qualquer cidade. Gratuito, sem chave de API. Dados atualizados a cada hora.',
                        command='uv',
                        args=['run', 'python', '/app/mcp_servers/weather.py'],
                        env={},
                        ativo=False,
                    ),
                ]
                for s in servidores_exemplo:
                    session.add(s)
                print('[entrypoint] Servidores MCP de exemplo criados (inativos).')

asyncio.run(main())
"

echo "[entrypoint] Pronto. Iniciando servidor..."
exec "$@"
