"""Tabela oficial da NCM (Portal Único Siscomex), para a regra 12 do PDM."""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = r"""
create table ncm_versao (
  id          serial primary key,
  fonte       text not null,
  ato         text,
  vigente_em  text,
  sha256      text not null unique,
  importada_em timestamptz not null default now(),
  ativa       boolean not null default false
);
create unique index ncm_versao_unica_ativa on ncm_versao (ativa) where ativa;

create table ncm_tabela (
  versao_id    int  not null references ncm_versao(id) on delete cascade,
  codigo       text not null,          -- 0000.00.00
  descricao    text,
  data_inicio  date,
  data_fim     date,
  primary key (versao_id, codigo)
);
"""


def upgrade() -> None:
    op.execute(SQL)


def downgrade() -> None:
    raise NotImplementedError
