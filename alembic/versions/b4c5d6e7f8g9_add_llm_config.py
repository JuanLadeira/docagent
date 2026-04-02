"""add llm config to tenant + system_config table

Revision ID: b4c5d6e7f8g9
Revises: a3b4c5d6e7f8
Create Date: 2026-03-31

"""
from alembic import op
import sqlalchemy as sa

revision = 'b4c5d6e7f8g9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Campos LLM no tenant
    op.add_column('tenant', sa.Column('llm_provider', sa.String(50), nullable=True))
    op.add_column('tenant', sa.Column('llm_model', sa.String(100), nullable=True))
    op.add_column('tenant', sa.Column('llm_api_key', sa.String(500), nullable=True))

    # Tabela de configurações globais do sistema
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_system_config_key', 'system_config', ['key'], unique=True)

    # Seed: modo padrão = local
    op.execute("INSERT INTO system_config (id, created_at, updated_at, key, value) VALUES (1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'llm_mode', 'local')")


def downgrade() -> None:
    op.drop_index('ix_system_config_key', table_name='system_config')
    op.drop_table('system_config')
    op.drop_column('tenant', 'llm_api_key')
    op.drop_column('tenant', 'llm_model')
    op.drop_column('tenant', 'llm_provider')
