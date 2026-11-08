# Resultado: gabarito de PEDIDOS — classe e caixas

Gerado por `avaliacao/evaluate_pedidos.py` em 2026-11-08 10:32, sobre `artefatos/medicao_pedidos/4_classe_llm_sem_gabarito`. Gabarito: `gold_pedidos.csv` (562 rótulos de caixa) e `gold_classe_pedidos.csv` (120 de classe), em 112 pedidos. Sorteio: `22_candidatos_pedidos.py` (semente 20261108); adjudicação: `23_adjudicar_pedidos.py`.

IC = intervalo de confiança de 95% de Wilson.

## Resumo

- **Classe:** acerto 92.5% [86.4%–96.0%] em 120 pedidos.
- **Caixas:** precisão 99.0% [97.7%–99.6%] nos 497 valores afirmados sobre caixa que o gabarito define; cobertura 91.0% [88.3%–93.1%].
- **Invenção:** estrita 3 de 16 caixas vazias (18.8% [6.6%–43.0%]); permissiva 3 de 16 (18.8% [6.6%–43.0%]).
- **Cobertura com a classe certa:** 98.4% [96.9%–99.2%] — é o número que mede a leitura, porque exclui as caixas que se perderam só porque a classe errou.
- **Perdido** (gabarito define, pipeline não preencheu): 49 de 546, sendo 41 por classe errada (o atributo nunca foi considerado), 8 como 'não informado no texto' e 0 como ambíguo.
- **Concordância A×B:** acordo bruto 98.4%, kappa 0.984; 11 divergências, todas adjudicadas com motivo escrito.

> **Ressalva de método, que vale para todos os números acima.** As duas passadas de anotação (A e B) são do mesmo anotador — um LLM — sob duas regras de decisão diferentes, e **não** de dois anotadores independentes. O kappa mede quanto a regra de anotação muda o rótulo, não concordância entre duas cabeças. Enquanto `revisao_humana_pedidos.csv` não voltar respondida por uma pessoa do time, este gabarito é **provisório**.

## 1. Classe

Acerto: **92.5% [86.4%–96.0%]** em 120 pedidos.

**Por estilo de entrada — é o corte que explica o número inteiro:**

| estilo de entrada | n | acertos | acerto [IC 95%] |
|---|---:|---:|---|
| telegrafico | 51 | 51 | 100.0% [93.0%–100.0%] |
| ficha | 32 | 32 | 100.0% [89.3%–100.0%] |
| catalogo | 19 | 10 | 52.6% [31.7%–72.7%] |
| email_longo | 18 | 18 | 100.0% [82.4%–100.0%] |

Os três formatos em português somam 100.0% [96.3%–100.0%]. O catálogo do fornecedor fica em 52.6% [31.7%–72.7%], e é de onde vem **9 dos 9** erros de classe. A causa é a língua: essas linhas vêm em inglês (`Ball valve`, `Hex head bolt`, `Oil seal`, `Twist drill`), o pipeline não acha o substantivo do PDM e conclui FORA_DO_PDM. Os poucos acertos do canal confirmam a causa — são justamente os itens cujo termo inglês coincide com o vocabulário do PDM (`O-ring`) ou que trazem os atributos em português.


**Por estrato de sorteio:**

| estrato | n | acertos | acerto [IC 95%] |
|---|---:|---:|---|
| familia:sobressalentes | 16 | 16 | 100.0% [80.6%–100.0%] |
| anexo:ficha | 14 | 14 | 100.0% [78.5%–100.0%] |
| anexo:catalogo | 12 | 7 | 58.3% [32.0%–80.7%] |
| familia:fixadores | 10 | 10 | 100.0% [72.2%–100.0%] |
| fora_pdm | 10 | 10 | 100.0% [72.2%–100.0%] |
| armadilha:ordem_sem_rotulo | 5 | 4 | 80.0% [37.6%–96.4%] |
| familia:conexoes_tubo | 5 | 5 | 100.0% [56.6%–100.0%] |
| armadilha:pn_ambiguo | 4 | 3 | 75.0% [30.1%–95.4%] |
| armadilha:polegada_aspas | 4 | 4 | 100.0% [51.0%–100.0%] |
| armadilha:polegada_mista | 4 | 4 | 100.0% [51.0%–100.0%] |
| armadilha:rosca_fina | 4 | 4 | 100.0% [51.0%–100.0%] |
| armadilha:unidade_nao_bar | 4 | 4 | 100.0% [51.0%–100.0%] |
| familia:filtros | 3 | 3 | 100.0% [43.8%–100.0%] |
| familia:mangueiras | 3 | 3 | 100.0% [43.8%–100.0%] |
| familia:valvulas | 3 | 3 | 100.0% [43.8%–100.0%] |
| familia:vedacao | 3 | 2 | 66.7% [20.8%–93.9%] |
| armadilha:multi_item | 2 | 2 | 100.0% [34.2%–100.0%] |
| armadilha:rosca_bitola_comp | 2 | 2 | 100.0% [34.2%–100.0%] |
| armadilha:virgula_decimal | 2 | 1 | 50.0% [9.5%–90.5%] |
| familia:eletricos | 2 | 2 | 100.0% [34.2%–100.0%] |
| familia:epi | 2 | 2 | 100.0% [34.2%–100.0%] |
| familia:rolamentos | 2 | 2 | 100.0% [34.2%–100.0%] |
| familia:transmissao | 2 | 2 | 100.0% [34.2%–100.0%] |
| armadilha:contexto_aplicacao | 1 | 1 | 100.0% [20.7%–100.0%] |
| armadilha:ruido_cortesia | 1 | 1 | 100.0% [20.7%–100.0%] |

**Erros de classe** (gabarito → pipeline):

| gabarito | pipeline | n | são irmãs? |
|---|---|---:|---|
| PDM060 | FORA_DO_PDM | 1 | não |
| PDM050 | FORA_DO_PDM | 1 | não |
| PDM032 | FORA_DO_PDM | 1 | não |
| PDM082 | FORA_DO_PDM | 1 | não |
| PDM070 | FORA_DO_PDM | 1 | não |
| PDM021 | FORA_DO_PDM | 1 | não |
| PDM043 | FORA_DO_PDM | 1 | não |
| PDM034 | FORA_DO_PDM | 1 | não |
| PDM002 | PDM050 | 1 | não |

## 2. Caixas, por recorte


### Por atributo

| campo | n gold | afirmados | precisão [IC 95%] | cobertura | invenção estrita | invenção permissiva |
|---|---:|---:|---|---|---:|---:|
| MATERIAL | 45 | 37 | 100.0% [90.6%–100.0%] | 82.2% [68.7%–90.7%] | 0/0 | 0/0 |
| COMPRIMENTO | 35 | 33 | 100.0% [89.6%–100.0%] | 97.1% [85.1%–99.5%] | 0/1 | 0/1 |
| NORMA | 30 | 29 | 100.0% [88.3%–100.0%] | 96.7% [83.3%–99.4%] | 0/0 | 0/0 |
| ACABAMENTO | 26 | 23 | 100.0% [85.1%–100.0%] | 95.7% [79.0%–99.2%] | 1/3 | 1/3 |
| BITOLA | 26 | 25 | 100.0% [86.7%–100.0%] | 96.2% [81.1%–99.3%] | 0/0 | 0/0 |
| CLASSE RESISTENCIA | 26 | 25 | 100.0% [86.7%–100.0%] | 96.2% [81.1%–99.3%] | 0/0 | 0/0 |
| FABRICANTE | 26 | 26 | 100.0% [87.1%–100.0%] | 100.0% [87.1%–100.0%] | 0/0 | 0/0 |
| REFERENCIA FABRICANTE | 26 | 24 | 95.8% [79.8%–99.3%] | 96.0% [80.5%–99.3%] | 0/1 | 0/1 |
| APLICACAO | 21 | 16 | 100.0% [80.6%–100.0%] | 100.0% [80.6%–100.0%] | 0/5 | 0/5 |
| DIAMETRO NOMINAL | 21 | 18 | 100.0% [82.4%–100.0%] | 85.7% [65.4%–95.0%] | 0/0 | 0/0 |
| MODELO EQUIPAMENTO | 21 | 21 | 100.0% [84.5%–100.0%] | 100.0% [84.5%–100.0%] | 0/0 | 0/0 |
| ROSCA | 20 | 20 | 100.0% [83.9%–100.0%] | 100.0% [83.9%–100.0%] | 0/0 | 0/0 |
| CLASSE PRESSAO | 18 | 15 | 100.0% [79.6%–100.0%] | 83.3% [60.8%–94.2%] | 0/0 | 0/0 |
| TIPO | 18 | 13 | 100.0% [77.2%–100.0%] | 76.5% [52.7%–90.4%] | 0/1 | 0/1 |
| CONEXAO | 15 | 13 | 100.0% [77.2%–100.0%] | 86.7% [62.1%–96.3%] | 0/0 | 0/0 |
| DIAMETRO INTERNO | 14 | 14 | 100.0% [77.2%–100.0%] | 100.0% [77.2%–100.0%] | 1/1 | 1/1 |
| MATERIAL CORPO | 14 | 12 | 100.0% [75.7%–100.0%] | 92.3% [66.7%–98.6%] | 0/1 | 0/1 |
| ACIONAMENTO | 11 | 11 | 100.0% [74.1%–100.0%] | 100.0% [74.1%–100.0%] | 0/0 | 0/0 |
| MATERIAL TERMINAIS | 10 | 10 | 100.0% [72.2%–100.0%] | 100.0% [72.2%–100.0%] | 0/0 | 0/0 |
| TERMINAL A | 10 | 8 | 100.0% [67.6%–100.0%] | 80.0% [49.0%–94.3%] | 0/0 | 0/0 |
| TERMINAL B | 10 | 8 | 85.7% [48.7%–97.4%] | 77.8% [45.3%–93.7%] | 1/1 | 1/1 |
| VEDACAO SEDE | 8 | 8 | 100.0% [67.6%–100.0%] | 100.0% [67.6%–100.0%] | 0/0 | 0/0 |
| REFERENCIA | 7 | 6 | 50.0% [18.8%–81.2%] | 85.7% [48.7%–97.4%] | 0/0 | 0/0 |
| CA | 6 | 5 | 100.0% [56.6%–100.0%] | 83.3% [43.6%–97.0%] | 0/0 | 0/0 |
| DIAMETRO ALOJAMENTO | 6 | 5 | 100.0% [56.6%–100.0%] | 83.3% [43.6%–97.0%] | 0/0 | 0/0 |
| DIAMETRO EIXO | 6 | 5 | 100.0% [56.6%–100.0%] | 83.3% [43.6%–97.0%] | 0/0 | 0/0 |
| LARGURA | 6 | 5 | 100.0% [56.6%–100.0%] | 83.3% [43.6%–97.0%] | 0/0 | 0/0 |
| SECAO | 6 | 5 | 100.0% [56.6%–100.0%] | 83.3% [43.6%–97.0%] | 0/0 | 0/0 |
| TAMANHO | 6 | 5 | 100.0% [56.6%–100.0%] | 83.3% [43.6%–97.0%] | 0/0 | 0/0 |
| TIPO CABECA | 6 | 4 | 100.0% [51.0%–100.0%] | 80.0% [37.6%–96.4%] | 0/1 | 0/1 |
| PASSAGEM | 5 | 5 | 100.0% [56.6%–100.0%] | 100.0% [56.6%–100.0%] | 0/0 | 0/0 |
| DUREZA | 4 | 4 | 100.0% [51.0%–100.0%] | 100.0% [51.0%–100.0%] | 0/0 | 0/0 |
| FOLGA | 4 | 3 | 100.0% [43.8%–100.0%] | 75.0% [30.1%–95.4%] | 0/0 | 0/0 |
| CASTELO | 3 | 3 | 100.0% [43.8%–100.0%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |
| CORRENTE NOMINAL | 3 | 3 | 100.0% [43.8%–100.0%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |
| MATERIAL DISCO | 3 | 3 | 100.0% [43.8%–100.0%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |
| PERFIL | 3 | 3 | 100.0% [43.8%–100.0%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |
| TIPO CORPO | 3 | 3 | 100.0% [43.8%–100.0%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |
| VEDACAO | 3 | 3 | 100.0% [43.8%–100.0%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |
| BIQUEIRA | 2 | 2 | 100.0% [34.2%–100.0%] | 100.0% [34.2%–100.0%] | 0/0 | 0/0 |
| CAPACIDADE INTERRUPCAO | 2 | 2 | 100.0% [34.2%–100.0%] | 100.0% [34.2%–100.0%] | 0/0 | 0/0 |
| COR | 2 | 1 | 100.0% [20.7%–100.0%] | 50.0% [9.5%–90.5%] | 0/0 | 0/0 |
| CURVA | 2 | 2 | 100.0% [34.2%–100.0%] | 100.0% [34.2%–100.0%] | 0/0 | 0/0 |
| ESPESSURA | 2 | 1 | 100.0% [20.7%–100.0%] | 50.0% [9.5%–90.5%] | 0/0 | 0/0 |
| ISOLACAO | 2 | 1 | 100.0% [20.7%–100.0%] | 50.0% [9.5%–90.5%] | 0/0 | 0/0 |
| NUMERO CONDUTORES | 2 | 1 | 100.0% [20.7%–100.0%] | 50.0% [9.5%–90.5%] | 0/0 | 0/0 |
| POLOS | 2 | 2 | 100.0% [34.2%–100.0%] | 100.0% [34.2%–100.0%] | 0/0 | 0/0 |
| SOLADO | 2 | 2 | 100.0% [34.2%–100.0%] | 100.0% [34.2%–100.0%] | 0/0 | 0/0 |
| TENSAO ISOLAMENTO | 2 | 1 | 100.0% [20.7%–100.0%] | 50.0% [9.5%–90.5%] | 0/0 | 0/0 |
| TIPO FACE | 2 | 1 | 100.0% [20.7%–100.0%] | 50.0% [9.5%–90.5%] | 0/0 | 0/0 |
| ANEL INTERNO | 1 | 1 | 100.0% [20.7%–100.0%] | 100.0% [20.7%–100.0%] | 0/0 | 0/0 |
| DIAMETRO | 1 | 0 | — | 0.0% [0.0%–79.3%] | 0/0 | 0/0 |
| DIAMETRO REDUZIDO | 1 | 1 | 100.0% [20.7%–100.0%] | 100.0% [20.7%–100.0%] | 0/0 | 0/0 |
| ENCHIMENTO | 1 | 1 | 100.0% [20.7%–100.0%] | 100.0% [20.7%–100.0%] | 0/0 | 0/0 |
| FURO | 1 | 0 | — | 0.0% [0.0%–79.3%] | 0/0 | 0/0 |
| HASTE | 1 | 0 | — | 0.0% [0.0%–79.3%] | 0/0 | 0/0 |
| LENTE | 1 | 0 | — | — | 0/1 | 0/1 |
| MATERIAL FITA | 1 | 1 | 100.0% [20.7%–100.0%] | 100.0% [20.7%–100.0%] | 0/0 | 0/0 |
| TRATAMENTO | 1 | 1 | 100.0% [20.7%–100.0%] | 100.0% [20.7%–100.0%] | 0/0 | 0/0 |

### Por família prevista

| familia | n gold | afirmados | precisão [IC 95%] | cobertura | invenção estrita | invenção permissiva |
|---|---:|---:|---|---|---:|---:|
| fixadores | 170 | 156 | 100.0% [97.6%–100.0%] | 93.9% [89.2%–96.7%] | 1/5 | 1/5 |
| sobressalentes | 87 | 82 | 98.8% [93.4%–99.8%] | 100.0% [95.5%–100.0%] | 0/5 | 0/5 |
| valvulas | 72 | 66 | 100.0% [94.5%–100.0%] | 93.0% [84.6%–97.0%] | 0/1 | 0/1 |
| vedacao | 56 | 46 | 100.0% [92.1%–100.0%] | 81.8% [69.7%–89.8%] | 1/1 | 1/1 |
| mangueiras | 54 | 52 | 98.0% [89.7%–99.7%] | 96.2% [87.2%–99.0%] | 1/1 | 1/1 |
| conexoes_tubo | 29 | 26 | 100.0% [87.1%–100.0%] | 92.9% [77.4%–98.0%] | 0/1 | 0/1 |
| eletricos | 25 | 19 | 100.0% [83.2%–100.0%] | 76.0% [56.6%–88.5%] | 0/0 | 0/0 |
| nenhuma | 21 | 17 | 100.0% [81.6%–100.0%] | 85.0% [64.0%–94.8%] | 0/1 | 0/1 |
| epi | 16 | 12 | 100.0% [75.7%–100.0%] | 80.0% [54.8%–93.0%] | 0/1 | 0/1 |
| rolamentos | 12 | 9 | 100.0% [70.1%–100.0%] | 75.0% [46.8%–91.1%] | 0/0 | 0/0 |
| filtros | 10 | 9 | 100.0% [70.1%–100.0%] | 90.0% [59.6%–98.2%] | 0/0 | 0/0 |
| transmissao | 6 | 6 | 50.0% [18.8%–81.2%] | 100.0% [61.0%–100.0%] | 0/0 | 0/0 |
| solda_ferramenta | 4 | 0 | — | 0.0% [0.0%–49.0%] | 0/0 | 0/0 |

### Por estilo de entrada (é o recorte que o pedido tem e a base não)

| estilo | n gold | afirmados | precisão [IC 95%] | cobertura | invenção estrita | invenção permissiva |
|---|---:|---:|---|---|---:|---:|
| telegrafico | 214 | 205 | 99.0% [96.5%–99.7%] | 100.0% [98.2%–100.0%] | 1/10 | 1/10 |
| ficha | 155 | 154 | 98.7% [95.4%–99.6%] | 100.0% [97.6%–100.0%] | 1/2 | 1/2 |
| catalogo | 99 | 50 | 98.0% [89.5%–99.6%] | 51.0% [41.3%–60.7%] | 0/1 | 0/1 |
| email_longo | 94 | 91 | 100.0% [95.9%–100.0%] | 98.9% [94.0%–99.8%] | 1/3 | 1/3 |

### Por fonte do valor — qual camada erra

| fonte | n gold | afirmados | precisão [IC 95%] | cobertura | invenção estrita | invenção permissiva |
|---|---:|---:|---|---|---:|---:|
| acordo | 308 | 308 | 100.0% [98.8%–100.0%] | 100.0% [98.8%–100.0%] | 1/1 | 1/1 |
| gazetteer | 70 | 70 | 98.6% [92.2%–99.7%] | 100.0% [94.7%–100.0%] | 1/1 | 1/1 |
| rotulo | 63 | 63 | 100.0% [94.3%–100.0%] | 100.0% [94.3%–100.0%] | 0/0 | 0/0 |
| sem_decisao | 40 | 0 | — | 0.0% [0.0%–8.8%] | 0/0 | 0/0 |
| bert | 26 | 26 | 96.2% [81.1%–99.3%] | 100.0% [87.1%–100.0%] | 0/0 | 0/0 |
| - | 22 | 0 | — | 0.0% [0.0%–29.9%] | 0/13 | 0/13 |
| llm | 14 | 14 | 100.0% [77.2%–100.0%] | 100.0% [77.2%–100.0%] | 1/1 | 1/1 |
| dominio | 9 | 9 | 100.0% [70.1%–100.0%] | 100.0% [70.1%–100.0%] | 0/0 | 0/0 |
| sinonimo | 4 | 4 | 100.0% [51.0%–100.0%] | 100.0% [51.0%–100.0%] | 0/0 | 0/0 |
| gramatica | 3 | 3 | 100.0% [43.8%–100.0%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |
| ordem_pdm | 3 | 3 | 0.0% [0.0%–56.2%] | 100.0% [43.8%–100.0%] | 0/0 | 0/0 |

### Por armadilha (um rótulo conta em cada armadilha do seu pedido)

| arm | n gold | afirmados | precisão [IC 95%] | cobertura | invenção estrita | invenção permissiva |
|---|---:|---:|---|---|---:|---:|
| minuscula | 562 | 500 | 99.0% [97.7%–99.6%] | 91.0% [88.3%–93.1%] | 3/16 | 3/16 |
| valor_indefinivel | 125 | 119 | 99.2% [95.4%–99.9%] | 95.9% [90.8%–98.3%] | 1/2 | 1/2 |
| polegada_aspas | 117 | 116 | 100.0% [96.8%–100.0%] | 100.0% [96.8%–100.0%] | 1/2 | 1/2 |
| ruido_cortesia | 88 | 85 | 100.0% [95.6%–100.0%] | 98.8% [93.6%–99.8%] | 1/3 | 1/3 |
| classe_pressao_hash | 76 | 67 | 100.0% [94.6%–100.0%] | 88.2% [79.0%–93.6%] | 0/0 | 0/0 |
| contexto_aplicacao | 76 | 74 | 98.6% [92.7%–99.8%] | 100.0% [95.1%–100.0%] | 0/2 | 0/2 |
| virgula_decimal | 47 | 38 | 100.0% [90.4%–100.0%] | 80.0% [66.2%–89.1%] | 2/2 | 2/2 |
| rosca_fina | 42 | 40 | 100.0% [91.2%–100.0%] | 97.6% [87.4%–99.6%] | 0/1 | 0/1 |
| polegada_mista | 38 | 37 | 100.0% [90.6%–100.0%] | 100.0% [90.6%–100.0%] | 0/1 | 0/1 |
| ingles | 37 | 33 | 100.0% [89.3%–100.0%] | 91.4% [77.6%–97.0%] | 1/2 | 1/2 |
| multi_item | 32 | 32 | 100.0% [89.3%–100.0%] | 100.0% [89.3%–100.0%] | 0/0 | 0/0 |
| unidade_nao_bar | 30 | 30 | 100.0% [88.6%–100.0%] | 100.0% [88.6%–100.0%] | 0/0 | 0/0 |
| ordem_sem_rotulo | 26 | 18 | 100.0% [82.4%–100.0%] | 69.2% [50.0%–83.5%] | 0/0 | 0/0 |
| pn_ambiguo | 24 | 18 | 100.0% [82.4%–100.0%] | 78.3% [58.1%–90.3%] | 0/1 | 0/1 |
| rosca_bitola_comp | 21 | 21 | 100.0% [84.5%–100.0%] | 100.0% [84.5%–100.0%] | 0/0 | 0/0 |

## 3. Cada erro de valor

5 erro(s).

| pedido | classe | campo | gabarito | pipeline | fonte | evidência |
|---|---|---|---|---|---|---|
| SC-202600033 | PDM030 | REFERENCIA | `A157` | `4038MM` | ordem_pdm |  |
| SC-202600034 | PDM030 | REFERENCIA | `B146` | `3777MM` | ordem_pdm | b146 |
| SC-202600217 | PDM011 | TERMINAL B | `FEMEA RETA ORFS` | `FEMEA CURVA 90 GRAUS ORFS` | gazetteer | ORFS female |
| SC-202600239 | PDM110 | REFERENCIA FABRICANTE | `561-7310` | `561-7310 PARA A` | bert |  |
| SC-202600500 | PDM030 | REFERENCIA | `SPB 3650` | `3672MM` | ordem_pdm |  |

## 4. Cada invenção

3 preenchimento(s) sobre caixa que o gabarito diz vazia. A coluna `permissivo` diz quando a operação defenderia o valor.

| pedido | classe | campo | status gold | pipeline | permissivo | conta na permissiva? | fonte |
|---|---|---|---|---|---|---|---|
| SC-202600078 | PDM011 | TERMINAL B | AUSENTE | `FEMEA RETA JIC` | `—` | sim | gazetteer |
| SC-202600325 | PDM001 | ACABAMENTO | AUSENTE | `SEM ACABAMENTO` | `—` | sim | llm |
| SC-202600495 | PDM031 | DIAMETRO INTERNO | AUSENTE | `2,5MM` | `—` | sim | acordo |

## 5. Cada caixa perdida

49 caixa(s) que o gabarito define e o pipeline deixou vazia. Não é invenção — é leitura que faltou. Os três motivos são defeitos diferentes e pedem conserto diferente.

**(a) 41 por classe errada.** O pipeline deu outra classe ao pedido e por isso nunca considerou este atributo. Conserta-se na classificação, não na extração.

| pedido | classe gold | classe pipeline | caixas perdidas |
|---|---|---|---:|
| SC-202600065 | PDM060 | FORA_DO_PDM | 6 |
| SC-202600480 | PDM002 | PDM050 | 6 |
| SC-202600096 | PDM032 | FORA_DO_PDM | 5 |
| SC-202600330 | PDM043 | FORA_DO_PDM | 5 |
| SC-202600468 | PDM034 | FORA_DO_PDM | 5 |
| SC-202600087 | PDM050 | FORA_DO_PDM | 4 |
| SC-202600175 | PDM082 | FORA_DO_PDM | 4 |
| SC-202600269 | PDM070 | FORA_DO_PDM | 3 |
| SC-202600291 | PDM021 | FORA_DO_PDM | 3 |

**(b) 8 com a classe certa** — aqui a leitura é que falhou. Agrupado por atributo:

| campo | classe | n | estado do pipeline |
|---|---|---:|---|
| MATERIAL | PDM001 | 3 | PENDENTE |
| TERMINAL A | PDM011 | 2 | PENDENTE |
| TERMINAL B | PDM011 | 2 | PENDENTE |
| REFERENCIA FABRICANTE | PDM100 | 1 | PENDENTE |

Linha a linha:

| pedido | classe | campo | gabarito | estado | evidência no texto |
|---|---|---|---|---|---|
| SC-202600141 | PDM011 | TERMINAL A | `FEMEA RETA JIC` | PENDENTE | JIC female swivel |
| SC-202600141 | PDM011 | TERMINAL B | `FEMEA CURVA 90 GRAUS JIC` | PENDENTE | JIC female 90° elbow |
| SC-202600279 | PDM011 | TERMINAL A | `FEMEA RETA DKO` | PENDENTE | DKOL female |
| SC-202600279 | PDM011 | TERMINAL B | `FEMEA RETA DKO` | PENDENTE | DKOL female |
| SC-202600286 | PDM001 | MATERIAL | `ACO CARBONO` | PENDENTE | carbon steel |
| SC-202600424 | PDM100 | REFERENCIA FABRICANTE | `LE 3269` | PENDENTE |  |
| SC-202600453 | PDM001 | MATERIAL | `ACO CARBONO` | PENDENTE | carbon steel |
| SC-202600473 | PDM001 | MATERIAL | `ACO CARBONO` | PENDENTE | carbon steel |

## 6. Limitações deste gabarito

- **Só 16 das 562 caixas do gabarito (2.8%) são AUSENTE ou INDEFINIVEL**, contra os 25% que o `PROMPT_gabarito_caracteristicas.md` pede. Não é falha do sorteio: os 520 pedidos chegam quase completos contra o PDM, ao contrário da base (onde 78,5% da referência do fabricante é vazia). Forçar um estrato de pedido incompleto encheria o denominador de um caso raro e daria uma taxa de invenção que não vale para a entrada real. A consequência é que o IC da invenção é largo — leia o intervalo, não a média.
- **A conversão de pressão não é exercida.** Os pedidos com PSI são todos de mangueira montada (PDM011), classe em que `PRESSAO TRABALHO` não é obrigatória. Para medir conversão de unidade seria preciso sortear PDM010, 012, 013 ou 014, que não aparecem nestes 120.
- **Três armadilhas da base não existem no pedido** e estão com zero casos nos 520: `polegada_in`, `abrev_ambigua` e `equivalencia`.
- **BERT e LLM desligados** na execução medida: `artefatos/modelo_bert` está vazio e a camada de LLM custa dinheiro. Estes são números do piso (regras, gazetteer, gramática e dicionário aprendido).
- **A anotação é de um LLM, em duas passadas não independentes.** `revisao_humana_pedidos.csv` tem as linhas que uma pessoa precisa conferir; até lá, provisório.

