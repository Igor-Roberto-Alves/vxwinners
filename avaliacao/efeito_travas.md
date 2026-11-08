# Efeito das travas do dicionario aprendido

Dicionario curado: `aprendizado_curado.json` · 487 entradas, 166 aplicaveis como regra, 137 marcadas como interpretacao.

Rotulos do gold decididos pelo dicionario hoje: **70**; o dicionario curado muda **35** deles.

## Antes e depois (1 131 rotulos do gold)

| metrica | antes | depois |
|---|---|---|
| precisao | 97.5% [96%–98%] | 98.7% [98%–99%] |
| cobertura | 92.6% | 90.4% |
| taxa de invencao | 19/84 (23%) | 6/84 (7%) |
| acertos | 945 | 935 |
| erros | 24 | 12 |
| absteve (perda de cobertura) | 78 | 100 |

Erros e invencoes removidos: **25** (viraram {'ABSTEVE': 12, 'ABSTENCAO_CORRETA': 13}). Acertos perdidos: **10**.

## Cada rotulo que muda

| codigo | atributo | gold | antes | depois | veredito | motivo |
|---|---|---|---|---|---|---|
| 16064168 | ACABAMENTO | DEFINIDO:ZINCADO AMARELO | `ZINCADO AMARELO` | `(PENDENTE)` | ACERTO → ABSTEVE | termo nao aponta um unico valor do enum |
| 25277179 | CONEXAO | DEFINIDO:SOLDA TOPO BW | `SOLDA TOPO BW` | `(PENDENTE)` | ACERTO → ABSTEVE | termo nao aponta um unico valor do enum |
| 27542120 | CONEXAO | DEFINIDO:SOLDA TOPO BW | `SOLDA TOPO BW` | `(PENDENTE)` | ACERTO → ABSTEVE | termo nao aponta um unico valor do enum |
| 10361413 | MATERIAL | DEFINIDO:FERRO MALEAVEL GALVANIZADO | `FERRO MALEAVEL GALVANIZADO` | `(PENDENTE)` | ACERTO → ABSTEVE | entrada descartada na curadoria |
| 22166850 | MATERIAL | DEFINIDO:POLIURETANO | `POLIURETANO` | `(PENDENTE)` | ACERTO → ABSTEVE | entrada descartada na curadoria |
| 29595824 | MATERIAL | DEFINIDO:FERRO MALEAVEL GALVANIZADO | `FERRO MALEAVEL GALVANIZADO` | `(PENDENTE)` | ACERTO → ABSTEVE | entrada descartada na curadoria |
| 16108655 | TERMINAL A | DEFINIDO:FEMEA CURVA 90 GRAUS JIC | `FEMEA CURVA 90 GRAUS JIC` | `(PENDENTE)` | ACERTO → ABSTEVE | contexto alcanca 2 valores |
| 27846113 | TERMINAL A | DEFINIDO:FEMEA CURVA 90 GRAUS JIC | `FEMEA CURVA 90 GRAUS JIC` | `(PENDENTE)` | ACERTO → ABSTEVE | termo nao aponta um unico valor do enum |
| 16249002 | TERMINAL B | DEFINIDO:FEMEA RETA DKO | `FEMEA RETA DKO` | `(PENDENTE)` | ACERTO → ABSTEVE | termo nao aponta um unico valor do enum |
| 27430680 | TERMINAL B | DEFINIDO:FEMEA CURVA 90 GRAUS JIC | `FEMEA CURVA 90 GRAUS JIC` | `(PENDENTE)` | ACERTO → ABSTEVE | contexto alcanca 2 valores |
| 27542120 | ACIONAMENTO | DEFINIDO:VOLANTE | `ALAVANCA` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 10858863 | MATERIAL | DEFINIDO:ACO LIGA | `ACO CARBONO` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 11109434 | MATERIAL | DEFINIDO:ACO INOX FORJADO A182 F316 | `ACO INOX A403 WP316` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 11889917 | MATERIAL | DEFINIDO:ACO LIGA | `ACO CARBONO` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 20043393 | MATERIAL | DEFINIDO:ACO INOX FORJADO A182 F316 | `ACO INOX A403 WP316` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 20084323 | MATERIAL | DEFINIDO:ACO INOX FORJADO A182 F316 | `ACO INOX A403 WP316` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 20121043 | MATERIAL | DEFINIDO:ACO INOX FORJADO A182 F316 | `ACO INOX A403 WP316` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 22181613 | MATERIAL | DEFINIDO:ACO INOX FORJADO A182 F316 | `ACO INOX A403 WP316` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 23167204 | MATERIAL | DEFINIDO:ACO INOX FORJADO A182 F316 | `ACO INOX A403 WP316` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 25169236 | MATERIAL | DEFINIDO:ACO INOX FORJADO A182 F316 | `ACO INOX A403 WP316` | `(PENDENTE)` | ERRO → ABSTEVE | termo nao aponta um unico valor do enum |
| 27430680 | TERMINAL A | DEFINIDO:FEMEA RETA BSP | `FEMEA CURVA 90 GRAUS JIC` | `(PENDENTE)` | ERRO → ABSTEVE | contexto alcanca 2 valores |
| 29700768 | TERMINAL A | DEFINIDO:FEMEA RETA BSP | `FEMEA CURVA 90 GRAUS JIC` | `(PENDENTE)` | ERRO → ABSTEVE | contexto alcanca 2 valores |
| 18266130 | ACIONAMENTO | INDEFINIVEL:— | `ALAVANCA` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 13203081 | CONEXAO | INDEFINIVEL:— | `FLANGE RF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 14624421 | CONEXAO | INDEFINIVEL:— | `FLANGE RF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 15099478 | CONEXAO | INDEFINIVEL:— | `FLANGE FF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 18266130 | CONEXAO | INDEFINIVEL:— | `FLANGE FF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 19421041 | CONEXAO | INDEFINIVEL:— | `FLANGE FF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 23044290 | CONEXAO | INDEFINIVEL:— | `FLANGE RF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 23816864 | CONEXAO | INDEFINIVEL:— | `FLANGE RF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 28478391 | CONEXAO | INDEFINIVEL:— | `FLANGE RF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 28638567 | CONEXAO | INDEFINIVEL:— | `FLANGE RF` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 20504737 | MATERIAL | AUSENTE:— | `ACO CARBONO` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 14692586 | MATERIAL CORPO | INDEFINIVEL:— | `ACO INOX FORJADO A182 F316` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |
| 27846113 | TERMINAL B | AUSENTE:— | `FEMEA CURVA 90 GRAUS JIC` | `(PENDENTE)` | INVENCAO → ABSTENCAO_CORRETA | termo nao aponta um unico valor do enum |

## O que as travas NAO resolvem

- **29700768 TERMINAL B** (ERRO): gold `DEFINIDO:FEMEA CURVA 90 GRAUS JIC`, pipeline `FEMEA RETA BSP`  
  texto: MANGUEIRA HID MONT, EN 856 4SP, DIAM INTERNO:1/2", COMP:6000MM, TERMINAL A:FEMEA BSP, LADO B:JIC FEMEA 90, MATERIAL TERMINAIS:ACO CARBONO
- **25059059 TERMINAL B** (INVENCAO): gold `INDEFINIVEL:—`, pipeline `FEMEA RETA JIC`  
  texto: MANGUEIRA HID MONTADA, NORMA CONSTRUCAO EN 856 4SP, DIAM INT -8, PRESSAO 6020PSI, COMPR 2000 MM, FEM RETA JIC, TERM B JIC FEMEA, TERMINAIS A
- **28718449 TERMINAL A** (INVENCAO): gold `INDEFINIVEL:—`, pipeline `MACHO RETO NPT`  
  texto: MANG HIDRAULICA MONT SAE 100R1AT 1.1/4POL 4500MM FEMEA DKO NPT MACHO ACO CARBONO ZINCADO

## Os acertos perdidos, um por um

- **22166850 MATERIAL** = `POLIURETANO` deixa de ser preenchido (entrada descartada na curadoria)  
  texto: MANGUEIRA PNEUMATICA, MAT PU, D.E. 4MM, DIAM INTERNO 2,5MM, PT 145 PSI, COR AZUL
- **27542120 CONEXAO** = `SOLDA TOPO BW` deixa de ser preenchido (termo nao aponta um unico valor do enum)  
  texto: VALV. GAV, DIAMETRO:3/4 IN, CLASSE PRESSAO:150#, MAT CORPO:ACO INOX, TIPO CONEXAO:PONTAS CHANFRADAS, ACIONAMENTO:VOLANTE
- **25277179 CONEXAO** = `SOLDA TOPO BW` deixa de ser preenchido (termo nao aponta um unico valor do enum)  
  texto: VALVULA GLOBO DN 2-1/2" CL 300# COM CONEXAO PONTAS CHANFRADAS ACIONAMENTO DE VOLANTE
- **10361413 MATERIAL** = `FERRO MALEAVEL GALVANIZADO` deixa de ser preenchido (entrada descartada na curadoria)  
  texto: BUCHA REDUCAO 3/4 POL 1/2" 150# MALEAVEL GALV ROSCADA BSP NBR 6943
- **16064168 ACABAMENTO** = `ZINCADO AMARELO` deixa de ser preenchido (termo nao aponta um unico valor do enum)  
  texto: PARAFUSO SEXTAVADO, ROSCA:ROSCA FINA, BITOLA:M-10X1,25, C:35MM, CLASSE:8.8, ACO CARBONO, ACAB:BICROMATIZADO, NORMA:DIN 931
- **27846113 TERMINAL A** = `FEMEA CURVA 90 GRAUS JIC` deixa de ser preenchido (termo nao aponta um unico valor do enum)  
  texto: MANGUEIRA HID MONTADA EN 853 2SN 1815 PSI 1800MM FEMEA 90G JIC ACO CARBONO
- **29595824 MATERIAL** = `FERRO MALEAVEL GALVANIZADO` deixa de ser preenchido (entrada descartada na curadoria)  
  texto: LUVA REDUCAO 1/2" 1/8" MALEAVEL GALV
- **27430680 TERMINAL B** = `FEMEA CURVA 90 GRAUS JIC` deixa de ser preenchido (contexto alcanca 2 valores)  
  texto: MANG. HIDRAULICA MONTADA, NORMA:EN 856 4SP, DI:3/8 IN, PRESS TRAB:6455PSI, COMPRIMENTO:5000MM, TERM A:FEMEA BSP, TERMINAL B:FEM CURVA 90 JIC
- **16249002 TERMINAL B** = `FEMEA RETA DKO` deixa de ser preenchido (termo nao aponta um unico valor do enum)  
  texto: MANGUEIRA MONTADA HIDR, SAE 100R2AT, DIAM INT:-20, MATERIAL TERMINAIS:ACO ZINCADO, COMPRIMENTO:800MM, JIC FEMEA, TERM B:FEMEA RETA DKOL, PT:
- **16108655 TERMINAL A** = `FEMEA CURVA 90 GRAUS JIC` deixa de ser preenchido (contexto alcanca 2 valores)  
  texto: MANG. HIDRAULICA MONTADA NORMA CONSTRUCAO EN 853 2SN, DI 3/4POL, COM PRESS TRAB 219KGF/CM2, COMPRIMENTO DE 3000MM, JIC FEMEA 90, LADO B DE N

