# Backend do modo de cadastro de materiais

API em FastAPI e PostgreSQL que ajuda o responsável pelo cadastro a criar um material novo: ele digita o
nome, confirma a classe do PDM, preenche os atributos com sugestões do histórico e vê se o item já existe.
Tudo é editável e a decisão final é de uma pessoa. O plano e as medições estão em
[`docs/04-plano-modo-cadastro.md`](../docs/04-plano-modo-cadastro.md); o contrato para o frontend é
[`docs/openapi.json`](../docs/openapi.json).

## Como rodar

Requer Python 3.12.

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt          # em produção: requirements.txt

cp .env.example .env                          # e preencha; o .env não vai para o git
python -m app.cli migrar                      # cria/atualiza o esquema (a API recusa subir sem isso)
python -m app.cli ingerir                     # PDM, tabela oficial da NCM, base e pedidos (dados/)
python -m app.cli estruturar --etapa regras   # classe e atributos por regras (~25 s)
python -m app.cli estruturar --etapa llm --tudo --teto-usd 60   # LLM no resíduo (~17 min, ~US$ 40)
python -m app.cli relatorio                   # cobertura da estruturação

uvicorn app.main:app --reload                 # API: http://localhost:8000/docs
                                              # painel de desenvolvimento: http://localhost:8000/painel
python -m pytest                              # 215 testes
```

Sem `DATABASE_URL`, o desenvolvimento sobe um PostgreSQL embutido em `backend/.pgdata` (pacote `pgserver`).
Isso é só para desenvolvimento e testes. Em produção use um PostgreSQL de verdade e `DATABASE_URL`.

A etapa de LLM chama a AWS e **gasta dinheiro**. Ela é retomável (não refaz o que já passou), grava a cada
lote de 2.000, mantém cache pelo hash da entrada e para sozinha no teto de gasto estimado ou se um lote
inteiro falhar (por exemplo, credencial expirada). Teste antes com `--amostra --limite 200`.

## Painel de desenvolvimento

`http://localhost:8000/painel` (só com `AUTH_MODO=dev`) é uma tela mínima para **ver e testar o fluxo ao vivo** contra a
API e a base real: digitar o nome do material, confirmar a classe, preencher com sugestões, ver a duplicidade mudar a
cada atributo e aprovar. Atalhos: `?pedido=SC-202600261`, `?classe=PDM020`, `?q=valv esf`. **Não é o frontend do
produto** (que vem de outra branch): serve para validar a API e o comportamento. Cada abertura de pedido ou cadastro
cria dados reais no banco de desenvolvimento.

## Comandos

| Comando | O que faz |
|---|---|
| `migrar` | aplica as migrações Alembic |
| `ingerir [--baixar-ncm]` | publica o PDM (idempotente pelo hash), importa a tabela oficial da NCM, a base e os pedidos |
| `estruturar --etapa regras\|llm` | lê classe e atributos de cada material; a base legada **não é alterada** |
| `relatorio` | cobertura de classe e chave, por método e por grupo |
| `avaliar -n 120` | precisão do LLM contra gabarito derivado da base |
| `avaliar-sugestoes -n 1500` | acerto das sugestões de valor na base inteira |

## Configuração

Por variável de ambiente ou `.env` (modelo em [`.env.example`](.env.example)). As principais:
`DATABASE_URL`, `AUTH_MODO`, `CORS_ORIGENS`, `LLM_PROVIDER` (`bedrock` ou `aws_platform`), `LLM_MODELO_EXTRACAO`,
`LLM_MODELO_DIFICIL`, `LLM_CONCORRENCIA`, `LLM_HABILITADO` e as credenciais AWS.

Os modelos permitidos dependem da conta. Em 2026-11-07 a conta de desenvolvimento só liberava Haiku 4.5, Sonnet 4.6,
Sonnet 5 e Opus 4.6 a 5; por isso os padrões são o Haiku 4.5 e o Sonnet 5.

## Como o código se organiza

```
app/
├── pdm/            PDM versionado no banco, condições (19) e modelo em memória
├── normalizacao/   texto, números pt-BR, grandezas (polegada, mm, bar, mm², rosca), vocabulário
├── classes/        resolvedor do nome digitado (abreviações, plural, inglês de catálogo)
├── estruturacao/   extração por regras, LLM em lote, canonicalização, avaliação
├── llm/            cliente (Bedrock ou Platform), prompt, extrator com validação da saída
├── identidade/     chave (regra 10 do PDM), referências, candidatos de duplicidade
├── sugestoes/      opções de valor por nome do material e contexto
├── ncm/            regra de NCM por classe e tabela oficial do Siscomex
├── tabelas/        tabelas técnicas locais com fonte (rolamentos, ISO 15)
├── leitura/        pedidos: e-mail, ficha técnica e catálogo viram atributos
├── cadastro/       estados, exceções, aprovação, descrição no padrão
├── erp/            conector por arquivos e sincronização
├── api/            rotas, esquemas, permissões
migrations/         Alembic (0001 esquema, 0002 NCM oficial, 0003 classe confirmada)
tests/              unidade e integração, com PostgreSQL real
```

## Garantias e limites

- **O PDM é a referência, a palavra final é da pessoa.** O que contraria o PDM vira exceção com justificativa
  (mínimo de 10 caracteres) e passa por um segundo analista; só "duplicidade provável" dispensa a revisão. O que
  não tem remédio bloqueia: obrigatório vazio, NCM inexistente ou fora de vigência, classe não confirmada.
- **A classe é sempre confirmada por uma pessoa**, e nada vindo do histórico entra preenchido sozinho.
- **O LLM propõe, o código decide.** Cada valor passa pelo canonicalizador e pelo PDM, e o trecho de origem
  precisa existir no texto. Falha do LLM nunca trava o cadastro.
- **Dois analistas não aprovam o mesmo item:** índice único parcial na chave. Toda mudança entra em
  `evento_auditoria`, que o banco recusa alterar ou apagar.
- **O painel de duplicidade não afirma que um item não existe.** Devolve também quantos registros da classe
  puderam ser comparados por atributos.

**Não use em produção ainda:** a autenticação é só `dev` (a API recusa outro modo), o e-mail de devolução vai para
`erp_out/emails/` e não há integração com SES, e não há deploy, CI nem observabilidade.
