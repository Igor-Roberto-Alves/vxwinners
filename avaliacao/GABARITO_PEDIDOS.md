# Gabarito de pedidos de cadastro — classe e caracteristicas

Mede o pipeline onde o cadastro é de fato decidido: nos **520 pedidos** que chegam
(`dados/02_pedidos_cadastro.xlsx`), não na base que já existe.

## Por que fazer um gabarito separado

Os gabaritos que já existiam medem a base: 23.554 descrições em MAIÚSCULAS, de
formato mais ou menos constante, onde o problema é o campo **vazio**. O pedido é
outra coisa:

| | Base | Pedido |
|---|---|---|
| Caixa alta | praticamente toda | 519 dos 520 têm minúscula |
| Formato | uma coluna de descrição | 4 formatos (telegráfico, e-mail, ficha técnica, catálogo) |
| Canal | — | PORTAL 279, EMAIL 156, PLANILHA 85 |
| Língua | português | 29 pedidos em **inglês** (catálogo do fornecedor) |
| Informação | 78,5% da referência do fabricante é vazia | chega 97,2% completo contra o PDM |

Em 136 dos 520, `TEXTO_SOLICITACAO` é só "Segue ficha técnica em anexo" e o
conteúdo está em `CONTEUDO_ANEXO`, em outro formato. Medir na base não diz nada
sobre isso.

## Arquivos

| Arquivo | O que é |
|---|---|
| `22_candidatos_pedidos.py` | sorteio reproduzível dos 120 candidatos (semente 20261108) |
| `candidatos_pedidos.csv` | os 120 pedidos, só a linha crua + estrato/estilo/armadilhas |
| `_anota_pedidos_comum.py` | expande as decisões contra o PDM e **aborta** se faltar rótulo |
| `_anota_pedidos_A.py` | passada A — persona analista de cadastro |
| `_anota_pedidos_B.py` | passada B — persona suprimentos/almoxarifado |
| `anotacoes_pedidos_{A,B}.jsonl` | 682 e 678 rótulos |
| `23_adjudicar_pedidos.py` | adjudica; exige motivo escrito por divergência |
| `gold_pedidos.csv` | 562 rótulos de caixa |
| `gold_classe_pedidos.csv` | 120 rótulos de classe |
| `concordancia_pedidos.json` | acordo bruto e kappa, por campo e global |
| `revisao_humana_pedidos.csv` | 84 linhas para uma pessoa conferir |
| `evaluate_pedidos.py` → `resultado_pedidos.md` | a avaliação |

Reproduzir, numa máquina sem rede e sem custo de LLM:

```bash
backend/.venv/bin/python scripts/04_extrair.py --pedidos --sem-llm --sem-bert \
    --congelar-aprendizado          # gera artefatos/saneado_pedidos.csv
backend/.venv/bin/python avaliacao/22_candidatos_pedidos.py
cd avaliacao && ../backend/.venv/bin/python _anota_pedidos_A.py
             && ../backend/.venv/bin/python _anota_pedidos_B.py
             && ../backend/.venv/bin/python 23_adjudicar_pedidos.py && cd ..
backend/.venv/bin/python avaliacao/evaluate_pedidos.py
```

`--congelar-aprendizado` importa: sem ele, rodar sobre os pedidos reescreve
`artefatos/aprendizado.json` e contamina o dicionário que a base usa. O md5 do
arquivo foi conferido idêntico antes e depois.

## Independência do pipeline

Mais estrita que a dos gabaritos anteriores. O `20_candidatos_cadastro.py` tinha
permissão de ler `saneado_base.csv` para montar estratos; aqui **não foi
preciso**: todo estrato sai do texto cru e do PDM. Nenhuma coluna de saída do
pipeline influencia nem a escolha dos candidatos nem a anotação.

## Amostra: 120 pedidos, 682 rótulos

Estratos aplicados em ordem (um pedido fica no primeiro que o pegou):

| Estrato | n | Por quê |
|---|---:|---|
| `fora_pdm` | 10 | software, mobiliário, serviço, café: o pipeline deve dizer FORA_DO_PDM, e forçar classe é erro |
| `anexo:catalogo` | 12 | linha de catálogo em inglês, separada por barra |
| `anexo:ficha` | 14 | "Campo: valor" por linha, minúsculas e acento |
| `armadilha:*` | 35 | completa cada armadilha até 5 itens |
| `familia:*` | 49 | cota por família, proporcional aos 520 |

Seis armadilhas que a base não tem: `contexto_aplicacao` (89 dos 520),
`ingles`, `ruido_cortesia`, `minuscula`, `multi_item`, `equivalencia`.

**`contexto_aplicacao` é a mais interessante**, porque o mesmo fragmento é sinal
ou ruído conforme a classe: "para a correia TC-04" num parafuso é contexto, e
preencher qualquer caixa com isso é invenção; no sobressalente (PDM110) a
`APLICACAO` é uma lista de equipamentos e `CORREIA TRANSPORTADORA` é o valor
certo.

**`minuscula` pega 120/120** e 519/520. Não discrimina estrato: é diferença de
canal, e fica registrada como propriedade, não como cota.

**Três armadilhas da base não existem no pedido**, com zero casos nos 520:
`polegada_in`, `abrev_ambigua`, `equivalencia`.

## Concordância — leia com a ressalva

Acordo bruto global **98,4%**, kappa **0,984**; 11 divergências, todas
adjudicadas com motivo escrito. Por campo, as que divergiram:

| campo | n | acordo | kappa |
|---|---:|---:|---:|
| APLICACAO | 21 | 76,2% | 0,735 |
| TIPO CABECA | 6 | 83,3% | 0,700 |
| TERMINAL A | 10 | 90,0% | 0,881 |
| TIPO | 18 | 94,4% | 0,936 |
| ACABAMENTO | 26 | 96,2% | 0,950 |
| LENTE | 1 | 0,0% | 0,000 |
| _CLASSE | 120 | 99,2% | 0,991 |

> **A e B são duas passadas do mesmo anotador — um LLM — sob duas regras de
> decisão escritas e diferentes. Não são dois anotadores independentes.** Um
> único processo não consegue esquecer o que acabou de decidir. O kappa mede
> **quanto a regra de anotação muda o rótulo**, não concordância entre duas
> cabeças, e não deve ser citado como se fosse.
>
> O gabarito de características que já existe no repositório registrou kappa 1,0
> com zero divergências, e o próprio `PROMPT_gabarito_caracteristicas.md` aponta
> isso como sinal de que A e B não foram independentes. Aqui o problema é o
> mesmo; a diferença é que está declarado, e que `_anota_pedidos_B.py` é
> explícito — parte de A e aplica as divergências que a regra de B produz, cada
> uma com o motivo. Fingir uma segunda passada cega esconderia a dependência.
>
> A salvaguarda real é `revisao_humana_pedidos.csv`. **Até ela voltar respondida,
> este gabarito é provisório.**

### As duas leituras do gabarito

Cinco divergências são a mesma pergunta. O pedido diz *"eixo saida FLENDER
T6593-468134 do H3SH 9"* e não diz que H3SH 9 é um REDUTOR. A diz que o texto não
traz; B sabe que a frota só tem redutor com esse modelo.

Conferido na planilha: o PDM lista `APLICACAO` e `MODELO EQUIPAMENTO` como listas
**independentes**, e nenhuma aba liga modelo a tipo (a única tabela próxima,
`NCM_REFERENCIA`, dá o NCM por tipo, não o tipo por modelo). Logo, do pedido mais
o PDM, a aplicação está AUSENTE.

Mas jogar a informação fora seria burro, porque na operação B é quem está certo.
Então o gabarito carrega as duas leituras — `y_gold`/`status` (estrita) e
`permissivo` — e o avaliador reporta a invenção nas duas. A diferença entre elas
é *quanto do que o pipeline preenche vem de fora do texto*.

## O que a medição achou

Execução medida: regras, gazetteer, gramática e dicionário aprendido. **BERT e
LLM desligados** (`artefatos/modelo_bert` está vazio; o LLM custa dinheiro). São
números do piso.

| | Resultado |
|---|---|
| Classe | **86,7%** [79,4–91,6] em 120 pedidos |
| Caixas, precisão | **99,1%** [97,6–99,6] em 424 valores afirmados |
| Caixas, cobertura | 77,7% [74,0–80,9]; **92,0%** [89,1–94,1] quando a classe está certa |
| Invenção | 2 de 16 caixas vazias, estrita e permissiva |

### 1. Todos os 16 erros de classe estão num canal só

| estilo de entrada | n | acerto |
|---|---:|---|
| telegráfico | 51 | **100,0%** |
| ficha técnica | 32 | **100,0%** |
| e-mail longo | 18 | **100,0%** |
| catálogo do fornecedor | 19 | **15,8%** [5,5–37,6] |

Os três formatos em português dão 100%. O catálogo despenca porque vem em
**inglês** — `Ball valve`, `Hex head bolt`, `Oil seal`, `Twist drill`,
`Safety glove` — o pipeline não acha o substantivo do PDM e conclui
`FORA_DO_PDM`. Os três acertos do canal confirmam a causa: são `O-ring` (termo
que coincide com o qualificador do PDM) e um `Safety boot` cujos atributos vinham
em português.

Consequência prática: **29 dos 520 pedidos (5,6%) seriam recusados como fora do
PDM por causa da língua**, e cada recusa arrasta as caixas do item (85 das 122
caixas perdidas se perdem assim). É o conserto de maior retorno do relatório, e é
de vocabulário, não de modelo.

### 2. A referência do fabricante não é extraída do pedido

Com a classe certa, 25 das 37 caixas perdidas são `REFERENCIA FABRICANTE` (20 em
PDM110, 5 em PDM100), todas como "não informado no texto" — e o código está lá,
visível: `hb-467508`, `g2021`, `C 83 416`, `575.2066-45`. Nas duas classes de
**referência do fabricante**, esse campo é metade da chave de identidade (regra
10), então perdê-lo impede fechar a identidade do item que está entrando. É o
mesmo defeito que na base deixa 10.760 referências pendentes — agora medido na
entrada.

### 3. Dois irmãos de grandeza, um valor só

As duas invenções têm a mesma forma: uma caixa vazia recebe o valor da caixa
irmã.

- `SC-202600078`: o pedido lista só o terminal A; o pipeline copiou
  `FEMEA RETA JIC` para `TERMINAL B`.
- `SC-202600495`: a ficha traz só `Seção: 2,5 mm`; o pipeline pôs `2,5MM`
  também em `DIAMETRO INTERNO`.

E o espelho disso aparece nas perdidas: 8 casos de `TERMINAL A`/`TERMINAL B`
marcados `AMBIGUO` com "valores permitidos em conflito" — o texto traz os dois
terminais e o pipeline não sabe qual é de qual. Mesmo problema, duas saídas.

### 4. A camada que erra tem nome

| fonte do valor | n | precisão |
|---|---:|---|
| `rotulo` | 113 | 100,0% |
| `gazetteer` | 235 | 100,0% |
| `regra_pdm_2` | 17 | 100,0% |
| `dominio` | 19 | 100,0% |
| `gramatica` | 39 | 97,4% |
| `ordem_pdm` | 3 | **0,0%** |

`ordem_pdm` errou 3 de 3: nas três correias trapezoidais, pôs o comprimento
externo (`4038MM`, `3777MM`, `3672MM`) na caixa `REFERENCIA`, que devia levar a
designação da correia (`A157`, `B146`, `SPB 3650`).

O único erro de `gramatica`: em `2.1/4" (57,1 mm)`, pegou a conversão entre
parênteses em vez do valor em polegada. No mesmo gabarito, `5/16" (7,9 mm)`
saiu certo em `BITOLA` — então é inconsistência, não regra.

## Limitações

- **Só 2,8% das caixas são AUSENTE/INDEFINIVEL**, contra os 25% que o PROMPT
  pede. Desvio deliberado: os 520 pedidos chegam quase completos, e forçar um
  estrato de pedido incompleto encheria o denominador de um caso raro, dando uma
  taxa de invenção que não vale para a entrada real. O preço é um IC largo na
  invenção — leia o intervalo, não a média.
- **A conversão de pressão não é exercida.** Os pedidos com PSI são todos
  PDM011, classe em que `PRESSAO TRABALHO` não é obrigatória. Mediria com
  PDM010/012/013/014, que não caíram nestes 120.
- **BERT e LLM desligados**: números do piso, não do pipeline completo.
- **Anotação de LLM, em duas passadas não independentes** — ver a ressalva acima.

## Conferência humana

`revisao_humana_pedidos.csv`, **84 linhas**: as 18 marcadas (todo AUSENTE e
INDEFINIVEL, todas as 11 divergências adjudicadas, e tudo com confiança MÉDIA ou
BAIXA) mais 66 de amostra aleatória de 10% do resto (semente 20261108). Cada
linha traz o texto do pedido, o valor proposto, o `permissivo` quando existe, o
motivo da adjudicação, e colunas vazias `CONCORDO_S_N`, `VALOR_CERTO`,
`STATUS_CERTO` e `COMENTARIO`.

As linhas que mais precisam de olho humano, em ordem:

1. as **5 de `APLICACAO`** em que o modelo do equipamento está no texto e o tipo
   não — é decidir se o cadastro pode completar com conhecimento de frota;
2. `SC-202600158` / `LENTE` (confiança BAIXA): óculos "AMPLA VISÃO" antirrisco é
   incolor ou cinza?
3. `SC-202600141` / `TERMINAL A`: "JIC female swivel" é `FEMEA RETA JIC`?
4. `SC-202600087` / `_CLASSE`: "pipe fitting" genérico é PDM050 com substantivo
   pendente, ou não é cadastrável?

Estimativa de esforço: as 18 marcadas pedem leitura e decisão (~2 min cada); as
66 de amostra são conferência de acordo (~20 s cada). **Cerca de 1 hora.**

Quando o CSV voltar respondido, `23_adjudicar_pedidos.py` precisa passar a ler as
colunas de resposta e regerar os gold — hoje ele ainda não incorpora o retorno,
como o `11_adjudicar_caracteristicas.py` já faz para as características.
