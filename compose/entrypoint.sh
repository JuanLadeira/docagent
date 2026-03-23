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
from docagent.agente.models import Agente
from docagent.whatsapp.models import WhatsappInstancia  # garante que a tabela é registrada no metadata
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
                print(f'[entrypoint] Usuário {username!r} já existe, pulando seed.')
                return

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

asyncio.run(main())
"

echo "[entrypoint] Pronto. Iniciando servidor..."
exec "$@"
