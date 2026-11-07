# Os dados do Desafio 01 — Cadastro e saneamento de materiais

Empresa fictícia: **Serra Azul Mineração e Energia**. Seis centros (plantas):

| Centro | Nome |
|---|---|
| 1100 | MINA SERRA AZUL |
| 1200 | USINA DE BENEFICIAMENTO |
| 1300 | TERMINAL PORTUARIO |
| 2100 | UTE SERRA AZUL |
| 2200 | PCH RIO CLARO |
| 9000 | CD CENTRAL |

Quatro artefatos foram entregues:

| Arquivo | O que é | Papel no projeto |
|---|---|---|
| `Hackathon_VX_Desafio01_Cadastro_e_Saneamento.pdf` | Briefing do desafio (6 páginas) | Define problema, escopo e entregáveis |
| `01_base_materiais.xlsx` | Base legada de materiais — **23.554 registros** | Entrada do **saneamento** |
| `02_pedidos_cadastro.xlsx` | **520 pedidos** de cadastro de item novo | Entrada do **cadastro** |
| `03_padrao_cadastro_PDM.xlsx` | O padrão descritivo de materiais (PDM) | **Especificação / ground truth** do que é "certo" |

> O PDM diz **o que é um cadastro correto. Ele não descreve como chegar lá.** Chegar lá é o projeto.

---

## 0. O briefing (PDF)

O problema tem três frentes, e cada time escolhe o ângulo:

1. **Saneamento** — corrigir a base que já existe: juntar duplicidades, padronizar descrições, acertar unidade, NCM e grupo. Um código continua ativo; os outros viram `BLOQUEADO · USAR <código>`.
2. **Cadastro** — padronizar o que está chegando: transformar pedido em texto livre / ficha técnica / catálogo num cadastro no padrão. Antes de criar, conferir se o item já existe; devolver o pedido quando falta informação.
3. **Enriquecimento** — completar o que falta a partir de fontes externas (catálogos de fabricante, normas, tabela NCM), **registrando a procedência de cada dado novo**.

Os quatro custos que a bagunça gera (e que a análise de negócio precisa quantificar):
**capital parado** (mesmo item estocado várias vezes), **compra fragmentada** (sem escala de negociação), **operação parada** (manutenção esperando peça que estava no almoxarifado) e **risco fiscal** (NCM errado).

Entregáveis: **MVP funcional demonstrado**, **análise de mercado e do problema**, **pitch de 5 minutos**.

Nota do briefing: *os últimos 15 registros da base de materiais são produtos reais* — servem para validar enriquecimento contra catálogo público. Fontes públicas são liberadas desde que a fonte de cada dado seja registrada.

---

## 1. `01_base_materiais.xlsx` — a base legada

Aba `BASE_MATERIAIS`, 23.554 linhas × 15 colunas (+ aba `DICIONARIO_CAMPOS`).

| Coluna | Tipo | Preenchimento | Observação |
|---|---|---|---|
| `CODIGO_MATERIAL` | texto 8 díg. | 100%, **sem duplicata de chave** | código no ERP |
| `DESCRICAO_CURTA` | texto ≤40 | 100% | truncado em 40 por limite de tela do ERP; cheio de abreviação |
| `DESCRICAO_LONGA` | texto 9–253 (média 92) | 100% | texto usado no pedido de compra; é **o campo-alvo do saneamento** |
| `UNIDADE_MEDIDA` | texto | 100%, **19 valores distintos** | padrão PDM só admite 5 |
| `NCM` | texto | **95%** (1.173 vazios) | 3 formatos diferentes conviver |
| `GRUPO_MERCADORIA` | código | 100%, 15 valores | bate com a aba `GRUPOS_MERCADORIA` do PDM |
| `FABRICANTE` | texto | **33,5%** (15.674 vazios), 90 valores | crítico: é parte da identidade nas classes de referência |
| `REFERENCIA_FABRICANTE` | part number | **21,5%** (18.488 vazios) | idem |
| `CENTRO` | texto | 100%, 6 plantas | mesma peça cadastrada em plantas diferentes = fonte de duplicata |
| `STATUS` | enum | 100% | `ATIVO` 20.014 / `BLOQUEADO` 2.331 / `OBSOLETO` 1.209 |
| `DATA_CRIACAO` | data | 100% | **2004-01-01 → 2026-09-30** (22 anos de deriva) |
| `USUARIO_CRIACAO` | texto anon. | 100%, 260 usuários | cada um cadastrou do seu jeito |
| `DATA_ULTIMA_MOVIMENTACAO` | data | 81,7% (4.306 vazios) | sem movimentação ≈ item morto |
| `ESTOQUE_ATUAL` | número | 100% | usado para dimensionar capital parado |
| `PRECO_MEDIO_UNITARIO` | número | 100% | idem |

### Distribuição por grupo de mercadoria

```
SOB01 SOBRESSALENTES        7.673   ████████████████████
FIX01 FIXADORES             4.516   ████████████
VED01 VEDACOES              1.851   █████
TUB01 TUBOS E CONEXOES      1.717   ████
MAN01 MANGUEIRAS/MANGOTES   1.545   ████
ELE01 MATERIAL ELETRICO     1.483   ████
VAL01 VALVULAS              1.342   ███
FIL01 FILTROS                 937   ██
EPI01 EPI                     609   █
ROL01 ROLAMENTOS/MANCAIS      484   █
TRA01 TRANSMISSAO MECANICA    456   █
INS01 INSTRUMENTACAO          331
FER01 FERRAMENTAS             250
SOL01 SOLDA E CORTE           195
LUB01 LUBRIFICANTES           165
```

### Problemas medidos na base (números reais, já apurados)

| Problema | Medição |
|---|---|
| Descrição **fora** do formato PDM (`SUBST; ATRIBUTO: VALOR;…`) | **18.677 de 23.554 (79%)** — só 4.877 têm `;` e `:` |
| **Unidade de medida** fora do padrão da classe | **2.469 registros**; variantes `UN`, `PÇ`, `PCA`, `CT`, `JG`, `CX`, `PAR`, `MTS`, `MT`, `BR`, `RL`, `LT`, `GL`, `BD` |
| **NCM fora do formato** `0000.00.00` | **8.480** (6.703 em `00000000`, 1.777 em `0000.0000`) |
| **NCM ausente** | **1.173** |
| **NCM divergente** do esperado para o grupo | **1.737** |
| **Duplicidade exata** de `DESCRICAO_LONGA` | **663** |
| **Clusters de duplicata provável** (mesmo saco de palavras, mesmo grupo) | **620 clusters / 1.271 códigos** — e isso é só o piso: não pega `2POL` ≡ `DN 50` nem `VALV ESF` ≡ `VALVULA ESFERA` |
| Itens `BLOQUEADO`/`OBSOLETO` **com estoque > 0** | **2.027** |
| Fabricante ausente em classes de referência | relevante nos 8.610 registros `SOB01`+`FIL01` |
| Acentos/cedilha remanescentes | 50 (texto já é 100% maiúsculo) |

### Abreviações mais frequentes na descrição curta

`PARAF` (3.940), `SEXT` (2.976), `HIDR` (2.224), `INT` (1.651), `MANG` (1.500), `DIAM` (1.400), `MONT` (1.072), `REF` (1.030), `APLIC` (948), `MOD` (838), `MAT` (526), `INOX` (474), `ROL` (441), `CAB` (379), `COMP` (346), `LUBR` (343), `FABR` (226), `EXT` (190).

Esse é o dicionário de expansão que o normalizador precisa ter.

### Os quatro "estilos" de descrição que convivem na base

```
1) Pseudo-PDM (com ; e :)   PARAFUSO SEXTAVADO INTERNO, C 120MM, BITOLA M-8, TIPO CABECA ABAULADA,...
2) Rótulo abreviado         PARAF CAB SEXTAVADA ALLEN - CILINDRICA - BITOLA:M14 - COMP:50MM - G...
3) Texto corrido            CONCAVO BRITADOR CONICO HP400 METSO MM0998461 ACO MANGANES
4) Telegráfico/cru          RET. 110MM 15MM BASL NBR
```

### Os últimos 15 registros (produtos reais)

São dois clusters de duplicidade **deliberados**, prontos para servir de caso de teste de ponta a ponta:

- **Rolamentos**: `6205-2RSH/C3 SKF`, `6205-C-2HRS-C3 FAG`, `6205DDUC3 NSK` (mesmo rolamento 6205 vedado, folga C3, três fabricantes) e `6310-2Z/C3 SKF`, `6310-C-2Z-C3 FAG`, `6310ZZC3 NTN`.
- **Filtros**: `LF9009`, `FLEETGUARD LF 9009`, `FLEETGUARD LF3970`, `1R1808 CAT`, `CATERPILLAR 1R-1808`, `P551808 DONALDSON`, `B40142 BALDWIN`, `DBL7300`, `LF691A FLEETGUARD`.

**Cuidado — pegadinha do PDM (regra 13):** nos rolamentos (classe de *especificação técnica*) `SKF 6205-2RSH/C3` e `FAG 6205-C-2HRS-C3` **são o mesmo item** e devem ser unificados. Nos filtros (classe de *referência do fabricante*) `CAT 1R-1808` e `DONALDSON P551808` são **intercambiáveis mas itens distintos**: a equivalência deve ser *registrada*, nunca usada para juntar códigos. Um algoritmo de similaridade ingênuo erra exatamente aqui.

---

## 2. `02_pedidos_cadastro.xlsx` — os pedidos de item novo

Aba `PEDIDOS`, 520 linhas × 9 colunas (+ `DICIONARIO_CAMPOS`).

| Coluna | Conteúdo |
|---|---|
| `ID_PEDIDO` | `SC-2026000NN` |
| `DATA_SOLICITACAO` | 2026 |
| `CENTRO` | 1100 (161), 1200 (125), 9000 (72), 2100 (65), 1300 (56), 2200 (41) |
| `AREA_SOLICITANTE` | ALMOXARIFADO (132), PCM (112), MANUTENCAO MECANICA (71), PRODUCAO (58), SUPRIMENTOS (52), UTILIDADES (48), + 6 áreas menores |
| `CANAL` | PORTAL (279), EMAIL (156), PLANILHA (85) |
| `URGENCIA` | NORMAL (364), ALTA (115), EMERGENCIAL (41) |
| `TEXTO_SOLICITACAO` | texto livre, 25–332 caracteres (média 102) |
| `TIPO_ANEXO` | vazio (384), FICHA TECNICA (107), CATALOGO FORNECEDOR (29) |
| `CONTEUDO_ANEXO` | o anexo transcrito em texto — **136 pedidos têm anexo** |

### Os formatos de entrada que o extrator tem de aguentar

**a) Frase corrida, minúscula, com acento, com abreviação e com ruído de uso final:**
```
favor cadastrar bucha excentrico britador conico RAPTOR 450 flsmidth 1
precisamos de retentor 75 mm 100 mm 13 mm ba nbr pra bomba da barragem
Favor cadastrar porca autotravante metrica grossa m27 a2-70 aco inox 304 natural din 985 para reposição de estoque
```

**b) E-mail com saudação, bullets e assinatura (o atributo vem rotulado):**
```
Bom dia,

Peço por favor cadastrar mangueira hidráulica montada, com as seguintes características:
- Norma: EN 853 2SN
- Diâmetro interno: 3/4" (19 mm)
- Pressão de trabalho: 215BAR
- Comprimento: 2000 mm
- Terminal a: FEMEA CURVA 90 GRAUS JIC
- Terminal b: MACHO RETO NPT
- Material terminais: aco carbono zincado

Obrigado,
Thiago
```

**c) Texto que só aponta para o anexo** (`"Segue ficha técnica em anexo."`) — a informação está em `CONTEUDO_ANEXO`:
```
FICHA TÉCNICA
Produto: Retentor
Diametro eixo: 60 mm
Diametro alojamento: 80 mm
Largura: 15mm
Tipo: ba
Fabricante: FREUDENBERG
```

**d) Catálogo de fornecedor, em inglês, em uma linha:**
```
Generic | Ball valve | 1POL, 150#, A216 WCB, RF flanged, reduced bore, metal-metal, lever
```

### Armadilhas plantadas nos pedidos

- **Unidade misturada na mesma frase**: `3/4" (19 mm)`, `1/2 pol`, `3.650 psi`, `6.000 psi`, `215BAR` — o PDM exige **BAR** para pressão e fração+`POL` para polegada. Converter psi→bar e normalizar a notação é obrigatório.
- **Notação compacta a separar**: `M12X50` → `BITOLA: M12` + `COMPRIMENTO: 50MM`; e quando o passo não aparece, a rosca é **métrica grossa** (regra 2 do PDM).
- **Pedido fora do escopo do PDM**: `"Cadeira de escritório giratória com braço, para a sala de controle"` — não existe classe para isso. O pipeline tem de **recusar/encaminhar**, não inventar classe.
- **Pedido com informação faltando** — tem de voltar ao solicitante com a lista exata do que falta (caso `PARAFUSO ... M12X50` sem classe de resistência, do briefing).
- **Pedido que na verdade já existe na base** — tem de cair no detector de duplicata *antes* de criar código.
- Milhar com ponto (`3.650`, `6.000`) e decimal com vírgula convivendo: `6.000 psi` é seis mil, não seis.

---

## 3. `03_padrao_cadastro_PDM.xlsx` — a especificação

Oito abas. É o contrato que o MVP tem de cumprir, e é **executável**: dá para transformar quase tudo aqui em validador.

### `REGRAS_GERAIS` (13 regras) — as que mais importam

| # | Regra | Consequência de engenharia |
|---|---|---|
| 1–2 | Descrição = `SUBSTANTIVO QUALIFICADOR; ATRIBUTO: VALOR; ATRIBUTO: VALOR; …`, atributos **na ordem da aba ATRIBUTOS** | o "sujeito + características" do seu plano já é a estrutura oficial |
| 2 | `M12X50` = `BITOLA M12` + `COMPRIMENTO 50MM`; passo ausente ⇒ métrica grossa | regra de desmembramento determinística |
| 3 | Maiúsculas, **sem acento e sem cedilha** | normalização de texto trivial, mas obrigatória |
| 4 | Sem abreviação; valores de lista **exatamente** um dos permitidos | casamento contra vocabulário controlado, não texto livre |
| 5 | Polegada: fração + `POL`, inteiro separado por **ponto** (`1/2POL`, `1.1/4POL`). Milímetro: número + `MM`, decimal com **vírgula** (`16,25MM`) | formatador dedicado por tipo de grandeza |
| 6 | Pressão sempre em **BAR**; mangueira montada em **MM**; cabo em **MM2** | tabela de conversão psi/MPa/kgf→bar |
| 7 | Obrigatórios sempre preenchidos; condicionais conforme `QUANDO_SE_APLICA`; opcionais quando conhecidos | validação condicional por classe |
| 8 | Classes de **especificação técnica**: fabricante/referência **fora** da descrição | atenção: a base legada hoje viola isso |
| 9 | Classes de **referência do fabricante** (filtros, sobressalentes): fabricante + referência **dentro** da descrição | dois modelos de identidade distintos |
| 10 | **Identidade**: mesma classe + mesmos valores nos obrigatórios; ou, nas classes de referência, mesmo fabricante + mesma referência. **Um único código ativo por item** | define a chave de deduplicação — não é similaridade de texto, é igualdade de chave |
| 11 | Unidade conforme `UNIDADE_PADRAO` da classe | mapa 19 variantes → 5 unidades |
| 12 | NCM 8 dígitos `0000.00.00`, existente e vigente na tabela oficial (Portal Único Siscomex, módulo Classif) | formatação + validação contra tabela externa |
| 13 | **Equivalência não é duplicidade** | filtros intercambiáveis permanecem itens distintos |

### `CLASSES` — 44 classes

`ID_PDM` (PDM001…PDM110), `SUBSTANTIVO`, `QUALIFICADOR`, `GRUPO_MERCADORIA`, `UNIDADE_PADRAO`, `NCM`, `CRITERIO_IDENTIDADE`.

Exemplos: `PDM001 PARAFUSO SEXTAVADO / FIX01 / PC / 7318.15.00`, `PDM040 VALVULA ESFERA / VAL01 / PC / 8481.80.95`, `PDM032 RETENTOR / VED01 / PC / 4016.93.00`.

Três classes são "guarda-chuva" e exigem tratamento especial:

| Classe | Substantivo | Como resolve |
|---|---|---|
| `PDM050` | *(ver aba `SUBSTANTIVOS_CONEXOES`)* | 11 substantivos: BUCHA REDUCAO, CAP, COTOVELO 45/90 GRAUS, FLANGE, LUVA, LUVA REDUCAO, NIPLE, TE, TE REDUCAO, UNIAO |
| `PDM100` | `FILTRO AR \| COMBUSTIVEL \| HIDRAULICO \| OLEO LUBRIFICANTE \| SEPARADOR AR/OLEO` | identidade = **FABRICANTE + PART NUMBER** |
| `PDM110` | *(ver aba `SUBSTANTIVOS_SOBRESSALENTES`)* | **62 substantivos** (ANEL DESGASTE, BUCHA EXCENTRICO, …); identidade = **FABRICANTE + PART NUMBER** |

**Dois critérios de identidade** (coluna `CRITERIO_IDENTIDADE`):
- `ESPECIFICACAO TECNICA (ATRIBUTOS OBRIGATORIOS)` — 42 classes
- `REFERENCIA DO FABRICANTE (FABRICANTE + PART NUMBER)` — `PDM100` (filtros, 937 itens) e `PDM110` (sobressalentes, 7.673 itens) = **37% da base**

### `ATRIBUTOS` — 229 linhas, 44 classes

`ID_PDM`, `ORDEM`, `ATRIBUTO`, `OBRIGATORIO` (195 `S` / 34 `N`), `QUANDO_SE_APLICA`, `FORMATO`, `VALORES_PERMITIDOS`.

**É o schema de extração, pronto.** Média de ~5 atributos por classe. 210 atributos valem `sempre`; 19 são condicionais, com regras em linguagem natural que precisam virar código:

```
"somente FLANGE"                                   "somente cabos de 1 condutor"
"somente MINIDISJUNTOR DIN e CAIXA MOLDADA"        "somente disjuntor MOTOR"
"somente TE REDUCAO, LUVA REDUCAO e BUCHA REDUCAO" "somente terminais de OLHAL e FORQUILHA"
"todas, exceto conexões para solda de topo (BW)"   "quando informado pelo fabricante"
```

Exemplo de schema completo — `PDM040 VALVULA ESFERA`:

| Ordem | Atributo | Obrig. | Formato / valores |
|---|---|---|---|
| 1 | DIAMETRO NOMINAL | S | fração + POL (`1.1/4POL`) |
| 2 | CLASSE PRESSAO | S | `150# \| 300# \| 600# \| 800# \| PN 16 \| PN 25` |
| 3 | MATERIAL CORPO | S | `ACO CARBONO FORJADO A105 \| ACO CARBONO FUNDIDO A216 WCB \| ACO INOX FORJADO A182 F316 \| ACO INOX FUNDIDO A351 CF8M \| …` |
| 4 | CONEXAO | S | `FLANGE FF \| FLANGE RF \| ROSCA BSP \| ROSCA NPT \| SOLDA ENCAIXE SW \| SOLDA TOPO BW` |
| 5 | PASSAGEM | S | `PLENA \| REDUZIDA` |
| 6 | VEDACAO SEDE | S | `METAL-METAL \| PTFE \| RPTFE` |
| 7 | ACIONAMENTO | S | `ALAVANCA \| ATUADOR PNEUMATICO \| REDUTOR` |

E `PDM100 FILTRO` (note o inverso: fabricante/referência obrigatórios, dimensões opcionais):

| Ordem | Atributo | Obrig. | Observação |
|---|---|---|---|
| 1 | APLICACAO | N | lista (CAMINHAO FORA DE ESTRADA, COMPRESSOR, …) |
| 2 | FABRICANTE | **S** | lista de 9 fabricantes |
| 3 | REFERENCIA FABRICANTE | **S** | part number como o fabricante informa |
| 4–6 | ALTURA, DIAMETRO EXTERNO, ROSCA | N | *"quando informado pelo fabricante"* → alvo do enriquecimento |

### `GRUPOS_MERCADORIA` — 15 grupos
`FIX01` FIXADORES · `MAN01` MANGUEIRAS E MANGOTES · `ROL01` ROLAMENTOS E MANCAIS · `VED01` VEDACOES · `TRA01` TRANSMISSAO MECANICA · `VAL01` VALVULAS · `TUB01` TUBOS E CONEXOES · `ELE01` MATERIAL ELETRICO · `INS01` INSTRUMENTACAO · `EPI01` EPI · `SOL01` SOLDA E CORTE · `FER01` FERRAMENTAS · `LUB01` LUBRIFICANTES · `FIL01` FILTROS · `SOB01` SOBRESSALENTES

### `UNIDADES` — só 5 valores válidos
`PC` Peça · `M` Metro · `PR` Par · `KG` Quilograma · `L` Litro

Contra as **19** que existem na base. O mapa a construir: `UN|PÇ|PCA|CT|JG|CX|BD|RL|BR → PC` (com cuidado: `JG`=jogo e `CX`=caixa são *embalagem*, não unidade básica — exigem decisão de negócio), `PAR → PR`, `MTS|MT → M`, `LT|GL → L`.

### `NCM_REFERENCIA` — 59 linhas

Para 31 classes o NCM é `único para a classe`. Para as outras, **o NCM depende de um atributo** — é regra condicional em linguagem natural que precisa virar árvore de decisão:

```
PDM012 mangueira industrial  PVC=3917.39.00; borracha c/ lonas têxteis=4009.31.00; c/ espiral de aço=4009.41.00
PDM030 correia trapezoidal   circunf. ≤60cm ou >240cm=4010.39.00; >60 a 180cm=4010.32.00; >180 a 240cm=4010.34.00
PDM034 junta plana           PTFE=3926.90.90; borracha (EPDM, NBR)=4016.93.00
PDM071 calçado segurança     biqueira aço=6403.40.00; biqueira composite=6403.99.90
PDM081 disco abrasivo        corte e desbaste=6804.22.11; flap=6805.10.00
PDM100 filtro                óleo/combustível=8421.23.00; ar=8421.31.00; hidráulico=8421.29.90; separador=8421.39.90
PDM110 sobressalente         segue o EQUIPAMENTO DE APLICAÇÃO (13 regras) + exceções por substantivo
                             (PASTILHA FREIO=8708.30.11, DISCO FREIO=8708.30.90)
```

`PDM050` (conexões, 9 NCMs possíveis) e `PDM051` (tubo aço, 5 NCMs) dependem de material + tipo + forma de ligação — são as mais difíceis.

### `SUBSTANTIVOS_SOBRESSALENTES` (62) e `SUBSTANTIVOS_CONEXOES` (11)
Vocabulário fechado para as classes guarda-chuva. `SOB01` concentra 7.673 registros (33% da base) e usa essa lista.

---

## 4. Como os três arquivos se encaixam

```
03_padrao_cadastro_PDM.xlsx  ──►  SCHEMA + VOCABULÁRIO + REGRAS
          │                        (classes, atributos, listas de valores,
          │                         unidades, NCM, critério de identidade)
          │
          ├──────────────► aplicado em ──► 01_base_materiais.xlsx   (SANEAMENTO)
          │                                 23.554 linhas sujas
          │                                 → descrição padronizada
          │                                 → duplicatas unificadas
          │                                 → unidade/NCM/grupo corrigidos
          │
          └──────────────► aplicado em ──► 02_pedidos_cadastro.xlsx (CADASTRO)
                                            520 pedidos em texto livre
                                            → confere se já existe na base saneada
                                            → cria no padrão, ou devolve o que falta
```

As **chaves de junção** disponíveis: `GRUPO_MERCADORIA` (base ↔ PDM), `CENTRO` (base ↔ pedidos), `ID_PDM` (PDM interno), `NCM` (base ↔ `NCM_REFERENCIA`). O que **não** existe é a ligação `CODIGO_MATERIAL → ID_PDM`: **classificar cada um dos 23.554 registros numa das 44 classes é o primeiro trabalho do projeto.**

---

## 5. O que esses dados permitem provar (para o pitch)

Tudo abaixo sai dos próprios dados, sem premissa inventada:

| Métrica de negócio | Como calcular |
|---|---|
| **Capital parado em duplicidade** | Σ `ESTOQUE_ATUAL × PRECO_MEDIO_UNITARIO` dos códigos redundantes de cada cluster (o estoque do cluster deveria estar num código só) |
| **Estoque travado** | 2.027 itens `BLOQUEADO`/`OBSOLETO` com estoque > 0, valorizados |
| **Compra fragmentada** | nº de clusters com códigos em ≥2 `CENTRO` distintos → volume que poderia ser negociado junto |
| **Dispersão de preço do mesmo item** | desvio de `PRECO_MEDIO_UNITARIO` dentro do cluster: a diferença entre o maior e o menor preço do mesmo item é economia direta |
| **Exposição fiscal** | 1.173 sem NCM + 1.737 com NCM divergente, ponderados por valor movimentado |
| **Risco de parada** | itens com estoque > 0 num código, zero no código "espelho" e sem movimentação recente |
| **Custo de cadastro** | 520 pedidos / período, 136 com anexo a ler à mão; tempo médio de cadastro manual × volume |

---

## 6. Observações de engenharia

- `xlsx` sem `pandas` instalado no ambiente: usar `uv run --with openpyxl` (ou `duckdb` com a extensão `excel`). Converter os três arquivos para **Parquet/DuckDB** na ingestão e nunca mais reler Excel.
- `NCM`, `CODIGO_MATERIAL` e `ESTOQUE_ATUAL` chegam como **texto** — forçar tipo na ingestão (`NCM` deve permanecer string, com zeros à esquerda preservados).
- `CONTEUDO_ANEXO` tem `\n` embutido: multi-linha dentro da célula.
- 23.554 linhas × ~5 atributos é escala para rodar LLM na base **inteira**, desde que haja cache e um caminho determinístico para os casos fáceis.
- LLM: o repositório não traz `claude-bedrock.sh` nem `.env`. As credenciais AWS ficam em um `.env` local, fora do git (modelo em `backend/.env.example`). Em 2026-11-07 a conta só permitia Haiku 4.5, Sonnet 4.6/5 e Opus 4.6 a 5 no Bedrock; ver `docs/04-plano-modo-cadastro.md`, seção 0.
