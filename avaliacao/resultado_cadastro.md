# Resultado: gabarito de cadastro (V2) — unidade, descrição e sobrevivente

Gerado por `avaliacao/evaluate_cadastro.py` em 2026-11-07 23:26, sobre `/home/igor-alves/clas/hack/vxwinners/artefatos`. Gabaritos: `gold_unidade.csv` (60), `gold_descricao.csv` (40), `gold_sobrevivente.csv` (30 clusters). Sorteio: `20_candidatos_cadastro.py` (semente 20261107); adjudicação: `21_adjudicar_cadastro.py`.

IC = intervalo de confiança de 95% de Wilson.

## 0. Concordância entre as anotações A e B
## Resumo

- **Unidade:** precisão 86.7% [75.8%–93.1%] em 60 itens; **0 erro(s) grave(s)** de embalagem convertida sem fator; 9 troca(s) de grandeza sem fator.
- **Descrição:** igualdade exata 62.5% [47.0%–75.8%]; módulo valores 80.0% [65.2%–89.5%]; caixas certas 91.1% [86.4%–94.3%]; na base inteira, 7.7% das 23,517 descrições violam alguma regra verificável.
- **Sobrevivente:** acerto 100.0% [88.6%–100.0%]; estoque consolidado 96.7% [83.3%–99.4%]; concorda com a regra 83.3% [66.4%–92.7%].
- **Concordância A×B:** acordo bruto 93.6%, kappa 0.930 (campos de rótulo, sem id_pdm); 16 itens adjudicados.


A = analista de cadastro (PDM ao pé da letra); B = suprimentos/almoxarifado (saldo e uso). Passadas separadas, em ordens diferentes, lendo só a linha crua e o PDM. Itens com divergência: 16 (todos adjudicados com justificativa escrita).

| tarefa | campo | n | acordo bruto | kappa de Cohen |
|---|---|---|---|---|
| unidade | id_pdm | 60 | 100.0% | 1.000 |
| unidade | unidade_esperada | 60 | 88.3% | 0.840 |
| unidade | exige_fator | 60 | 96.7% | 0.933 |
| descricao | id_pdm | 40 | 100.0% | 1.000 |
| descricao | descricao | 40 | 85.0% | 0.847 |
| descricao | por caixa (atributo) | 203 | 97.0% | 0.970 |
| sobrevivente | sobrevivente_esperado | 30 | 100.0% | 1.000 |
| sobrevivente | estoque_consolidado_esperado | 30 | 100.0% | 1.000 |
| sobrevivente | concorda_com_a_regra | 30 | 96.7% | 0.870 |
| **global** | todos os campos | 350 | 95.4% | 0.952 |
| **global** | sem id_pdm (que não divergiu) | 250 | 93.6% | 0.930 |

## 1. Unidade de medida (V2.1)

Avalia `UNIDADE_PDM` + `UNIDADE_MOTIVO`. Predição `FILA_FATOR` = unidade vazia com motivo pedindo o fator de conversão.

| estrato | n | acertos | precisão [IC 95%] | ERRO GRAVE: converteu embalagem sem fator | risco: trocou grandeza sem fator |
|---|---|---|---|---|---|
| sinonimo | 15 | 14 | 93.3% [70.2%–98.8%] | 0 | 0 |
| embalagem | 20 | 20 | 100.0% [83.9%–100.0%] | 0 | 0 |
| incompativel | 15 | 8 | 53.3% [30.1%–75.2%] | 0 | 9 |
| ja_correta | 10 | 10 | 100.0% [72.2%–100.0%] | 0 | 0 |
| **total** | 60 | 52 | 86.7% [75.8%–93.1%] | 0 | 9 |

- **Erros graves (embalagem convertida sem fator): 0 de 20 itens de embalagem.**
- Trocas de grandeza sem fator (o gabarito diz `exige_fator=SIM` e a unidade-alvo está certa, mas o saldo muda de significado — KG→PC, UN de cabo→M, UN de tambor→L, UN/PC→PR): **9 de 9**. Não é erro grave pela definição do plano, mas mexe no saldo do mesmo jeito.
- Alarme de classe incompatível falso (o pipeline trocou a unidade, mas a unidade crua já era a da classe certa, lida no texto): **6 de 15** no estrato incompatível. Classe do pipeline x classe do gabarito: U040 PDM090≠PDM110, U041 PDM090≠PDM066, U042 PDM010≠PDM011, U043 PDM010≠PDM011, U045 PDM110≠PDM060, U048 PDM082≠PDM070.
- Unidade trocada sem `UNIDADE_MOTIVO` preenchido: 3 (PÇ).

### Erros e riscos de unidade, um a um

| item | código | estrato | crua | gabarito | exige fator | pipeline | motivo do pipeline | tipo | justificativa do gabarito |
|---|---|---|---|---|---|---|---|---|---|
| U015 | 28269908 | sinonimo | LT | L | NAO | PC | classe PDM030 exige PC, cadastro tem LT | erro | oleo e L; LT e grafia de litro |
| U036 | 23558189 | incompativel | KG | PC | SIM | PC | classe PDM110 exige PC, cadastro tem KG | risco | decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe (regra 11). FILA_FATOR fica reservado a |
| U037 | 29761154 | incompativel | KG | PC | SIM | PC | classe PDM030 exige PC, cadastro tem KG | risco | decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe (regra 11). FILA_FATOR fica reservado a |
| U038 | 19951358 | incompativel | KG | PC | SIM | PC | classe PDM001 exige PC, cadastro tem KG | risco | decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe (regra 11). FILA_FATOR fica reservado a |
| U039 | 17359550 | incompativel | KG | PC | SIM | PC | classe PDM001 exige PC, cadastro tem KG | risco | decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe (regra 11). FILA_FATOR fica reservado a |
| U040 | 20014703 | incompativel | PC | PC | NAO | L | classe PDM090 exige L, cadastro tem PC | erro | pistao de perfuratriz, PC; correto |
| U041 | 17936562 | incompativel | PC | PC | NAO | L | classe PDM090 exige L, cadastro tem PC | erro | sensor indutivo, PC; correto |
| U042 | 12891491 | incompativel | PC | PC | NAO | M | classe PDM010 exige M, cadastro tem PC | erro | mangueira montada (terminais + comprimento 700MM), PC; correto |
| U043 | 24647361 | incompativel | PC | PC | NAO | M | classe PDM010 exige M, cadastro tem PC | erro | mangueira com terminais e comprimento 1000MM = montada (PDM011), PC; correto |
| U044 | 26397754 | incompativel | UN | M | SIM | M | classe PDM060 exige M, cadastro tem UN | risco | decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe (regra 11). FILA_FATOR fica reservado a |
| U045 | 15596076 | incompativel | M | M | NAO | PC | classe PDM110 exige PC, cadastro tem M | erro | cabo eletrico rigido, classe pede M e o cadastro ja esta em M |
| U046 | 16055658 | incompativel | UN | PR | SIM | PR | classe PDM070 exige PR, cadastro tem UN | risco | decisao do adjudicador: PR e a unidade da classe; UN de luva pode ser o par ou a peca avulsa e a troca pode do |
| U047 | 17509093 | incompativel | PC | PR | SIM | PR | classe PDM071 exige PR, cadastro tem PC | risco | decisao do adjudicador: PR e a unidade da classe; PC de calcado e ambiguo (pe ou par); conservador, como U046  |
| U048 | 17181928 | incompativel | PR | PR | NAO | PC | classe PDM082 exige PC, cadastro tem PR | erro | luva de seguranca em PR; correto |
| U049 | 21659603 | incompativel | KG | PC | SIM | M | classe PDM010 exige M, cadastro tem KG | erro | decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe (regra 11). FILA_FATOR fica reservado a |
| U050 | 11472033 | incompativel | UN | L | SIM | L | classe PDM090 exige L, cadastro tem UN | risco | decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe (regra 11). FILA_FATOR fica reservado a |

## 2. Descrição no padrão PDM (V2.2)

Rótulo: a descrição que o PDM manda escrever, com os valores tirados do texto cru (obrigatório ausente ou ambíguo = `<PENDENTE>`; opcional só se o texto traz).

| medida | acertos | n | taxa [IC 95%] |
|---|---|---|---|
| igualdade exata com DESCRICAO_PDM | 25 | 40 | 62.5% [47.0%–75.8%] |
| igualdade módulo valores (mesma cabeça e mesmas caixas na mesma ordem) | 32 | 40 | 80.0% [65.2%–89.5%] |
| cabeça (substantivo + qualificador) igual | 35 | 40 | 87.5% [73.9%–94.5%] |
| classe (ID_PDM) igual | 38 | 40 | 95.0% [83.5%–98.6%] |
| caixas do gabarito com o mesmo valor no pipeline | 184 | 202 | 91.1% [86.4%–94.3%] |

| família | n | exata | módulo valores | cabeça igual |
|---|---|---|---|---|
| conexoes_tubo | 4 | 2 | 4 | 4 |
| eletricos | 4 | 2 | 2 | 4 |
| filtros | 4 | 0 | 0 | 0 |
| fixadores | 4 | 3 | 4 | 4 |
| mangueiras | 4 | 1 | 3 | 3 |
| outras | 4 | 3 | 4 | 4 |
| rolamentos | 4 | 2 | 3 | 4 |
| sobressalentes | 4 | 4 | 4 | 4 |
| valvulas | 4 | 4 | 4 | 4 |
| vedacao | 4 | 4 | 4 | 4 |

### Regras verificáveis do PDM, uma a uma

Contagem de descrições que **violam** cada regra. A coluna do gabarito é sanidade (tem de ser zero); a da base inteira é o invariante sobre todas as `DESCRICAO_PDM` com classe.

| regra | gabarito (40) | pipeline nos 40 | pipeline na base inteira | exemplos na base |
|---|---|---|---|---|
| começa por substantivo + qualificador da classe (regras 1 e 2) | 0 / 40 | 4 / 40 | 961 / 23,517 (4.1%) | `20019238` PDM100: FILTRO<br>`12864167` PDM100: FILTRO<br>`27772417` PDM100: FILTRO<br>`21488129` PDM100: FILTRO |
| caixas da classe, na ordem da coluna ORDEM (regra 1) | 0 / 40 | 0 / 40 | 0 / 23,517 (0.0%) | — |
| maiúsculas, sem acento e sem cedilha (regra 3) | 0 / 40 | 0 / 40 | 0 / 23,517 (0.0%) | — |
| sem abreviação (regra 4) | 0 / 40 | 0 / 40 | 0 / 23,517 (0.0%) | — |
| valor de lista é um dos VALORES_PERMITIDOS (regra 4) | 0 / 40 | 0 / 40 | 0 / 23,517 (0.0%) | — |
| formato de medida: 16,25MM, 1.1/4POL, BAR, MM2 (regras 5 e 6) | 0 / 40 | 1 / 40 | 503 / 23,517 (2.1%) | `19570982` PDM030: REFERENCIA=3295MM<br>`17197742` PDM020: REFERENCIA=22217E<br>`27504721` PDM030: REFERENCIA=1091MM<br>`28448321` PDM030: REFERENCIA=1488MM |
| toda caixa obrigatória 'sempre' está presente (regra 7) | 0 / 40 | 0 / 40 | 0 / 23,517 (0.0%) | — |
| obrigatório condicional presente quando a condição vale, e ausente quando não vale (regra 7) | 0 / 40 | 2 / 40 | 347 / 23,517 (1.5%) | `25571564` PDM050: falta CONEXAO<br>`18277834` PDM050: falta FACE<br>`10272132` PDM062: falta CAPACIDADE INTERRUPCAO<br>`12405736` PDM050: falta DIAMETRO REDUZIDO |
| fabricante/referência na descrição só em PDM100/PDM110, e lá obrigatórios (regras 8 e 9) | 0 / 40 | 0 / 40 | 0 / 23,517 (0.0%) | — |
| **alguma regra** | 0 / 40 | 7 / 40 | 1,811 / 23,517 (7.7%) |  |

### Divergências de descrição, uma a uma

- **D004** `12327984` (fixadores, classe gabarito PDM001, pipeline PDM001) — módulo valores: sim
  - gabarito: `PARAFUSO SEXTAVADO; ROSCA: UNC; BITOLA: 3/4POL; COMPRIMENTO: 5POL; CLASSE RESISTENCIA: SAE GRAU 5; MATERIAL: ACO CARBONO; ACABAMENTO: ZINCADO AMARELO; NORMA: ASME B18.2.1`
  - pipeline: `PARAFUSO SEXTAVADO; ROSCA: UNC; BITOLA: 3/4POL; COMPRIMENTO: 5POL; CLASSE RESISTENCIA: SAE GRAU 5; MATERIAL: <PENDENTE>; ACABAMENTO: ZINCADO AMARELO; NORMA: ASME B18.2.1`
  - caixas diferentes: MATERIAL: gab=ACO CARBONO / pipe=<PENDENTE>
- **D009** `29678788` (rolamentos, classe gabarito PDM020, pipeline PDM020) — módulo valores: sim
  - gabarito: `ROLAMENTO RIGIDO ESFERAS; REFERENCIA: 6203-2RS; DIAMETRO INTERNO: 17MM; DIAMETRO EXTERNO: 40MM; LARGURA: 12MM; VEDACAO: BORRACHA AMBOS LADOS; FOLGA: NORMAL`
  - pipeline: `ROLAMENTO RIGIDO ESFERAS; REFERENCIA: 62032RS; DIAMETRO INTERNO: 17MM; DIAMETRO EXTERNO: 40MM; LARGURA: 12MM; VEDACAO: BORRACHA AMBOS LADOS; FOLGA: NORMAL`
  - caixas diferentes: REFERENCIA: gab=6203-2RS / pipe=62032RS
  - regras violadas pelo pipeline: R5_formato (REFERENCIA=62032RS)
- **D012** `10320864` (rolamentos, classe gabarito PDM020, pipeline PDM020) — módulo valores: não
  - gabarito: `ROLAMENTO RIGIDO ESFERAS; REFERENCIA: 6008-2RS; DIAMETRO EXTERNO: 68MM; LARGURA: 15MM; VEDACAO: BORRACHA AMBOS LADOS; FOLGA: NORMAL`
  - pipeline: `ROLAMENTO RIGIDO ESFERAS; REFERENCIA: 6008-2RS; DIAMETRO INTERNO: 15MM; DIAMETRO EXTERNO: 68MM; LARGURA: 15MM; VEDACAO: <PENDENTE>; FOLGA: NORMAL`
  - caixas diferentes: VEDACAO: gab=BORRACHA AMBOS LADOS / pipe=<PENDENTE>; DIAMETRO INTERNO: gab=(fora) / pipe=15MM
- **D018** `23796118` (conexoes_tubo, classe gabarito PDM050, pipeline PDM050) — módulo valores: sim
  - gabarito: `TE REDUCAO; DIAMETRO NOMINAL: <PENDENTE>; DIAMETRO REDUZIDO: 1/2POL; CLASSE PRESSAO: 3000#; MATERIAL: ACO INOX FORJADO A182 F316; CONEXAO: SOLDA ENCAIXE SW; NORMA: ASME B16.11`
  - pipeline: `TE REDUCAO; DIAMETRO NOMINAL: 1/2POL; DIAMETRO REDUZIDO: 1POL; CLASSE PRESSAO: 3000#; MATERIAL: ACO INOX FORJADO A182 F316; CONEXAO: SOLDA ENCAIXE SW; NORMA: ASME B16.11`
  - caixas diferentes: DIAMETRO NOMINAL: gab=<PENDENTE> / pipe=1/2POL; DIAMETRO REDUZIDO: gab=1/2POL / pipe=1POL
- **D020** `26339546` (conexoes_tubo, classe gabarito PDM050, pipeline PDM050) — módulo valores: sim
  - gabarito: `FLANGE; TIPO: PESCOCO WN; DIAMETRO NOMINAL: 2.1/2POL; CLASSE PRESSAO: 300#; FACE: RF; MATERIAL: ACO CARBONO FORJADO A105; NORMA: ASME B16.5`
  - pipeline: `FLANGE; TIPO: PESCOCO WN; DIAMETRO NOMINAL: 2.1/2POL; CLASSE PRESSAO: 300#; FACE: RF; MATERIAL: <PENDENTE>; NORMA: ASME B16.5`
  - caixas diferentes: MATERIAL: gab=ACO CARBONO FORJADO A105 / pipe=<PENDENTE>
- **D022** `16266802` (eletricos, classe gabarito PDM062, pipeline PDM062) — módulo valores: não
  - gabarito: `DISJUNTOR; TIPO: MINIDISJUNTOR DIN; POLOS: 3P; CORRENTE NOMINAL: <PENDENTE>; CURVA: B; CAPACIDADE INTERRUPCAO: 10KA`
  - pipeline: `DISJUNTOR; TIPO: MINIDISJUNTOR DIN; POLOS: 3P; CURVA: B; CAPACIDADE INTERRUPCAO: 10KA`
  - caixas diferentes: CORRENTE NOMINAL: gab=<PENDENTE> / pipe=(fora)
  - regras violadas pelo pipeline: R7_condicional (falta CORRENTE NOMINAL)
- **D024** `26963756` (eletricos, classe gabarito PDM061, pipeline PDM061) — módulo valores: não
  - gabarito: `TERMINAL ELETRICO; TIPO: PRE-ISOLADO FORQUILHA; SECAO CABO: <PENDENTE>; FURO: M5; MATERIAL: COBRE ESTANHADO`
  - pipeline: `TERMINAL ELETRICO; TIPO: PRE-ISOLADO FORQUILHA; SECAO CABO: 5MM2; MATERIAL: COBRE ESTANHADO`
  - caixas diferentes: SECAO CABO: gab=<PENDENTE> / pipe=5MM2; FURO: gab=M5 / pipe=(fora)
  - regras violadas pelo pipeline: R7_condicional (falta FURO)
- **D025** `23429477` (mangueiras, classe gabarito PDM011, pipeline PDM011) — módulo valores: sim
  - gabarito: `MANGUEIRA HIDRAULICA MONTADA; NORMA: EN 853 1SN; DIAMETRO INTERNO: 1/2POL; PRESSAO TRABALHO: 160BAR; COMPRIMENTO: 1100MM; TERMINAL A: FEMEA RETA JIC; TERMINAL B: FEMEA CURVA 90 GRAUS JIC; MATERIAL TERMINAIS: ACO CARBONO ZINCADO`
  - pipeline: `MANGUEIRA HIDRAULICA MONTADA; NORMA: EN 853 1SN; DIAMETRO INTERNO: 1/2POL; PRESSAO TRABALHO: 160BAR; COMPRIMENTO: 1100MM; TERMINAL A: FEMEA RETA JIC; TERMINAL B: FEMEA RETA JIC; MATERIAL TERMINAIS: ACO CARBONO ZINCADO`
  - caixas diferentes: TERMINAL B: gab=FEMEA CURVA 90 GRAUS JIC / pipe=FEMEA RETA JIC
- **D027** `17260137` (mangueiras, classe gabarito PDM011, pipeline PDM011) — módulo valores: sim
  - gabarito: `MANGUEIRA HIDRAULICA MONTADA; NORMA: SAE 100R1AT; DIAMETRO INTERNO: 1/2POL; PRESSAO TRABALHO: 135BAR; COMPRIMENTO: 1500MM; TERMINAL A: FEMEA CURVA 90 GRAUS DKO; TERMINAL B: MACHO RETO BSP; MATERIAL TERMINAIS: ACO CARBONO ZINCADO`
  - pipeline: `MANGUEIRA HIDRAULICA MONTADA; NORMA: SAE 100R1AT; DIAMETRO INTERNO: 1/2POL; PRESSAO TRABALHO: 135BAR; COMPRIMENTO: 1500MM; TERMINAL A: FEMEA CURVA 90 GRAUS DKO; TERMINAL B: FEMEA CURVA 90 GRAUS DKO; MATERIAL TERMINAIS: ACO CARBONO ZINCADO`
  - caixas diferentes: TERMINAL B: gab=MACHO RETO BSP / pipe=FEMEA CURVA 90 GRAUS DKO
- **D028** `22245104` (mangueiras, classe gabarito PDM014, pipeline PDM010) — módulo valores: não
  - gabarito: `MANGOTE; APLICACAO: SUCCAO E DESCARGA; MATERIAL: PVC COM ESPIRAL PVC RIGIDO; DIAMETRO INTERNO: <PENDENTE>; PRESSAO TRABALHO: 4,1BAR`
  - pipeline: `MANGUEIRA HIDRAULICA; NORMA: <PENDENTE>; DIAMETRO INTERNO: <PENDENTE>; PRESSAO TRABALHO: 4,1BAR; REFORCO: <PENDENTE>; MATERIAL COBERTURA: <PENDENTE>`
  - caixas diferentes: APLICACAO: gab=SUCCAO E DESCARGA / pipe=(fora); MATERIAL: gab=PVC COM ESPIRAL PVC RIGIDO / pipe=(fora); NORMA: gab=(fora) / pipe=<PENDENTE>; REFORCO: gab=(fora) / pipe=<PENDENTE>; MATERIAL COBERTURA: gab=(fora) / pipe=<PENDENTE>
- **D029** `17093730` (filtros, classe gabarito PDM100, pipeline PDM100) — módulo valores: não
  - gabarito: `FILTRO OLEO LUBRIFICANTE; FABRICANTE: MANN; REFERENCIA FABRICANTE: W 875/81`
  - pipeline: `FILTRO; FABRICANTE: MANN; REFERENCIA FABRICANTE: W 875/81`
  - caixas diferentes: —
  - regras violadas pelo pipeline: R1_cabeca (FILTRO)
- **D030** `16695938` (filtros, classe gabarito PDM100, pipeline PDM100) — módulo valores: não
  - gabarito: `FILTRO AR; APLICACAO: GERADOR DIESEL; FABRICANTE: TECFIL; REFERENCIA FABRICANTE: ARL 1301`
  - pipeline: `FILTRO; APLICACAO: GERADOR DIESEL; FABRICANTE: TECFIL; REFERENCIA FABRICANTE: ARL 1301`
  - caixas diferentes: —
  - regras violadas pelo pipeline: R1_cabeca (FILTRO)
- **D031** `28919602` (filtros, classe gabarito PDM100, pipeline PDM100) — módulo valores: não
  - gabarito: `FILTRO COMBUSTIVEL; APLICACAO: GERADOR DIESEL; FABRICANTE: MANN; REFERENCIA FABRICANTE: WK 329/5`
  - pipeline: `FILTRO; APLICACAO: GERADOR DIESEL; FABRICANTE: MANN; REFERENCIA FABRICANTE: WK 329/5`
  - caixas diferentes: —
  - regras violadas pelo pipeline: R1_cabeca (FILTRO)
- **D032** `12939529` (filtros, classe gabarito PDM110, pipeline PDM100) — módulo valores: não
  - gabarito: `MANDIBULA MOVEL; APLICACAO: BRITADOR MANDIBULA; MODELO EQUIPAMENTO: CJ615; FABRICANTE: SANDVIK; REFERENCIA FABRICANTE: 243.728539; MATERIAL: ACO LIGA`
  - pipeline: `FILTRO; FABRICANTE: <PENDENTE>; REFERENCIA FABRICANTE: 243.728539`
  - caixas diferentes: APLICACAO: gab=BRITADOR MANDIBULA / pipe=(fora); MODELO EQUIPAMENTO: gab=CJ615 / pipe=(fora); FABRICANTE: gab=SANDVIK / pipe=<PENDENTE>; MATERIAL: gab=ACO LIGA / pipe=(fora)
  - regras violadas pelo pipeline: R1_cabeca (FILTRO)
- **D040** `23372583` (outras, classe gabarito PDM082, pipeline PDM082) — módulo valores: sim
  - gabarito: `BROCA HELICOIDAL; TIPO: HSS COBALTO; DIAMETRO: 15MM; HASTE: CONE MORSE; NORMA: DIN 345`
  - pipeline: `BROCA HELICOIDAL; TIPO: <PENDENTE>; DIAMETRO: 15MM; HASTE: CONE MORSE; NORMA: DIN 345`
  - caixas diferentes: TIPO: gab=HSS COBALTO / pipe=<PENDENTE>

## 3. Sobrevivente e consolidação de estoque (V2.3)

Regra escrita (06_juntar.py): ATIVO > completude > movimentação mais recente > valor em estoque > código mais antigo. No gabarito, a completude foi julgada lendo o texto cru (fração dos obrigatórios informados), não copiada da coluna COMPLETUDE.

| medida | acertos | n | taxa [IC 95%] |
|---|---|---|---|
| cluster íntegro no plano (mesma chave, um MANTER ATIVO, bloqueados apontam para ele) | 30 | 30 | 100.0% [88.6%–100.0%] |
| sobrevivente = regra aplicada à mão nas linhas cruas | 30 | 30 | 100.0% [88.6%–100.0%] |
| ESTOQUE_CONSOLIDADO = soma esperada | 29 | 30 | 96.7% [83.3%–99.4%] |
| concorda_com_a_regra = SIM (suprimentos escolheria o mesmo código) | 25 | 30 | 83.3% [66.4%–92.7%] |
| pipeline escolheu o código que suprimentos escolheria | 25 | 30 | 83.3% [66.4%–92.7%] |

| estrato | n | sobrevivente certo | estoque certo | concorda com a regra |
|---|---|---|---|---|
| dois | 10 | 10 | 9 | 9 |
| multicentro | 10 | 10 | 10 | 7 |
| tres_a_cinco | 10 | 10 | 10 | 9 |

### Clusters com erro ou em que a regra não convence

| cluster | estrato | códigos | gabarito (regra) | pipeline | estoque gab. | estoque pipe | concorda | suprimentos escolheria | justificativa |
|---|---|---|---|---|---|---|---|---|---|
| S001 | multicentro | 19486377 14752839 | 19486377 | 19486377 | 95 | 95 | NAO | NENHUM (manter bloqueados) | nenhum ATIVO (BLOQUEADO x OBSOLETO); a regra cai para movimentacao e elege o bloqueado; suprimentos nao reativaria nenhum sem analise |
| S002 | multicentro | 23296141 10461721 | 23296141 | 23296141 | 3 | 3 | NAO | 10461721 | empate de completude; a regra elege 23296141 pela movimentacao (2023 > 2022), mas ele esta em KG e o saldo (3) esta no codigo em PC; suprimentos ficaria com 104 |
| S005 | multicentro | 11134069 10839375 | 11134069 | 11134069 | 9 | 9 | NAO | NENHUM (manter bloqueados) | os dois BLOQUEADOS; a regra reativa um deles |
| S012 | dois | 10348933 28426322 | 10348933 | 10348933 | 0 | 0 | NAO | NENHUM (manter bloqueados) | os dois estao BLOQUEADOS; a regra elege 10348933 pela completude (28426322 nao tem aplicacao nem modelo), mas manter um ativo reativa codigo bloqueado sem saber |
| S015 | dois | 28006689 28795842 | 28006689 | 28006689 | NAO_SOMAVEL | 13 | SIM | 28006689 | empate; movimentacao 2024 > 2019. Saldo nao soma: 2 PC + 11 JG sem fator do jogo |
| S024 | tres_a_cinco | 26402191 24774110 28561418 24574301 | 24774110 | 24774110 | 9 | 9 | NAO | 28561418 | decisao do adjudicador: a regra elege 24774110 porque o texto cru de 28561418 nao traz o modelo; mas os quatro codigos tem a mesma chave, a descricao do sobrevi |

