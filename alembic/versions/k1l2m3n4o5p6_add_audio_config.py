"""add audio_config

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'k1l2m3n4o5p6'
down_revision = 'j0k1l2m3n4o5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audio_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('agente_id', sa.Integer(), nullable=True),
        sa.Column('stt_habilitado', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('stt_provider', sa.String(50), nullable=False, server_default='faster_whisper'),
        sa.Column('stt_modelo', sa.String(50), nullable=False, server_default='base'),
        sa.Column('tts_habilitado', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('tts_provider', sa.String(50), nullable=False, server_default='piper'),
        sa.Column('piper_voz', sa.String(200), nullable=False, server_default='pt_BR-faber-medium'),
        sa.Column('openai_tts_voz', sa.String(50), nullable=False, server_default='nova'),
        sa.Column('elevenlabs_voice_id', sa.String(200), nullable=True),
        sa.Column('elevenlabs_api_key', sa.Text(), nullable=True),
        sa.Column('modo_resposta', sa.String(50), nullable=False, server_default='audio_e_texto'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['agente_id'], ['agente.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'agente_id', name='uq_audio_config_tenant_agente'),
    )


def downgrade() -> None:
    op.drop_table('audio_config')
