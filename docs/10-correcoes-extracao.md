# Correções na extração das características

Data: 2026-11-07. Origem: revisão dos pontos fracos da tabela de características
(depois de `docs/09-pipeline-correto.md`). Cada correção tem teste de regressão
e foi medida na base inteira contra o código anterior.

Arquivos: `texto.py`, `rotulos.py`, `regras.py`, `validador.py`, `arbitro.py`,
`pipeline.py`. Testes: `tests/test_texto.py`, `tests/test_pipeline.py`
(407 passando).

## 1. Resultado

Linha de base: commit `106cd19` mais a correção do `P/N` (`docs/07`). As duas
execuções partem do mesmo `aprendizado.json`, sobre os 23.554 registros.

### Só regras (`--sem-bert --sem-llm`)

| Indicador | Antes | Depois | Δ |
|---|---|---|---|
| SANEADO | 12.922 | **14.177** | **+1.255** |
| PENDENTE | 10.214 | 9.071 | −1.143 |
| REVISAO_HUMANA | 381 | 269 | −112 |
| Chaves fechadas | 13.926 | **15.467** | **+1.541** |
| Códigos redundantes | 1.393 | **2.306** | **+913** |

### Com BERT (`--sem-llm`)

| Indicador | Antes | Depois | Δ |
|---|---|---|---|
| SANEADO | 9.493 (40,3%) | **14.481 (61,5%)** | **+4.988** |
| PENDENTE | 9.008 | 8.201 | −807 |
| REVISAO_HUMANA | 5.016 (21,3%) | **820 (3,5%)** | **−4.196** |
| Registros que o árbitro escalaria ao LLM | 6.430 | 2.372 | −4.058 |
| Chaves fechadas | 16.215 | 16.358 | +143 |
| Códigos redundantes | 1.766 | **2.520** | **+754** |
| Caixas INVÁLIDAS | 8.882 | 757 | −8.125 |
| Caixas em CONFLITO | 4.878 | 760 | −4.118 |

De onde vem a queda da revisão: dos 4.878 conflitos da linha de base, 3.383
eram de REFERÊNCIA FABRICANTE, todos causados pelo vazamento da descrição curta
(2.2). A regra lia `1884 4438 17 TAMPA DESCARGA APLIC COMPRESSOR`, o BERT lia
`1884 4438 17`, e o registro ia para revisão humana por uma divergência que não
existia. O commit da camada 0 (`106cd19`) tinha levado a revisão a 21% da base
por essa razão.

A tabela usa a execução de confirmação, que inclui a correção 2.13. As linhas
de PENDENTE, escalada, INVÁLIDO e CONFLITO são da execução imediatamente
anterior; a 2.13 mudou só cerca de 60 registros (SANEADO completo 14.451 →
14.481, revisão 865 → 820).

Os conflitos que sobram (760) são, na maioria, divergências reais entre medidas
(DIAMETRO INTERNO, ALOJAMENTO, REDUZIDO), que é o que a revisão humana deve
receber.

## 1b. Sanear não é completar: os dois eixos

Decisão de definição, tomada depois das correções acima. **Sanear** é extrair e
padronizar corretamente tudo o que o texto informa. Um obrigatório que o texto não
traz não torna o registro "não saneado": torna-o **incompleto**, o que é
resolvido por enriquecimento ou devolução ao solicitante, nunca por extração.

| Estado | Significa |
|---|---|
| `SANEADO` | tudo o que o texto informa foi extraído e validado, sem dúvida |
| `PENDENTE` | o texto traz um valor obrigatório que o PDM não reconhece (ex.: `ACO ESPECIAL`) |
| `REVISAO_HUMANA` | conflito: duas leituras plausíveis do mesmo dado |
| `FORA_DO_PDM` | não existe classe para o item |

E, à parte, `COMPLETO` (coluna nova no `saneado_base.csv`): todo obrigatório
cheio e chave de identidade fechada. `SANEADO` + `COMPLETO` é exatamente o
`SANEADO` da definição anterior.

### Números pela definição nova (23.554 registros)

| | Só regras | **Regras + BERT** |
|---|---|---|
| **SANEADO** | **23.248 (98,7%)** | **22.038 (93,6%)** |
| ↳ saneado e completo | 14.177 (60,2%) | **14.481 (61,5%)** |
| ↳ saneado e incompleto | 9.071 (38,5%) | 7.557 (32,1%) |
| PENDENTE (valor não reconhecido) | 0 | 659 (2,8%) |
| REVISAO_HUMANA | 269 (1,1%) | 820 (3,5%) |
| FORA_DO_PDM | 37 (0,2%) | 37 (0,2%) |
| Chaves fechadas | 15.467 | 16.358 |
| Códigos redundantes | 2.306 | 2.520 |
| Tempo | 34 s | 12 min |

**Por que o SANEADO cai com o BERT** (98,7% para 93,6%) enquanto o completo sobe:
o BERT **preenche** mais (+304 saneados completos, +891 chaves, +214
redundantes), mas também **duvida** mais. Ele aponta conflitos com a regra
(+551 em revisão) e recorta valores que o PDM não reconhece em caixas
obrigatórias (+659 pendentes). Só com regras não existe a segunda opinião, e
por isso nada fica em dúvida. Isso não quer dizer que esteja tudo certo: lida
uma amostra dos conflitos, o BERT estava certo em cerca de 1/3 deles (o-ring
com `DIAMETRO: 30MM` lido pela regra como 1,5MM, arruela, faixa de manômetro).
O número a apresentar é o **com BERT**.

Estes números foram recalculados das decisões gravadas nas execuções finais,
com a mesma regra de estado do código. A coluna com BERT é a execução de
confirmação, já com todas as correções deste documento.

### O cuidado que este número exige

`saneado e incompleto` parte da premissa de que **caixa vazia significa
informação ausente do texto**, e quem diz que está vazio é o próprio extrator.
Nesta rodada apareceram vários casos em que o dado estava no texto e tinha sido
perdido (polegada com aspas, vírgula decimal, o-ring). O grupo mistura dois
casos:

- **ausente de verdade:** correto contar como saneado;
- **perdido pela extração:** erro do pipeline, que infla o número.

Antes de apresentar o 93,6%, é preciso medir a proporção. Uma amostra de ~100
registros "saneados e incompletos", estratificada por classe, conferida a mão
("o dado que falta aparece no texto?"), dá algo como "em X% dos incompletos o
dado não está no texto, IC 95% ±Y". Sem essa medida, o número é o pipeline
dando nota para si mesmo.

## 2. As correções, da mais grave para a menos grave

### 2.1 Vírgula decimal cortava o valor rotulado (`rotulos.py`)

`pares()` tratava toda vírgula como separador de par:

```
DIAMETRO EIXO:16,25MM   ->  16MM      aceito com confianca 0,99
SECAO:1,5MM2            ->  1MM2
BITOLA:M12X1,5          ->  M12X1     (recusado; a regra 2 assumia M12)
```

944 registros têm valor rotulado com vírgula decimal. O valor truncado era
**aceito**, porque `16MM` está no formato. É o pior tipo de erro, porque cria
item errado. **62 clusters de junção eram falsos** por causa disso: cabo de
1MM² junto com cabo de 1,5MM², o-ring de seção 2MM junto com o de 2,5MM, junta
de 3MM junto com a de 3,2MM, bucha de 1" junto com a de 1,25". Agora a
vírgula só separa quando não está entre dígitos.

### 2.2 O último par da descrição longa vazava para a curta (`pipeline.py`)

O texto estruturado juntava as duas descrições com espaço:

```
REFERENCIA FABRICANTE: V1596R71 LUVA EIXO BOMBA POLPA MODELO EQUIPAMENTO
```

A caixa REFERÊNCIA aceita formato livre, então o lixo entrava: **3.177 part
numbers** e 119 números de CA estavam corrompidos. Cada um gerava uma chave
única, que nunca juntava. Agora as descrições são juntadas com `; `. É a
maior fonte dos +913 códigos redundantes, e as junções novas foram conferidas
por amostragem (mesmo fabricante e mesmo part number, como `PN:334224-758` =
`PN:334224758`).

### 2.3 Rosca fina lida como comprimento (`texto.separar_rosca_metrica`)

```
M10X1,25X70  ->  BITOLA M10, COMPRIMENTO 1,25MM    agora: M10X1,25 e 70MM
M12X1,5      ->  BITOLA M12                        agora: M12X1,5
```

`M12` e `M12X1,5` são itens diferentes (rosca grossa e rosca fina), e os dois
estão na lista do PDM. Agora o segundo número é passo quando vale até 3
(ISO 261). O passo grosso escrito por extenso (`M8X1,25`) continua sendo M8. Um
número colado a unidade é comprimento (`M16X1M` é barra de 1 metro). Foram 269
bitolas corrigidas. Foi o BERT que apontou esse erro: em 136 casos ele dizia
`M10X1,25` onde a regra dizia `M10`.

### 2.4 Polegada com aspas era apagada (`texto.normalizar`)

`normalizar()` removia `"` antes de qualquer camada. **1.273 registros** escrevem
polegada assim (`2"`, `1/2"`), e o diâmetro deles chegava como um número solto.
Agora `2"` vira `2POL`, `1 3/4POL` vira `1.3/4POL` (regra 5) e `7/8"X2"` vira
`7/8POL X 2POL`.

Dois efeitos colaterais apareceram na medição e foram corrigidos:
- a fração mista juntava o ângulo à bitola (`COTOV GRAUS 90 1/4POL` virou
  `90.1/4POL`, e o cotovelo perdeu a classe). Agora a parte inteira vai só de
  1 a 12 e nunca vem depois de GRAUS ou SCH;
- `DN 6"` passou a ser lido também como `DN 6` (que equivale a 1/8"). Agora DN
  seguido de polegada fica para a família POL.

### 2.5 Polegada decimal virava só a parte decimal (`regras.RX['POL']`)

`1,5POL` casava a partir do `5` e virava `5POL`, e uma válvula de 1.1/2"
entrava como de 5". O regex agora aceita decimal e não começa no meio de um
número.

### 2.6 Parafuso em polegada: bitola e comprimento ambíguos (`regras.py`)

Com as aspas lidas, o texto passou a ter duas medidas em polegada, e as duas
estão na lista de COMPRIMENTO. Duas regras determinísticas resolvem:
- duas grafias do mesmo valor não são ambiguidade (`['1.1/4POL', '1.1/4POL']`);
- um valor já usado sem ambiguidade por outra caixa (a BITOLA) não serve para
  esta (`_desambiguar_por_exclusao`).

E o validador agora reformata na unidade que o valor traz quando o atributo
aceita duas (COMPRIMENTO de PDM001 é MM **ou** POL). Antes, `1-1/4POL` era
recusado com "o atributo exige MM".

### 2.7 Mesmo valor, chaves diferentes (`validador.py`)

Com o valor decimal inteiro, `COMPR:35,0MM` passou a chegar como `35,0MM`, e a
chave compara texto. Agora o validador tira o zero decimal inútil (`35,0MM` vira
`35MM`, `1,50MM2` vira `1,5MM2`). Também aceita `SECAO:2,5MM` num atributo de MM²,
porque a unidade só veio abreviada.

### 2.8 Caixa INVÁLIDA de atributo opcional travava o registro (`pipeline._montar`)

Qualquer caixa INVÁLIDA mandava o registro para PENDENTE, mesmo de atributo
opcional. Eram 3.180 registros com a chave fechada e todos os obrigatórios
cheios, presos por um `MATERIAL = "FABRICANTE"` que o BERT recortou num
atributo que na PDM110 é "quando informado pelo fabricante". Agora só conta
o INVÁLIDO de atributo obrigatório para aquele registro.

### 2.9 BERT em caixa textual: só valor da lista (`pipeline._bert`)

Em caixa TEXTUAL, o BERT nunca preencheu nada que a regra não preenchesse, e
gerou 8.038 propostas fora da lista. Mas quando ele propõe **outro valor
válido**, aponta erro real da regra (foi assim que apareceu o 2.3). Agora a
proposta fora da lista é descartada antes do árbitro, e a proposta válida
continua indo, como CONFLITO quando diverge.

A primeira versão desta mudança tirava o BERT de toda caixa textual. A
medição mostrou que isso perderia os 179 conflitos válidos, e ela foi revertida
para este meio-termo.

### 2.10 BERT recebia o texto expandido (`pipeline._tokens_para_bert`)

O treino (`rotulos.py`) usa o valor como está escrito, e a inferência expandia
abreviações (`FAB` virava `FABRICANTE`). Era a origem dos 3.141 `FABRICANTE`
recortados como MATERIAL. Agora a inferência usa o mesmo texto do treino.

### 2.11 Part number depois de rótulo sem dois-pontos (`regras._por_rotulo_telegrafico`)

`FAB CATERPILLAR P/N 519-8798`, `COD 458.6479-93 REV A`: a camada 0 só lê
`P/N: 519-8798`. A regra nova lê o código depois de `P/N`, `PN` (exceto `PN 16`),
`REF`, `REFERENCIA (FABRICANTE)`, `COD`, `CODIGO` e `PART NUMBER`:
- junta os grupos só de dígitos (`1728 9860 67`, formato Epiroc);
- recusa uma medida (`REF 25MM`) e um número seguido de unidade (`12345 50 MM`);
- só atua quando a coluna `REFERENCIA_FABRICANTE` do ERP está vazia. A
  coluna é o campo próprio do cadastro e vence tanto essa regra quanto o BERT
  (2.12).

Só com regras, preencheu 1.211 part numbers que estavam vazios. Com BERT, ela
vira segunda opinião: o árbitro compara os part numbers pela forma A–Z0–9 e
aceita prefixo como acordo (`N45459632 REV A` = `N45459632-REVA`;
`MM1728484 APLICACAO`, em que o BERT engoliu a palavra seguinte, vale como
`MM1728484`).

### 2.12 Coluna do ERP vence o texto (`pipeline.processar`)

Com a coluna `REFERENCIA_FABRICANTE` preenchida, nem a regra telegráfica nem o
BERT a substituem. Antes, o BERT preenchia a caixa e a coluna só entrava se a
caixa estivesse vazia.

### 2.13 BERT recortava o rótulo junto com o part number (`pipeline._bert`)

Com o texto cru (2.10), o BERT vê `PN`, `COD` e `REF` e às vezes os recorta:
`PN 12560` contra `12560` da regra (CONFLITO), ou só `PN` (caixa preenchida com
o rótulo). Eram 53 dos 77 conflitos de part number. Agora o rótulo no começo
é retirado, e um trecho sem dígito não é aceito como part number.

## 3. O que ainda não está resolvido

- **Precedência num lugar só** (`docs/09`, seção 9). Esta rodada acrescentou
  dois pontos de decisão: a comparação de part number no árbitro e a
  precedência da coluna do ERP em `processar`. Os dois precisam entrar na
  tabela única quando ela existir.
- **Parafuso em polegada com bitola e comprimento escritos sem rótulo e sem
  separador** (`UNC 7/8X2 1/4`): continua ambíguo em alguns casos.
- **Empate de classe** (`docs/08`): 1.123 registros na primeira classe da
  lista. Isso não muda aqui.
- Nenhum número acima foi medido contra um conjunto-ouro. As amostras foram
  conferidas pelo Claude lendo o texto de cada registro, e não por uma pessoa
  do time.

## 4. Como reproduzir

Ver `docs/07-abreviacoes.md`, seção 6: duas cópias do código, cada uma com seu
`--artefatos` e uma cópia do `aprendizado.json`, comparadas com
`scripts/12_comparar_execucoes.py`.
