#!/bin/bash
set -e

echo "[entrypoint] Inicializando banco de dados..."

uv run python -c "
import asyncio, sys
sys.path.insert(0, '/app/src')
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text
from docagent.database import Base
from docagent.tenant.models import Tenant
from docagent.usuario.models import Usuario, UsuarioRole
from docagent.agente.models import Agente, Documento  # noqa
from docagent.whatsapp.models import WhatsappInstancia  # garante que a tabela é registrada no metadata
from docagent.telegram.models import TelegramInstancia  # noqa
from docagent.atendimento.models import Atendimento, MensagemAtendimento, Contato  # noqa
from docagent.mcp_server.models import McpServer, McpTool  # noqa
from docagent.admin.models import Admin  # noqa
from docagent.system_config.models import SystemConfig  # noqa
from docagent.agente.defaults import AGENTES_PADRAO
from docagent.auth.security import get_password_hash
from docagent.settings import Settings

settings = Settings()
username = settings.ADMIN_DEFAULT_USERNAME
password = settings.ADMIN_DEFAULT_PASSWORD

async def main():
    engine = create_async_engine(settings.DOCAGENT_DB_URL)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('[entrypoint] Tabelas verificadas/criadas.')

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

    # Seed admin global (sys-mgmt)
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(Admin).where(Admin.username == username))
            existing_admin = result.scalar_one_or_none()
            if existing_admin:
                print('[entrypoint] Admin ' + repr(username) + ' já existe, pulando seed de admin.')
            else:
                admin = Admin(
                    username=username,
                    email=username + '@docagent.com',
                    password=get_password_hash(password),
                    nome='Administrador',
                    ativo=True,
                )
                session.add(admin)
                await session.flush()
                print('[entrypoint] Admin ' + repr(username) + ' criado.')

    # Seed agentes padrão — upsert por nome para cada tenant
    # Garante que novos agentes adicionados ao catálogo cheguem a todos os tenants existentes
    async with SessionLocal() as session:
        async with session.begin():
            tenant_result = await session.execute(select(Tenant).order_by(Tenant.id))
            for tenant in tenant_result.scalars().all():
                nomes_result = await session.execute(
                    select(Agente.nome).where(Agente.tenant_id == tenant.id)
                )
                nomes_existentes = {row[0] for row in nomes_result.all()}
                criados = 0
                for dados in AGENTES_PADRAO:
                    if dados['nome'] not in nomes_existentes:
                        session.add(Agente(**dados, tenant_id=tenant.id))
                        criados += 1
                if criados:
                    print('[entrypoint] ' + str(criados) + ' agente(s) padrão adicionado(s) ao tenant_id=' + str(tenant.id))

    # Seed system config — garante que llm_mode existe com padrão 'local'
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(SystemConfig).where(SystemConfig.key == 'llm_mode'))
            if not result.scalar_one_or_none():
                session.add(SystemConfig(key='llm_mode', value='local'))
                print('[entrypoint] SystemConfig llm_mode=local criado.')

    # Seed servidores MCP — upsert por nome (adiciona novos, não sobrescreve existentes)
    servidores_exemplo = [
        dict(
            nome='Fetch',
            descricao='Busca e converte o conteúdo de qualquer URL para texto. Requer uvx (uv).',
            command='uvx',
            args=['mcp-server-fetch'],
            env={},
        ),
        dict(
            nome='Memory',
            descricao='Grafo de conhecimento persistente: o agente pode salvar e recuperar fatos entre conversas. Requer Node.js.',
            command='npx',
            args=['-y', '@modelcontextprotocol/server-memory'],
            env={},
        ),
        dict(
            nome='Time',
            descricao='Fornece data/hora atual e conversão de fusos horários. Requer Node.js.',
            command='npx',
            args=['-y', '@modelcontextprotocol/server-time'],
            env={},
        ),
        dict(
            nome='Puppeteer',
            descricao='Automação de browser real: navega páginas, clica, extrai conteúdo e tira screenshots. Requer Node.js e Chromium.',
            command='npx',
            args=['-y', '@modelcontextprotocol/server-puppeteer'],
            env={},
        ),
        dict(
            nome='Clima (Open-Meteo)',
            descricao='Previsão do tempo em tempo real para qualquer cidade. Gratuito, sem chave de API. Dados atualizados a cada hora.',
            command='uv',
            args=['run', 'python', '/app/mcp_servers/weather.py'],
            env={},
        ),
    ]
    async with SessionLocal() as session:
        async with session.begin():
            for dados in servidores_exemplo:
                existe = await session.execute(
                    select(McpServer).where(McpServer.nome == dados['nome'])
                )
                if not existe.scalar_one_or_none():
                    session.add(McpServer(**dados, ativo=False))
                    print('[entrypoint] Servidor MCP criado: ' + dados['nome'])

asyncio.run(main())
"

echo "[entrypoint] Pronto. Iniciando servidor..."
exec "$@"
