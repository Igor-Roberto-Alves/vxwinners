# Plano do modo de cadastro de materiais

Plano e estado da implementação · 2026-11-07 · branch `modo-cadastro` · código em [`backend/`](../backend/README.md)

O modo de cadastro é o módulo em que o responsável pelo cadastro cria um material novo a partir de poucas palavras. A pessoa digita o que precisa, confirma a classe do PDM e preenche os atributos dessa classe com a ajuda de sugestões baseadas no que já está cadastrado. Antes de aprovar, o sistema mostra se o item já existe. **Tudo é editável e a decisão final é sempre de uma pessoa.**

O módulo é tratado como produto, não como demonstração. Por isso, este plano substitui parte do [02-plano-projeto.md](02-plano-projeto.md): Streamlit, DuckDB e telas pré-calculadas dão lugar a FastAPI, PostgreSQL e React. O pipeline das etapas E0 a E5 continua valendo, agora como base deste módulo.

Termos usados no documento:

- **Classe:** tipo de material no PDM, como `PARAFUSO SEXTAVADO` (`PDM001`).
- **Atributo:** característica exigida pela classe, como `BITOLA` ou `COMPRIMENTO`.
- **Chave de identidade:** combinação definida pela regra 10 do PDM para dizer que dois registros são o mesmo item.
- **Exceção:** decisão que contraria o PDM, permitida com justificativa.


---

## 0. Estado da implementação

O backend está em [`backend/`](../backend/README.md) (FastAPI, PostgreSQL, 276 testes) e foi rodado contra a base inteira. **O frontend é o do time:** [`mockup_plataforma.html`](../mockup_plataforma.html) é a casca, e o cadastro real está em [`frontend/`](../frontend/cadastro.js), servido em `http://localhost:8000/`. Busca, cadastro, pedidos, acompanhamento e revisão usam a API e a base real. As demais telas (Início, Radar, Requisições, Aprovar compras, Estoque, Base e Clusters) continuam com dados de demonstração, e a etiqueta do topo diz isso. O contrato é [`docs/openapi.json`](openapi.json), gerado dos esquemas da API.

| Fase | Estado | Evidência |
|---|---|---|
| 0. Fundação | Feita | 23.554 materiais, 520 pedidos, 44 classes, 229 atributos e 10.516 NCMs oficiais importados; 4 migrações |
| 1. PDM e normalização | Feita | PDM versionado no banco; as 19 condições do PDM (15 com predicado, 4 "quando informado pelo fabricante"), com falha explícita se uma nova versão trouxer condição desconhecida; normalizadores de polegada, mm, bar, mm², rosca; regras de NCM por classe |
| 2. Estruturação da base | Feita, com ressalva | 99,5% com classe e 78,2% com chave fechada. A avaliação usa gabarito derivado da base, **não a amostra anotada à mão** que o plano previa |
| 3. Núcleo do cadastro | Feita | autocomplete, rascunho com bloqueio otimista, sugestões, descrição gerada |
| 4. Identidade | Feita | cinco níveis de candidato, ponderados; índice único; teste com duas transações concorrentes |
| 5. Decisões | Feita | estados, exceções, segundo analista, propostas ao PDM, auditoria imutável. Papéis só no modo `dev` |
| 6. Pedidos | Feita | leitura por regras e LLM; devolução gravada, mas o e-mail vai para uma caixa de saída em arquivo |
| 7. ERP | Feita para o conector por arquivos | envio idempotente, retorno do código, erro visível, reativação. A reimportação periódica é manual (`python -m app.cli ingerir`) |
| 8. Integração e piloto | Em andamento | fluxo completo no frontend do time, com 75 verificações de ponta a ponta em navegador real. Falta o uso por analistas e o que está em "O que ainda não existe" |

### Resultados medidos

| Medida | Resultado |
|---|---|
| Base com classe | 93,3% só com regras; **99,5%** com regras e LLM |
| Base com chave de identidade fechada | 40,3% só com regras; **78,2%** com LLM (especificação 68,7%, referência do fabricante 95,0%) |
| Redundância encontrada | 2.417 chaves com mais de um código, 3.314 códigos redundantes, R$ 19,27 milhões em estoque nesses códigos, de R$ 200,87 milhões na base (sobrevivente: o ativo de maior valor). Estimativa deste pipeline, ainda sem revisão do time |
| Casos do briefing | Rolamentos 6205 e 6310 unem em duas chaves; `CAT 1R1808` une com `CATERPILLAR 1R-1808`; `DONALDSON P551808` fica separado (regra 13) |
| LLM na base | 13.604 chamadas, 0 erros, cerca de US$ 39,5 (Haiku 4.5), 17 minutos com 24 chamadas simultâneas |
| Qualidade do LLM | em 120 registros: classe 99,2%, precisão de atributos 100% (465 de 465), recall 95,3%. Entrada telegráfica feita dos próprios valores do gabarito, então o recall é otimista. **Esse 100% mede localizar o valor no texto, não converter unidade:** na base inteira, o LLM errou 18,7% das conversões de DN (104 de 555) e 16,4% das de pressão (60 de 365). Por isso a conversão saiu da mão dele (ver abaixo) |
| Sugestões de valor (6.225 casos, base inteira) | acerto no 1º lugar 50,1%, entre os 3 primeiros 76,1%. Listas de especificação 49,6% e 79,7%, listas de filtros e sobressalentes 66,9% e 89,1%, medidas 19,9% e 40,7% |
| Leitura dos 520 pedidos | regras: 91,3% com classe (os 8,7% restantes são em geral itens fora do PDM: cadeira, toner, serviços). Em 40 pedidos incompletos, o LLM preencheu 46 de 60 obrigatórios faltantes e deixou 29 completos, a US$ 0,0028 por pedido |
| NCM | dos 73 NCMs do PDM, 72 existem na tabela oficial. **`7306.30.00` (tubo galvanizado) deixou de existir em 01/02/2026** e virou `7306.30.10` e `7306.30.90`; o sistema bloqueia a aprovação e mostra os sucessores. O PDM precisa de manutenção |
| Tabela técnica de rolamentos | ISO 15 séries 60, 62 e 63 conferida contra a base: 139 de 141 medidas batem; as 2 divergentes eram dado errado da base (6218) |

### O que mudou em relação ao plano

1. **LLM pelo Bedrock, não pelo Claude Platform on AWS.** A conta de desenvolvimento não tem o ID de workspace do Platform, o endpoint Mantle do Bedrock devolve 404, e uma política (`ws-bedrock-model-allowlist-policy-1`) nega a família 5.5 e o Fable. Os modelos permitidos são Haiku 4.5, Sonnet 4.6, Sonnet 5 e Opus 4.6 a 5. Por isso a extração usa **Haiku 4.5** e o difícil fica com Sonnet 5. O Platform continua suportado: troque `LLM_PROVIDER=aws_platform` e defina `AWS_REGION` e `ANTHROPIC_AWS_WORKSPACE_ID`.
2. **Sem `pg_trgm` e `unaccent`.** O PostgreSQL embutido de desenvolvimento não traz esses módulos. O texto é normalizado em Python, e a busca por semelhança usa arrays com índice GIN, que funcionam em qualquer PostgreSQL, inclusive o RDS.
3. **PDM como documento versionado**, em uma coluna `jsonb` de `pdm_versao`, em vez de tabelas por classe, atributo e valor. É pequeno, vai para a memória do processo e cada cadastro guarda a versão usada.
4. **Chave de identidade legível** (`PDM020|ROLAMENTO...|REFERENCIA=6205-2RS/C3|...`), não um hash: dá para ler no banco e no log.
5. **Sem `cadastro_candidato`**: a fotografia dos candidatos na aprovação vai no evento de auditoria, que não pode ser alterado.
6. **SQLAlchemy Core com SQL explícito** e Alembic, em vez do ORM.
7. **A comparação de duplicidade é ponderada.** Atributos com poucos valores (vedação, folga) provam pouco; a série do rolamento prova muito. Sem isso, qualquer rolamento aparecia "divergente" de todos os outros.

### Integração com o trabalho do time

Em 2026-11-07 as três branches do GitHub foram unidas a `modo-cadastro`: `main` (preenchimento, serviço de sugestão e mockup), `analise-de-mercado` e `Expli` (pipeline de saneamento). A integração foi de código, não só de arquivos:

- **Conhecimento de domínio em um lugar só.** `backend/app/normalizacao/curados.py` importa sinônimos e a limpeza de referência de `src/saneamento`, em vez de manter cópias. Por isso, **o deploy do backend precisa levar `src/`**.
- **Conversão de unidade feita pelo código.** Quando o trecho apontado pelo LLM tem uma só medida, `reconverte()` em `llm/extrator.py` recalcula o valor (DN para polegada, pressão para bar, milímetros). Com várias medidas no trecho, vale a escolha do modelo. A comparação mostrou por que isso importa: `DN8` havia sido unido a `1/2"`, mas DN 8 equivale a 1/4".
- **Classificação estrutural.** `_irmao_mais_especifico` em `estruturacao/regras.py` veio do saneamento: troca a classe genérica pela irmã mais específica quando há ao menos duas evidências no texto.
- **Modelos de sugestão.** Os modelos do serviço de sugestão rodam dentro do backend, em `/sugestao/*` (`app/sugestoes/modelos.py`). A migração 0004 cria `material_sugestao`, com os valores de `preenchimento/saida`, e `GET /cadastros/{id}/sugestoes-modelo` leva NCM, fabricante e referência ao painel.
- **Vizinhos de texto na busca de duplicidade.** Quando os modelos estão carregados, os vizinhos mais próximos entram como candidatos do nível `PARECIDO` (`acrescenta_vizinhos`). Eles ampliam a lista para a pessoa olhar, mas não afirmam duplicidade.

**O que ficou de fora da identidade, de propósito:** o que vem dos modelos não entra na chave. O fabricante inferido tem confiança média de 0,43, e só 79 chaves fechariam com evidência no texto. Inferência não prova que dois itens são o mesmo, então esses valores são só sugestões: exigem clique e nunca são aplicados sozinhos.

### Comparação dos dois pipelines

`python -m app.cli comparar-pipelines` compara o backend com `artefatos/saneado_base.csv`. Nenhum dos dois é gabarito: uma divergência diz onde olhar, não quem acertou.

| Medida | Resultado |
|---|---|
| Classe igual, entre os registros que os dois classificam | 96,08% (21.877 de 22.769). A maior divergência são 281 parafusos Allen, em que o backend usa `PDM002` e o saneamento `PDM001`; lido o caso, o backend parece certo |
| Pares de duplicidade | saneamento 1.459, backend 4.480, em comum 1.398 |
| Pares em que os dois têm chave e discordam | 19 (eram 201 antes das correções) |
| Pares que só o saneamento une | 61, dos quais 4 discordam de verdade |
| Pares que só o backend une | 3.082, dos quais 15 discordam de verdade. O restante é item em que o saneamento sem BERT não fechou a chave |

A divergência achou erros nos dois lados, corrigidos com teste. No backend: `REV A`, ruído e `-00` na referência, zero à esquerda, `7,0MM`, `A DENTADA 4546` (LLM juntando perfil e comprimento), mangueira com terminais tratada como avulsa (73 registros) e Allen classificado como `PDM001`. No saneamento: passo da rosca lido como comprimento (68 registros, unia parafusos de 35, 60 e 150 mm), O-ring com diâmetro interno e seção trocados (41), `1/2POLX3 1/2POL`, ruído na referência e substantivo na chave de referência, contra a regra 10.

### Frontend

O frontend do time continua sendo um arquivo só, que o time pode seguir redesenhando. A lógica do cadastro fica fora dele, em `frontend/cadastro.js` e `frontend/cadastro.css`, e usa os mesmos componentes visuais. Toda regra de negócio fica no servidor. A base é a versão integrada de `origin/main` (`aac4fbb`). O redesign de 57f4726, que ficou fora dela, voltou em `frontend/tema.css`: cores semânticas, contraste, foco visível e movimento reduzido.

Da versão integrada vieram para o fluxo real: o banner `JÁ EXISTE`, "Aplicar aos campos", o corte de confiança em 0,60 com chip tracejado e a entrada colando o texto do pedido. **Uma decisão difere:** lá, "já existe" era similaridade de texto ≥ 85%. Aqui vem da comparação por atributos, porque na análise de mercado comparar texto não achou nenhum dos duplicados reais.

| Tela | O que faz |
|---|---|
| Buscar material | lê o texto, propõe a classe, compara com a base por atributos **sem gravar nada** (`POST /busca`), e permite usar um código, pedir reativação ou cadastrar |
| Cadastrar novo item | colar o pedido ou escolher a classe; rascunho com salvamento automático, opções do histórico, origem de cada valor, sugestões dos modelos, descrição gerada, validação, exceções e duplicidade ao vivo |
| Pedidos de cadastro | fila real com filtros; assumir lê o texto e o anexo e abre o rascunho |
| Cadastros | todos os cadastros e o estado de cada um |
| Revisão de exceções | decisão do segundo analista e envios ao ERP |

O usuário e o papel são escolhidos no topo da tela, porque a autenticação ainda é só de desenvolvimento. O menu de usuário sai quando o OIDC entrar.

**Testes de ponta a ponta.** `frontend/e2e.mjs` usa um Chrome de verdade e clica como uma pessoa, sempre em um banco descartável, porque aprova itens e grava auditoria imutável. São 75 verificações, sem erro de JavaScript nem resposta 5xx, em três execuções seguidas a partir de um banco limpo. Os testes acharam quatro problemas que a suíte da API não via:

- **A resposta saía antes do `COMMIT`.** Com o padrão atual do FastAPI, o cliente ouvia "criado" antes de o dado estar gravado, e a chamada seguinte recebia 404. A falha era intermitente. Agora `deps.Conexao` grava antes de responder, e um teste mede essa ordem.
- **Conflito de versão falso.** Sair de um campo e clicar em Aprovar disparava as duas escritas quase juntas. As escritas de um rascunho agora vão em fila, e a tela mostra "salvando…".
- **Cadastro em revisão era duplicata de si mesmo**, o que criava um bloqueio falso.
- **Duplo clique em Aprovar** mostrava erro logo depois do sucesso.

### O que ainda não existe

- **Telas de gestão ligadas à API.** Início, Radar, Requisições, Aprovar compras, Estoque, Base e Clusters ainda são demonstração. A entrada por foto saiu da busca, porque está fora da primeira versão.
- **Autenticação OIDC.** A API só aceita `AUTH_MODO=dev` (cabeçalhos `X-Usuario` e `X-Papel`) e **recusa subir** com outro modo, em vez de fingir proteção. Não pode ir para produção assim.
- **Envio real de e-mail (SES).** A devolução grava o e-mail em `backend/erp_out/emails/`. Também não há contato por área cadastrado: sem ele, a API avisa que nada foi enviado.
- **Amostra anotada à mão** e as metas de 98% e 97% do plano.
- **Reimportação automática do ERP**, conector por API, deploy, CI e observabilidade.
- **BERT do saneamento treinado nesta máquina.** O modelo não está no GitHub (518 MB, 40 minutos de CPU, exige `torch`). A comparação abaixo usa o saneamento **sem** BERT, então ela subestima o que esse pipeline alcança.

---

## 1. Decisões

| Tema | Decisão | Motivo |
|---|---|---|
| Usuário | O responsável pelo cadastro preenche e aprova. O solicitante não usa a ferramenta na primeira versão. | O briefing atribui a confirmação a essa pessoa, e a palavra final fica com quem responde pela qualidade da base. |
| Entrada | Busca e cadastro são o mesmo fluxo. A pessoa começa em "Buscar material" e, se nada servir, o que preencheu segue para o cadastro. | Une a ideia original ao [mockup](../mockup_plataforma.html) e evita preencher duas vezes. |
| Classe | Campo único com autocomplete. A classe é sempre confirmada por uma pessoa. | Substantivos como `LUVA` caem em classes diferentes. |
| Sugestões | Campo vazio, com até 3 opções clicáveis e sua frequência. Só entram preenchidos valores de regra do PDM, de tabela local ou encontrados no pedido, sempre com a origem. | O valor mais frequente erra com frequência (seção 2), e um valor pré-preenchido parece confirmado. |
| Limites | Valor fora do PDM é aceito com justificativa e vira exceção. Sem os obrigatórios, o item não é aprovado e volta ao solicitante. | Mantém a decisão humana sem aprovar item incompleto por engano. |
| Aprovação | Item normal: uma pessoa aprova. Exceção: um segundo analista revisa antes de valer. | Controla o risco sem travar a rotina. São cerca de 1.024 cadastros por ano, e 30% dos pedidos têm urgência alta ou emergencial. |
| Duplicidade | Painel ao vivo com candidatos, mais confirmação final na aprovação. | O briefing exige conferir antes de criar, e é melhor descobrir cedo. |
| Base | Os 23.554 registros são estruturados antes do uso, em uma camada de leitura. Nenhum código é alterado ou unificado. | Sem isso, a verificação fica cega em cerca de 80% da base. |
| Pedidos | Regras e LLM juntos. O LLM propõe valores com o trecho de origem, mas não decide classe nem duplicidade. | Cobre e-mails e anexos sem perder auditoria. |
| Stack | FastAPI, PostgreSQL e React. O React virá de outra branch. | Atende autocomplete, escrita concorrente e histórico, e reaproveita o Python do pipeline. |
| ERP | O ERP continua dono do cadastro e gera o código. O produto se conecta por um conector trocável. | Compras, estoque e fiscal seguem no ERP. |
| Acesso ao Claude | Claude Platform on AWS é o destino; hoje roda no Bedrock (seção 0), com o acesso isolado em um módulo. | A conta de desenvolvimento só tem o Bedrock, e só com alguns modelos. A troca é uma variável de ambiente. |
| Devolução | E-mail para um contato cadastrado por área. O analista registra a resposta no cadastro. | Os pedidos não identificam o solicitante. |
| Foto | Fora da primeira versão. | Não há fotos nos dados para medir a precisão. |
| Enriquecimento | Só tabelas locais curadas, com fonte registrada, em atributos opcionais. | A regra 7 prevê essa dedução. Part numbers fictícios podem coincidir com produtos reais, o que torna a busca externa enganosa. |
| Itens bloqueados | Código `BLOQUEADO` ou `OBSOLETO` igual ao item pedido vira exceção: pedir reativação ou criar código novo. | São 2.027 itens nesses status com estoque, e um código novo pode repetir a compra. |
| Fora do PDM | O analista recusa com motivo ou propõe uma classe nova. Nesse caso, o pedido aguarda a nova versão do PDM. | Evita que um material legítimo seja cadastrado direto no ERP. |

As premissas ainda não confirmadas estão na [seção 16](#16-premissas-e-pendências).

---

## 2. O que os dados mostram

As medições são de 2026-11-07, sobre os arquivos em `dados/`. Os dados são sintéticos, então a base real pode se comportar de outra forma.

| Medição | Resultado | Consequência |
|---|---|---|
| Nomes de material no PDM | 119 nomes em 44 classes. 11 palavras iniciais levam a mais de uma classe (`LUVA` leva a 3). | O substantivo sugere a classe, mas não a define. |
| Registros de especificação técnica com todos os obrigatórios presentes e válidos | 1.652, ou 7,0% da base (cerca de 11% dos 14.944 itens fora de `SOB01` e `FIL01`). | A comparação exata funciona em poucos itens. |
| Registros de filtros e sobressalentes com fabricante e referência | 3.320 de 8.610 nas colunas próprias, sem normalizar. 1.007 completos na descrição. | A chave de referência funciona melhor, mas ainda deixa a maioria de fora. |
| Cobertura total da comparação exata | 11,3% usando só a descrição, e até 21,1% somando as colunas de fabricante e referência. | Cerca de 80% da base não é comparável hoje. |
| Comparação de texto ([análise de mercado](#referências)) | Nenhum duplicado encontrado entre os 15 produtos reais, mesmo com normalização pesada. | "Parecido" por texto é só uma pista, não uma verificação. |
| Pedidos com classe candidata por regras simples | 454 de 520 (378 com uma classe, 76 com duas ou mais). Mede candidatos encontrados, não acerto. | Regras resolvem a maior parte, e a pessoa confirma de qualquer forma. |
| Pedidos sem candidata | 66, entre itens fora do PDM (cadeira, toner, serviços) e catálogos em inglês (`BALL VALVE`, `OIL SEAL`). | É preciso um glossário inglês-português e o estado `FORA_DO_PDM`. |
| Dados de contato nos pedidos | Só centro e área. Não há nome nem e-mail do solicitante. | A devolução usa um contato por área. |

### Teste das sugestões

O teste usou 3.655 registros com atributos legíveis, em 5 divisões (80% para calcular, 20% para testar). Cada célula mostra o acerto no 1º lugar e entre os 3 primeiros. As classes comuns incluem só as que têm ao menos 20 registros.

| Grupo e tipo de atributo | Frequência na classe | Frequência no nome do material | Nome e atributos já preenchidos |
|---|---:|---:|---:|
| Classes comuns, lista fechada | 46% e 80% | 46% e 80% | 48% e 79% |
| Classes comuns, campos livres | 11% e 25% | 11% e 25% | 16% e 32% |
| Filtros e sobressalentes, lista fechada | 12% e 27% | 50% e 83% | 65% e 86% |
| Filtros e sobressalentes, campos livres | 0% e 0% | 1% e 3% | 2% e 6% |
| Conexões, lista fechada | 44% e 91% | 54% e 94% | 56% e 94% |
| Conexões, campos livres | 7% e 33% | 10% e 29% | 12% e 32% |

O que isso muda:

- **A frequência precisa ser por nome, não por classe.** `PDM110` reúne 62 nomes diferentes, e a frequência da classe quase não acerta.
- **O contexto vale a pena em sobressalentes.** `FABRICANTE` vai de 43% para 94% de acerto no 1º lugar quando aplicação e modelo já estão preenchidos.
- **Part number não se sugere.** `REFERENCIA FABRICANTE` tem 935 valores distintos em 995 sobressalentes. Em filtros, são 96 em 103. Como esse campo define a identidade nesses grupos, ele é digitado ou lido do pedido.
- **Três opções funcionam em listas fechadas,** com 79% a 94% de acerto entre as 3 primeiras. Em medidas, o caminho principal é a digitação.

A amostra de filtros é pequena (113 registros). O teste precisa ser refeito com a base estruturada.

---

## 3. Fluxo

```
 texto digitado ou pedido aberto
            │
            ▼
 1. confirmar a classe ─────── nenhuma serve ──────► FORA_DO_PDM ou AGUARDANDO_CLASSE
            │
            ▼
 2. preencher atributos ◄───────────────┐
    (regra, pedido, opções, digitação)  │ cada alteração recalcula
            │                           │ validações e candidatos
            ├───────────────────────────┘
            ├── um candidato serve ────────────────► JA_EXISTE
            ├── falta informação ──────────────────► AGUARDANDO_SOLICITANTE
            ▼
 3. conferir dados fiscais e descrição gerada
            │
            ├── há exceção ──► EM_REVISAO ──► segundo analista
            ▼
 4. APROVADO ──► conector ERP ──► CADASTRADO (com o código devolvido)
```

| Estado | Significado | Próximo estado |
|---|---|---|
| `RASCUNHO` | Em preenchimento, com salvamento automático. | Qualquer decisão abaixo. |
| `AGUARDANDO_SOLICITANTE` | Devolvido com a lista exata do que falta, ou com uma pergunta específica. | `RASCUNHO`, com a resposta, ou `CANCELADO`. |
| `EM_REVISAO` | Tem exceção aguardando o segundo analista. | `APROVADO`, `AGUARDANDO_REATIVACAO` ou `RASCUNHO`. |
| `APROVADO` | Decisão tomada, aguardando o código do ERP. A chave já impede outro cadastro igual. | `CADASTRADO` ou `ERRO_ERP`. |
| `CADASTRADO` | O ERP devolveu o código. | Fim. |
| `AGUARDANDO_REATIVACAO` | O segundo analista aprovou reativar um código bloqueado ou obsoleto, e o pedido aguarda o ERP. | `JA_EXISTE` ou `ERRO_ERP`. |
| `ERRO_ERP` | O envio falhou e aparece em uma fila visível. | O estado anterior, ao reenviar. |
| `JA_EXISTE` | A pessoa usou um código ativo existente. O pedido fica vinculado a ele. | Fim. |
| `AGUARDANDO_CLASSE` | Há uma proposta de classe nova com o administrador do PDM. | `RASCUNHO`, com a nova versão do PDM, ou `FORA_DO_PDM`. |
| `FORA_DO_PDM` | Recusado com motivo. | Fim. |
| `CANCELADO` | Encerrado sem efeito. | Fim. |

`AGUARDANDO_SOLICITANTE` corresponde ao estado `DEVOLVIDO` do plano anterior.

---

## 4. Arquitetura

```
 React (outra branch) ──► API FastAPI ──► PostgreSQL
                              │              ▲
                              ▼              │
                       leitura de pedido     │
                              │              │
                              ▼              │
                       Claude na AWS ◄── Worker ──► conector ERP (S3)
                                       (lotes, importações, envios)
```

| Parte | Escolha | Observação |
|---|---|---|
| API | FastAPI, Pydantic, SQLAlchemy 2, Alembic | O OpenAPI gerado é o contrato com o frontend. |
| Banco | PostgreSQL (arrays com índice GIN, sem extensões obrigatórias) | Concorrência, auditoria, busca por semelhança e fila. `pgvector` fica disponível para uma etapa futura de embeddings. |
| Tarefas | Worker com fila em tabela (`FOR UPDATE SKIP LOCKED`) | Evita outro serviço na primeira versão. Se a carga crescer, migra para SQS. |
| Autenticação | OIDC (Cognito, trocável por SSO do cliente) | A API confere papéis, nunca a interface. |
| Arquivos | S3 para anexos e troca com o ERP | |
| Hospedagem | ECS Fargate e RDS | |

```
backend/
├── app/
│   ├── api/           rotas
│   ├── pdm/           versões do PDM, classes, condições
│   ├── normalizacao/  funções puras por grandeza e vocabulário
│   ├── tabelas/       tabelas técnicas curadas, com fonte
│   ├── classes/       resolução de classe e autocomplete
│   ├── sugestoes/     ranking de valores
│   ├── identidade/    chave de identidade e candidatos
│   ├── ncm/           regras de NCM
│   ├── cadastro/      estados, validações, exceções
│   ├── leitura/       regras e LLM para pedidos
│   ├── erp/           interface e conectores
│   └── auditoria/
├── worker/            estruturação da base, importações, envios
├── migrations/
└── tests/
```

As tabelas de `scripts/analise_normalizacao.py`, da branch `analise-de-mercado` (`ABREV`, `SINONIMOS`, `DN_POL`, `POL_CANON`), são o ponto de partida de `normalizacao/`.

Metas de tempo propostas (p95, no servidor): autocomplete em até 100 ms e atualização de candidatos em até 300 ms. A leitura de pedido por LLM é assíncrona, e a pessoa pode preencher enquanto ela roda.

---

## 5. Modelo de dados

| Grupo | Tabela | Conteúdo principal |
|---|---|---|
| PDM | `pdm_versao` | Arquivo de origem, hash, data e versão ativa. |
| | `pdm_classe`, `pdm_nome` | Classes e os 119 nomes, com grupo, unidade e critério de identidade. |
| | `pdm_atributo`, `pdm_valor` | Ordem, obrigatoriedade, condição, formato e valores permitidos. |
| | `pdm_ncm_regra` | Regras de NCM por classe. |
| | `sinonimo`, `abreviacao` | Vocabulário curado e versionado. |
| | `tabela_tecnica` | Tabelas curadas para deduzir atributos opcionais, com fonte. |
| | `pdm_proposta` | Propostas de classe nova e de novos valores, com pedido de origem e decisão. |
| Base | `material` | Cópia da base do ERP, sem correções. |
| | `material_classificacao` | Classe, confiança, método e versões usadas. |
| | `material_atributo` | Valor bruto, valor canônico, origem, trecho e confiança. |
| | `material_identidade` | Chave e indicação de chave completa. |
| | `equivalencia` | Itens intercambiáveis, com fonte (regra 13). |
| Cadastro | `pedido` | Pedido original, estado e analista responsável. |
| | `cadastro` | Estado, classe, versão do PDM, dados fiscais, descrições, chave e código devolvido. |
| | `cadastro_valor` | Valor, origem, trecho, opções mostradas e opção escolhida. |
| | `cadastro_excecao` | Tipo, valor padrão, valor usado, justificativa, autor, revisor e decisão. |
| | `cadastro_candidato` | Fotografia dos candidatos e da decisão no momento da aprovação. |
| | `cadastro_pergunta` | Perguntas ao solicitante e respostas. |
| | `area_contato` | E-mail de contato por área solicitante. |
| Operação | `evento_auditoria` | Registro somente de inclusão: quem, quando, antes e depois. |
| | `llm_chamada` | Hash da entrada, modelo, versão do prompt, tokens, tempo e resultado. |
| | `erp_envio` | Tipo (item novo ou reativação), tentativas, arquivo, protocolo e retorno. |
| | `estatistica_valor` | Frequência por classe, atributo e valor. |

Cada cadastro guarda a versão do PDM usada, para que uma mudança no padrão não reescreva decisões antigas.

---

## 6. Motor de sugestão

### 6.1 Classe

1. O índice reúne os 119 nomes, as abreviações (`PARAF`, `VALV`, `ROL`) e o glossário inglês-português.
2. A resposta traz até 5 opções, ordenadas por correspondência de início, de palavras e por trigramas. A frequência na base desempata.
3. Opções ambíguas mostram o contexto: `LUVA` (conexão), `LUVA SEGURANCA` (EPI) e `LUVA EIXO` (sobressalente).
4. A confirmação é obrigatória, mesmo com uma só opção.
5. Texto além do substantivo já preenche atributos por regra: `M12X50` vira `BITOLA M12` e `COMPRIMENTO 50MM`.
6. Sem correspondência em texto longo, o LLM pode propor classes. A pessoa confirma do mesmo jeito.

O autocomplete não usa LLM.

### 6.2 Atributos

Os atributos, a ordem e a obrigatoriedade vêm do PDM, não do histórico. As 19 condições de `QUANDO_SE_APLICA` viram predicados no backend. A cada alteração, a API devolve quais campos valem, e assim o frontend não duplica regras do PDM.

### 6.3 Valores

| Origem | Exemplo | Entra preenchido? |
|---|---|---|
| `REGRA_PDM` | `ROSCA: METRICA GROSSA` quando o passo não aparece; unidade da classe | Sim, marcado como regra. |
| `PEDIDO_REGRA`, `PEDIDO_LLM` | `BITOLA: M16`, extraído de "m16 x 60" | Sim, com o trecho de origem. |
| `TABELA_LOCAL` | `DIAMETRO INTERNO: 25MM`, pela referência 6205 | Sim, só em atributos opcionais e com a fonte. |
| `HISTORICO` | `8.8 (30%)` | Não. Aparece como opção. |
| `DIGITADO` | Medida digitada e normalizada na hora | Quem preencheu foi a pessoa. |

Valores `REGRA_PDM`, `PEDIDO_*` e `TABELA_LOCAL` continuam editáveis. Se a regra do PDM for contrariada, vira exceção.

Regras do ranking:

- Só entram valores válidos no PDM, de registros `ATIVO`, com alta confiança.
- O ranking usa a frequência dentro do nome do material, não da classe.
- O ranking considera os atributos já preenchidos quando há ao menos 3 registros com essa combinação. Se não houver, volta para a frequência do nome.
- Com menos de 20 registros no nome, a tela mostra a lista sem percentuais.
- `REFERENCIA FABRICANTE` não tem opções, porque quase cada item tem a sua. A pessoa digita, e a verificação de duplicidade roda assim que fabricante e referência estão preenchidos.
- A lista completa do PDM está sempre a um clique.
- Em medidas, o foco é a digitação com pré-visualização (`2"` vira `2POL`), e valores já usados aparecem conforme a pessoa digita.
- Se a pessoa não souber um obrigatório, o campo fica vazio e o item segue para devolução. Nenhum valor é assumido.

Itens aprovados sem exceção alimentam a estatística. A taxa de aceite por posição e por atributo é registrada, para detectar sugestões aceitas por inércia.

---

## 7. Validações e exceções

| Verificação | Quando falha |
|---|---|
| Obrigatório vazio (regra 7) | Bloqueia a aprovação. O caminho é devolver ao solicitante. |
| Valor fora da lista (regra 4) | Exceção com justificativa. |
| Formato não normalizável (regras 5 e 6) | Exceção com justificativa. |
| Unidade ou grupo diferente do padrão da classe (regra 11) | Exceção com justificativa. |
| NCM válido, mas diferente da regra da classe | Exceção com justificativa. |
| NCM inexistente ou fora de vigência (regra 12) | Bloqueia a aprovação. Não admite exceção. |
| Item novo com candidato `IGUAL` (regra 10) | Exceção com justificativa. |
| Item igual a código `BLOQUEADO` ou `OBSOLETO` | Exceção com justificativa: pedir reativação ou criar código novo. |
| Item novo com candidato `PROVAVEL` | Justificativa, sem segundo analista. |
| Texto, ordem e fabricante na descrição (regras 1 a 3, 8 e 9) | Resolvido automaticamente, porque a descrição é gerada. |

Uma exceção envia o item para `EM_REVISAO`. O revisor precisa ser outro analista. Valores de exceção recorrentes geram uma lista de propostas de mudança no PDM.

---

## 8. Verificação de duplicidade

O painel separa cinco situações:

| Nível | Critério | Efeito |
|---|---|---|
| `IGUAL` | Mesma chave completa, com valores de alta confiança. | Sugere usar o código. Criar outro exige exceção. |
| `PROVAVEL` | Mesma chave com valores de baixa confiança, ou parte dos obrigatórios iguais e nenhum divergente. | Exige decisão com justificativa. |
| `DIVERGENTE` | Mesma família, com atributo de identidade diferente. | Mostra qual atributo difere e não bloqueia. A confiança fica limitada a 85%, como no mockup. |
| `PARECIDO` | Só texto ou embedding. | Apenas informa. |
| `EQUIVALENTE` | Item intercambiável registrado (regra 13). | Apenas informa. Nunca une códigos. |

Regras de funcionamento:

- A busca começa pela classe confirmada e compara atributo por atributo. A similaridade de texto só amplia a lista.
- Nas classes de especificação, a chave usa classe, nome e obrigatórios. Nas de referência, usa fabricante e referência normalizados (`1R-1808` e `1R1808` são iguais; `CAT` vira `CATERPILLAR`).
- Só códigos `ATIVO` podem ser usados diretamente. `BLOQUEADO` e `OBSOLETO` aparecem com status e estoque, e a decisão segue a seção 7. O motivo do bloqueio não está nos dados, por isso a reativação passa por um segundo analista.
- O painel nunca afirma que um item não existe. A mensagem informa quantos registros da classe puderam ser comparados.
- Na aprovação, a verificação roda de novo dentro da transação. Um índice único sobre a chave impede que dois analistas aprovem o mesmo item ao mesmo tempo.

---

## 9. Estruturação da base

```
importar ──► classificar ──► extrair ──► normalizar ──► chave ──► avaliar ──► publicar
             regras + LLM   regras + LLM   código       código    amostra
```

- **Não altera a base.** O resultado fica nas tabelas `material_classificacao`, `material_atributo` e `material_identidade`. Unificar códigos continua sendo trabalho do saneamento.
- **Confiança por atributo.** Só valores de alta confiança fecham `IGUAL` e alimentam sugestões. Os demais geram `PROVAVEL`.
- **Reprocessável.** O cache usa `sha256(texto + classe + versão do prompt + modelo + versão do PDM)`.
- **Ordem por valor.** Começa em `SOB01` e `FIL01`, que concentram 84% do valor em estoque, e segue até cobrir tudo. O uso em produção só começa com a base completa.
- **Atualização contínua.** Cada importação do ERP reprocessa apenas o que mudou.

Antes do lote, o time anota à mão uma amostra de 300 registros, estratificada por grupo e estilo de descrição, mais os 15 produtos reais. Metas propostas: 98% de precisão na classe e 97% de precisão por atributo obrigatório, ambas entre valores de alta confiança. A cobertura é medida e publicada, sem meta prévia, porque muitos registros realmente não têm a informação.

São 23.134 textos distintos, com 3,3 milhões de caracteres. Vale atenção aos 5.290 registros de `SOB01` e `FIL01` sem fabricante ou referência nas colunas: o que não estiver no texto continua sem chave, e esses itens precisam aparecer como não comparáveis.

---

## 10. Uso de LLM

| Usa LLM | Não usa LLM |
|---|---|
| Classificar e extrair no lote da base, quando as regras não bastam. | Autocomplete e ranking de sugestões. |
| Ler pedidos e anexos em texto livre. | Formatação, conversão de unidade e geração da descrição. |
| Propor classes para textos sem correspondência. | NCM, chave de identidade e aprovação. |

Contrato de cada chamada:

- O texto do pedido entra como dado, com delimitação clara, e nunca como instrução.
- A saída é JSON validado por um schema gerado do PDM para aquela classe. `null` é uma resposta válida.
- Cada valor traz o trecho de origem. Se o trecho não existir no texto ou o valor não for permitido, ele é descartado.
- Não há ferramentas com efeito colateral. A saída é apenas uma proposta para a pessoa revisar.
- Sem resposta, com erro ou com `stop_reason: "refusal"`, a tela segue no preenchimento por regras e digitação.

Detalhes de implementação, conferidos na documentação da API em 2026-11-07:

- Usar saídas estruturadas com `client.messages.parse()`. Forçar `tool_choice` retorna erro 400 no Opus 5.5 e no Sonnet 5.5.
- Usar prompt caching no bloco de instruções e schema. O prefixo mínimo é de 512 tokens, e a eficácia precisa ser conferida em `cache_read_input_tokens`.
- Modelos: Haiku 4.5 para volume e leitura de pedidos, Sonnet 5 reservado aos casos difíceis (ainda sem uso). A comparação entre modelos com amostra anotada por especialistas não foi feita.

**Provedor.** O módulo `app/llm/cliente.py` isola o acesso. `LLM_PROVIDER=bedrock` usa `AnthropicBedrock` com perfis de inferência (`us.anthropic.claude-haiku-4-5-20251001-v1:0`); `LLM_PROVIDER=aws_platform` usa `AnthropicAWS`, com IDs sem prefixo e as variáveis `AWS_REGION` e `ANTHROPIC_AWS_WORKSPACE_ID`. Os modelos são configuráveis (`LLM_MODELO_EXTRACAO`, `LLM_MODELO_DIFICIL`) porque a lista permitida muda de conta para conta.

**Custo medido.** US$ 0,0029 por chamada na estruturação (Haiku 4.5, cerca de 2 mil tokens de entrada e 180 de saída), o que deu cerca de US$ 39,5 para a base inteira, e US$ 0,0028 por pedido na leitura ao vivo. O cache de prompt não entrou: o Haiku 4.5 só cacheia prefixos a partir de 4.096 tokens e o prompt tem cerca de 2 mil. Os preços são a estimativa do módulo; a cobrança real vem da conta AWS.

---

## 11. Integração com o ERP

O produto depende de uma interface `ConectorERP`, com quatro operações: `enviar_item`, `solicitar_reativacao`, `consultar_retorno` e `exportar_base`.

- A primeira implementação troca arquivos pelo S3. Depois, pode virar API sem mudar o restante.
- O envio é idempotente, com o identificador do cadastro.
- A base é reimportada periodicamente. Códigos criados fora do produto são detectados e estruturados.
- Enquanto o código não volta, o item fica `APROVADO`, e sua chave já bloqueia cadastros iguais.
- O ERP real ainda não está definido. Os materiais do desafio não dizem qual é.

---

## 12. Contrato da API

Base: `/api/v1`. O OpenAPI gerado é a referência, e os tipos TypeScript do frontend saem dele.

| Método e rota | Uso | Elemento do mockup |
|---|---|---|
| `GET /pdm/nomes?q=` | Autocomplete de classe | Campo de busca |
| `GET /pdm/classes/{id}` | Atributos da classe | "Classe e atributos" |
| `POST /cadastros` | Cria rascunho vazio ou a partir de um pedido | "Cadastrar novo item" |
| `GET /cadastros/{id}` | Estado completo | Todas as etapas |
| `PATCH /cadastros/{id}` | Altera valores e devolve o estado recalculado | "Refinar por atributos", formulário |
| `GET /cadastros/{id}/sugestoes/{atributo}` | Opções de valor | Novo |
| `GET /cadastros/{id}/candidatos` | Candidatos e motivos | "Itens existentes sugeridos" |
| `POST /cadastros/{id}/usar-existente` | Encerra em `JA_EXISTE` | "Validar item selecionado" |
| `POST /cadastros/{id}/devolver` | Devolve com a lista ou a pergunta | "Enviar pergunta" |
| `POST /cadastros/{id}/aprovar` | Aprova ou envia para revisão | "Enviar para aprovação" |
| `POST /cadastros/{id}/recusar` | Encerra em `FORA_DO_PDM` | Novo |
| `POST /cadastros/{id}/propor-classe` | Envia a proposta e aguarda o PDM | Novo |
| `POST /cadastros/{id}/reativar` | Pede a reativação de um código | Novo |
| `POST /cadastros/{id}/revisao` | Segundo analista decide | Novo |
| `GET /cadastros/{id}/historico` | Auditoria | Novo |
| `GET /pedidos`, `POST /pedidos/{id}/assumir` | Fila e atribuição | "Pedidos de cadastro" |
| `POST /importacoes/pedidos` | Carga de pedidos | Novo |
| `POST /pdm/versoes`, `GET /pdm/propostas`, `GET /excecoes` | Administração do PDM | Novo |

O `PATCH` usa controle de versão e devolve campos válidos, origens, pendências, exceções, descrição gerada e NCM. Assim, a interface não calcula regra de negócio. Erros seguem `application/problem+json`.

Os quatro ajustes previstos para o mockup estão feitos: opções clicáveis nos atributos, marcação de origem por valor, etapa de revisão de exceções e remoção da entrada por foto. "Enviar para aprovação" virou "Aprovar" quando não há exceção e "Enviar para revisão" quando há. Foram acrescentadas `POST /busca`, `GET /resumo`, `GET /pedidos/{id}` e `GET /cadastros/{id}/perguntas`.

---

## 13. Permissões, auditoria e operação

| Papel | Pode |
|---|---|
| `analista` | Assumir pedidos, preencher, devolver, recusar e aprovar item normal. |
| `revisor` | Tudo que o analista faz, e decidir exceções de outras pessoas. |
| `admin_pdm` | Publicar versões do PDM e tratar propostas de mudança. |
| `leitor` | Consultar. |

- Toda alteração gera um evento de auditoria com autor, data, antes, depois e origem.
- Um pedido fica com um analista por vez, e o `PATCH` rejeita gravação sobre versão antiga.
- Logs e métricas vão para o CloudWatch, com alarmes de erro no ERP, falha do LLM e custo.
- Sem chaves no código: a aplicação usa papéis IAM e o Secrets Manager. Credenciais em `.env` servem só para desenvolvimento local.
- Pedidos podem conter nomes em assinaturas de e-mail. Remover assinaturas antes de chamar o LLM e guardar só hashes e métricas em `llm_chamada`.
- CI com lint, tipos, testes e verificação de migrações.

---

## 14. Fases de entrega

| Fase | Entrega | Pronto quando |
|---|---|---|
| 0. Fundação | Backend, banco, migrações, CI, ambiente AWS e importação das 3 planilhas | Os totais importados batem com a origem: 23.554 materiais, 520 pedidos, 44 classes e 229 atributos. |
| 1. PDM e normalização | PDM versionado, 19 condições, normalizadores, tabelas locais, regras de NCM e geração de descrição | Os exemplos das regras do PDM passam nos testes e nenhum atributo é digitado à mão. |
| 2. Estruturação da base | Regras, LLM, amostra anotada, avaliação e lote | Metas de precisão atingidas e 23.554 registros processados, com cobertura publicada. |
| 3. Núcleo do cadastro | Autocomplete, rascunho, atributos, sugestões e validações | Um item completo é preenchido pela API, e o teste de sugestão é refeito com a base inteira. |
| 4. Identidade | Chave, níveis de candidato e índice único | Os casos obrigatórios da seção 15 passam. |
| 5. Decisões | Estados, exceções, revisão, propostas ao PDM, permissões e auditoria | Todas as transições são testadas e registradas. |
| 6. Pedidos | Fila, leitura por regras e LLM, glossário e devolução por e-mail | Os 520 pedidos passam pelo fluxo e o LLM desligado não trava a tela. |
| 7. ERP | Interface, conector por arquivos, reativação e reimportação | Um item vai e volta com código, inclusive após falha simulada, e uma reativação é confirmada. |
| 8. Integração e piloto | React da outra branch, testes de ponta a ponta e uso por analistas | Analistas concluem cadastros reais e as metas da seção 15 são medidas. |

As fases 2 e 3 podem correr em paralelo: a fase 3 usa os registros já legíveis até o lote terminar. O frontend pode integrar a partir do fim da fase 3, porque o contrato já existe.

---

## 15. Testes e métricas

Casos obrigatórios:

| Caso | Resultado esperado |
|---|---|
| `SKF 6205-2RSH/C3`, `FAG 6205-C-2HRS-C3`, `NSK 6205DDUC3` | Mesma chave. Candidato `IGUAL`. |
| `CAT 1R-1808` e `DONALDSON P551808` | Chaves diferentes. `EQUIVALENTE`, sem unir. |
| `PARAFUSO SEXTAVADO M12X50 ZINCADO` | Classe de resistência fica vazia e o item não aprova. |
| "preciso de 10 parafuso sextavado m16 x 60 galvanizado 8.8 din 933 pra peneira" | Valores vêm do pedido com trecho. `galvanizado` fica ambíguo. "peneira" não entra na identidade. |
| `3.650 psi` e `6.000 psi` | Lidos como milhares e convertidos para BAR. |
| `LUVA` | Mostra as três classes e exige escolha. |
| "Cadeira de escritório giratória" | Nenhuma classe serve e o pedido termina em `FORA_DO_PDM`. |
| Material legítimo sem classe no PDM | A proposta aguarda a nova versão do PDM e o pedido retoma depois. |
| Item igual a código `BLOQUEADO` com estoque | Mostra status e estoque, e exige decisão com segundo analista. |
| Rolamento `6205-2RSH/C3` sem medidas | `TABELA_LOCAL` propõe 25MM, 52MM e 15MM, com a fonte. |
| Sobressalente com aplicação e modelo preenchidos | A opção de `FABRICANTE` usa esse contexto, e `REFERENCIA FABRICANTE` fica sem opções. |
| Dois analistas aprovando o mesmo item | Só um aprova. O outro vê o candidato `IGUAL`. |
| LLM indisponível | O fluxo segue com regras e digitação. |
| Item normal alterado depois de aprovado | Nova alteração é recusada e o histórico fica intacto. |

Também entram testes unitários dos normalizadores, testes de integração em PostgreSQL real, avaliação do LLM com a amostra anotada e testes de contrato do OpenAPI.

Métricas do produto:

- Tempo mediano por cadastro e por pedido. É preciso medir o tempo atual dos analistas, porque ele não está nos dados.
- Parcela de pedidos que termina em `JA_EXISTE`.
- Duplicados aprovados, medidos por auditoria posterior.
- Taxa de exceção por classe e atributo.
- Taxa de aceite por posição da sugestão, comparada ao acerto esperado.
- Parcela de campos corrigidos depois de virem preenchidos do pedido.

---

## 16. Premissas e pendências

Premissas ainda não confirmadas. Qualquer uma pode ser alterada na revisão:

1. "Requisições" e análise de estoque, que aparecem no mockup, ficam fora deste plano.
2. NCM inexistente bloqueia a aprovação, mesmo com justificativa.
3. Qualquer outro analista com papel `revisor` pode revisar uma exceção.
4. Item novo sempre usa a unidade padrão da classe. Fatores de embalagem (`JG`, `CX`) ficam fora.
5. Pedidos chegam por importação, e a devolução por e-mail usa o SES.
6. As metas numéricas e os demais serviços AWS deste plano são propostas.

Configuração necessária na AWS:

- [ ] Para usar o Claude Platform on AWS: obter o ID do workspace e definir `AWS_REGION` e `ANTHROPIC_AWS_WORKSPACE_ID`.
- [ ] Pedir a liberação dos modelos 5.5 na política `ws-bedrock-model-allowlist-policy-1`, se forem desejados.
- [ ] Trocar as credenciais temporárias do `.env` por um papel IAM da aplicação e do worker (hoje há um `AWS_SESSION_TOKEN`, que expira).
- [ ] Confirmar as cotas, criar orçamento e alarme de custo.

Pendências do time:

- [ ] Enviar ao GitHub o código do pipeline da branch `Expli` e reconciliar com este backend.
- [ ] Alinhar o mockup com a seção 12 antes de a branch de frontend avançar.
- [ ] Implementar a autenticação OIDC antes de qualquer uso fora do desenvolvimento.
- [ ] Integrar o envio de e-mail (SES) e levantar o contato de cada uma das 12 áreas solicitantes (`area_contato`).
- [ ] Definir quem anota uma amostra à mão (o plano propunha 300 registros) e quem administra o PDM.
- [ ] Corrigir o PDM: o NCM `7306.30.00` não é mais vigente (seção 0).
- [ ] Medir o tempo atual de um cadastro com quem faz esse trabalho.
- [ ] Atualizar a seção de stack do [02-plano-projeto.md](02-plano-projeto.md).

---

## Referências

- [01-dados.md](01-dados.md): descrição dos dados.
- [02-plano-projeto.md](02-plano-projeto.md): pipeline E0 a E8.
- `docs/03-analise-mercado.md`, na branch `analise-de-mercado`: tese de identidade, volumes e valor por grupo.
- [mockup_plataforma.html](../mockup_plataforma.html): telas de busca, cadastro e requisições.
