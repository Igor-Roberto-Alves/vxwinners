# Avaliação contra o conjunto-ouro


Gerado em 07/11/2026 18:59 · ouro: `/home/rviana/projects/hackathonXV/vxwinners/avaliacao/gold.csv` (456 rótulos, 177 itens, estratos: abreviacao, ancora_coluna_vazia, ancora_com_coluna, faltante, plantados, typo)


Regras: DEFINIDO exige o valor exato (normalizado); AUSENTE exige abstenção — preencher conta como **invenção**; INDEFINIVEL fica fora da conta. Intervalos de confiança de Wilson a 95%.


## base_preenchida_nossa.csv

### Resumo por campo

| Campo | Rótulos (definidos) | Acertos | Erros | Absteve | Precisão (IC 95%) | Cobertura | Ausentes no ouro | Invenções | Taxa de invenção (IC 95%) |
|---|---|---|---|---|---|---|---|---|---|
| FABRICANTE | 72 | 72 | 0 | 0 | 100.0% [95%–100%] | 100% | 55 | 55 | 100.0% [93%–100%] |
| GRUPO_MERCADORIA | 137 | 133 | 4 | 0 | 97.1% [93%–99%] | 100% | 0 | 0 | — |
| NCM | 65 | 60 | 5 | 0 | 92.3% [83%–97%] | 100% | 0 | 0 | — |
| REFERENCIA_FABRICANTE | 73 | 66 | 4 | 3 | 94.3% [86%–98%] | 96% | 54 | 19 | 35.2% [24%–49%] |

### Por campo × estrato

| Campo | Estrato | Definidos | Precisão (IC 95%) | Ausentes | Taxa de invenção |
|---|---|---|---|---|---|
| FABRICANTE | ancora_coluna_vazia | 19 | 100.0% [83%–100%] | 1 | 100.0% [21%–100%] |
| FABRICANTE | ancora_com_coluna | 20 | 100.0% [84%–100%] | 0 | — |
| FABRICANTE | faltante | 0 | — | 36 | 100.0% [90%–100%] |
| FABRICANTE | plantados | 15 | 100.0% [80%–100%] | 0 | — |
| FABRICANTE | typo | 18 | 100.0% [82%–100%] | 18 | 100.0% [82%–100%] |
| GRUPO_MERCADORIA | abreviacao | 50 | 96.0% [87%–99%] | 0 | — |
| GRUPO_MERCADORIA | faltante | 36 | 100.0% [90%–100%] | 0 | — |
| GRUPO_MERCADORIA | plantados | 15 | 100.0% [80%–100%] | 0 | — |
| GRUPO_MERCADORIA | typo | 36 | 94.4% [82%–98%] | 0 | — |
| NCM | abreviacao | 50 | 90.0% [79%–96%] | 0 | — |
| NCM | plantados | 15 | 100.0% [80%–100%] | 0 | — |
| REFERENCIA_FABRICANTE | ancora_coluna_vazia | 19 | 89.5% [69%–97%] | 1 | 100.0% [21%–100%] |
| REFERENCIA_FABRICANTE | ancora_com_coluna | 20 | 100.0% [84%–100%] | 0 | — |
| REFERENCIA_FABRICANTE | faltante | 2 | 100.0% [34%–100%] | 34 | 23.5% [12%–40%] |
| REFERENCIA_FABRICANTE | plantados | 15 | 85.7% [60%–96%] | 0 | — |
| REFERENCIA_FABRICANTE | typo | 17 | 100.0% [80%–100%] | 19 | 52.6% [32%–73%] |

### Linhas que erraram (13)

| Código | Campo | Estrato | Esperado (ouro) | Veio do modelo | Evidência do ouro | Nota do anotador |
|---|---|---|---|---|---|---|
| 20866024 | REFERENCIA_FABRICANTE | plantados | 62052RSHC3 | ROL62052RSHC3 | 6205-2RSH/C3 | designacao completa do rolamento = referencia; sem separadores |
| 14840397 | REFERENCIA_FABRICANTE | plantados | 6310C2ZC3 | ROL6310C2ZC3 | 6310-C-2Z-C3 | designacao FAG completa = referencia; sem separadores |
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

### Invenções — preencheu onde o ouro diz AUSENTE (74)

O valor pode até ser plausível, mas a informação não existe no registro — nenhum sistema (nem humano) pode verificá-la. Preencher aqui é risco de dado inventado na base.

| Código | Campo | Estrato | Veio do modelo | Por que é AUSENTE (anotador) |
|---|---|---|---|---|
| 16096492 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 17206377 | FABRICANTE | typo | INTRAL | item por especificacao tecnica; fabricante nao consta no registro |
| 17206377 | REFERENCIA_FABRICANTE | typo | B1821 | item por especificacao tecnica; referencia nao consta |
| 12220777 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 14061434 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 14061434 | REFERENCIA_FABRICANTE | typo | B1821 | item por especificacao tecnica; referencia nao consta |
| 12801789 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 12801789 | REFERENCIA_FABRICANTE | typo | B1821 | item por especificacao tecnica; referencia nao consta |
| 23624224 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 27111070 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 27111070 | REFERENCIA_FABRICANTE | typo | C412 | item por especificacao tecnica; referencia nao consta |
| 18265458 | FABRICANTE | typo | KLINGER | valvula por especificacao; fabricante nao consta no registro |
| 28367671 | FABRICANTE | typo | KSB | valvula por especificacao; fabricante nao consta no registro |
| 28367671 | REFERENCIA_FABRICANTE | typo | CF8M | referencia nao consta no registro |
| 13928906 | FABRICANTE | typo | INTRAL | item por especificacao tecnica; fabricante nao consta no registro |
| 13928906 | REFERENCIA_FABRICANTE | typo | B1821 | item por especificacao tecnica; referencia nao consta |
| 21911453 | FABRICANTE | typo | MOBIL | oleo por especificacao; fabricante nao consta no registro |
| 17166872 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 21002046 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 21002046 | REFERENCIA_FABRICANTE | typo | D118 | item por especificacao tecnica; referencia nao consta |
| 28703486 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 28703486 | REFERENCIA_FABRICANTE | typo | UNC78POLX6POL | item por especificacao tecnica; referencia nao consta |
| 29488190 | FABRICANTE | typo | GERDAU | item por especificacao tecnica; fabricante nao consta no registro |
| 29488190 | REFERENCIA_FABRICANTE | typo | B1821 | item por especificacao tecnica; referencia nao consta |
| 24972660 | FABRICANTE | typo | KSB | valvula por especificacao; fabricante nao consta no registro |
| 16000573 | FABRICANTE | typo | KSB | valvula por especificacao; fabricante nao consta no registro |
| 16000573 | REFERENCIA_FABRICANTE | typo | CF8M | referencia nao consta no registro |
| 14192153 | FABRICANTE | typo | INTELLI | terminal por especificacao; fabricante nao consta no registro |
| 13605949 | FABRICANTE | ancora_coluna_vazia | SCHNEIDER | sensor por especificacao tecnica; nenhuma marca no registro |
| 13605949 | REFERENCIA_FABRICANTE | ancora_coluna_vazia | 1030VCC | referencia do fabricante nao consta no registro |
| 23453094 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 15814023 | FABRICANTE | faltante | SKF | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 16788030 | FABRICANTE | faltante | FREUDENBERG | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 13534805 | FABRICANTE | faltante | OSG | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 22258696 | FABRICANTE | faltante | TEADIT | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 22258696 | REFERENCIA_FABRICANTE | faltante | B1611 | Sem part number no registro; abster e a resposta correta |
| 11008145 | FABRICANTE | faltante | FLSMIDTH | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 12513087 | FABRICANTE | faltante | STECK | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 21229951 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 15628120 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 23845685 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 15651424 | FABRICANTE | faltante | 3M | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 15651424 | REFERENCIA_FABRICANTE | faltante | CA22003 | Sem part number no registro; abster e a resposta correta |
| 29761646 | FABRICANTE | faltante | 3M | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 29761646 | REFERENCIA_FABRICANTE | faltante | NR17034 | Sem part number no registro; abster e a resposta correta |
| 18210260 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 25741888 | FABRICANTE | faltante | DORMER | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 10479311 | FABRICANTE | faltante | PARKER | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 10479311 | REFERENCIA_FABRICANTE | faltante | B1611 | Sem part number no registro; abster e a resposta correta |
| 12055497 | FABRICANTE | faltante | WEIR | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 12055497 | REFERENCIA_FABRICANTE | faltante | F316 | Sem part number no registro; abster e a resposta correta |
| 10843276 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 16917437 | FABRICANTE | faltante | SKF | Designacao ISO de rolamento nao identifica fabricante |
| 19681337 | FABRICANTE | faltante | ALFAGOMMA | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 15368014 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 15139081 | FABRICANTE | faltante | KLINGER | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 29105527 | FABRICANTE | faltante | FREUDENBERG | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 24640445 | FABRICANTE | faltante | LAMONS | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 24640445 | REFERENCIA_FABRICANTE | faltante | B1611 | Sem part number no registro; abster e a resposta correta |
| 24913662 | FABRICANTE | faltante | METSO | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 24913662 | REFERENCIA_FABRICANTE | faltante | CF8M | Sem part number no registro; abster e a resposta correta |
| 20954223 | FABRICANTE | faltante | NTN | Designacao ISO de rolamento nao identifica fabricante |
| 10858863 | FABRICANTE | faltante | INTRAL | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 12205332 | FABRICANTE | faltante | FREUDENBERG | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 17755183 | FABRICANTE | faltante | INTRAL | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 28962728 | FABRICANTE | faltante | FREUDENBERG | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 19149584 | FABRICANTE | faltante | KLINGER | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 10907065 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 28188660 | FABRICANTE | faltante | SKF | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 22211710 | FABRICANTE | faltante | FREUDENBERG | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 16872064 | FABRICANTE | faltante | PARKER | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 16872064 | REFERENCIA_FABRICANTE | faltante | F316 | Sem part number no registro; abster e a resposta correta |
| 11479441 | FABRICANTE | faltante | SKF | Classe de especificacao tecnica; marca nao consta em texto nem coluna |
| 17369943 | FABRICANTE | faltante | GERDAU | Classe de especificacao tecnica; marca nao consta em texto nem coluna |

### Abstenções em rótulos definidos (3) — o ouro tem valor, o modelo deixou vazio

| Código | Campo | Estrato | Esperado (ouro) | Evidência |
|---|---|---|---|---|
| 16031971 | REFERENCIA_FABRICANTE | plantados | LF9009 | LF 9009 (DESCRICAO_LONGA) |
| 27494117 | REFERENCIA_FABRICANTE | typo | PEC7281 | PEC 7281 |
| 29893321 | REFERENCIA_FABRICANTE | typo | 62122RSC3 | MODELO:6212 2RS/C3 |