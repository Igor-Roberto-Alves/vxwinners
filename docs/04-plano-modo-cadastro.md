# Plano do modo de cadastro de materiais

Proposta para revisão do time · 2026-11-07 · branch `modo-cadastro`

O modo de cadastro é o módulo em que o responsável pelo cadastro cria um material novo a partir de poucas palavras. A pessoa digita o que precisa, confirma a classe do PDM e preenche os atributos dessa classe com a ajuda de sugestões baseadas no que já está cadastrado. Antes de aprovar, o sistema mostra se o item já existe. **Tudo é editável e a decisão final é sempre de uma pessoa.**

O módulo é tratado como produto, não como demonstração. Por isso, este plano substitui parte do [02-plano-projeto.md](02-plano-projeto.md): Streamlit, DuckDB e telas pré-calculadas dão lugar a FastAPI, PostgreSQL e React. O pipeline das etapas E0 a E5 continua valendo, agora como base deste módulo.

Termos usados no documento:

- **Classe:** tipo de material no PDM, como `PARAFUSO SEXTAVADO` (`PDM001`).
- **Atributo:** característica exigida pela classe, como `BITOLA` ou `COMPRIMENTO`.
- **Chave de identidade:** combinação definida pela regra 10 do PDM para dizer que dois registros são o mesmo item.
- **Exceção:** decisão que contraria o PDM, permitida com justificativa.

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
| Acesso ao Claude | Claude Platform on AWS, com o acesso isolado em um módulo. | A API de lote cuida de filas e limites, e os recursos novos chegam junto com a API. |
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
| Banco | PostgreSQL com `pg_trgm`, `unaccent` e `pgvector` | Concorrência, auditoria, busca por similaridade e fila. |
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
- O plano anterior prevê Haiku 5.5 para volume e Sonnet 5.5 para casos difíceis. Esse é o ponto de partida, e a amostra anotada compara os dois com o Opus 5.5 antes do lote.

**Claude Platform on AWS.** O produto usa o cliente `AnthropicAWS()`, com IDs de modelo sem prefixo (como `claude-haiku-5-5`). O serviço usa IAM e cobrança pela AWS, e a API de lote cuida de filas e limites no processamento da base. Ele é operado pela Anthropic. Se uma política de cliente exigir serviço operado pela AWS, a alternativa é o Bedrock (`AnthropicBedrockMantle(aws_region=...)`, IDs com prefixo `anthropic.`), que não tem API de lote. O acesso fica isolado em um único módulo, então a troca não afeta o resto.

**Custo estimado.** Uma passada pela base custa entre cerca de US$ 2 (Haiku 5.5) e US$ 70 (Opus 5.5), o que não deve limitar o projeto. A conta supõe 2,6 milhões de tokens de entrada e 3 milhões de saída, com preços da API direta, sem contar desconto de lote, thinking ou repetições. É uma estimativa grosseira: precisa ser refeita com `count_tokens` em uma amostra, e os preços precisam ser conferidos na conta AWS.

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

O mockup precisa de quatro ajustes: opções clicáveis nos atributos, marcação de origem por valor, etapa de revisão de exceções e remoção da entrada por foto. "Enviar para aprovação" vira "Aprovar" quando não há exceção. Em 2026-11-07 ainda não havia branch de frontend no remoto, então a API deve ser testada pelo próprio contrato até ela chegar.

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

- [ ] Ativar o Claude Platform on AWS e obter o ID do workspace.
- [ ] Definir `AWS_REGION` e `ANTHROPIC_AWS_WORKSPACE_ID`, exigidas pelo cliente.
- [ ] Confirmar na região os modelos Haiku 5.5, Sonnet 5.5 e Opus 5.5.
- [ ] Criar o papel IAM da aplicação e do worker.
- [ ] Confirmar as cotas para o lote da base.
- [ ] Criar orçamento e alarme de custo.

Pendências do time:

- [ ] Alinhar o mockup com a seção 12 antes de a branch de frontend avançar.
- [ ] Definir quem anota a amostra de 300 registros.
- [ ] Levantar o e-mail de contato de cada uma das 12 áreas solicitantes.
- [ ] Definir quem administra o PDM e responde às propostas de classe.
- [ ] Medir o tempo atual de um cadastro com quem faz esse trabalho.
- [ ] Corrigir o [01-dados.md](01-dados.md), que cita `claude-bedrock.sh` e `.env` como já configurados. Eles não estão no repositório.
- [ ] Atualizar a seção de stack do [02-plano-projeto.md](02-plano-projeto.md).

---

## Referências

- [01-dados.md](01-dados.md): descrição dos dados.
- [02-plano-projeto.md](02-plano-projeto.md): pipeline E0 a E8.
- `docs/03-analise-mercado.md`, na branch `analise-de-mercado`: tese de identidade, volumes e valor por grupo.
- [mockup_plataforma.html](../mockup_plataforma.html): telas de busca, cadastro e requisições.
