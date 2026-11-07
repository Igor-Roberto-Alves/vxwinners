# Plano de projeto — pipeline de normalização e saneamento

Arquitetura no formato pedido: **texto livre → modelo de linguagem separa sujeito e características → tabela → normalização de unidades e materiais → identidade/dedup**.

```
                 ┌──────────────────────────────────────────────────────────────────┐
                 │  PDM (03_padrao_cadastro_PDM.xlsx) = schema + vocabulário        │
                 │  44 classes · 229 atributos · listas de valores · unidades · NCM │
                 └────────────────┬─────────────────────────────────────────────────┘
                                  │ compilado em JSON Schema + dicionários
                                  ▼
 ENTRADA              E1            E2             E3            E4           E5
┌──────────┐    ┌───────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐
│ base 23k │───►│ CLASSIFICA│─►│ EXTRAI   │─►│ TABELA    │─►│NORMALIZA │─►│IDENTIDADE│
│ pedidos  │    │ sujeito   │  │ caracte- │  │ canônica  │  │unidades  │  │ + dedup  │
│ 520      │    │ (classe   │  │ rísticas │  │ (EAV→wide)│  │materiais │  │ + NCM    │
└──────────┘    │  PDM)     │  │(atributos│  └───────────┘  │ formatos │  └────┬─────┘
                └───────────┘  │ da classe)│                └──────────┘       │
                                └──────────┘                                   ▼
                                                                    ┌────────────────────┐
                                                                    │ SAÍDAS             │
                                                                    │ descrição PDM      │
                                                                    │ clusters/sobrevivente│
                                                                    │ NCM + unidade      │
                                                                    │ pendências         │
                                                                    │ evidência/métricas │
                                                                    └────────────────────┘
```

**Decisão central:** o LLM **classifica e extrai**; ele **não formata e não decide identidade**. Formatação, conversão de unidade, casamento de vocabulário, NCM e deduplicação são **código determinístico** — porque o PDM é um contrato fechado e porque o júri vai pedir para repetir o resultado. LLM em cima de regra é alucinação caríssima; regra em cima de LLM é um sistema auditável.

---

## E0 — Ingestão e compilação do PDM

**Objetivo:** transformar o PDM de planilha em artefatos que o código consome.

| Saída | Conteúdo |
|---|---|
| `warehouse.duckdb` | as 3 planilhas em tabelas tipadas (NCM como `VARCHAR`, zeros à esquerda preservados) |
| `pdm/classes.json` | 44 classes: `id_pdm`, substantivo(s), qualificador, grupo, unidade padrão, critério de identidade |
| `pdm/schemas.json` | **1 JSON Schema por classe**, gerado da aba `ATRIBUTOS`: propriedade por atributo, `enum` quando há `VALORES_PERMITIDOS`, `required` conforme `OBRIGATORIO`+`QUANDO_SE_APLICA` |
| `pdm/vocab.json` | índice invertido de todos os valores permitidos → `(classe, atributo, valor canônico)` |
| `pdm/ncm_rules.py` | as regras condicionais de `NCM_REFERENCIA` como funções Python por classe |
| `pdm/abreviacoes.yaml` | `PARAF→PARAFUSO`, `SEXT→SEXTAVADO`, `HIDR→HIDRAULICA`, `MANG→MANGUEIRA`, `RET→RETENTOR`, `ROL→ROLAMENTO`, `DIAM→DIAMETRO`, `COMP→COMPRIMENTO`, `MAT→MATERIAL`, `APLIC→APLICACAO`, `MOD→MODELO`, `FABR→FABRICANTE`, `REF→REFERENCIA`, `INT→INTERNO`, `EXT→EXTERNO`, `MONT→MONTADA`, `LUBR→LUBRIFICANTE`, `CAB→CABO\|CABECA` (ambíguo → resolver pela classe) |

Gerar os schemas **a partir da planilha**, nunca à mão: 229 atributos digitados à mão é bug garantido, e se a banca mudar o PDM o pipeline continua válido.

As 19 regras condicionais (`"somente FLANGE"`, `"somente cabos de 1 condutor"`, …) viram predicados; `"quando informado pelo fabricante"` vira atributo opcional alvo de enriquecimento.

---

## E1 — Separar o **sujeito** (classificação na classe PDM)

Isto é o "sujeito" do seu plano, e o PDM já define o vocabulário: `SUBSTANTIVO + QUALIFICADOR` de uma das 44 classes.

**Por que antes da extração:** o conjunto de características a extrair **depende da classe**. `PARAFUSO SEXTAVADO` pede 7 atributos; `RETENTOR` pede 5; `FILTRO` pede fabricante + part number. Sem a classe não há schema, e sem schema a extração devolve campo livre — que é exatamente o problema que estamos resolvendo.

**Cascata de três níveis, do barato ao caro:**

| Nível | Método | Cobertura esperada |
|---|---|---|
| 1 | **Regra léxica** — descrição expandida (abreviações) casada contra substantivo+qualificador das classes e das listas de substantivos; filtro por `GRUPO_MERCADORIA`, que já vem preenchido em 100% da base e reduz 44 classes a ~1–3 candidatas | maioria dos casos |
| 2 | **Embedding + kNN** — vetorizar descrição e as 44 classes (+ 73 substantivos das guarda-chuva); resolve abreviação não dicionarizada e ordem de palavras | o resto fácil |
| 3 | **LLM** — só quando nível 1 e 2 discordam ou a confiança é baixa; prompt recebe apenas as classes candidatas do grupo e devolve `id_pdm` + confiança + justificativa curta | casos difíceis |

Saída: `classificacao(codigo_material, id_pdm, substantivo, qualificador, confianca, metodo, justificativa)`.

**Casos que a classificação precisa tratar explicitamente:**
- `GRUPO_MERCADORIA` **errado** na origem (há 1.737 NCM divergentes, sinal de grupo errado também) → a classificação pode *corrigir* o grupo, e isso é entregável.
- Item **sem classe PDM** (a cadeira de escritório nos pedidos) → status `FORA_DO_PDM`, nunca forçar classe.
- `PDM050`/`PDM110` precisam também do **substantivo específico** da lista (62 e 11 valores).

---

## E2 — Separar as **características** (extração de atributos)

Agora sim o modelo de linguagem natural, com o schema da classe em mãos.

**Modelo:** Claude via Bedrock. **Haiku 4.5** (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) para o volume, **Sonnet 5** (`us.anthropic.claude-sonnet-5`) para os casos de baixa confiança e para os anexos longos.

> Correção verificada na conta: a role tem uma **allowlist de IAM** que nega
> `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` e `claude-fable-5-1`,
> apesar de o `list_foundation_models` devolvê-los como `ACTIVE`. Todos os Claude
> exigem perfil de inferência (prefixo `us.`), não aceitam `anthropic.*` direto.
> E **`temperature` é rejeitado** por Sonnet 5 / Opus 5 / Opus 4.7+ / Fable 5
> (`temperature is deprecated for this model`) — mandar o campo faz 100% das
> chamadas falharem. Usar **tool use / structured output** com o JSON Schema da classe: o modelo é obrigado a devolver os campos daquela classe e só pode usar valores do `enum`. Isso elimina a maior parte da alucinação de formato de graça.

**Contrato do prompt (um por classe, montado em runtime):**

```
Você extrai atributos de materiais industriais. Devolva APENAS o que está no texto.

CLASSE: PARAFUSO SEXTAVADO (PDM001)
ATRIBUTOS:
  ROSCA                (obrigatório) um de: METRICA FINA | METRICA GROSSA | UNC | UNF
  BITOLA               (obrigatório) M + diâmetro em mm. Ex.: M12
  COMPRIMENTO          (obrigatório) número + MM
  CLASSE RESISTENCIA   (obrigatório) um de: 10.9 | 5.8 | 8.8 | A2-70 | A4-70 | SAE GRAU 2 | ...
  MATERIAL             (obrigatório) um de: ACO CARBONO | ACO INOX 304 | ACO INOX 316
  ACABAMENTO           (obrigatório) um de: GALVANIZADO A FOGO | NATURAL | ... | ZINCADO BRANCO
  NORMA                (obrigatório) um de: ASME B18.2.1 | DIN 931 | DIN 933

REGRAS
- Notação compacta junta atributos: "M12X50" = BITOLA M12 + COMPRIMENTO 50MM.
- Passo da rosca ausente ⇒ ROSCA = METRICA GROSSA.
- Nunca invente valor. Atributo ausente no texto ⇒ null.
- Para cada atributo devolva o TRECHO do texto que o originou.

TEXTO: PARAF SEXT INT C 120MM BITOLA M-8 TIPO CABECA ABAULADA A4-70
```

**Três exigências não negociáveis na saída:**

1. **`null` é resposta válida e desejada.** 1.173 registros sem NCM, 66% sem fabricante — o pipeline tem de distinguir *"não informado"* de *"inventado"*. Atributo obrigatório com `null` vira **pendência**, que é entregável (é o caso do parafuso sem classe de resistência no briefing).
2. **Evidência por atributo** (`span` do texto de origem). Sem isso não há auditoria, e a tela de revisão humana fica inútil.
3. **Confiança por atributo**, não por registro.

**Entrada da extração por fonte:**

| Fonte | Texto alimentado ao modelo |
|---|---|
| Base | `DESCRICAO_LONGA` + `DESCRICAO_CURTA` + `FABRICANTE` + `REFERENCIA_FABRICANTE` (a curta é truncada em 40, mas às vezes tem palavra que a longa perdeu) |
| Pedido sem anexo | `TEXTO_SOLICITACAO` |
| Pedido com anexo | `TEXTO_SOLICITACAO` + `CONTEUDO_ANEXO` (136 casos; o texto costuma ser só `"Segue ficha técnica em anexo."`) |

**Otimizações que viabilizam 23.554 registros:**
- **Deduplicar antes de chamar**: 22.891 descrições longas distintas, e muitas iguais após normalização de espaço/caixa. Extrair por *texto distinto*, não por linha. Economia direta.
- **Prompt caching** do bloco de schema da classe (ele se repete em todos os registros daquela classe) + **batch por classe**, que mantém o cache quente.
- **Lote de 10–20 itens por chamada** da mesma classe.
- Cache em disco com chave `sha256(texto + id_pdm + versão_do_prompt)` — reexecução custa zero, e em hackathon você vai reexecutar muito.
- Rodar nível 1 (parser determinístico por regex para fixadores, retentores, rolamentos, cabos) *antes* do LLM: `FIX01` são 4.516 registros de padrão muito regular e caem quase todos em regex.

---

## E3 — A tabela

Dois formatos, porque servem a coisas diferentes.

**`atributos_extraidos` (EAV — longa, uma linha por atributo):** é a tabela de trabalho, auditável, e aceita as 44 classes com schemas diferentes sem 229 colunas.

| codigo_material | id_pdm | atributo | valor_bruto | valor_canonico | unidade_bruta | unidade_canonica | obrigatorio | origem | span | confianca |
|---|---|---|---|---|---|---|---|---|---|---|
| 18028103 | PDM001 | BITOLA | `M-8` | `M8` | | | S | regex | `BITOLA M-8` | 0.99 |
| 18028103 | PDM001 | COMPRIMENTO | `C 120MM` | `120MM` | MM | MM | S | regex | `C 120MM` | 0.95 |
| 18028103 | PDM001 | CLASSE RESISTENCIA | `A4-70` | `A4-70` | | | S | llm | `A4-70` | 0.92 |
| 18028103 | PDM001 | ROSCA | *null* | `METRICA GROSSA` | | | S | **regra 2 PDM** | — | 0.80 |
| 18028103 | PDM001 | MATERIAL | *null* | *null* | | | S | — | — | — |
| 18028103 | PDM001 | ACABAMENTO | *null* | *null* | | | S | — | — | — |

Daí já sai, de graça, a **tabela de pendências**: `MATERIAL` e `ACABAMENTO` obrigatórios e vazios → o item não pode ser considerado saneado, e o pedido equivalente seria devolvido ao solicitante com essa lista exata.

**`materiais_normalizados` (wide — uma linha por material):** é a tabela de apresentação e a base da deduplicação.

| codigo_material | id_pdm | substantivo | qualificador | grupo | unidade_padrao | ncm | fabricante | referencia | **descricao_pdm** | chave_identidade | completude | status_saneamento |
|---|---|---|---|---|---|---|---|---|---|---|---|

`descricao_pdm` é montada por template a partir da EAV, **na ordem da coluna `ORDEM`**:
`{SUBSTANTIVO} {QUALIFICADOR}; {ATRIBUTO}: {VALOR}; …`

Resultado:
```
antes:  PARAF SEXT INT C 120MM BITOLA M-8 TIPO CABECA ABAULADA
depois: PARAFUSO SEXTAVADO INTERNO; TIPO CABECA: ABAULADA; BITOLA: M8;
        COMPRIMENTO: 120MM; CLASSE RESISTENCIA: A4-70; MATERIAL: <pendente>; ...
```

E **regra 8 vs 9** aplicada aqui: nas classes de especificação técnica, fabricante e referência saem da descrição e vão para os campos próprios; nas classes de referência (`PDM100`, `PDM110` — 37% da base) eles entram na descrição.

---

## E4 — Normalizar unidades e materiais

Pós-processamento **100% determinístico** sobre a EAV. Esta é a etapa que você destacou, e é onde o resultado fica defensável.

### 4.1 Unidade de medida do cadastro (19 → 5)

| Variantes | Canônico | Risco |
|---|---|---|
| `UN`, `PÇ`, `PCA` | `PC` | nenhum — sinônimo |
| `MTS`, `MT` | `M` | nenhum |
| `PAR` | `PR` | nenhum |
| `LT`, `GL` | `L` | **`GL` (galão) precisa de fator**, não é renomear |
| `JG`, `CX`, `CT`, `BD`, `RL`, `BR` | ⚠️ **não é sinônimo** | jogo, caixa, cartela, balde, rolo, barra são **embalagem**: 1 `CX` = N `PC`. Converter sem fator corrompe o estoque |

São 2.469 registros com unidade fora do padrão da classe. Tratamento: sinônimos convertem automaticamente; **embalagens vão para fila de decisão** com o fator a confirmar. Dizer isso na banca vale mais que converter tudo errado — mostra que você entendeu que unidade de medida mexe em saldo de estoque e em preço unitário.

### 4.2 Grandezas dentro dos atributos

| Grandeza | Regra PDM | Conversões a implementar |
|---|---|---|
| **Pressão** | sempre `BAR` | `psi → bar` (÷14,5038), `MPa → bar` (×10), `kgf/cm² → bar` (×0,98067), `#`/classe ANSI **não** é pressão (é classe de flange — atributo próprio). Cuidado com `3.650 psi` e `6.000 psi`: ponto é **milhar** |
| **Polegada** | fração + `POL`, inteiro separado por **ponto** | `1 1/4"` / `1-1/4 in` / `1.25"` / `DN 32` → `1.1/4POL`; `2POL ≡ DN 50` (tabela DN↔POL completa, é a duplicidade-exemplo do briefing) |
| **Milímetro** | número + `MM`, decimal com **vírgula** | `15mm`, `15 MM`, `15.0mm`, `0.591"` → `15MM`; `16.25MM → 16,25MM` |
| **Seção de cabo** | `MM2` | `1,5mm2`, `1.5 mm²`, `AWG 16` → `1,5MM2` (tabela AWG↔mm²) |
| **Comprimento de mangueira montada** | `MM` | `2 m`, `2000mm`, `2,0 M` → `2000MM` |
| **Rosca** | desmembrar | `M12X50` → `BITOLA M12` + `COMPRIMENTO 50MM`; `M-8` → `M8`; `1/2-13 UNC` → bitola + rosca |
| **Temperatura, tensão, potência** | conforme atributo | `24VCC`, `450/750v`, `0,6/1 kV` → valor do `enum` |

Implementar como `normalizers/{pressao,polegada,milimetro,secao,rosca}.py`, cada um uma função pura `str → (valor_canonico, unidade, confianca, motivo)`, **cada uma com teste unitário**. É o pedaço do código que mais rende demo ("digite qualquer notação e veja sair no padrão") e o que menos dá problema na apresentação.

### 4.3 Materiais e demais vocabulários controlados

O PDM dá a lista fechada de valores para 195 atributos obrigatórios. Normalizar = casar o valor extraído contra o `enum` da classe, em três passos:

1. **Exato** após normalizar texto (maiúscula, sem acento, sem cedilha, espaço colapsado) — regra 3 do PDM.
2. **Dicionário de sinônimos** curado, por família:
   - Aços: `INOX 316 ≡ AISI 316 ≡ A4 ≡ SS316 → ACO INOX 316`; `INOX 304 ≡ AISI 304 ≡ A2`; `A105 → ACO CARBONO FORJADO A105`; `WCB ≡ A216 WCB → ACO CARBONO FUNDIDO A216 WCB`; `CF8M ≡ A351 CF8M → ACO INOX FUNDIDO A351 CF8M`; `ACO MANGANES`, `ACO CROMO-MOLIBDENIO`, `SAE 1045`
   - Elastômeros: `NBR ≡ BUNA-N ≡ NITRILICA`; `VITON ≡ FKM → FKM (VITON)`; `EPDM`; `PTFE ≡ TEFLON`; `RPTFE`
   - Acabamentos: `ZINCADO ≡ ZN ≡ ZINCADO BRANCO`; `GALVANIZADO A FOGO ≡ HDG ≡ ZINCADO A QUENTE`; `OXIDADO PRETO ≡ BLACK OXIDE`
   - Vedação de rolamento: `2RS ≡ 2RSH ≡ DDU ≡ 2HRS → BORRACHA AMBOS LADOS`; `2Z ≡ ZZ → METALICA AMBOS LADOS`; folga `C3`
   - Terminais/conexões: `BSP`, `NPT`, `JIC`, `ORFS`, `SW`, `BW`, `FF`, `RF`
3. **Fuzzy + embedding** contra o `enum`, com **limiar**; abaixo do limiar → revisão humana, nunca escolha silenciosa.

O item 2 é trabalho de curadoria, não de modelo — e é o maior diferencial técnico do MVP, porque é exatamente o conhecimento de domínio que o júri (gente de suprimentos e manutenção) reconhece. O dicionário vale ser mantido em YAML versionado e **mostrado no pitch**.

### 4.4 Texto
Maiúsculas, remoção de acento e cedilha (50 registros ainda têm), colapso de espaço, remoção de pontuação de sobra (`RET.` → `RETENTOR`), expansão das abreviações do `pdm/abreviacoes.yaml`.

---

## E5 — Identidade, deduplicação e NCM

### 5.1 Chave de identidade (regra 10 do PDM)

Depois da normalização, duplicidade **não é mais problema de similaridade de texto — é igualdade de chave**:

```python
if criterio == "ESPECIFICACAO TECNICA":
    chave = hash(id_pdm, substantivo, qualificador, *[valor_canonico[a] for a in obrigatorios_ordenados])
else:  # REFERENCIA DO FABRICANTE  (PDM100, PDM110)
    chave = hash(id_pdm, substantivo, fabricante_canonico, referencia_normalizada)
```

Essa é a virada do projeto: o LLM não vota em duplicidade. Ele só preenche os campos; a chave decide. Resultado reproduzível e explicável — "estes dois códigos são o mesmo item porque **todos** os atributos obrigatórios coincidem", com a tabela lado a lado na tela.

Para registros **incompletos** (atributo obrigatório pendente), a chave não fecha: entram como **duplicata provável** via blocking por embedding, com score, e vão para revisão. Honestidade aqui > recall inflado.

**As duas armadilhas (regra 13), que precisam estar na demo:**
- `SKF 6205-2RSH/C3` + `FAG 6205-C-2HRS-C3` + `NSK 6205DDUC3` → classe `PDM020`, especificação técnica → **mesma chave, unificar**. Exige o dicionário de vedação (`2RSH ≡ DDU ≡ 2HRS`) e saber que a referência do rolamento *determina* as dimensões.
- `CAT 1R-1808` + `DONALDSON P551808` → classe `PDM100`, referência do fabricante → **chaves diferentes, NÃO unificar**. Registrar em `equivalencias(codigo_a, codigo_b, tipo='INTERCAMBIAVEL', fonte)`.

Um sistema que acerta as duas vence um sistema que só junta texto parecido, e a diferença dá 30 segundos de pitch.

### 5.2 Escolha do sobrevivente

Regra explícita e auditável, por cluster:

1. `ATIVO` ganha de `BLOQUEADO`/`OBSOLETO`;
2. maior completude de atributos obrigatórios;
3. movimentação mais recente (`DATA_ULTIMA_MOVIMENTACAO`);
4. maior estoque × preço;
5. empate → código mais antigo (`DATA_CRIACAO`).

Saída no formato do briefing:
```
10293847  VALVULA ESFERA; DIAMETRO NOMINAL: 2POL; CLASSE PRESSAO: 800#; ...   ATIVO
20384756  BLOQUEADO · USAR 10293847
10482213  BLOQUEADO · USAR 10293847
```
Mais o **plano de merge de estoque**: somar saldos no sobrevivente e recalcular preço médio ponderado — é o que transforma o saneamento em número financeiro.

### 5.3 NCM

Em três passos: **formatar** `0000.00.00` (8.480 registros fora do formato) → **derivar** da classe (31 classes têm NCM único) → **resolver condicional** com `pdm/ncm_rules.py` para `PDM012/030/034/050/051/070/071/081/100/110`.

`PDM110` (7.673 registros) segue o **equipamento de aplicação**, que é atributo obrigatório da classe — logo o NCM sai da própria extração, com exceções por substantivo (`PASTILHA FREIO`, `DISCO FREIO`). Validar os 8 dígitos contra a tabela oficial da NCM (Portal Único Siscomex) baixada uma vez e guardada local. Saída: `ncm_atual`, `ncm_proposto`, `regra_aplicada`, `divergencia (S/N)` — os 1.737 divergentes já identificados viram a lista de exposição fiscal.

---

## E6 — Enriquecimento (completar o que falta)

Só para os atributos que ficaram pendentes, e **sempre com procedência**: `atributo, valor, fonte, url, data_consulta, confianca`. Atributo enriquecido entra com flag distinta de atributo extraído — o briefing exige isso ("cada dado novo precisa dizer de onde veio").

Fontes: tabela oficial NCM (determinística, usar sempre), catálogos de fabricante para os part numbers (os **15 registros reais** do fim da base são a validação: `6205-2RSH/C3` → DI 25MM, DE 52MM, largura 15MM), normas (`DIN 931/933`, `DIN 985`, `SAE 100R1AT`, `EN 853 2SN`) e tabelas técnicas derivadas (DN↔POL, AWG↔mm², circunferência de correia).

Para a demo, **tabelas locais curadas valem mais que scraping ao vivo**: cabem no tempo, não quebram no palco e já cobrem os casos reais. Scraping/LLM-com-busca entra como extensão, se sobrar tempo.

---

## E7 — Fluxo de cadastro (os 520 pedidos)

Mesmo pipeline, com dois passos extras, e é aqui que mora o **produto** (saneamento é projeto, cadastro é operação contínua):

```
pedido (texto + anexo)
  ├─► E1 classifica  ──► sem classe PDM?  ──► RECUSADO · FORA DO PDM (ex.: cadeira de escritório)
  ├─► E2 extrai características (texto + CONTEUDO_ANEXO)
  ├─► E4 normaliza unidades/materiais  (psi→bar, 3/4"→3/4POL, inox 316→ACO INOX 316)
  ├─► E5 calcula chave de identidade
  │     ├─ chave já existe na base saneada ──► JA_EXISTE · USAR <código>   ◄── evita a próxima duplicata
  │     └─ não existe
  └─► obrigatórios completos?
        ├─ sim ──► APROVADO · cadastro no padrão + NCM + unidade + grupo (pronto para o ERP)
        └─ não ──► DEVOLVIDO · "falta CLASSE RESISTENCIA e ACABAMENTO"  ◄── com a lista exata
```

Os quatro estados — `APROVADO`, `JA_EXISTE`, `DEVOLVIDO`, `FORA_DO_PDM` — são o resultado mensurável: *"de 520 pedidos, X já existiam na base, Y foram cadastrados automaticamente, Z voltaram com pendência objetiva, W estão fora do padrão"*. Esse slide é o pitch.

---

## E8 — Evidência, métricas e interface

**Placar de saneamento (antes → depois), que é a resposta a "como provar que a base ficou melhor?":**

| Indicador | Antes (medido) | Depois |
|---|---|---|
| Descrição no formato PDM | 4.877 / 23.554 (21%) | ? |
| Unidade dentro do padrão da classe | 21.085 (89,5%) | ? |
| NCM no formato `0000.00.00` | 13.901 (59% do total; 62% dos preenchidos) | ? |
| NCM presente | 22.381 (95%) | ? |
| NCM aderente à regra da classe | — | ? |
| Atributos obrigatórios preenchidos | ~0% (não havia atributo) | ? |
| Códigos ativos redundantes | ≥1.271 identificados | ? |
| Itens com estoque e status não-ativo | 2.027 | ? |

**Validação da própria extração** (sem isso o número não vale nada): amostra de **150–200 registros estratificada por classe**, anotada à mão pelo time, medindo precisão/recall **por atributo**; e os 15 produtos reais como teste de ponta a ponta. Reportar erro também, não só acerto — banca técnica pergunta.

**Interface (Streamlit):** 5 telas.
1. **Diagnóstico** — os números acima, com os gráficos de problema por grupo.
2. **Antes/Depois de um registro** — descrição crua → tabela de atributos com evidência → descrição PDM.
3. **Clusters de duplicidade** — tabela lado a lado, atributos coincidentes destacados, sobrevivente escolhido com o motivo, valor do capital liberado. Incluir o caso `6205` (une) e o caso `1R-1808/P551808` (não une, registra equivalência).
4. **Fila de revisão humana** — tudo abaixo do limiar, com aprovar/corrigir. É o que responde "quando a decisão pode ser automática e quando precisa de alguém validando?".
5. **Simulador de pedido** — caixa de texto livre → os quatro estados. A tela que fecha a demo.

---

## Stack

| Camada | Escolha | Por quê |
|---|---|---|
| Dados | **DuckDB + Parquet** | 23k linhas e joins; roda local, zero infra, e o `duckdb-skills` já está disponível |
| Leitura xlsx | `uv run --with openpyxl` ou extensão `excel` do DuckDB | `pandas` não está instalado no ambiente |
| LLM | **Claude via Bedrock** — `us.anthropic.claude-haiku-4-5-20251001-v1:0` em volume, `us.anthropic.claude-sonnet-5` nos difíceis | IDs verificados na conta; structured output via tool use garante o schema |
| Embeddings | `sentence-transformers` multilíngue local, ou Titan/Cohere no Bedrock | blocking de duplicata e casamento de vocabulário; local evita custo e rate limit |
| Normalização | Python puro + YAML versionado | determinístico, testável, auditável |
| Testes | `pytest` nos normalizadores e na chave de identidade | é o que sustenta o "é reproduzível" na banca |
| UI | **Streamlit** | 5 telas em poucas horas |
| Cache | disco, chave `sha256(texto+classe+versão_prompt)` | reexecução custa zero |

```
vxwinners/
├── data/raw/           # os 3 xlsx (intocados)
├── data/warehouse.duckdb
├── pdm/                # schemas.json, vocab.json, ncm_rules.py, sinonimos/, abreviacoes.yaml
├── src/
│   ├── ingest.py           # E0
│   ├── classify.py         # E1  sujeito
│   ├── extract.py          # E2  características (LLM)
│   ├── tabulate.py         # E3  EAV → wide → descrição PDM
│   ├── normalize/          # E4  unidades, materiais, formatos  ← coração do projeto
│   ├── identity.py         # E5  chave, clusters, sobrevivente
│   ├── ncm.py              # E5.3
│   ├── enrich.py           # E6
│   └── intake.py           # E7  pedidos
├── tests/
├── app/                # Streamlit
└── docs/               # 01-dados.md, 02-plano-projeto.md, análise de negócio, pitch
```

---

## Sequência de execução

Ordem de dependência, com o critério de pronto de cada etapa:

| Ordem | Etapa | Pronto quando |
|---|---|---|
| 1 | E0 ingestão + compilação do PDM | 44 schemas gerados da planilha; `warehouse.duckdb` consultável |
| 2 | E1 classificação | ≥95% dos 23.554 com `id_pdm`; os sem classe isolados e contados |
| 3 | **E4 normalizadores** (antes da extração!) | testes passando para pressão, polegada, mm, mm², rosca, texto |
| 4 | E2 extração — **fatia vertical primeiro** | `FIX01` (4.516) + `VED01` (1.851) + `ROL01` (484) ponta a ponta, com métrica de acerto |
| 5 | E3 tabela + descrição PDM | `descricao_pdm` montada e validada contra as regras 1–9 |
| 6 | E5 identidade + dedup + NCM | caso `6205` unificando e caso `1R-1808` **não** unificando |
| 7 | E7 pedidos | 520 pedidos nos quatro estados |
| 8 | E2 nas classes restantes | base inteira processada |
| 9 | E8 UI + placar antes/depois | 5 telas navegáveis |
| 10 | E6 enriquecimento | validado nos 15 produtos reais |
| 11 | Análise de negócio + pitch | números saídos do pipeline, não estimados |

**Fatia vertical antes de largura.** Três grupos (`FIX01`+`VED01`+`ROL01` = 6.851 registros, 29% da base) atravessando as oito etapas valem muito mais que 44 classes classificadas e nada normalizado. `FIX01` é o padrão mais regular (cai em regex), `ROL01` contém o caso real de duplicidade do briefing e `VED01` aparece nos pedidos — os três cobrem a demo inteira. Depois é só repetir por classe.

Se o tempo apertar, o corte é nesta ordem: **E6 enriquecimento** sai primeiro (vira "próximos passos"), depois as classes difíceis de NCM (`PDM050`, `PDM051`), depois as classes de baixo volume (`SOL01`, `FER01`, `LUB01` = 610 registros). **E5 e E7 nunca saem** — são o valor demonstrável.

---

## Riscos e como cada um é contido

| Risco | Contenção |
|---|---|
| LLM inventa valor para atributo ausente | `enum` no structured output + `null` explícito + evidência obrigatória por atributo + pendência como saída legítima |
| 23.554 registros não caberem no tempo/custo | dedup de texto antes de chamar, regex nas classes regulares, cache em disco, prompt caching, lote por classe, fatia vertical primeiro |
| Dedup agressivo junta itens diferentes | identidade por **igualdade de chave**, não por similaridade; regra 13 implementada e **testada** nos dois casos reais; abaixo do limiar vai para humano |
| `JG`/`CX`/`CT`/`GL` convertidos sem fator corrompem estoque | não converter: fila de decisão com fator a confirmar, e dizer isso na banca |
| `3.650 psi` lido como 3,65 | normalizador de número com teste para ponto-milhar vs vírgula-decimal pt-BR |
| NCM condicional (`PDM050`/`PDM051`) consumir o dia | atacar por último; `PDM110` sai de graça do atributo de aplicação |
| Métrica de qualidade sem baseline | o placar antes/depois já está medido neste documento — está pronto desde o minuto zero |
| Demo quebrar ao vivo | tudo pré-computado em DuckDB; a UI só lê; o simulador de pedido é a única chamada ao vivo, com fallback em cache |

---

## Ajuste que vale fazer no plano original

O seu plano era: *extrair sujeito + características → tabela → normalizar unidades e materiais*. A espinha está certa e é a do PDM. Três refinamentos, por ordem de impacto:

1. **Classificar a classe PDM antes de extrair** (E1 antes de E2). As características a extrair dependem da classe — é o schema que torna a extração confiável em vez de campo livre.
2. **Normalizar em duas camadas**: no prompt (o `enum` já força o valor canônico, de graça) *e* depois, em código determinístico (que é o que você audita e reexecuta). Os normalizadores devem existir **antes** da extração em massa, para não ter de reprocessar 23k registros.
3. **A normalização não é o fim — ela é o que viabiliza a identidade.** Depois do E4, duplicidade deixa de ser um problema de NLP e vira comparação de chave. É esse encadeamento — *extrair → normalizar → a chave fecha* — que vira o pitch: `VALV ESF 2" AISI 316 NPT` e `VALVULA DE ESFERA DN 50 CORPO INOX 316 EXTREMIDADE NPT` colapsam na mesma chave porque `2POL ≡ DN 50` e `AISI 316 ≡ ACO INOX 316`, e nenhuma linha de LLM foi necessária para decidir isso.
