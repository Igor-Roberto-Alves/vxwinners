"""Esquema inicial do modo de cadastro."""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = r"""
-- ---------------------------------------------------------------- PDM versionado
create table pdm_versao (
  id          serial primary key,
  arquivo     text        not null,
  sha256      text        not null unique,
  conteudo    jsonb       not null,
  ativa       boolean     not null default false,
  criada_em   timestamptz not null default now()
);
create unique index pdm_versao_unica_ativa on pdm_versao (ativa) where ativa;

-- ---------------------------------------------------------------- base legada (cópia do ERP, sem correções)
create table material (
  codigo                    text primary key,
  descricao_curta           text,
  descricao_longa           text,
  unidade                   text,
  ncm                       text,
  grupo                     text,
  fabricante                text,
  referencia_fabricante     text,
  centro                    text,
  status                    text,
  data_criacao              date,
  usuario_criacao           text,
  data_ultima_movimentacao  date,
  estoque                   numeric,
  preco_medio               numeric
);
create index material_grupo on material (grupo);
create index material_status on material (status);

-- camada de leitura: classe e atributos de cada registro
create table material_classificacao (
  codigo          text primary key references material(codigo) on delete cascade,
  id_pdm          text,
  nome            text,
  confianca       real,
  metodo          text not null,
  pdm_versao_id   int  references pdm_versao(id),
  extrator        text,
  atualizado_em   timestamptz not null default now()
);
create index material_classificacao_nome on material_classificacao (id_pdm, nome);

create table material_atributo (
  codigo        text not null references material(codigo) on delete cascade,
  atributo      text not null,
  valor_bruto   text,
  valor         text,
  origem        text not null,
  trecho        text,
  confianca     real,
  primary key (codigo, atributo)
);

create table material_identidade (
  codigo      text primary key references material(codigo) on delete cascade,
  id_pdm      text,
  nome        text,
  ativo       boolean not null default true,
  chave       text,
  completa    boolean not null default false,
  valores     jsonb   not null default '{}',
  texto_norm  text,
  tokens      text[]  not null default '{}'
);
create index material_identidade_chave on material_identidade (chave) where completa;
create index material_identidade_nome  on material_identidade (id_pdm, nome);
create index material_identidade_tokens on material_identidade using gin (tokens);

create materialized view estatistica_valor as
select c.id_pdm, c.nome, a.atributo, a.valor, count(*)::int as n
  from material_atributo a
  join material_classificacao c using (codigo)
  join material m using (codigo)
 where a.valor is not null and a.confianca >= 0.9 and m.status = 'ATIVO'
 group by c.id_pdm, c.nome, a.atributo, a.valor;
create index estatistica_valor_idx on estatistica_valor (id_pdm, nome, atributo);

-- equivalência não é duplicidade (regra 13 do PDM): fica registrada, nunca junta códigos
create table equivalencia (
  a_fabricante text not null, a_referencia text not null,
  b_fabricante text not null, b_referencia text not null,
  tipo         text not null default 'INTERCAMBIAVEL',
  fonte        text not null,
  primary key (a_fabricante, a_referencia, b_fabricante, b_referencia)
);

create table cache_extracao (
  chave      text primary key,
  resultado  jsonb not null,
  modelo     text,
  criada_em  timestamptz not null default now()
);

-- ---------------------------------------------------------------- pedidos e cadastros
create table pedido (
  id                text primary key,
  data_solicitacao  date,
  centro            text,
  area              text,
  canal             text,
  urgencia          text,
  texto             text,
  tipo_anexo        text,
  conteudo_anexo    text,
  estado            text not null default 'NOVO',
  analista          text,
  criado_em         timestamptz not null default now()
);
create index pedido_estado on pedido (estado);

create table cadastro (
  id                     uuid primary key default gen_random_uuid(),
  pedido_id              text references pedido(id),
  estado                 text not null default 'RASCUNHO',
  id_pdm                 text,
  nome                   text,
  pdm_versao_id          int references pdm_versao(id),
  valores                jsonb not null default '{}',
  grupo                  text,
  unidade                text,
  ncm                    text,
  fabricante             text,
  referencia_fabricante  text,
  centro                 text,
  descricao_longa        text,
  descricao_curta        text,
  chave                  text,
  versao                 int  not null default 1,
  analista               text,
  codigo_erp             text,
  usar_codigo            text,
  motivo                 text,
  texto_inicial          text,
  criado_em              timestamptz not null default now(),
  atualizado_em          timestamptz not null default now()
);
create index cadastro_estado on cadastro (estado);
create index cadastro_pedido on cadastro (pedido_id);
-- Dois analistas nunca aprovam o mesmo item: só um cadastro por chave pode estar aprovado.
create unique index cadastro_chave_aprovada on cadastro (chave)
  where chave is not null and estado in ('APROVADO', 'AGUARDANDO_REATIVACAO', 'CADASTRADO');

create table cadastro_excecao (
  id             bigserial primary key,
  cadastro_id    uuid not null references cadastro(id) on delete cascade,
  tipo           text not null,
  atributo       text,
  padrao         text,
  usado          text,
  justificativa  text,
  autor          text,
  revisor        text,
  decisao        text,
  decidido_em    timestamptz,
  criada_em      timestamptz not null default now()
);
create index cadastro_excecao_cadastro on cadastro_excecao (cadastro_id);

create table cadastro_pergunta (
  id            bigserial primary key,
  cadastro_id   uuid not null references cadastro(id) on delete cascade,
  destinatario  text,
  pergunta      text not null,
  resposta      text,
  enviada_em    timestamptz not null default now(),
  respondida_em timestamptz
);

create table area_contato (
  area   text primary key,
  email  text not null
);

create table pdm_proposta (
  id           bigserial primary key,
  tipo         text not null,
  cadastro_id  uuid references cadastro(id),
  descricao    jsonb not null,
  estado       text not null default 'ABERTA',
  autor        text,
  decisao      text,
  criada_em    timestamptz not null default now()
);

-- ---------------------------------------------------------------- operação
create table evento_auditoria (
  id           bigserial primary key,
  quando       timestamptz not null default now(),
  autor        text,
  entidade     text not null,
  entidade_id  text not null,
  acao         text not null,
  antes        jsonb,
  depois       jsonb
);
create index evento_auditoria_entidade on evento_auditoria (entidade, entidade_id);

create function auditoria_somente_insercao() returns trigger as $$
begin
  raise exception 'evento_auditoria aceita apenas inserções';
end;
$$ language plpgsql;
create trigger evento_auditoria_imutavel
  before update or delete on evento_auditoria
  for each row execute function auditoria_somente_insercao();

create table llm_chamada (
  id              bigserial primary key,
  quando          timestamptz not null default now(),
  finalidade      text not null,
  modelo          text not null,
  prompt_versao   text not null,
  entrada_hash    text not null,
  tokens_entrada  int,
  tokens_cache    int,
  tokens_saida    int,
  ms              int,
  resultado       text not null,
  erro            text
);

create table erp_envio (
  id           bigserial primary key,
  cadastro_id  uuid not null references cadastro(id),
  tipo         text not null,
  estado       text not null default 'PENDENTE',
  tentativas   int  not null default 0,
  arquivo      text,
  protocolo    text,
  retorno      jsonb,
  criado_em    timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);
create index erp_envio_estado on erp_envio (estado);
"""


def upgrade() -> None:
    op.execute(SQL)


def downgrade() -> None:
    raise NotImplementedError("sem downgrade: recriar o banco")
