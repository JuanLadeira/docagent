"""merge_heads

Revision ID: 02c972d3cdb6
Revises: b4c5d6e7f8g9, g7h8i9j0k1l2
Create Date: 2026-04-01 22:23:13.320183

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02c972d3cdb6'
down_revision: Union[str, Sequence[str], None] = ('b4c5d6e7f8g9', 'g7h8i9j0k1l2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
