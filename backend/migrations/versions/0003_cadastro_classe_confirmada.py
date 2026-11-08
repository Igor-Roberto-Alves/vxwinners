"""A classe é sempre confirmada por uma pessoa; propostas de leitura ficam separadas."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        alter table cadastro
          add column classe_confirmada boolean not null default false,
          add column proposta jsonb,
          add column resumo_leitura jsonb;
    """)


def downgrade() -> None:
    raise NotImplementedError
