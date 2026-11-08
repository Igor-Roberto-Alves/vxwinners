# Dado genérico: detectar, marcar e sugerir completações

Data: 2026-11-07. Scripts: `scripts/12_detectar_ausentes.py` (LLM, Bedrock) e
`scripts/14_sugerir_completacoes.py` (sem LLM). Pipeline: `--aplicar-deteccao`
em `scripts/04_extrair.py`.

## 1. O problema

Quando uma caixa obrigatória fica vazia, o pipeline só sabe que **não achou** o
valor. A heurística de sinais (rótulo escrito, grandeza sobrando, valor
parecido) dizia que 85% das 11.114 caixas faltantes eram ausência de verdade. A
detecção com LLM mostrou que não:

| Grupo | Caixas | Ausente | Presente, fora do padrão | Perdido |
|---|---|---|---|---|
| Com sinal (todas) | 1.629 | 5,8% | 91,8% | 2,5% |
| Sem sinal (amostra de 400) | 400 | 74,5% | 21,8% | 3,8% |

Estimativa para as 9.485 sem sinal: dado no texto em 25,5% (IC 95%: 21,5–30,0%).
Custo: US$ 2,92 (Haiku 4.5, 1.919 chamadas). O LLM só diz se o atributo aparece
e copia o trecho; o código descarta o trecho que não existe no texto (21
descartados) e decide pelo validador se ele é valor do PDM. Ele erra a
atribuição em alguns casos (nos 18 lidos, 2 ou 3 eram o valor de outro
atributo, como `MODELO = "BRITADOR MANDIBULA"`).

## 2. Três coisas diferentes que pareciam "faltante"

| Tipo | Exemplo | Tratamento |
|---|---|---|
| **Ausente** | parafuso que não diz a norma | saneado e incompleto: enriquecimento ou devolução |
| **Genérico** | `ZINCADO` (branco ou amarelo?), `INOX` (304 ou 316?), `ACO FORJADO` | **PENDENTE**, com pergunta pré-preenchida ao solicitante (seção 3) |
| **Fora do vocabulário do PDM** | `MANOPLA`, `MANUAL` (acionamento), `DACROMET`, `GRAFOIL`, `ACO ESPECIAL`, `12.9` em PDM001 | governança do PDM: incluir o valor ou criar o sinônimo |
| **Perdido** | `O-RING 260X5` (seção 5) | bug de extração: o valor volta, e a regra precisa ser corrigida |

`--aplicar-deteccao` leva isso para os registros:
- caixa **genérica** → estado de caixa `GENERICO`, com o trecho como evidência;
  o registro vai para **PENDENTE** (o dado existe e não foi padronizado);
- caixa **perdida** → o valor entra pelo validador, como no desempate;
- nos dois casos, só se a caixa continuar vazia na extração atual.

A detecção cobriu todas as caixas com sinal e uma **amostra** das sem sinal.
Para marcar todas as sem sinal, rode o script 12 com `--amostra 9485` (cerca de
US$ 15).

## 3. O modelo de completação

**Um dado genérico não é ausência de informação, é uma restrição.** `ZINCADO`
elimina todos os acabamentos menos dois. O modelo usa isso em três passos.

**1. Candidatos.** São os valores da lista do PDM (daquela classe e daquele
atributo) que **refinam** o termo: todo token do termo aparece, por prefixo, num
token do valor. `INOX` → {ACO INOX 304, ACO INOX 316}; `ACO FORJADO` → {ACO
CARBONO FORJADO A105, ACO INOX FORJADO A182 F316}.

**2. Ordem.** É a probabilidade de cada candidato dado o que o registro já tem
preenchido (Bayes ingênuo, com suavização de Laplace), contada nos registros da
própria base em que o atributo está preenchido. É o conhecimento da base: a
classe de resistência `A4-70` puxa o material para 316; `ASME B16.11` puxa a
rosca para NPT; `8.8` puxa para aço carbono.

**3. Faixa e uso:**

| Faixa | Critério | O que fazer |
|---|---|---|
| PROVÁVEL | ≥ 90% e ≥ 20 registros de base | pedir **confirmação** da sugestão |
| INCLINADA | 60–90% | oferecer as duas primeiras |
| ABERTA | < 60% | perguntar sem sugerir |
| ÚNICO | um candidato só na lista | confirmar: é o único **da lista**, e o real pode estar fora dela |

Exemplo de saída (`artefatos/completacoes_sugeridas.jsonl`):

```
O cadastro diz 'ACO FORJADO' para MATERIAL. Qual destes:
  ACO CARBONO FORJADO A105 (89%); ACO INOX FORJADO A182 F316 (11%)?
```

**A sugestão nunca vai para a caixa nem para a chave de identidade.** Ela serve
a três usos:
1. **devolução ao solicitante** com uma pergunta objetiva, em vez de "falta
   material";
2. **revisão humana** com a resposta mais provável já marcada;
3. **duplicata provável:** se o candidato mais provável fecha a chave de um
   registro completo, os dois vão para revisão como possível par, sem junção
   automática.

## 4. Teste retroativo

Em registros que têm o valor específico, o valor é escondido e só o termo
genérico fica visível (o próprio registro sai da contagem). São 11.059 casos:

| Faixa | Casos | Acerto |
|---|---|---|
| PROVÁVEL (≥90%) | 6.583 | **96,3%** |
| INCLINADA (60–90%) | 3.161 | 66,5% |
| ABERTA (<60%) | 1.315 | 52,4% |
| Total | 11.059 | **82,6%** (o valor mais comum da classe acerta 69,0%) |

A faixa PROVÁVEL está calibrada: diz ≥90% e acerta 96%. As outras não
sustentam sugestão.

Por termo, onde o contexto decide e onde não decide:

| Classe · atributo | Termo | Casos | Acerto |
|---|---|---|---|
| PDM001 · MATERIAL | `ACO` | 2.638 | 98,0% |
| PDM050 · CONEXAO | `ROSCA` | 487 | 99,0% |
| PDM001 · MATERIAL | `INOX` | 369 | 91,1% |
| PDM050 · MATERIAL | `INOX` | 482 | 82,4% |
| PDM001 · ACABAMENTO | `ZINCADO` | 921 | **56,7%**: nada no registro diz a cor |
| PDM050 · MATERIAL | `ACO FORJADO` | 712 | **53,7%** |

**Limites do teste:**
- Quem escreve só `ZINCADO` pode não ser parecido com quem escreve `ZINCADO
  BRANCO` (outra época, outra área, outro fornecedor). O teste mede o modelo na
  população que escreveu o valor completo, e a precisão real na população
  genérica pode ser menor.
- O contexto vem da própria extração: se uma caixa do contexto está errada, a
  sugestão herda o erro.
- A prova definitiva é a resposta dos solicitantes. Quando houver respostas,
  elas viram o gabarito do modelo.

## 5. Efeito nos registros (extração com BERT, desempates e detecção aplicados)

| Indicador | Antes da detecção | Depois |
|---|---|---|
| SANEADO | 23.287 (98,9%) | **21.779 (92,5%)** |
| ↳ saneado e completo | 15.358 (65,2%) | 15.383 (65,3%) |
| ↳ saneado e incompleto | 7.929 | 6.396 |
| PENDENTE | 130 | **1.638 (7,0%)** |
| REVISAO_HUMANA | 100 | 100 |
| Caixas marcadas GENERICO | — | 1.582 |
| Valores perdidos recuperados | — | 55 |
| Códigos redundantes | 2.642 | 2.649 |

O SANEADO caiu porque ficou mais honesto: 1.508 registros que contavam como
"saneados e incompletos" têm o dado no texto, só que genérico. Ainda falta uma
parte: a detecção cobriu só uma amostra de 400 das 9.485 caixas sem sinal, e
pela amostra umas 2.000 delas escondem dado genérico. Marcá-las todas (`12 --amostra
9485`, ~US$ 15) deve levar o SANEADO para perto de 85%.

## 6. Detecção em todas as caixas faltantes

A segunda rodada do script 12 (`--amostra 9485`) cobriu as caixas que a amostra
deixou de fora: 6.382 chamadas, US$ 9,83, sem erros. Nas 8.750 caixas sem sinal,
o dado estava no texto em **25,8%** (IC 95%: 24,9–26,8%); a amostra de 400 tinha
estimado 25,5%. 336 trechos foram descartados por não existirem no texto.

O script passou a **acrescentar** ao `deteccao_ausentes.jsonl` em vez de
sobrescrevê-lo. Antes, a segunda rodada apagava as marcações da primeira, e
reaplicar o arquivo as desfazia.

| Indicador | Detecção por amostra | Detecção completa |
|---|---|---|
| SANEADO | 21.779 (92,5%) | **20.055 (85,1%)** |
| ↳ saneado e completo | 15.383 (65,3%) | **15.536 (66,0%)** |
| ↳ saneado e incompleto | 6.396 (27,2%) | 4.519 (19,2%) |
| PENDENTE | 1.638 (7,0%) | **3.362 (14,3%)** |
| REVISAO_HUMANA | 100 | 100 |
| Caixas GENERICO | 1.582 | 3.464 |
| Valores perdidos recuperados | 55 | 437 |
| Chaves fechadas | 16.835 | 16.996 |
| Códigos redundantes | 2.649 | **2.687** |
| Capital em código redundante | R$ 30,2 mi | R$ 30,3 mi (15,1%) |

Completações sugeridas sobre os 3.464 genéricos: 799 na faixa provável, 417
inclinada, 245 aberta e 242 com candidato único. Teste retroativo: 96,0% de
acerto na faixa provável (6.891 casos) e 81,9% no geral (o valor mais comum
acerta 68,2%).

Custo total de LLM do projeto até aqui: **US$ 19,60** (termos 1,32, desempate
5,53, detecção 2,92 + 9,83).
