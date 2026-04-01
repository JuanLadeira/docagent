import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Importa todos os modelos para que o autogenerate os detecte
from docagent.database import Base  # noqa: F401
from docagent.tenant.models import Tenant  # noqa: F401
from docagent.usuario.models import Usuario  # noqa: F401
from docagent.admin.models import Admin  # noqa: F401
from docagent.whatsapp.models import WhatsappInstancia  # noqa: F401
from docagent.telegram.models import TelegramInstancia  # noqa: F401
from docagent.agente.models import Agente  # noqa: F401
from docagent.atendimento.models import Atendimento, Contato, MensagemAtendimento  # noqa: F401
from docagent.system_config.models import SystemConfig  # noqa: F401
from docagent.settings import Settings

settings = Settings()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injeta URL do banco via settings (sobrescreve alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DOCAGENT_DB_URL)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
