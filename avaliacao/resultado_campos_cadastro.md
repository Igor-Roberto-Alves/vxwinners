# Avaliação contra o conjunto-ouro


Gerado em 07/11/2026 23:26 · ouro: `/home/igor-alves/clas/hack/vxwinners/avaliacao/gold.csv` (456 rótulos, 177 itens, estratos: abreviacao, ancora_coluna_vazia, ancora_com_coluna, faltante, plantados, typo)


Regras: DEFINIDO exige o valor exato (normalizado); AUSENTE exige abstenção — preencher conta como **invenção**; INDEFINIVEL fica fora da conta. Intervalos de confiança de Wilson a 95%.


## base_original.csv

### Resumo por campo

| Campo | Rótulos (definidos) | Acertos | Erros | Absteve | Precisão (IC 95%) | Cobertura | Ausentes no ouro | Invenções | Taxa de invenção (IC 95%) |
|---|---|---|---|---|---|---|---|---|---|
| FABRICANTE | 72 | 50 | 0 | 22 | 100.0% [93%–100%] | 69% | 55 | 0 | 0.0% [0%–7%] |
| GRUPO_MERCADORIA | 137 | 133 | 4 | 0 | 97.1% [93%–99%] | 100% | 0 | 0 | — |
| NCM | 65 | 46 | 5 | 14 | 90.2% [79%–96%] | 78% | 0 | 0 | — |
| REFERENCIA_FABRICANTE | 73 | 32 | 2 | 39 | 94.1% [81%–98%] | 47% | 54 | 0 | 0.0% [0%–7%] |

### Por campo × estrato

| Campo | Estrato | Definidos | Precisão (IC 95%) | Ausentes | Taxa de invenção |
|---|---|---|---|---|---|
| FABRICANTE | ancora_coluna_vazia | 19 | 100.0% [70%–100%] | 1 | 0.0% [0%–79%] |
| FABRICANTE | ancora_com_coluna | 20 | 100.0% [84%–100%] | 0 | — |
| FABRICANTE | faltante | 0 | — | 36 | 0.0% [0%–10%] |
| FABRICANTE | plantados | 15 | 100.0% [77%–100%] | 0 | — |
| FABRICANTE | typo | 18 | 100.0% [68%–100%] | 18 | 0.0% [0%–18%] |
| GRUPO_MERCADORIA | abreviacao | 50 | 96.0% [87%–99%] | 0 | — |
| GRUPO_MERCADORIA | faltante | 36 | 100.0% [90%–100%] | 0 | — |
| GRUPO_MERCADORIA | plantados | 15 | 100.0% [80%–100%] | 0 | — |
| GRUPO_MERCADORIA | typo | 36 | 94.4% [82%–98%] | 0 | — |
| NCM | abreviacao | 50 | 89.4% [77%–95%] | 0 | — |
| NCM | plantados | 15 | 100.0% [51%–100%] | 0 | — |
| REFERENCIA_FABRICANTE | ancora_coluna_vazia | 19 | 71.4% [36%–92%] | 1 | 0.0% [0%–79%] |
| REFERENCIA_FABRICANTE | ancora_com_coluna | 20 | 100.0% [84%–100%] | 0 | — |
| REFERENCIA_FABRICANTE | faltante | 2 | — | 34 | 0.0% [0%–10%] |
| REFERENCIA_FABRICANTE | plantados | 15 | — | 0 | — |
| REFERENCIA_FABRICANTE | typo | 17 | 100.0% [65%–100%] | 19 | 0.0% [0%–17%] |

### Linhas que erraram (11)

| Código | Campo | Estrato | Esperado (ouro) | Veio do modelo | Evidência do ouro | Nota do anotador |
|---|---|---|---|---|---|---|
| 27111070 | GRUPO_MERCADORIA | typo | FIX01 | FIL01 | PARAFUSO SEXTAVADO ... ASME B18.2.1; coluna GRUPO=FIL01 | descricao contradiz coluna: parafuso sextavado -> FIX01 (PDM001); coluna errada |
| 14192153 | GRUPO_MERCADORIA | typo | ELE01 | VED01 | TERMINAL ELETRICO, PRE-ISOLADO FORQUILHA; coluna GRUPO=VED01 | descricao contradiz coluna: terminal eletrico -> ELE01 (PDM061); coluna errada |
| 26337536 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 486798140 | 48679814000 | texto PN 4867981-40; coluna 486.7981-40-00 | -00 extra na coluna e revisao; texto traz o PN completo Sandvik |
| 23825170 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | CT6110181 | CT6110181REVA | P/N CT6110181; coluna 'CT6110181 REV A' | REV A na coluna e revisao, fora da referencia |
| 15603929 | NCM | abreviacao | 73181500 | 73181900 | PARAFUSO SEXTAVADO, METRICA GROSSA, M18, 60MM, INOX 316, DIN 931 | PDM001: NCM unico 7318.15.00; coluna 7318.19.00 contradiz o PDM |
| 26470129 | NCM | abreviacao | 73181500 | 73181400 | PARAFUSO SEXT, UNC, 1/4 POL, 8 IN, SAE GRAU 5, ZINC AMARELO | PDM001: NCM unico 7318.15.00; coluna 7318.14.00 contradiz o PDM |
| 26946121 | NCM | abreviacao | 84813000 | 84818099 | VALVULA RETENCAO;3POL;150#;A216 WCB;SOLDA TOPO;TIPO:ESFERA | PDM043: NCM unico 8481.30.00; coluna 8481.80.99 contradiz o PDM |
| 11752076 | GRUPO_MERCADORIA | abreviacao | VAL01 | TUB01 | VALVULA ESF, 1POL, CL:800#, ACO CARBONO, ROSCA NPT, VEDACAO:METAL-METAL | VALV ESF = valvula esfera (PDM040) -> VAL01; coluna TUB01 contradiz a descricao |
| 17673590 | GRUPO_MERCADORIA | abreviacao | SOB01 | ROL01 | BUCHA MANCAL GUIA;APLICACAO:TURBINA HIDRAULICA;FRANCIS 6MW;WEG;PN:53291196 | BUCHA MANCAL GUIA em SUBSTANTIVOS_SOBRESSALENTES -> SOB01; coluna ROL01 contradiz |
| 28799530 | NCM | abreviacao | 84839000 | 84834010 | PINHAO, APLIC:REDUTOR, MODELO:MC3RLSF07, REF:99457776 | PDM110: sobressalente de redutor = 8483.90.00; coluna 8483.40.10 contradiz |
| 25560040 | NCM | abreviacao | 73182100 | 73182200 | ARRUELA PRESSAO, PARA PARAFUSO:M-14, ACO MOLA, GALV A FOGO, DIN 127 | PDM005: NCM unico 7318.21.00; coluna 7318.22.00 (lisa) contradiz |

### Invenções — preencheu onde o ouro diz AUSENTE (0)

Nenhuma invenção: o modelo se absteve corretamente nos ausentes. 


### Abstenções em rótulos definidos (75) — o ouro tem valor, o modelo deixou vazio

| Código | Campo | Estrato | Esperado (ouro) | Evidência |
|---|---|---|---|---|
| 20866024 | NCM | plantados | 84821010 | ROL 6205-2RSH/C3 |
| 20866024 | REFERENCIA_FABRICANTE | plantados | 62052RSHC3 | 6205-2RSH/C3 |
| 27026717 | REFERENCIA_FABRICANTE | plantados | 6205C2HRSC3 | 6205-C-2HRS-C3 |
| 28490077 | NCM | plantados | 84821010 | ROLAMENTO 6205DDUC3 |
| 28490077 | REFERENCIA_FABRICANTE | plantados | 6205DDUC3 | ROLAMENTO 6205DDUC3 |
| 29364361 | REFERENCIA_FABRICANTE | plantados | 63102ZC3 | 6310-2Z/C3 |
| 14840397 | NCM | plantados | 84821010 | ROL 6310-C-2Z-C3 |
| 14840397 | REFERENCIA_FABRICANTE | plantados | 6310C2ZC3 | 6310-C-2Z-C3 |
| 16303905 | NCM | plantados | 84821010 | ROLAMENTO NTN 6310ZZC3 |
| 16303905 | REFERENCIA_FABRICANTE | plantados | 6310ZZC3 | 6310ZZC3 |
| 27841570 | NCM | plantados | 84212300 | FILTRO LF9009 |
| 27841570 | FABRICANTE | plantados | FLEETGUARD | FILTRO LF9009; coluna FAB vazia |
| 27841570 | REFERENCIA_FABRICANTE | plantados | LF9009 | FILTRO LF9009 |
| 16031971 | NCM | plantados | 84212300 | FILTRO OLEO LUBRIFICANTE |
| 16031971 | REFERENCIA_FABRICANTE | plantados | LF9009 | LF 9009 (DESCRICAO_LONGA) |
| 12456213 | REFERENCIA_FABRICANTE | plantados | LF3970 | LF3970 (DESCRICAO_LONGA) |
| 11315577 | NCM | plantados | 84212300 | FILTRO OLEO |
| 11315577 | REFERENCIA_FABRICANTE | plantados | 1R1808 | 1R1808 |
| 29458054 | NCM | plantados | 84212300 | FILTRO OLEO MOTOR |
| 29458054 | REFERENCIA_FABRICANTE | plantados | 1R1808 | 1R-1808 |
| 20388699 | NCM | plantados | 84212300 | FILTRO P551808 |
| 20388699 | REFERENCIA_FABRICANTE | plantados | P551808 | P551808 |
| 21927396 | NCM | plantados | 84212300 | FILTRO LUBR |
| 21927396 | REFERENCIA_FABRICANTE | plantados | B40142 | B40142 |
| 18308575 | NCM | plantados | 84212300 | FILTRO DBL7300 |
| 18308575 | FABRICANTE | plantados | DONALDSON | FILTRO DBL7300; coluna FAB vazia |
| 18308575 | REFERENCIA_FABRICANTE | plantados | DBL7300 | DBL7300 |
| 23476944 | REFERENCIA_FABRICANTE | plantados | LF691A | LF691A |
| 21875657 | FABRICANTE | typo | TECFIL | FABRICANTE: TECFIL |
| 28098676 | REFERENCIA_FABRICANTE | typo | 8363454397 | PART NUMBER:836-34-54397 |
| 20554906 | FABRICANTE | typo | KOMATSU | FABRICANTE KOMATSU |
| 20554906 | REFERENCIA_FABRICANTE | typo | 0772693307 | REFERENCA FABRICANTE 077-26-93307 |
| 27494117 | REFERENCIA_FABRICANTE | typo | PEC7281 | PEC 7281 |
| 19749876 | REFERENCIA_FABRICANTE | typo | 1828991782 | 182-89-91782 REV A |
| 22825576 | FABRICANTE | typo | SULZER | FABR SULZER |
| 16707167 | FABRICANTE | typo | MANN | FILTRO OLEO LUBRIF, MANN |
| 16707167 | REFERENCIA_FABRICANTE | typo | W07605 | COD FABRICANTE:W 076/05 |
| 22518432 | FABRICANTE | typo | METSO | MARCA:METSO |
| 19580539 | FABRICANTE | typo | METSO | EQUIP: C106, METSO |
| 19615390 | FABRICANTE | typo | MANN | FABRICANTE: MANN |
| 19615390 | REFERENCIA_FABRICANTE | typo | W19992 | REFERENCIA FABRICANTE: W 199/92 |
| 10410458 | FABRICANTE | typo | SULZER | FABRICANTE:SULZER |
| 17549957 | FABRICANTE | typo | SANDVIK | CHAPA LATERAL CJ412 PN 37.3424-48 SANDVIK |
| 17549957 | REFERENCIA_FABRICANTE | typo | 37342448 | PN 37.3424-48 |
| 13182042 | REFERENCIA_FABRICANTE | typo | N10601168 | PN N10601168 |
| 27716713 | FABRICANTE | typo | MARTIN ENGINEERING | MARCA MARTIN ENGINEERING |
| 27716713 | REFERENCIA_FABRICANTE | typo | 65514AS | COD FABRICANTE 65514-AS REV A |
| 29893321 | REFERENCIA_FABRICANTE | typo | 62122RSC3 | MODELO:6212 2RS/C3 |
| 21795996 | FABRICANTE | ancora_coluna_vazia | METSO | FAB:METSO (coluna FAB vazia) |
| 22733083 | FABRICANTE | ancora_coluna_vazia | WEG | FABR:WEG (coluna FAB vazia) |
| 12952459 | FABRICANTE | ancora_coluna_vazia | METSO | MODELO EQUIPAMENTO:MP800, MARCA:METSO (colunas vazias) |
| 12952459 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | MM6873619 | P/N:MM6873619 (coluna REF vazia) |
| 15109751 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 0682032350 | REFERENCIA FABRICANTE: 0682 0323 50 (coluna REF vazia) |
| 11416625 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 105161507 | REFERENCIA FABRICANTE: 105.1615-07 (coluna REF vazia) |
| 21262147 | FABRICANTE | ancora_coluna_vazia | CATERPILLAR | BUCHA 6015B PN 480-0954 CATERPILLAR (colunas vazias) |
| 21262147 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 4800954 | PN 480-0954 (coluna REF vazia) |
| 26337536 | FABRICANTE | ancora_coluna_vazia | SANDVIK | CABECOTE DP1500 PN 4867981-40 SANDVIK (coluna FAB vazia) |
| 29448580 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 8452508 | PN:8452508 (coluna REF vazia) |
| 16031121 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 9699377942 | PART NUMBER: 9699377942 (coluna REF vazia) |
| 21457728 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 3585436 | COD FABRICANTE:3585436, CONF AMOSTRA |
| 24695479 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | N96275812 | COD FABRICANTE:N96275812 (coluna REF vazia) |
| 27216616 | FABRICANTE | ancora_coluna_vazia | METSO | HP400 PN MM1686521 REV A METSO (coluna FAB vazia) |
| 23403958 | FABRICANTE | ancora_coluna_vazia | SANDVIK | MOD: CH440, FABR: SANDVIK (coluna FAB vazia) |
| 26733873 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | N34076729 | REFERENCIA FABRICANTE: N34076729 (coluna REF vazia) |
| 17093730 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | W87581 | PART NUMBER W 875/81 (coluna REF vazia) |
| 24132586 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | V8739882779 | PN V8739-882779 (coluna REF vazia) |
| 23825170 | FABRICANTE | ancora_coluna_vazia | CONTINENTAL | FAB DE CONTINENTAL (coluna FAB vazia) |
| 16951994 | FABRICANTE | ancora_coluna_vazia | EPIROC | FABRICANTE: EPIROC; MODELO EQUIPAMENTO: SMARTROC D65 |
| 16951994 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 5348234076 | P/N: 5348 2340 76 |
| 29461903 | FABRICANTE | ancora_coluna_vazia | SANDVIK | FABRICANTE:SANDVIK, APLIC:BRITADOR CONICO |
| 16917437 | REFERENCIA_FABRICANTE | faltante | 6012C3 | REFERENCIA: 6012/C3 |
| 20954223 | REFERENCIA_FABRICANTE | faltante | 62042RS | REF: 6204-2RS, PROTECAO: 2RS |
| 29110507 | NCM | abreviacao | 84821010 | ROLAMENTO RIGIDO ESFERAS; REFERENCIA: 6304-2RS/C3; DI: 20MM; DE: 52MM |
| 17473520 | NCM | abreviacao | 40092210 | MANG. HIDRAULICA MONTADA SAE 100R2AT 1/2POL 3480PSI 300 MM FEMEA 90G JIC |
| 17378833 | NCM | abreviacao | 40169300 | ANEL O-RING; DI: 15MM; SECAO: 1,5MM; MATERIAL: FKM (VITON) |

## pipeline.csv

### Resumo por campo

| Campo | Rótulos (definidos) | Acertos | Erros | Absteve | Precisão (IC 95%) | Cobertura | Ausentes no ouro | Invenções | Taxa de invenção (IC 95%) |
|---|---|---|---|---|---|---|---|---|---|
| FABRICANTE | 72 | 70 | 0 | 2 | 100.0% [95%–100%] | 97% | 55 | 0 | 0.0% [0%–7%] |
| GRUPO_MERCADORIA | 137 | 135 | 2 | 0 | 98.5% [95%–100%] | 100% | 0 | 0 | — |
| NCM | 65 | 56 | 2 | 7 | 96.6% [88%–99%] | 89% | 0 | 0 | — |
| REFERENCIA_FABRICANTE | 73 | 57 | 7 | 9 | 89.1% [79%–95%] | 88% | 54 | 0 | 0.0% [0%–7%] |

### Por campo × estrato

| Campo | Estrato | Definidos | Precisão (IC 95%) | Ausentes | Taxa de invenção |
|---|---|---|---|---|---|
| FABRICANTE | ancora_coluna_vazia | 19 | 100.0% [83%–100%] | 1 | 0.0% [0%–79%] |
| FABRICANTE | ancora_com_coluna | 20 | 100.0% [84%–100%] | 0 | — |
| FABRICANTE | faltante | 0 | — | 36 | 0.0% [0%–10%] |
| FABRICANTE | plantados | 15 | 100.0% [77%–100%] | 0 | — |
| FABRICANTE | typo | 18 | 100.0% [82%–100%] | 18 | 0.0% [0%–18%] |
| GRUPO_MERCADORIA | abreviacao | 50 | 98.0% [90%–100%] | 0 | — |
| GRUPO_MERCADORIA | faltante | 36 | 100.0% [90%–100%] | 0 | — |
| GRUPO_MERCADORIA | plantados | 15 | 100.0% [80%–100%] | 0 | — |
| GRUPO_MERCADORIA | typo | 36 | 97.2% [86%–100%] | 0 | — |
| NCM | abreviacao | 50 | 96.0% [87%–99%] | 0 | — |
| NCM | plantados | 15 | 100.0% [68%–100%] | 0 | — |
| REFERENCIA_FABRICANTE | ancora_coluna_vazia | 19 | 89.5% [69%–97%] | 1 | 0.0% [0%–79%] |
| REFERENCIA_FABRICANTE | ancora_com_coluna | 20 | 95.0% [76%–99%] | 0 | — |
| REFERENCIA_FABRICANTE | faltante | 2 | — | 34 | 0.0% [0%–10%] |
| REFERENCIA_FABRICANTE | plantados | 15 | 88.9% [56%–98%] | 0 | — |
| REFERENCIA_FABRICANTE | typo | 17 | 81.2% [57%–93%] | 19 | 0.0% [0%–17%] |

### Linhas que erraram (11)

| Código | Campo | Estrato | Esperado (ouro) | Veio do modelo | Evidência do ouro | Nota do anotador |
|---|---|---|---|---|---|---|
| 16031971 | REFERENCIA_FABRICANTE | plantados | LF9009 | 9009 | LF 9009 (DESCRICAO_LONGA) | PN com espaco no texto; normalizado LF9009 |
| 20554906 | REFERENCIA_FABRICANTE | typo | 0772693307 | 0772693307COM | REFERENCA FABRICANTE 077-26-93307 | typo REFERENCA no rotulo; PN normalizado sem separadores |
| 19749876 | REFERENCIA_FABRICANTE | typo | 1828991782 | 1828991782REVA | 182-89-91782 REV A | REV A e revisao, fora da referencia; PN sem separadores |
| 27111070 | GRUPO_MERCADORIA | typo | FIX01 | FIL01 | PARAFUSO SEXTAVADO ... ASME B18.2.1; coluna GRUPO=FIL01 | descricao contradiz coluna: parafuso sextavado -> FIX01 (PDM001); coluna errada |
| 27716713 | REFERENCIA_FABRICANTE | typo | 65514AS | 65514ASREVA | COD FABRICANTE 65514-AS REV A | REV A e revisao; sufixo AS integra o PN; sem separadores |
| 25454162 | REFERENCIA_FABRICANTE | ancora_com_coluna | CA18490 | CA1849000 | texto P/N:CA18490-00; coluna REF=CA18490 | sufixo -00 apos PN completo e revisao (padrao do conjunto); coluna confirma |
| 26337536 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 486798140 | 48679814000 | texto PN 4867981-40; coluna 486.7981-40-00 | -00 extra na coluna e revisao; texto traz o PN completo Sandvik |
| 23825170 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | CT6110181 | CT6110181REVA | P/N CT6110181; coluna 'CT6110181 REV A' | REV A na coluna e revisao, fora da referencia |
| 17673590 | GRUPO_MERCADORIA | abreviacao | SOB01 | ROL01 | BUCHA MANCAL GUIA;APLICACAO:TURBINA HIDRAULICA;FRANCIS 6MW;WEG;PN:53291196 | BUCHA MANCAL GUIA em SUBSTANTIVOS_SOBRESSALENTES -> SOB01; coluna ROL01 contradiz |
| 17673590 | NCM | abreviacao | 84109000 | 84832000 | BUCHA MANCAL GUIA;APLICACAO:TURBINA HIDRAULICA;FRANCIS 6MW;WEG;PN:53291196 | PDM110: sobressalente de turbina hidraulica = 8410.90.00 |
| 28799530 | NCM | abreviacao | 84839000 | 84834010 | PINHAO, APLIC:REDUTOR, MODELO:MC3RLSF07, REF:99457776 | PDM110: sobressalente de redutor = 8483.90.00; coluna 8483.40.10 contradiz |

### Invenções — preencheu onde o ouro diz AUSENTE (0)

Nenhuma invenção: o modelo se absteve corretamente nos ausentes. 


### Abstenções em rótulos definidos (18) — o ouro tem valor, o modelo deixou vazio

| Código | Campo | Estrato | Esperado (ouro) | Evidência |
|---|---|---|---|---|
| 20866024 | REFERENCIA_FABRICANTE | plantados | 62052RSHC3 | 6205-2RSH/C3 |
| 27026717 | REFERENCIA_FABRICANTE | plantados | 6205C2HRSC3 | 6205-C-2HRS-C3 |
| 28490077 | REFERENCIA_FABRICANTE | plantados | 6205DDUC3 | ROLAMENTO 6205DDUC3 |
| 29364361 | REFERENCIA_FABRICANTE | plantados | 63102ZC3 | 6310-2Z/C3 |
| 14840397 | REFERENCIA_FABRICANTE | plantados | 6310C2ZC3 | 6310-C-2Z-C3 |
| 16303905 | REFERENCIA_FABRICANTE | plantados | 6310ZZC3 | 6310ZZC3 |
| 27841570 | NCM | plantados | 84212300 | FILTRO LF9009 |
| 27841570 | FABRICANTE | plantados | FLEETGUARD | FILTRO LF9009; coluna FAB vazia |
| 16031971 | NCM | plantados | 84212300 | FILTRO OLEO LUBRIFICANTE |
| 11315577 | NCM | plantados | 84212300 | FILTRO OLEO |
| 29458054 | NCM | plantados | 84212300 | FILTRO OLEO MOTOR |
| 20388699 | NCM | plantados | 84212300 | FILTRO P551808 |
| 21927396 | NCM | plantados | 84212300 | FILTRO LUBR |
| 18308575 | NCM | plantados | 84212300 | FILTRO DBL7300 |
| 18308575 | FABRICANTE | plantados | DONALDSON | FILTRO DBL7300; coluna FAB vazia |
| 29893321 | REFERENCIA_FABRICANTE | typo | 62122RSC3 | MODELO:6212 2RS/C3 |
| 16917437 | REFERENCIA_FABRICANTE | faltante | 6012C3 | REFERENCIA: 6012/C3 |
| 20954223 | REFERENCIA_FABRICANTE | faltante | 62042RS | REF: 6204-2RS, PROTECAO: 2RS |