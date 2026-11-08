# Conjunto-ouro das características técnicas, da classe e da junção

Este gabarito mede o que o pipeline mais produz e o que o `gold.csv` antigo não
cobria: os **atributos técnicos** de cada item, a **classe (ID_PDM)** e a
**junção de duplicados**. Ele é a régua; não é a saída do pipeline reorganizada.

| arquivo | conteúdo |
|---|---|
| `10_candidatos_caracteristicas.py` | seleção reproduzível (semente 20251107) dos 240 itens e dos 150 pares |
| `candidatos_caracteristicas.csv` | os 240 itens com linha crua + família prevista, estilo e armadilhas |
| `pares_juncao_candidatos.csv` | os 150 pares com `fonte_par` (só para o avaliador) |
| `pares_juncao_cego.csv` | os mesmos pares às cegas (só o texto cru dos dois códigos) |
| `anotacoes_carac_A.jsonl` / `anotacoes_carac_B.jsonl` | 1 521 rótulos por anotador |
| `11_adjudicar_caracteristicas.py` | adjudicação, com uma decisão escrita por divergência |
| `gold_caracteristicas.csv` | 1 131 rótulos (item × atributo obrigatório aplicável) |
| `gold_classe.csv` | 240 rótulos de classe |
| `gold_juncao.csv` | 150 rótulos de par |
| `concordancia_caracteristicas.json` | acordo bruto e kappa de Cohen por atributo e global |
| `revisao_humana_caracteristicas.csv` | 198 linhas para a conferência de uma pessoa do time |
| `evaluate_caracteristicas.py` | avalia o pipeline e gera `resultado_caracteristicas.md` |

## 1. Independência do pipeline

Na seleção e na anotação das partes A (características) e B (classe) foram
usados **apenas** `dados/01_base_materiais.xlsx` (texto cru, mais as colunas de
cadastro da própria base) e `dados/03_padrao_cadastro_PDM.xlsx` (classes,
atributos, QUANDO_SE_APLICA, valores permitidos, formatos, regras gerais).
Nada de `artefatos/`, nada de `src/saneamento/`, nada de `scripts/`, nada de
`docs/07`–`docs/11`, nenhuma chamada de LLM externa.

A única exceção autorizada é a parte C: `artefatos/saneado_base.csv` foi lido
**só para sortear os pares** (mesma chave de identidade, diferença em um
atributo, descrição parecida). O rótulo do par foi dado sobre
`pares_juncao_cego.csv`, que traz apenas o texto cru dos dois códigos, em ordem
sorteada, sem chave, sem cluster e sem a fonte do par.

## 2. Método

1. **Seleção** (`10_candidatos_caracteristicas.py`): semente fixa, estratos
   aplicados em ordem (fora do PDM → classes irmãs → armadilhas → grupo de
   mercadoria errado → cotas por família × estilo). A coluna
   `familia_prevista` é só um palpite de regex usado para estratificar; a
   classe verdadeira de cada item é o rótulo `_CLASSE`.
2. **Anotação A**: uma passada na ordem `ordem_A`.
3. **Anotação B**: outra passada, na ordem `ordem_B` (permutação diferente),
   sem reabrir o arquivo de A.
4. **Adjudicação** (`11_adjudicar_caracteristicas.py`): o script alinha por
   (código, campo), calcula acordo e kappa, lista as divergências e **aborta**
   se alguma não tiver decisão escrita no dicionário `ADJUDICACOES`. Ele
   também confere automaticamente que todo atributo anotado é obrigatório na
   classe que o próprio anotador deu ao item — é o que garante o respeito ao
   QUANDO_SE_APLICA.

### Unidade de anotação e status

Um rótulo por (item × atributo obrigatório que se aplica ao item, segundo o
PDM), mais um rótulo de classe por item e um de junção por par.

| status | quando | o que o pipeline deveria fazer |
|---|---|---|
| `DEFINIDO` | o texto traz o valor sem ambiguidade | preencher com esse valor |
| `AUSENTE` | o texto não traz o valor | deixar vazio; preencher é invenção |
| `INDEFINIVEL` | o texto traz algo que não decide entre dois valores do PDM | não preencher; preencher é invenção |

Valores no formato canônico do PDM: valor de lista exatamente como a lista
escreve; milímetro com vírgula decimal e sem zero inútil (`16,25MM`, `35MM`);
polegada em fração com inteiro separado por ponto (`1/2POL`, `1.1/4POL`);
pressão sempre em BAR, com a unidade original registrada em `evidencia` e a
conta em `justificativa` (`41 KGF/CM2 x 0,980665 = 40,2 BAR`); seção de cabo em
`MM2`; barra roscada em metro (`1M`).

## 3. Tamanhos e estratos

**240 itens**, 1 131 rótulos de atributo (73 atributos distintos), 36 valores de
classe (35 classes do PDM + `FORA_DO_PDM`), 150 pares.

Status no gold de características: `DEFINIDO` 1 047 (92,6%), `AUSENTE` 54
(4,8%), `INDEFINIVEL` 30 (2,7%) — **84 rótulos** que medem invenção (mínimo
pedido: 60).

### Família prevista × estilo de texto (itens)

| família | estruturado | telegráfico |
|---|---|---|
| fixadores | 16 | 20 |
| vedação | 15 | 13 |
| rolamentos | 8 | 12 |
| válvulas | 16 | 12 |
| conexões | 19 | 9 |
| elétricos | 18 | 10 |
| mangueiras | 17 | 11 |
| sobressalentes | 15 | 9 |
| outras | 13 | 7 |

### Estratos de seleção

13 estratos de armadilha com 9 itens cada; 16 estratos de classes irmãs com 4
itens cada (válvula esfera/gaveta/globo/retenção/borboleta, rolamento
rígido/autocompensador/cônico, parafuso sextavado/sextavado interno, arruela
lisa/pressão, mangueira avulsa/montada, junta espiralada/plana); 10 itens candidatos a ficar
fora do PDM (8 `TAMPAO`, que não está em SUBSTANTIVOS_CONEXOES e por isso o gold
rotula `FORA_DO_PDM`, e 2 `CAIXA MANCAL`, que o gold rotula `PDM023` porque o
texto traz o único TIPO da classe);
10 itens com grupo de mercadoria incompatível; o resto completa as cotas por
família e estilo.

### Cobertura das armadilhas (itens, contando sobreposição)

| armadilha | itens | armadilha | itens |
|---|---|---|---|
| vírgula decimal em valor rotulado | 26 | `PN` ambíguo (pressão × part number) | 10 |
| polegada com aspas | 37 | classe de pressão com `#` | 83 |
| polegada com `IN` | 22 | unidade que exige conversão (PSI, KGF/CM2) | 11 |
| fração mista (`1 1/4"`, `1-3/4"`) | 16 | abreviação ambígua (`VALV RET`, `RET`, `S/ACAB`) | 16 |
| rosca métrica fina (`M12X1,5`) | 9 | ordem de grandezas sem rótulo | 9 |
| bitola + comprimento (`M12X50`, `M16X1M`) | 12 | descrição curta truncada em 40 caracteres | 151 |
| valor indefinível (`INOX`, `ZINCADO`) | 40 | grupo de mercadoria errado na coluna | 44 |

`curta_truncada` e `classe_pressao_hash` são sinalizadores largos (qualquer
descrição curta de 40 caracteres cujo último token continua na longa; qualquer
`150#`), por isso pegam muitos itens e seus números ficam próximos da média
geral. As armadilhas estreitas são as que discriminam.

### Pares de junção

70 com a mesma `CHAVE_IDENTIDADE` do pipeline, 50 que diferem em exatamente um
atributo obrigatório, 30 com descrição parecida por palavras e chaves
diferentes. Rótulos do gold: `ITENS_DIFERENTES` 73, `MESMO_ITEM` 67,
`INDETERMINADO` 10.

## 4. Concordância A × B

| recorte | n | acordo bruto | kappa de Cohen |
|---|---|---|---|
| características | 1 131 | 0,9903 | 0,9902 |
| classe | 240 | 1,0000 | 1,0000 |
| junção | 150 | 0,9867 | 0,9762 |
| global | 1 521 | 0,9915 | 0,9914 |

Atributos com kappa abaixo de 1: MATERIAL (0,921), FOLGA (0,865), APLICACAO
(0,915), DIAMETRO INTERNO (0,955), ACABAMENTO (0,969). **13 divergências**
foram adjudicadas uma por uma, com justificativa escrita em
`11_adjudicar_caracteristicas.py` e repetida em `concordancia_caracteristicas.json`.

Quase toda divergência é do mesmo tipo: um anotador deduziu o valor de outro
atributo e o outro marcou `INDEFINIVEL`. Para decidir, o adjudicador fixou seis
regras, que valem para todo o gold:

| regra | conteúdo |
|---|---|
| R1 | material sem nenhuma palavra de material no texto → `AUSENTE` (deduzir da classe de resistência é extrapolação) |
| R2 | material com palavra genérica (`ACO`, `ACO ESPECIAL`, `INOX`) → desambigua pela lista do PDM e pelos outros atributos, quando sobra um único valor possível |
| R3 | no PDM050, `ACO INOX A403 WP316` e `ACO CARBONO A234 WPB` são conexões de solda de topo (usam SCHEDULE, norma B16.9); item com CLASSE PRESSAO, rosca, solda de encaixe, flange ou B16.11/B16.5 é forjado (`A182 F316`, `A105`) |
| R4 | no vocabulário do PDM, `ZINCADO` é eletrolítico e `GALVANIZADO A FOGO` é imersão a quente; texto com "GALVANIZADO" → `GALVANIZADO A FOGO` |
| R5 | a folga do rolamento está no sufixo da referência; referência sem `/C3` é folga `NORMAL` |
| R6 | part number vale no formato do fabricante (a pontuação da coluna `REFERENCIA_FABRICANTE`); `REV A` é revisão, não part number. A comparação ignora pontuação, então `529-26-87581` e `5292687581` são o mesmo rótulo |

Uma divergência (item 27810757, `REFERENCIA FABRICANTE`) desaparece por R6: os
dois anotadores escreveram o mesmo código com pontuação diferente. O gold
guarda a grafia do fabricante.

## 5. Primeira execução sobre os artefatos atuais

`resultado_caracteristicas.md`, gerado de `artefatos/decisoes_base.jsonl` e
`artefatos/saneado_base.csv`:

| métrica | valor |
|---|---|
| precisão das características | 97,5% [96–98] (945 acertos, 24 erros) |
| cobertura | 92,6% (78 rótulos DEFINIDO deixados vazios) |
| taxa de invenção | 19/84 = 23% |
| acerto de classe | 218/240 = 90,8% [87–94] |
| junção | precisão 98,5% (65/66), recall 97,0% (65/67) |

Números da execução sobre os artefatos de 2026-11-07 23:25. Eles mudam a cada
rodada do pipeline (uma rodada anterior na mesma noite dava 947 acertos e
cobertura de 92,7%, antes da fonte `llm_deteccao` aparecer); regere o `.md`
depois de reexecutar o pipeline.

O recorte por fonte é o que diz qual camada erra: `acordo` (548 rótulos) tem
99,8% de precisão e zero invenção; `aprendido` (70 rótulos) tem 76,4% de
precisão e **as 15 invenções**; `ordem_pdm` errou os 3 rótulos em que apareceu;
`bert` 75% em 12 rótulos. As invenções se concentram em `CONEXAO` de válvula
(`FLANGES` → o dicionário aprendido escolhe FF ou RF) e em `TERMINAL A/B` de
mangueira (`FEMEA DKO` → escolhe reta ou curva).

Outros achados que o gabarito isola: `TAMPAO` é mapeado para `CAP` (PDM050) nos
8 itens que o gold marca `FORA_DO_PDM`; `41KGF/CM2` sai como `41BAR` (sem a
conversão, erro de 2%); a referência de rolamento perde o sufixo de vedação e
folga (`6010-2RS/C3` → `6010`); `DN 25`, `DN 50` e o dash `-20` de mangueira não
são convertidos para polegada.

## 6. Limitações

1. **As duas anotações saíram do mesmo modelo.** A e B foram feitas por mim
   (Claude), em passadas separadas, com ordens diferentes e sem reabrir a saída
   da outra, mas não são anotadores independentes de verdade: o viés de
   interpretação é compartilhado. O kappa de 0,99 mede consistência interna, não
   confiabilidade entre humanos. É por isso que a conferência humana (§7) faz
   parte do entregável, e não é opcional.
2. Os primeiros 60 itens de `ordem_B` foram anotados em uma sessão anterior e
   são mais conservadores com `INDEFINIVEL` (foi de lá que saiu quase toda a
   divergência de `MATERIAL`). A adjudicação uniformizou o critério pelas
   regras R1–R6, mas o gold herda o fato de que o critério foi fixado **depois**
   de ver as duas anotações.
3. **A amostra não é aleatória.** Ela é estratificada para concentrar
   armadilhas e classes irmãs, então as taxas do `resultado_caracteristicas.md`
   não são estimativas da base inteira: são o desempenho nos casos difíceis.
   Para uma taxa populacional seria preciso uma amostra aleatória simples.
4. **35 das 44 classes do PDM** aparecem no gold. Ficaram de fora sobretudo
   classes de baixa frequência na base (EPI, consumíveis de solda, óleo em
   parte). Atributos com 1 a 3 rótulos têm IC inútil e estão no relatório só
   para rastreio.
5. **O recall da junção é otimista.** Dois terços dos pares vieram de grupos
   que o próprio pipeline já havia juntado (`mesma_chave`), porque é a única
   forma de encontrar candidatos sem reimplementar a busca. Pares de duplicados
   que o pipeline nunca aproximou têm baixa chance de entrar na amostra. O
   estrato `texto_parecido` (30 pares) é o que tenta medir isso.
6. `INDEFINIVEL` depende da leitura do PDM: R3 e R4 são defensáveis, mas são
   decisões de engenharia, não fatos do texto. Estão marcadas com
   `confianca=MEDIA` no gold e todas vão para a planilha de revisão.
7. O gold compara uma única execução dos artefatos. Reexecutar o pipeline muda
   `artefatos/` e o `.md` precisa ser regerado.

## 7. Conferência humana

`revisao_humana_caracteristicas.csv` tem **198 linhas**:

- 51 obrigatórias: todos os rótulos `INDEFINIVEL` e todas as divergências
  adjudicadas (características, classe e junção);
- 147 de amostra aleatória (10% do resto, semente 20251107).

Cada linha traz o texto cru (ou os dois textos, no caso de par), o rótulo do
gold, a evidência, a justificativa, o que A e B anotaram, e três colunas vazias
para a pessoa preencher: `concordo_discordo`, `valor_certo`, `status_certo`
(mais `comentario`).

**Tempo estimado.** Cada linha exige ler o texto do item e a lista de valores do
atributo no PDM: 1,5 a 3 minutos por linha para quem conhece a base, ou seja
**5 a 10 horas** para as 198 linhas (um dia de trabalho de um especialista).
Conferir os 1 521 rótulos seria outra ordem de grandeza: lendo por item (240
itens × ~5 rótulos, 4 a 6 minutos por item) mais os 150 pares (~1,5 minuto
cada), dá **cerca de 25 horas**, três dias de trabalho.

Quando a planilha voltar, salve-a como
`revisao_humana_caracteristicas_respondida.csv` em `avaliacao/` e rode de novo
o adjudicador: ele lê as linhas marcadas `DISCORDO`, aplica `valor_certo` e
`status_certo`, marca essas linhas com `origem_decisao=revisao_humana` e regera
`gold_caracteristicas.csv`, `gold_classe.csv` e `gold_juncao.csv`.

## 8. Como rodar

O `.venv` do projeto não tem pandas; use `uv`:

```bash
# 1) seleção (só se quiser regerar os candidatos; muda a amostra se a base mudar)
uv run --no-project --with pandas --with openpyxl python avaliacao/10_candidatos_caracteristicas.py

# 2) adjudicação: gera o gold, a concordância e a planilha de revisão
uv run --no-project --with pandas --with openpyxl python avaliacao/11_adjudicar_caracteristicas.py

# 3) avaliação do pipeline sobre os artefatos atuais
uv run --no-project --with pandas --with openpyxl python avaliacao/evaluate_caracteristicas.py \
    --saida avaliacao/resultado_caracteristicas.md
```
