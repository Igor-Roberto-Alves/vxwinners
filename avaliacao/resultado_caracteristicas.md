# Avaliação do pipeline contra o conjunto-ouro de características

Gabarito: `gold_caracteristicas.csv` (1131 rótulos de atributo), `gold_classe.csv` (240 itens), `gold_juncao.csv` (150 pares).  
Pipeline: `artefatos/decisoes_base.jsonl` + `artefatos/saneado_base.csv`.

Precisão = acertos / (acertos + erros) com IC 95% de Wilson. Cobertura = preenchidos / rótulos DEFINIDO do gold. Invenção = preencheu onde o gold diz AUSENTE ou INDEFINÍVEL.

## 1. Resumo

| recorte | itens | rotulos | precisao (IC 95%) | cobertura | erros | absteve | invencao |
|---|---|---|---|---|---|---|---|
| geral | 232 | 1131 | 97.5% [96%–98%] | 92.6% | 24 | 78 | 19/84 (23%) |

Vereditos: ABSTENCAO_CORRETA=65, ABSTEVE=78, ACERTO=945, ERRO=24, INVENCAO=19

Atributos preenchidos fora do universo do gold (classe divergente): 189

## 2. Por atributo

| recorte | itens | rotulos | precisao (IC 95%) | cobertura | erros | absteve | invencao |
|---|---|---|---|---|---|---|---|
| MATERIAL | 100 | 100 | 88.9% [80%–94%] | 87.1% | 9 | 12 | 1/7 (14%) |
| DIAMETRO NOMINAL | 87 | 87 | 97.6% [92%–99%] | 98.8% | 2 | 1 | 0/4 (0%) |
| CLASSE PRESSAO | 79 | 79 | 100.0% [95%–100%] | 100.0% | 0 | 0 | 0/3 (0%) |
| CONEXAO | 63 | 63 | 100.0% [93%–100%] | 100.0% | 0 | 0 | 9/15 (60%) |
| TIPO | 53 | 53 | 100.0% [93%–100%] | 94.1% | 0 | 3 | 0/2 (0%) |
| COMPRIMENTO | 49 | 49 | 100.0% [92%–100%] | 93.9% | 0 | 3 | 0/0 |
| NORMA | 44 | 44 | 100.0% [91%–100%] | 92.9% | 0 | 3 | 0/2 (0%) |
| ACABAMENTO | 39 | 39 | 100.0% [90%–100%] | 97.1% | 0 | 1 | 0/4 (0%) |
| BITOLA | 31 | 31 | 100.0% [89%–100%] | 100.0% | 0 | 0 | 0/0 |
| CLASSE RESISTENCIA | 31 | 31 | 100.0% [88%–100%] | 93.1% | 0 | 2 | 0/2 (0%) |
| MATERIAL CORPO | 28 | 28 | 95.0% [76%–99%] | 90.9% | 1 | 2 | 1/6 (17%) |
| DIAMETRO INTERNO | 25 | 25 | 95.0% [76%–99%] | 83.3% | 1 | 4 | 0/1 (0%) |
| DIAMETRO REDUZIDO | 24 | 24 | 95.7% [79%–99%] | 100.0% | 1 | 0 | 0/1 (0%) |
| ACIONAMENTO | 23 | 23 | 93.3% [70%–99%] | 75.0% | 1 | 5 | 1/3 (33%) |
| MATERIAL TERMINAIS | 22 | 22 | 100.0% [82%–100%] | 85.7% | 0 | 3 | 0/1 (0%) |
| TERMINAL A | 22 | 22 | 82.4% [59%–94%] | 94.4% | 3 | 1 | 2/4 (50%) |
| TERMINAL B | 22 | 22 | 84.6% [58%–96%] | 72.2% | 2 | 5 | 3/4 (75%) |
| ROSCA | 21 | 21 | 100.0% [85%–100%] | 100.0% | 0 | 0 | 0/0 |
| REFERENCIA | 20 | 20 | 82.4% [59%–94%] | 94.4% | 3 | 1 | 0/2 (0%) |
| FOLGA | 14 | 14 | 100.0% [77%–100%] | 92.9% | 0 | 1 | 0/0 |
| APLICACAO | 14 | 14 | 100.0% [76%–100%] | 92.3% | 0 | 1 | 1/1 (100%) |
| ANEL INTERNO | 13 | 13 | 100.0% [76%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| ENCHIMENTO | 13 | 13 | 100.0% [68%–100%] | 61.5% | 0 | 5 | 0/0 |
| MATERIAL FITA | 13 | 13 | 100.0% [72%–100%] | 100.0% | 0 | 0 | 0/3 (0%) |
| FABRICANTE | 13 | 13 | 100.0% [76%–100%] | 92.3% | 0 | 1 | 0/0 |
| REFERENCIA FABRICANTE | 13 | 13 | 100.0% [74%–100%] | 91.7% | 0 | 1 | 0/1 (0%) |
| CORRENTE NOMINAL | 13 | 13 | 100.0% [76%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| VEDACAO SEDE | 12 | 12 | 100.0% [72%–100%] | 90.9% | 0 | 1 | 0/1 (0%) |
| DIAMETRO EIXO | 11 | 11 | 100.0% [65%–100%] | 70.0% | 0 | 3 | 1/1 (100%) |
| MODELO EQUIPAMENTO | 10 | 10 | 100.0% [68%–100%] | 100.0% | 0 | 0 | 0/2 (0%) |
| COR | 10 | 10 | 100.0% [72%–100%] | 100.0% | 0 | 0 | 0/0 |
| VEDACAO | 9 | 9 | 100.0% [57%–100%] | 55.6% | 0 | 4 | 0/0 |
| DIAMETRO ALOJAMENTO | 9 | 9 | 100.0% [65%–100%] | 77.8% | 0 | 2 | 0/0 |
| LARGURA | 9 | 9 | 100.0% [68%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| PARA PARAFUSO | 8 | 8 | 100.0% [61%–100%] | 85.7% | 0 | 1 | 0/1 (0%) |
| FURO | 8 | 8 | 100.0% [51%–100%] | 50.0% | 0 | 4 | 0/0 |
| ISOLACAO | 8 | 8 | 100.0% [65%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| NUMERO CONDUTORES | 8 | 8 | 100.0% [68%–100%] | 100.0% | 0 | 0 | 0/0 |
| SECAO | 8 | 8 | 100.0% [65%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| TENSAO ISOLAMENTO | 8 | 8 | 100.0% [68%–100%] | 100.0% | 0 | 0 | 0/0 |
| TIPO CABECA | 7 | 7 | 100.0% [44%–100%] | 42.9% | 0 | 4 | 0/0 |
| POLOS | 7 | 7 | 100.0% [65%–100%] | 100.0% | 0 | 0 | 0/0 |
| TAMANHO | 7 | 7 | 100.0% [65%–100%] | 100.0% | 0 | 0 | 0/0 |
| PASSAGEM | 7 | 7 | 100.0% [57%–100%] | 100.0% | 0 | 0 | 0/2 (0%) |
| ESPESSURA | 6 | 6 | 100.0% [61%–100%] | 100.0% | 0 | 0 | 0/0 |
| TIPO FACE | 6 | 6 | 100.0% [61%–100%] | 100.0% | 0 | 0 | 0/0 |
| CAPACIDADE INTERRUPCAO | 6 | 6 | 100.0% [61%–100%] | 100.0% | 0 | 0 | 0/0 |
| PRESSAO TRABALHO | 6 | 6 | 83.3% [44%–97%] | 100.0% | 1 | 0 | 0/0 |
| MATERIAL DISCO | 5 | 5 | 100.0% [34%–100%] | 66.7% | 0 | 1 | 0/2 (0%) |
| TIPO CORPO | 5 | 5 | 100.0% [51%–100%] | 80.0% | 0 | 1 | 0/0 |
| CURVA | 5 | 5 | 100.0% [57%–100%] | 100.0% | 0 | 0 | 0/0 |
| CASTELO | 5 | 5 | 100.0% [34%–100%] | 66.7% | 0 | 1 | 0/2 (0%) |
| DISTANCIA SENSORA | 4 | 4 | 100.0% [51%–100%] | 100.0% | 0 | 0 | 0/0 |
| MONTAGEM | 4 | 4 | 100.0% [51%–100%] | 100.0% | 0 | 0 | 0/0 |
| ROSCA CORPO | 4 | 4 | 100.0% [44%–100%] | 75.0% | 0 | 1 | 0/0 |
| SAIDA | 4 | 4 | 100.0% [51%–100%] | 100.0% | 0 | 0 | 0/0 |
| FACE | 4 | 4 | 100.0% [51%–100%] | 100.0% | 0 | 0 | 0/0 |
| SCHEDULE | 3 | 3 | 100.0% [44%–100%] | 100.0% | 0 | 0 | 0/0 |
| DIAMETRO | 3 | 3 | 100.0% [44%–100%] | 100.0% | 0 | 0 | 0/0 |
| SECAO CABO | 3 | 3 | 100.0% [44%–100%] | 100.0% | 0 | 0 | 0/0 |
| DIAMETRO EXTERNO | 3 | 3 | 100.0% [44%–100%] | 100.0% | 0 | 0 | 0/0 |
| CONTATOS AUXILIARES | 2 | 2 | 100.0% [34%–100%] | 100.0% | 0 | 0 | 0/0 |
| CORRENTE AC3 | 2 | 2 | 100.0% [34%–100%] | 100.0% | 0 | 0 | 0/0 |
| TENSAO BOBINA | 2 | 2 | 100.0% [34%–100%] | 100.0% | 0 | 0 | 0/0 |
| BASE | 2 | 2 | 100.0% [34%–100%] | 100.0% | 0 | 0 | 0/0 |
| POTENCIA | 2 | 2 | 100.0% [21%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| TEMPERATURA COR | 2 | 2 | 100.0% [34%–100%] | 100.0% | 0 | 0 | 0/0 |
| TENSAO | 2 | 2 | 100.0% [21%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| REFORCO | 2 | 2 | 100.0% [34%–100%] | 100.0% | 0 | 0 | 0/0 |
| GRAO | 1 | 1 | 100.0% [21%–100%] | 100.0% | 0 | 0 | 0/0 |
| FAIXA AJUSTE | 1 | 1 | 100.0% [21%–100%] | 100.0% | 0 | 0 | 0/0 |
| CLASSIFICACAO AWS | 1 | 1 | 100.0% [21%–100%] | 100.0% | 0 | 0 | 0/0 |
| HASTE | 1 | 1 | 100.0% [21%–100%] | 100.0% | 0 | 0 | 0/0 |

## 3. Por família de classe

| recorte | itens | rotulos | precisao (IC 95%) | cobertura | erros | absteve | invencao |
|---|---|---|---|---|---|---|---|
| conexoes | 40 | 188 | 94.1% [90%–97%] | 96.0% | 10 | 7 | 0/11 (0%) |
| eletricos | 29 | 125 | 100.0% [97%–100%] | 99.2% | 0 | 1 | 0/6 (0%) |
| fixadores | 39 | 228 | 99.0% [96%–100%] | 93.1% | 2 | 15 | 1/11 (9%) |
| mangueiras | 28 | 158 | 94.6% [89%–97%] | 88.4% | 7 | 17 | 6/12 (50%) |
| outras | 10 | 36 | 100.0% [90%–100%] | 94.4% | 0 | 2 | 0/0 |
| rolamentos | 20 | 52 | 91.9% [79%–97%] | 74.0% | 3 | 13 | 0/2 (0%) |
| sobressalentes | 10 | 40 | 100.0% [90%–100%] | 91.9% | 0 | 3 | 0/3 (0%) |
| valvulas | 28 | 164 | 98.4% [94%–100%] | 91.0% | 2 | 12 | 11/30 (37%) |
| vedacao | 28 | 140 | 100.0% [97%–100%] | 93.9% | 0 | 8 | 1/9 (11%) |

## 4. Por estilo de texto

| recorte | itens | rotulos | precisao (IC 95%) | cobertura | erros | absteve | invencao |
|---|---|---|---|---|---|---|---|
| estruturado | 130 | 633 | 97.6% [96%–99%] | 92.8% | 13 | 43 | 7/39 (18%) |
| telegrafico | 102 | 498 | 97.4% [95%–99%] | 92.3% | 11 | 35 | 12/45 (27%) |

## 5. Por armadilha

| recorte | itens | rotulos | precisao (IC 95%) | cobertura | erros | absteve | invencao |
|---|---|---|---|---|---|---|---|
| (sem armadilha) | 19 | 84 | 98.5% [92%–100%] | 87.0% | 1 | 10 | 0/7 (0%) |
| abrev_ambigua | 16 | 84 | 100.0% [95%–100%] | 94.8% | 0 | 4 | 4/7 (57%) |
| classe_pressao_hash | 75 | 382 | 97.0% [95%–98%] | 95.4% | 10 | 16 | 10/36 (28%) |
| curta_truncada | 146 | 719 | 97.7% [96%–99%] | 91.8% | 14 | 55 | 13/51 (25%) |
| grupo_errado | 44 | 211 | 93.6% [89%–96%] | 85.1% | 11 | 30 | 0/10 (0%) |
| ordem_sem_rotulo | 9 | 33 | 92.9% [77%–98%] | 87.5% | 2 | 4 | 0/1 (0%) |
| pn_ambiguo | 10 | 36 | 100.0% [90%–100%] | 100.0% | 0 | 0 | 0/1 (0%) |
| polegada_aspas | 35 | 192 | 94.3% [90%–97%] | 91.9% | 9 | 14 | 2/19 (11%) |
| polegada_in | 21 | 95 | 95.0% [88%–98%] | 92.0% | 4 | 7 | 1/8 (12%) |
| polegada_mista | 16 | 80 | 98.5% [92%–100%] | 91.9% | 1 | 6 | 0/6 (0%) |
| rosca_bitola_comp | 12 | 76 | 98.5% [92%–100%] | 94.4% | 1 | 4 | 1/4 (25%) |
| rosca_fina | 9 | 61 | 100.0% [94%–100%] | 98.3% | 0 | 1 | 0/3 (0%) |
| unidade_nao_bar | 11 | 58 | 96.1% [87%–99%] | 98.1% | 2 | 1 | 3/6 (50%) |
| valor_indefinivel | 39 | 203 | 95.9% [92%–98%] | 92.5% | 7 | 14 | 5/17 (29%) |
| virgula_decimal | 26 | 101 | 97.9% [93%–99%] | 94.9% | 2 | 5 | 1/2 (50%) |

## 6. Por fonte do valor

| recorte | itens | rotulos | precisao (IC 95%) | cobertura | erros | absteve | invencao |
|---|---|---|---|---|---|---|---|
| (sem decisao) | 14 | 35 | — | 0.0% | 0 | 32 | 0/3 (0%) |
| (vazio) - | 50 | 59 | — | 0.0% | 0 | 10 | 0/49 (0%) |
| (vazio) llm_deteccao | 47 | 49 | — | 0.0% | 0 | 36 | 0/13 (0%) |
| acordo | 216 | 548 | 99.8% [99%–100%] | 100.0% | 1 | 0 | 0/0 |
| aprendido | 52 | 70 | 76.4% [64%–86%] | 100.0% | 13 | 0 | 15/15 (100%) |
| bert | 12 | 12 | 75.0% [47%–91%] | 100.0% | 3 | 0 | 0/0 |
| bert_desempata | 3 | 3 | 100.0% [34%–100%] | 100.0% | 0 | 0 | 1/1 (100%) |
| coluna_erp | 5 | 5 | 100.0% [57%–100%] | 100.0% | 0 | 0 | 0/0 |
| dominio | 7 | 8 | 100.0% [65%–100%] | 100.0% | 0 | 0 | 1/1 (100%) |
| gazetteer | 54 | 72 | 95.7% [88%–99%] | 100.0% | 3 | 0 | 2/2 (100%) |
| gramatica | 20 | 20 | 100.0% [84%–100%] | 100.0% | 0 | 0 | 0/0 |
| llm | 9 | 10 | 100.0% [72%–100%] | 100.0% | 0 | 0 | 0/0 |
| llm_deteccao | 8 | 8 | 100.0% [68%–100%] | 100.0% | 0 | 0 | 0/0 |
| ordem_pdm | 2 | 3 | 0.0% [0%–56%] | 100.0% | 3 | 0 | 0/0 |
| regra_pdm_2 | 24 | 44 | 100.0% [92%–100%] | 100.0% | 0 | 0 | 0/0 |
| rotulo | 72 | 110 | 99.1% [95%–100%] | 100.0% | 1 | 0 | 0/0 |
| sinonimo | 70 | 75 | 100.0% [95%–100%] | 100.0% | 0 | 0 | 0/0 |

## 7. Classe do item

Acerto de classe: **218/240** (90.8% [87%–94%]).

### Matriz de confusão — arruelas (8 itens do gold)

| gold \ pipeline | PDM004 | PDM005 | PDM082 |
|---|---|---|---|
| PDM004 | 3 | 0 | 1 |
| PDM005 | 0 | 4 | 0 |

### Matriz de confusão — conexoes_tubo (48 itens do gold)

| gold \ pipeline | PDM050 |
|---|---|
| FORA_DO_PDM | 8 |
| PDM050 | 40 |

### Matriz de confusão — juntas (19 itens do gold)

| gold \ pipeline | PDM033 | PDM034 |
|---|---|---|
| PDM033 | 13 | 0 |
| PDM034 | 0 | 6 |

### Matriz de confusão — mangueiras (28 itens do gold)

| gold \ pipeline | PDM011 | PDM012 | PDM013 | PDM014 | PDM090 | PDM110 |
|---|---|---|---|---|---|---|
| PDM011 | 20 | 0 | 0 | 0 | 1 | 1 |
| PDM012 | 0 | 2 | 0 | 0 | 0 | 0 |
| PDM013 | 0 | 0 | 3 | 0 | 0 | 0 |
| PDM014 | 0 | 0 | 0 | 1 | 0 | 0 |

### Matriz de confusão — parafusos (24 itens do gold)

| gold \ pipeline | PDM001 | PDM002 |
|---|---|---|
| PDM001 | 17 | 0 |
| PDM002 | 4 | 3 |

### Matriz de confusão — rolamentos (20 itens do gold)

| gold \ pipeline | PDM020 | PDM021 | PDM022 |
|---|---|---|---|
| PDM020 | 9 | 0 | 0 |
| PDM021 | 1 | 4 | 0 |
| PDM022 | 0 | 0 | 4 |
| PDM023 | 2 | 0 | 0 |

### Matriz de confusão — valvulas (28 itens do gold)

| gold \ pipeline | PDM040 | PDM041 | PDM042 | PDM043 | PDM044 | PDM082 |
|---|---|---|---|---|---|---|
| PDM040 | 7 | 0 | 0 | 0 | 0 | 0 |
| PDM041 | 2 | 3 | 0 | 0 | 0 | 0 |
| PDM042 | 0 | 0 | 6 | 0 | 0 | 0 |
| PDM043 | 0 | 0 | 0 | 5 | 0 | 0 |
| PDM044 | 0 | 0 | 0 | 0 | 4 | 1 |

### Erros de classe

| código | gold | pipeline | estado | texto cru |
|---|---|---|---|---|
| 10072893 | FORA_DO_PDM | PDM050 | SANEADO | TAMPAO 6000# ROSCA NPT ASME B16.11 |
| 10858863 | PDM002 | PDM001 | PENDENTE | PARAFUSO  SEXTAVADO ALLEN CILINDRICA M14X70 12.9 ACO ESPECIAL ZINC BRANCO |
| 11889917 | PDM002 | PDM001 | PENDENTE | PARAF. SEXTAVADO ALLEN ESCAREADA M 16X70 12.9 ACO ESPECIAL OXIDADO |
| 13687511 | PDM023 | PDM020 | SANEADO | CAIXA MANCAL COM TIPO PEDESTAL COM ROLAMENTO, FURO 75MM, COM MATERIAL CAIXA FERRO FUNDIDO |
| 14407539 | FORA_DO_PDM | PDM050 | SANEADO | TAMPAO, PADRAO:ASME B16.11, CLASSE:6000#, A182 F316, TIPO CONEXAO:SW, DN:1/4POL |
| 14848482 | FORA_DO_PDM | PDM050 | SANEADO | TAMPAO, BITOLA:1POL, CL:6000#, MATERIAL:A105, EXTREMIDADES:RSC NPT, NORMA CONSTRUCAO:ASME  |
| 15409091 | PDM011 | PDM110 | SANEADO | MANGUEIRA HIDRAULICA MONTADA; NORMA: SAE 100R2AT; DIAMETRO INTERNO: 3/8POL; PRESSAO TRABAL |
| 15642667 | PDM011 | PDM090 | SANEADO | MANG. HIDRAULICA MONTADA; PADRAO: EN 853 2SN; DIAM INT: 1.1/4"; PRESSAO MAX: 1815PSI; C: 5 |
| 18081854 | PDM023 | PDM020 | SANEADO | CAIXA MANCAL PEDESTAL COM ROLAMENTO 45 MM |
| 18612778 | PDM044 | PDM082 | SANEADO | VALV. BORB, DIAM NOMINAL:4 IN, TIPO CORPO:LUG, CORPO:ACO CARBONO FUNDIDO A216 WCB, MATERIA |
| 19182839 | PDM021 | PDM020 | SANEADO | ROLAMENTO AUTOCOMPENSADOR ROL 22206E DIAMETRO 30MM 62,0MM ESPESSURA DE 20 MM COM FURO CILI |
| 19396126 | FORA_DO_PDM | PDM050 | SANEADO | TAMPAO, DN:DN8, RATING:150#, MAT:FERRO MALEAVEL GALVANIZADO, CONEXAO:ROSCA BSP, CONF:NBR 6 |
| 19675722 | FORA_DO_PDM | PDM050 | PENDENTE | TAMPAO, MAT:INOX 316, CL:6000#, CONEXAO:ROSCA |
| 20014703 | PDM110 | PDM090 | PENDENTE | PISTAO; FAB:SANDVIK; APLICACAO:PERFURATRIZ; REF FABRICANTE:785.340790; MATERIAL:ACO CARBON |
| 21643278 | PDM002 | PDM001 | SANEADO | PARAFUSO CAB SEXTAVADA INTERNO, TIPO CABECA:CILINDRICA, DIAMETRO:M-10, COMPR:140MM, RESIST |
| 22145251 | FORA_DO_PDM | PDM050 | SANEADO | TAMPAO, CL:6000#, DIAM:3/4", MATERIAL:A182 F316, CONEXAO:ROSCADA NPT, CONF:ASME B16.11 |
| 26369766 | FORA_DO_PDM | PDM050 | PENDENTE | TAMPAO, DIAM:1 IN, CLASSE:3000#, INOX, EXTREMIDADE:ENCAIXE SOLDA, CONF:ASME B16.11 |
| 27089652 | FORA_DO_PDM | PDM050 | PENDENTE | TAMPAO, DIAM NOMINAL:1/2", PRESSAO NOMINAL:3000#, MATERIAL:ACO CARBONO, LIGACAO:SW |
| 27147155 | PDM002 | PDM001 | SANEADO | PARAFUSO CAB SEXTAVADA INTERNO, CLASSE RESISTENCIA:A2-70, BITOLA:M-20, COMPRIMENTO:110 MM, |
| 27542120 | PDM041 | PDM040 | PENDENTE | VALV. GAV, DIAMETRO:3/4 IN, CLASSE PRESSAO:150#, MAT CORPO:ACO INOX, TIPO CONEXAO:PONTAS C |
| 28638567 | PDM041 | PDM040 | SANEADO | VALVULA GAV DN200 300# FLANGES ROSCADO REDUTOR MANUAL |
| 28897955 | PDM004 | PDM082 | REVISAO_HUMANA | ARRUELA LISA; PARA PARAFUSO: M12; DIAMETRO INTERNO: 13MM; DIAMETRO EXTERNO: 37MM; ESPESSUR |

## 8. Junção de duplicados

Pares decidíveis: 140 (MESMO_ITEM=67, ITENS_DIFERENTES=73); INDETERMINADO no gold: 10 (o pipeline juntou 4 deles).

| métrica | valor |
|---|---|
| precisão | 98.5% [92%–100%]  (65/66) |
| recall | 97.0% [90%–99%]  (65/67) |
| verdadeiros positivos | 65 |
| falsos positivos | 1 |
| falsos negativos | 2 |
| verdadeiros negativos | 72 |

### Por fonte do par

| fonte do par | pares | decidíveis | acerto (IC 95%) | juntou errado | deixou passar |
|---|---|---|---|---|---|
| mesma_chave | 70 | 66 | 98.5% [92%–100%] | 1 | 0 |
| texto_parecido | 30 | 28 | 96.4% [82%–99%] | 0 | 1 |
| um_atributo | 50 | 46 | 97.8% [89%–100%] | 0 | 1 |

### Pares errados

- **P033** (um_atributo): gold `MESMO_ITEM`, pipeline separou  
  `25637537`: PARAFUSO SEXTAVADO METRICA M12X130 A2-70 NATURAL DIN 931  
  `26722816`: PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12; COMPRIMENTO: 130MM; CLASSE RESISTENCIA: A2-70; MATERIAL: ACO INOX 304; ACABAMENTO: NATURAL; NO  
  gold: A2-70 implica inox 304 nas opcoes do PDM001
- **P081** (texto_parecido): gold `MESMO_ITEM`, pipeline separou  
  `26560744`: CORREIA TRAPEZOIDAL, SPZ, MODELO: SPZ 2725, COMPRIMENTO: 2738MM  
  `27354718`: CORREIA TRAPEZOIDAL, MODELO:SPZ 2725, COMPRIMENTO:2738MM  
  gold: a referencia SPZ 2725 ja carrega o perfil SPZ
- **P105** (mesma_chave): gold `ITENS_DIFERENTES`, pipeline juntou  
  `26438272`: PARAFUSO SEXTAVADO, ROSCA:METRICA GROSSA, BITOLA:M24, C:110MM, DIN 931, MATERIAL:AC CARBONO, REVESTIMENTO:GEOMET, GRAU:8.8  
  `27811753`: PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M24; COMPRIMENTO: 110MM; CLASSE RESISTENCIA: 8.8; MATERIAL: ACO CARBONO; ACABAMENTO: ZINCADO AMAREL  
  gold: geomet = organometalico, acabamento diferente

## 9. Cada erro de característica

- **27542120 ACIONAMENTO**: gold `VOLANTE`, pipeline `ALAVANCA` (fonte aprendido, confiança 0.8)  
  texto: VALV. GAV, DIAMETRO:3/4 IN, CLASSE PRESSAO:150#, MAT CORPO:ACO INOX, TIPO CONEXAO:PONTAS CHANFRADAS, ACIONAMENTO:VOLANTE  
  gold: ACIONAMENTO:VOLANTE | 
- **16249002 DIAMETRO INTERNO**: gold `1.1/4POL`, pipeline `20POL` (fonte rotulo, confiança 0.99)  
  texto: MANGUEIRA MONTADA HIDR, SAE 100R2AT, DIAM INT:-20, MATERIAL TERMINAIS:ACO ZINCADO, COMPRIMENTO:800MM, JIC FEMEA, TERM B:FEMEA RETA DKOL, PT:112KGF/CM2  
  gold: DIAM INT:-20 | dash -20 = 20/16 pol = 1.1/4POL
- **23167204 DIAMETRO NOMINAL**: gold `1POL`, pipeline `25.3/4POL` (fonte ordem_pdm, confiança 0.65)  
  texto: BUCHA REDUCAO BITOLA DE DN 25 3/4" COM CL 6000# MATERIAL DE INOX 316 TIPO CONEXAO ROSCA ASME B16.11  
  gold: BITOLA DE DN 25 | DN 25 = 1POL
- **28759306 DIAMETRO NOMINAL**: gold `2POL`, pipeline `1.1/4POL` (fonte ordem_pdm, confiança 0.65)  
  texto: BUCHA REDUCAO, DN:DN 50, DIAMETRO REDUZIDO:1,25POL, CLASSE PRESSAO:3000#, MAT:F316, EXTREMIDADES:RSC NPT  
  gold: DN:DN 50 | DN 50 = 2POL
- **23167204 DIAMETRO REDUZIDO**: gold `3/4POL`, pipeline `1POL` (fonte ordem_pdm, confiança 0.5)  
  texto: BUCHA REDUCAO BITOLA DE DN 25 3/4" COM CL 6000# MATERIAL DE INOX 316 TIPO CONEXAO ROSCA ASME B16.11  
  gold: DN 25 3/4" | segunda medida = diametro reduzido
- **10858863 MATERIAL**: gold `ACO LIGA`, pipeline `ACO CARBONO` (fonte aprendido, confiança 0.8)  
  texto: PARAFUSO  SEXTAVADO ALLEN CILINDRICA M14X70 12.9 ACO ESPECIAL ZINC BRANCO  
  gold: ACO ESPECIAL | 12.9 | decisao do adjudicador (R2): o texto traz material (ACO ESPECIAL) e a classe 12.9 do PDM002 so existe fora do inox (as opcoes inox sao A2-70 e A4-70), logo ACO LIGA e o unico valor possivel da lista
- **11109434 MATERIAL**: gold `ACO INOX FORJADO A182 F316`, pipeline `ACO INOX A403 WP316` (fonte aprendido, confiança 0.8)  
  texto: BUCHA REDUCAO, BITOLA:1POL, DIAMETRO REDUZIDO:3/4 IN, CLASSE:3000#, MAT:INOX 316, EXTREMIDADE:SOCKET WELD, NORMA CONSTRUCAO:ASME B16.11  
  gold: MAT:INOX 316 ... ASME B16.11 | inox 316 forjado 3000# B16.11 = A182 F316
- **11889917 MATERIAL**: gold `ACO LIGA`, pipeline `ACO CARBONO` (fonte aprendido, confiança 0.8)  
  texto: PARAF. SEXTAVADO ALLEN ESCAREADA M 16X70 12.9 ACO ESPECIAL OXIDADO  
  gold: ACO ESPECIAL | 12.9 | classe 12.9 so existe em aco liga; as outras opcoes do PDM002 sao inox
- **20043393 MATERIAL**: gold `ACO INOX FORJADO A182 F316`, pipeline `ACO INOX A403 WP316` (fonte aprendido, confiança 0.8)  
  texto: BUCHA REDUCAO 1.1/2" 1 1/4POL 3000# INOX 316 SOLDA ENCAIXE SW ASME B16.11  
  gold: INOX 316 SOLDA ENCAIXE SW ASME B16.11 | inox 316 com CLASSE 3000# e SW = forjado A182 F316
- **20084323 MATERIAL**: gold `ACO INOX FORJADO A182 F316`, pipeline `ACO INOX A403 WP316` (fonte aprendido, confiança 0.8)  
  texto: BUCHA REDUCAO, BITOLA:1 POL, DIAMETRO REDUZIDO:3/8", MAT:INOX 316, LIGACAO:SOLDA ENCAIXE  
  gold: MAT:INOX 316, LIGACAO:SOLDA ENCAIXE | as duas opcoes inox do PDM050 sao 316; solda de encaixe define a forjada A182 F316
- **20121043 MATERIAL**: gold `ACO INOX FORJADO A182 F316`, pipeline `ACO INOX A403 WP316` (fonte aprendido, confiança 0.8)  
  texto: CAP 3/4 IN 6000# INOX 316 ENCAIXE SOLDA ASME B16.11  
  gold: INOX 316 ENCAIXE SOLDA ASME B16.11 | inox 316 com CLASSE 6000# e encaixe solda = forjado A182 F316
- **22181613 MATERIAL**: gold `ACO INOX FORJADO A182 F316`, pipeline `ACO INOX A403 WP316` (fonte aprendido, confiança 0.8)  
  texto: BUCHA REDUCAO 1/2" 3/8" 3000# INOX 316 SOLDA ENCAIXE SW ASME B16.11  
  gold: INOX 316 SOLDA ENCAIXE SW ASME B16.11 | decisao do adjudicador (R3): classe 3000# com solda de encaixe e norma ASME B16.11 e conexao forjada; A403 WP316 e de solda de topo
- **23167204 MATERIAL**: gold `ACO INOX FORJADO A182 F316`, pipeline `ACO INOX A403 WP316` (fonte aprendido, confiança 0.8)  
  texto: BUCHA REDUCAO BITOLA DE DN 25 3/4" COM CL 6000# MATERIAL DE INOX 316 TIPO CONEXAO ROSCA ASME B16.11  
  gold: MATERIAL DE INOX 316 TIPO CONEXAO ROSCA ASME B16.11 | decisao do adjudicador (R3): classe 6000# com rosca e ASME B16.11 e conexao forjada A182 F316
- **25169236 MATERIAL**: gold `ACO INOX FORJADO A182 F316`, pipeline `ACO INOX A403 WP316` (fonte aprendido, confiança 0.8)  
  texto: BUCHA REDUCAO, DIAMETRO NOMINAL: DN8, CLASSE: 3000#, MATERIAL: INOX 316, TIPO CONEXAO: ENCAIXE SOLDA, ASME B16.11  
  gold: MATERIAL: INOX 316 ... ASME B16.11 | inox 316 em conexao forjada 3000# ASME B16.11 = A182 F316 (A403 WP316 e para solda de topo)
- **10046540 MATERIAL CORPO**: gold `FERRO FUNDIDO NODULAR`, pipeline `ACO INOX FUNDIDO A351 CF8M` (fonte gazetteer, confiança 0.98)  
  texto: VALVULA  BORBOLETA, DIAM: 6POL, TIPO CORPO: WAFER, FERRO FUNDIDO, MATERIAL DISCO: ACO INOX FUNDIDO A351 CF8M, NITRILICA, ACIONAMENTO: ATUADOR ELETRICO  
  gold: FERRO FUNDIDO | unico ferro fundido da lista do PDM044
- **26544330 PRESSAO TRABALHO**: gold `40,2BAR`, pipeline `41BAR` (fonte acordo, confiança 0.975)  
  texto: MANG. INDUSTRIAL, APLICACAO:AR COMPRIMIDO, MAT:EPDM, DIAMETRO:2POL, PRESSAO TRABALHO:41KGF/CM2, REFORCO:LONAS TEXTEIS  
  gold: PRESSAO TRABALHO:41KGF/CM2 | 41 KGF/CM2 x 0,980665 = 40,2 BAR
- **12970453 REFERENCIA**: gold `6008ZZ`, pipeline `6008` (fonte bert, confiança 0.729)  
  texto: ROLAMENTO  RIGIDO ESFERAS;CODIGO:6008 ZZ;DIAM INTERNO:40,0MM;DIAMETRO EXTERNO:68MM;L:15 MM;2 PLACAS METALICAS;FOLGA INTERNA:NORMAL  
  gold: CODIGO:6008 ZZ | formato do PDM liga o sufixo por hifen
- **14548232 REFERENCIA**: gold `60102RSC3`, pipeline `6010` (fonte bert, confiança 0.925)  
  texto: ROLAMENTO RIGIDO ESFERAS 6010 2RS/C3 50MM 80MM 16 MM 2RS C3  
  gold: 6010 2RS/C3 | formato do PDM: 6010-2RS/C3
- **20344522 REFERENCIA**: gold `63152RSC3`, pipeline `6315` (fonte bert, confiança 0.944)  
  texto: ROLAMENTO RIGIDO ESFERAS 6315 2RS/C3 75MM 160MM 37MM VEDADO C3  
  gold: 6315 2RS/C3 | 
- **10017018 TERMINAL A**: gold `FEMEA CURVA 45 GRAUS JIC`, pipeline `FEMEA RETA ORFS` (fonte gazetteer, confiança 0.98)  
  texto: MANGUEIRA HID MONTADA SAE 100R2AT 1/4 POL 5005PSI 2200 MM JIC FEMEA 45 FEMEA RETA ORFS ACO ZINCADO  
  gold: JIC FEMEA 45 | 45 = curva de 45 graus
- **27430680 TERMINAL A**: gold `FEMEA RETA BSP`, pipeline `FEMEA CURVA 90 GRAUS JIC` (fonte aprendido, confiança 0.8)  
  texto: MANG. HIDRAULICA MONTADA, NORMA:EN 856 4SP, DI:3/8 IN, PRESS TRAB:6455PSI, COMPRIMENTO:5000MM, TERM A:FEMEA BSP, TERMINAL B:FEM CURVA 90 JIC, MATERIAL  
  gold: TERM A:FEMEA BSP | a lista tem so FEMEA RETA BSP
- **29700768 TERMINAL A**: gold `FEMEA RETA BSP`, pipeline `FEMEA CURVA 90 GRAUS JIC` (fonte aprendido, confiança 0.8)  
  texto: MANGUEIRA HID MONT, EN 856 4SP, DIAM INTERNO:1/2", COMP:6000MM, TERMINAL A:FEMEA BSP, LADO B:JIC FEMEA 90, MATERIAL TERMINAIS:ACO CARBONO  
  gold: TERMINAL A:FEMEA BSP | a lista tem so FEMEA RETA BSP
- **23376554 TERMINAL B**: gold `FEMEA RETA DKO`, pipeline `FEMEA RETA JIC` (fonte gazetteer, confiança 0.98)  
  texto: MANGUEIRA HIDRAULICA MONTADA - CONF:EN 856 4SH - DIAM INT:2" - PRESS TRAB:250BAR - C:900 MM - TERM A:FEMEA RETA JIC 37 GRAUS - TERMINAL B:FEMEA RETA D  
  gold: TERMINAL B:FEMEA RETA DKOL | DKOL = serie leve do DKO
- **29700768 TERMINAL B**: gold `FEMEA CURVA 90 GRAUS JIC`, pipeline `FEMEA RETA BSP` (fonte aprendido, confiança 0.93)  
  texto: MANGUEIRA HID MONT, EN 856 4SP, DIAM INTERNO:1/2", COMP:6000MM, TERMINAL A:FEMEA BSP, LADO B:JIC FEMEA 90, MATERIAL TERMINAIS:ACO CARBONO  
  gold: LADO B:JIC FEMEA 90 | 

## 10. Cada invenção

- **18266130 ACIONAMENTO** (gold INDEFINIVEL): pipeline `ALAVANCA` (fonte aprendido, confiança 0.8)  
  texto: VALV. ESFERA, METAL-METAL, CLASSE:150#, A216 WCB, EXTREMIDADE:FLANGEADA, PASSAGEM:PASSAGEM PLENA, DIAM NOMINAL:3/4POL, ACIONAMENTO:MANUAL  
  gold: manual nao decide entre ALAVANCA e REDUTOR, ambos manuais
- **29452826 APLICACAO** (gold INDEFINIVEL): pipeline `AR COMPRIMIDO` (fonte bert_desempata, confiança 0.88)  
  texto: MANGUEIRA MULTIUSO AR COMPRIMIDO EPDM 3/4POL 290 PSI LONAS TEXTEIS  
  gold: decisao do adjudicador: MULTIUSO e AR COMPRIMIDO sao dois valores da lista do PDM012 e o texto traz os dois sem hierarquia; escolher um e sorteio, logo o atributo e indefinivel
- **13203081 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE RF` (fonte aprendido, confiança 0.8)  
  texto: VALVULA ESFERA 6POL 150# ACO CARBONO FUNDIDO A216 WCB FLANGES TEFLON REFORCADO MANOPLA  
  gold: FLANGES nao decide entre FLANGE FF e FLANGE RF
- **14624421 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE RF` (fonte aprendido, confiança 0.8)  
  texto: VALVULA RETENCAO DN150 600# ACO INOX FUNDIDO A351 CF8M FLANGES PORTINHOLA  
  gold: FLANGES nao decide entre FLANGE FF e FLANGE RF
- **15099478 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE FF` (fonte aprendido, confiança 0.93)  
  texto: VALVULA GLOBO 300# WCB FLANGEADA VOLANTE  
  gold: flangeada nao decide entre FLANGE FF e FLANGE RF
- **18266130 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE FF` (fonte aprendido, confiança 0.93)  
  texto: VALV. ESFERA, METAL-METAL, CLASSE:150#, A216 WCB, EXTREMIDADE:FLANGEADA, PASSAGEM:PASSAGEM PLENA, DIAM NOMINAL:3/4POL, ACIONAMENTO:MANUAL  
  gold: flangeada nao decide entre FLANGE FF e FLANGE RF
- **19421041 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE FF` (fonte aprendido, confiança 0.93)  
  texto: VALV. RETENCAO, DN:DN 32, CLASSE:300#, MATERIAL:CF8M, TIPO CONEXAO:FLANGEADA, PORTINHOLA  
  gold: flangeada nao decide entre FLANGE FF e FLANGE RF
- **23044290 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE RF` (fonte aprendido, confiança 0.8)  
  texto: VALVULA  ESFERA, DIAMETRO:3", FULL BORE, CORPO:ACO INOX FUNDIDO A351 CF8M, TIPO CONEXAO:FLANGES, PRESSAO NOMINAL:300#, VEDACAO SEDE:METAL-METAL, ACION  
  gold: FLANGES nao decide entre FLANGE FF e FLANGE RF
- **23816864 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE RF` (fonte aprendido, confiança 0.8)  
  texto: VALVULA GLOBO; DIAMETRO NOMINAL:1,5POL; PRESSAO NOMINAL:300#; CORPO:A216 WCB; EXTREMIDADES:FLANGES  
  gold: FLANGES nao decide entre FLANGE FF e FLANGE RF
- **28478391 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE RF` (fonte aprendido, confiança 0.8)  
  texto: VALVULA ESFERA, ACIONAMENTO:ATUADOR PNEUM, MATERIAL:A216 WCB, CONEXAO:FLANGES, DIAMETRO NOMINAL:3"  
  gold: FLANGES nao decide entre FLANGE FF e FLANGE RF
- **28638567 CONEXAO** (gold INDEFINIVEL): pipeline `FLANGE RF` (fonte aprendido, confiança 0.8)  
  texto: VALVULA GAV DN200 300# FLANGES ROSCADO REDUTOR MANUAL  
  gold: FLANGES nao decide entre FLANGE FF e FLANGE RF
- **24496679 DIAMETRO EIXO** (gold AUSENTE): pipeline `135MM` (fonte dominio, confiança 0.85)  
  texto: RET. DIAMETRO ALOJAMENTO 135MM COM TIPO BA MAT DE FLUORELASTOMERO  
  gold: so o alojamento esta no texto
- **20504737 MATERIAL** (gold AUSENTE): pipeline `ACO CARBONO` (fonte aprendido, confiança 0.8)  
  texto: PARAFUSO HEXAGONAL MA M20X80 8.8 S/ACAB DIN 933  
  gold: decisao do adjudicador (R1): PARAFUSO HEXAGONAL MA M20X80 8.8 S/ACAB DIN 933 nao tem nenhuma palavra de material; deduzir ACO CARBONO da classe 8.8 e extrapolacao, e preencher conta como invencao
- **14692586 MATERIAL CORPO** (gold INDEFINIVEL): pipeline `ACO INOX FORJADO A182 F316` (fonte aprendido, confiança 0.8)  
  texto: VALVULA  ESFERA, DIAMETRO NOMINAL:1POL, 150#, MATERIAL:INOX 316, EXTREMIDADES:FLANGE RF, PASSAGEM:FULL BORE, ACIONAMENTO:MANOPLA, METAL-METAL  
  gold: inox 316 nao decide entre A351 CF8M (fundido) e A182 F316 (forjado)
- **15202078 TERMINAL A** (gold INDEFINIVEL): pipeline `FEMEA CURVA 90 GRAUS DKO` (fonte gazetteer, confiança 0.98)  
  texto: MANGUEIRA HIDR MONTADA EN 853 1SN, COM DIAM INT 1/2 IN, PT 2320 PSI, COMP DE 750MM, JIC FEMEA, FEMEA CURVA 90 GRAUS DKO, TERMINAIS DE ACO CARBONO ZINC  
  gold: JIC femea nao decide entre reta e curva 45/90
- **28718449 TERMINAL A** (gold INDEFINIVEL): pipeline `MACHO RETO NPT` (fonte aprendido, confiança 0.8)  
  texto: MANG HIDRAULICA MONT SAE 100R1AT 1.1/4POL 4500MM FEMEA DKO NPT MACHO ACO CARBONO ZINCADO  
  gold: femea DKO nao decide entre reta e curva 90
- **11848855 TERMINAL B** (gold INDEFINIVEL): pipeline `MACHO RETO NPT` (fonte gazetteer, confiança 0.98)  
  texto: MANGUEIRA HIDRAULICA MONT COM CONF EN 856 4SP, D.I. 1/2POL (-8), PT 6020PSI, COM COMP 750 MM, TERM A DE MACHO RETO NPT, LADO B DE FEMEA ORFS, MAT TERM  
  gold: femea ORFS nao decide entre reta e curva 90
- **25059059 TERMINAL B** (gold INDEFINIVEL): pipeline `FEMEA RETA JIC` (fonte aprendido, confiança 0.8)  
  texto: MANGUEIRA HID MONTADA, NORMA CONSTRUCAO EN 856 4SP, DIAM INT -8, PRESSAO 6020PSI, COMPR 2000 MM, FEM RETA JIC, TERM B JIC FEMEA, TERMINAIS ACO CARBONO  
  gold: JIC femea nao decide entre reta e curva 45/90
- **27846113 TERMINAL B** (gold AUSENTE): pipeline `FEMEA CURVA 90 GRAUS JIC` (fonte aprendido, confiança 0.8)  
  texto: MANGUEIRA HID MONTADA EN 853 2SN 1815 PSI 1800MM FEMEA 90G JIC ACO CARBONO  
  gold: so um terminal citado

## 11. Atributos preenchidos fora do universo do gold

Atributo que o pipeline preencheu porque escolheu outra classe; não entra na precisão, mas é consequência do erro de classe.

| código | atributo | valor | fonte | classe gold | classe pipeline |
|---|---|---|---|---|---|
| 10017018 | PRESSAO TRABALHO | 345,1BAR | gramatica | PDM011 | PDM011 |
| 10072893 | CLASSE PRESSAO | 6000# | acordo | FORA_DO_PDM | PDM050 |
| 10072893 | CONEXAO | ROSCA NPT | acordo | FORA_DO_PDM | PDM050 |
| 10072893 | NORMA | ASME B16.11 | acordo | FORA_DO_PDM | PDM050 |
| 10185788 | DIAMETRO EXTERNO | 140MM | acordo | PDM020 | PDM020 |
| 10185788 | DIAMETRO INTERNO | 65MM | acordo | PDM020 | PDM020 |
| 10185788 | LARGURA | 33MM | acordo | PDM020 | PDM020 |
| 10242631 | NORMA | ASME B16.20 | gazetteer | PDM033 | PDM033 |
| 10254470 | DIAMETRO EXTERNO | 100MM | acordo | PDM022 | PDM022 |
| 10254470 | DIAMETRO INTERNO | 55MM | acordo | PDM022 | PDM022 |
| 10254470 | LARGURA | 22,75MM | rotulo | PDM022 | PDM022 |
| 10257232 | NORMA | ASME B16.11 | acordo | PDM050 | PDM050 |
| 10272554 | NORMA | ASME B16.9 | acordo | PDM050 | PDM050 |
| 10361413 | NORMA | NBR 6943 | acordo | PDM050 | PDM050 |
| 10565956 | NORMA | DIN 985 | acordo | PDM003 | PDM003 |
| 10858863 | ROSCA | METRICA GROSSA | regra_pdm_2 | PDM002 | PDM001 |
| 10897046 | DIAMETRO EXTERNO | 62MM | acordo | PDM020 | PDM020 |
| 10897046 | DIAMETRO INTERNO | 30MM | acordo | PDM020 | PDM020 |
| 11109434 | NORMA | ASME B16.11 | acordo | PDM050 | PDM050 |
| 11166052 | NORMA | ASME B16.11 | acordo | PDM050 | PDM050 |
| 11247496 | CLASSE | GL/GG | gazetteer | PDM064 | PDM064 |
| 11731863 | NORMA | ASME B16.9 | acordo | PDM050 | PDM050 |
| 11848855 | PRESSAO TRABALHO | 415,1BAR | gramatica | PDM011 | PDM011 |
| 11889917 | ROSCA | METRICA GROSSA | regra_pdm_2 | PDM002 | PDM001 |
| 12970453 | DIAMETRO EXTERNO | 68MM | acordo | PDM020 | PDM020 |
| 12970453 | DIAMETRO INTERNO | 40MM | acordo | PDM020 | PDM020 |
| 12970453 | LARGURA | 15MM | acordo | PDM020 | PDM020 |
| 13065631 | DIAMETRO INTERNO | 10MM | acordo | PDM020 | PDM020 |
| 13210510 | DIAMETRO EXTERNO | 72MM | acordo | PDM004 | PDM004 |
| 13210510 | DIAMETRO INTERNO | 26MM | rotulo | PDM004 | PDM004 |
| 13210510 | ESPESSURA | 5MM | acordo | PDM004 | PDM004 |
| 13300117 | PRESSAO TRABALHO | 290BAR | acordo | PDM011 | PDM011 |
| 13420501 | NORMA | ASME B16.11 | acordo | PDM050 | PDM050 |
| 13614795 | CLASSE | GL/GG | gazetteer | PDM064 | PDM064 |
| 13687511 | DIAMETRO INTERNO | 75MM | dominio | PDM023 | PDM020 |
| 14105974 | NORMA | ASME B16.11 | gazetteer | PDM050 | PDM050 |
| 14205546 | NORMA | DIN 934 | acordo | PDM003 | PDM003 |
| 14297259 | DIAMETRO EXTERNO | 62MM | acordo | PDM022 | PDM022 |
| 14297259 | DIAMETRO INTERNO | 30MM | rotulo | PDM022 | PDM022 |
| 14297259 | LARGURA | 17,25MM | acordo | PDM022 | PDM022 |
| 14312408 | PRESSAO TRABALHO | 250BAR | acordo | PDM011 | PDM011 |
| 14407539 | CLASSE PRESSAO | 6000# | acordo | FORA_DO_PDM | PDM050 |
| 14407539 | CONEXAO | SOLDA ENCAIXE SW | sinonimo | FORA_DO_PDM | PDM050 |
| 14407539 | DIAMETRO NOMINAL | 1/4POL | rotulo | FORA_DO_PDM | PDM050 |
| 14407539 | MATERIAL | ACO INOX FORJADO A182 F316 | sinonimo | FORA_DO_PDM | PDM050 |
| 14407539 | NORMA | ASME B16.11 | rotulo | FORA_DO_PDM | PDM050 |
| 14458915 | DIAMETRO EXTERNO | 130MM | acordo | PDM021 | PDM021 |
| 14458915 | DIAMETRO INTERNO | 31MM | dominio | PDM021 | PDM021 |
| 14458915 | LARGURA | 31MM | acordo | PDM021 | PDM021 |
| 14548232 | DIAMETRO EXTERNO | 80MM | acordo | PDM020 | PDM020 |
| 14548232 | DIAMETRO INTERNO | 50MM | acordo | PDM020 | PDM020 |
| 14548232 | LARGURA | 16MM | acordo | PDM020 | PDM020 |
| 14571652 | FURO | 22,23MM | acordo | PDM081 | PDM081 |
| 14589488 | DIAMETRO EXTERNO | 56MM | rotulo | PDM004 | PDM004 |
| 14589488 | DIAMETRO INTERNO | 20MM | rotulo | PDM004 | PDM004 |
| 14848482 | CLASSE PRESSAO | 6000# | acordo | FORA_DO_PDM | PDM050 |
| 14848482 | CONEXAO | ROSCA NPT | sinonimo | FORA_DO_PDM | PDM050 |
| 14848482 | DIAMETRO NOMINAL | 1POL | acordo | FORA_DO_PDM | PDM050 |
| 14848482 | MATERIAL | ACO CARBONO FORJADO A105 | sinonimo | FORA_DO_PDM | PDM050 |
| 14848482 | NORMA | ASME B16.11 | rotulo | FORA_DO_PDM | PDM050 |

(+129 linhas)

