"""Sugestões de preenchimento vindas de preenchimento/saida: nunca viram dado confirmado sozinhas."""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        create table material_sugestao (
          codigo   text not null references material(codigo) on delete cascade,
          campo    text not null,          -- NCM, FABRICANTE, REFERENCIA_FABRICANTE, GRUPO_MERCADORIA
          valor    text not null,
          conf     real,
          metodo   text,
          primary key (codigo, campo)
        );
    """)


def downgrade() -> None:
    raise NotImplementedError
