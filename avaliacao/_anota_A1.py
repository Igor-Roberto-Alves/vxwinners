# -*- coding: utf-8 -*-
# Anotador A1 — serializa decisoes tomadas item a item (lote: linhas 0..88 de candidatos.csv).
# Cada rotulo abaixo foi decidido manualmente pelo anotador; este script apenas valida e grava.
import json, unicodedata
import pandas as pd

BASE = '/home/rviana/projects/hackathonXV/vxwinners'
df = pd.read_csv(f'{BASE}/avaliacao/candidatos.csv')

# (campo, y_gold, status, evidencia, justificativa, fonte)
D = {
# ---------------- PLANTADOS (0-14): GRUPO|NCM|FABRICANTE|REFERENCIA ----------------
0: [
 ("GRUPO_MERCADORIA","ROL01","DEFINIDO","ROL 6205-2RSH/C3 SKF","rolamento rigido de esferas -> PDM020, grupo ROL01","pdm"),
 ("NCM","84821010","DEFINIDO","ROL 6205-2RSH/C3","PDM020 rolamento rigido esferas: 8482.10.10 unico para a classe","pdm"),
 ("FABRICANTE","SKF","DEFINIDO","ROL 6205-2RSH/C3 SKF","marca explicita no texto; sufixo 2RSH e nomenclatura SKF","texto"),
 ("REFERENCIA_FABRICANTE","62052RSHC3","DEFINIDO","6205-2RSH/C3","designacao completa do rolamento = referencia; sem separadores","texto"),
],
1: [
 ("GRUPO_MERCADORIA","ROL01","DEFINIDO","ROLAMENTO FAG 6205-C-2HRS-C3","rolamento rigido de esferas -> PDM020, grupo ROL01","pdm"),
 ("NCM","84821010","DEFINIDO","ROLAMENTO FAG 6205-C-2HRS-C3","PDM020: 8482.10.10 unico para a classe","pdm"),
 ("FABRICANTE","FAG","DEFINIDO","ROLAMENTO FAG 6205-C-2HRS-C3","marca explicita no texto; designacao geracao C e da FAG","texto"),
 ("REFERENCIA_FABRICANTE","6205C2HRSC3","DEFINIDO","6205-C-2HRS-C3","designacao FAG completa = referencia; sem separadores","texto"),
],
2: [
 ("GRUPO_MERCADORIA","ROL01","DEFINIDO","ROLAMENTO 6205DDUC3","rolamento rigido de esferas -> PDM020, grupo ROL01","pdm"),
 ("NCM","84821010","DEFINIDO","ROLAMENTO 6205DDUC3","PDM020: 8482.10.10 unico para a classe","pdm"),
 ("FABRICANTE","NSK","DEFINIDO","6205DDUC3; coluna FAB=NSK","sufixo de vedacao DDU e proprio da NSK; coluna coerente","dominio"),
 ("REFERENCIA_FABRICANTE","6205DDUC3","DEFINIDO","ROLAMENTO 6205DDUC3","designacao NSK completa = referencia","texto"),
],
3: [
 ("GRUPO_MERCADORIA","ROL01","DEFINIDO","ROLAMENTO 6310-2Z/C3 SKF","rolamento rigido de esferas -> PDM020, grupo ROL01","pdm"),
 ("NCM","84821010","DEFINIDO","ROLAMENTO 6310-2Z/C3 SKF","PDM020: 8482.10.10 unico para a classe","pdm"),
 ("FABRICANTE","SKF","DEFINIDO","ROLAMENTO 6310-2Z/C3 SKF","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","63102ZC3","DEFINIDO","6310-2Z/C3","designacao completa = referencia; sem separadores","texto"),
],
4: [
 ("GRUPO_MERCADORIA","ROL01","DEFINIDO","ROL 6310-C-2Z-C3","rolamento rigido de esferas -> PDM020, grupo ROL01","pdm"),
 ("NCM","84821010","DEFINIDO","ROL 6310-C-2Z-C3","PDM020: 8482.10.10 unico para a classe","pdm"),
 ("FABRICANTE","FAG","DEFINIDO","ROL 6310-C-2Z-C3; coluna FAB=FAG","designacao geracao C (-C-) e da FAG; coluna coerente","dominio"),
 ("REFERENCIA_FABRICANTE","6310C2ZC3","DEFINIDO","6310-C-2Z-C3","designacao FAG completa = referencia; sem separadores","texto"),
],
5: [
 ("GRUPO_MERCADORIA","ROL01","DEFINIDO","ROLAMENTO NTN 6310ZZC3","rolamento rigido de esferas -> PDM020, grupo ROL01","pdm"),
 ("NCM","84821010","DEFINIDO","ROLAMENTO NTN 6310ZZC3","PDM020: 8482.10.10 unico para a classe","pdm"),
 ("FABRICANTE","NTN","DEFINIDO","ROLAMENTO NTN 6310ZZC3","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","6310ZZC3","DEFINIDO","6310ZZC3","designacao completa = referencia","texto"),
],
6: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO LF9009","filtro -> classe FILTRO (PDM100), grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO LF9009","LF9009 e filtro de oleo lubrificante; PDM100: oleo -> 8421.23.00; web indisponivel (403)","dominio"),
 ("FABRICANTE","FLEETGUARD","DEFINIDO","FILTRO LF9009; coluna FAB vazia","prefixo LF e numeracao classica Fleetguard (filtro lubrificante); web indisponivel","dominio"),
 ("REFERENCIA_FABRICANTE","LF9009","DEFINIDO","FILTRO LF9009","part number no texto","texto"),
],
7: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO OLEO LUBRIFICANTE FLEETGUARD LF 9009","filtro -> PDM100, grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO OLEO LUBRIFICANTE","PDM100: oleo e combustivel -> 8421.23.00","pdm"),
 ("FABRICANTE","FLEETGUARD","DEFINIDO","FLEETGUARD LF 9009","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","LF9009","DEFINIDO","LF 9009 (DESCRICAO_LONGA)","PN com espaco no texto; normalizado LF9009","texto"),
],
8: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","ELEMENTO FILTRANTE OLEO FLEETGUARD LF3970","elemento filtrante de oleo = filtro -> PDM100, FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","ELEMENTO FILTRANTE OLEO","PDM100: oleo -> 8421.23.00","pdm"),
 ("FABRICANTE","FLEETGUARD","DEFINIDO","FLEETGUARD LF3970","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","LF3970","DEFINIDO","LF3970 (DESCRICAO_LONGA)","curta truncada LF397; longa completa LF3970","texto"),
],
9: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO OLEO 1R1808 CAT","filtro -> PDM100, grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO OLEO","PDM100: oleo -> 8421.23.00","pdm"),
 ("FABRICANTE","CATERPILLAR","DEFINIDO","FILTRO OLEO 1R1808 CAT","CAT -> nome canonico CATERPILLAR na base","texto"),
 ("REFERENCIA_FABRICANTE","1R1808","DEFINIDO","1R1808","part number CAT no texto","texto"),
],
10: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO OLEO MOTOR CATERPILLAR 1R-1808","filtro -> PDM100, grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO OLEO MOTOR","PDM100: oleo -> 8421.23.00","pdm"),
 ("FABRICANTE","CATERPILLAR","DEFINIDO","CATERPILLAR 1R-1808","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","1R1808","DEFINIDO","1R-1808","PN sem separador","texto"),
],
11: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO P551808 DONALDSON","filtro -> PDM100, grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO P551808","P551808 e filtro lubrificante Donaldson (equivalente CAT 1R-1808); oleo -> 8421.23.00; web indisponivel","dominio"),
 ("FABRICANTE","DONALDSON","DEFINIDO","FILTRO P551808 DONALDSON","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","P551808","DEFINIDO","P551808","part number no texto","texto"),
],
12: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO LUBR B40142 BALDWIN","filtro -> PDM100, grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO LUBR","LUBR = lubrificante; PDM100: oleo -> 8421.23.00","pdm"),
 ("FABRICANTE","BALDWIN","DEFINIDO","B40142 BALDWIN","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","B40142","DEFINIDO","B40142","part number no texto","texto"),
],
13: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO DBL7300","filtro -> PDM100, grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO DBL7300","DBL = linha Donaldson Blue de filtros lubrificantes; oleo -> 8421.23.00; web indisponivel (403)","dominio"),
 ("FABRICANTE","DONALDSON","DEFINIDO","FILTRO DBL7300; coluna FAB vazia","prefixo DBL = Donaldson Blue; web indisponivel","dominio"),
 ("REFERENCIA_FABRICANTE","DBL7300","DEFINIDO","DBL7300","part number no texto","texto"),
],
14: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO OLEO MOTOR LF691A FLEETGUARD","filtro -> PDM100, grupo FIL01","pdm"),
 ("NCM","84212300","DEFINIDO","FILTRO OLEO MOTOR","PDM100: oleo -> 8421.23.00","pdm"),
 ("FABRICANTE","FLEETGUARD","DEFINIDO","LF691A FLEETGUARD","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","LF691A","DEFINIDO","LF691A","part number no texto","texto"),
],
# ---------------- TYPO (15-50): GRUPO|FABRICANTE|REFERENCIA ----------------
15: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILT OLEO LUBRIFICANTE;USO: CAMINHAO FORA DE ESTRADA","FILT = filtro -> PDM100, grupo FIL01","pdm"),
 ("FABRICANTE","TECFIL","DEFINIDO","FABRICANTE: TECFIL","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","PSL030","DEFINIDO","REF: PSL 030 (texto e coluna)","PN com espaco; normalizado sem separador","texto"),
],
16: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","BUCHA;ESCAVADEIRA HIDRAULICA;EQUIP:PC3000","BUCHA e substantivo de SOBRESSALENTES (PDM110) -> SOB01","pdm"),
 ("FABRICANTE","KOMATSU","DEFINIDO","MARCA:KOMATSU","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","8363454397","DEFINIDO","PART NUMBER:836-34-54397","PN Komatsu sem separadores","texto"),
],
17: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","BRACO SUSPENSAO ... CAMINHAO FORA DE ESTRADA, 830E","BRACO SUSPENSAO e substantivo de SOBRESSALENTES (PDM110)","pdm"),
 ("FABRICANTE","KOMATSU","DEFINIDO","FABRICANTE KOMATSU","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","0772693307","DEFINIDO","REFERENCA FABRICANTE 077-26-93307","typo REFERENCA no rotulo; PN normalizado sem separadores","texto"),
],
18: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO COMBUSTIVEL ESCAVADEIRA HIDRAULICA","filtro -> PDM100, grupo FIL01","pdm"),
 ("FABRICANTE","TECFIL","DEFINIDO","TECFIL PEC 7281","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","PEC7281","DEFINIDO","PEC 7281","PN com espaco; normalizado","texto"),
],
19: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","LABIRINTO TURBINA HIDRAULICA FRANCIS 12MW","labirinto = sobressalente de TURBINA HIDRAULICA (PDM110) -> SOB01","pdm"),
 ("FABRICANTE","VOITH","DEFINIDO","VOITH 983.327.460","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","983327460","DEFINIDO","VOITH 983.327.460 REF ANTIGA","unica referencia registrada; texto a marca como antiga","texto"),
],
20: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAF SEXTAVADO COM ROSCA UNC ... NORMA DE ASME B18.2.1","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
21: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXTAVADO, ROSCA:UNC ... ASME B18.2.1","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
22: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","ADAPTADOR ESCAVADEIRA HIDRAULICA PC3000","ADAPTADOR e substantivo de SOBRESSALENTES (PDM110) -> SOB01","pdm"),
 ("FABRICANTE","KOMATSU","DEFINIDO","PC3000 KOMATSU 182-89-91782","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","1828991782","DEFINIDO","182-89-91782 REV A","REV A e revisao, fora da referencia; PN sem separadores","texto"),
],
23: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","LUVA EIXO BOMBA CENTRIFUGA AHLSTAR A31-100","LUVA EIXO esta em SUBSTANTIVOS_SOBRESSALENTES (nao e conexao) -> SOB01","pdm"),
 ("FABRICANTE","SULZER","DEFINIDO","FABR SULZER","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","914405614","DEFINIDO","COD FABRICANTE 914405-614","PN sem separador","texto"),
],
24: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO OLEO LUBRIF, MANN","filtro -> PDM100, grupo FIL01","pdm"),
 ("FABRICANTE","MANN","DEFINIDO","FILTRO OLEO LUBRIF, MANN","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","W07605","DEFINIDO","COD FABRICANTE:W 076/05","PN estilo MANN; separadores removidos","texto"),
],
25: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXTAVADO; ROSCA: UNC; BITOLA: 5/16POL","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
26: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXTAVADO, UNC, DIAMETRO:1/2POL","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
27: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","MANDIBULA MOVEL, APLIC:BRITADOR MANDIBULA, EQUIP:C106","MANDIBULA MOVEL e substantivo de SOBRESSALENTES (PDM110)","pdm"),
 ("FABRICANTE","METSO","DEFINIDO","MARCA:METSO","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","N81788A66","DEFINIDO","PN:N81788A66 REV A","REV A e revisao, fora da referencia; coluna confirma","texto"),
],
28: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","CUNHA, APLICACAO: BRITADOR MANDIBULA, EQUIP: C106","CUNHA e substantivo de SOBRESSALENTES (PDM110) -> SOB01","pdm"),
 ("FABRICANTE","METSO","DEFINIDO","EQUIP: C106, METSO","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","N71088U72","DEFINIDO","PART NUMBER: N71088U72","PN no texto; coluna confirma","texto"),
],
29: [
 ("GRUPO_MERCADORIA","FIL01","DEFINIDO","FILTRO OLEO LUBRIFICANTE; APLICACAO: VEICULO LEVE","filtro -> PDM100, grupo FIL01","pdm"),
 ("FABRICANTE","MANN","DEFINIDO","FABRICANTE: MANN","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","W19992","DEFINIDO","REFERENCIA FABRICANTE: W 199/92","PN estilo MANN; separadores removidos","texto"),
],
30: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXTAVADO UNC 1/4\"X1 1/4POL","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto (COMPRA LOCAL e nota); colunas vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
31: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAF SEXTAVADO COM ROSCA METRICA GROSSA, M20 ... DIN 933","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
32: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXTAVADO ... ASME B18.2.1; coluna GRUPO=FIL01","descricao contradiz coluna: parafuso sextavado -> FIX01 (PDM001); coluna errada","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
33: [
 ("GRUPO_MERCADORIA","VAL01","DEFINIDO","VALVULA BORBOLETA, BITOLA: 2POL, TIPO CORPO: LUG","valvula borboleta -> PDM044, grupo VAL01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","valvula por especificacao; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","referencia nao consta no registro","texto"),
],
34: [
 ("GRUPO_MERCADORIA","VAL01","DEFINIDO","VALV BORBOLETA 2\" WAFER ACO INOX","valvula borboleta -> PDM044, grupo VAL01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","valvula por especificacao; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","referencia nao consta no registro","texto"),
],
35: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAF. HEXAGONAL, ROSCA:UNC ... ASME B18.2.1","hexagonal = sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
36: [
 ("GRUPO_MERCADORIA","LUB01","DEFINIDO","OLEO LUBRIFICANTE; APLICACAO: MOTOR DIESEL; SAE 5W40","oleo lubrificante -> PDM090, grupo LUB01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto (SAE 5W40 e viscosidade); colunas vazias","oleo por especificacao; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","referencia nao consta no registro","texto"),
],
37: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXT, MA, BITOLA:M-36 ... DIN 931","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
38: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","ROTOR; APLIC:BOMBA CENTRIFUGA; MODELO:AHLSTAR A22 80","ROTOR e substantivo de SOBRESSALENTES (PDM110) -> SOB01","pdm"),
 ("FABRICANTE","SULZER","DEFINIDO","FABRICANTE:SULZER","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem PN; AHLSTAR A22 80 e modelo do equipamento; coluna REF vazia","referencia do fabricante nao consta no registro","texto"),
],
39: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","CHAPA LATERAL CJ412","CHAPA LATERAL e substantivo de SOBRESSALENTES (PDM110); CJ412 = britador","pdm"),
 ("FABRICANTE","SANDVIK","DEFINIDO","CHAPA LATERAL CJ412 PN 37.3424-48 SANDVIK","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","37342448","DEFINIDO","PN 37.3424-48","PN Sandvik sem separadores","texto"),
],
40: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","CONTRAEIXO, APLICACAO: BRITADOR CONICO","CONTRAEIXO e substantivo de SOBRESSALENTES (PDM110) -> SOB01","pdm"),
 ("FABRICANTE","FLSMIDTH","DEFINIDO","MARCA: FLSMIDTH","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","4333990485","DEFINIDO","P/N: 4333990485","PN no texto; coluna confirma","texto"),
],
41: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXTAVADO, ROSCA:UNC, DIAMETRO:1-1/8\"","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
42: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","MANDIBULA MOVEL PN N10601168 METSO","MANDIBULA MOVEL e substantivo de SOBRESSALENTES (PDM110)","pdm"),
 ("FABRICANTE","METSO","DEFINIDO","MANDIBULA MOVEL PN N10601168 METSO","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","N10601168","DEFINIDO","PN N10601168","PN Metso no texto","texto"),
],
43: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAF. SEXTAVADO UNC 7/8POLX6POL ... ASME B18.2.1","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
44: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","LAMINA RASPADOR APLIC DE CORREIA TRANSPORTADORA","LAMINA RASPADOR e substantivo de SOBRESSALENTES (PDM110)","pdm"),
 ("FABRICANTE","MARTIN ENGINEERING","DEFINIDO","MARCA MARTIN ENGINEERING","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","65514AS","DEFINIDO","COD FABRICANTE 65514-AS REV A","REV A e revisao; sufixo AS integra o PN; sem separadores","texto"),
],
45: [
 ("GRUPO_MERCADORIA","FIX01","DEFINIDO","PARAFUSO SEXTAVADO, ROSCA:UNC, DIAMETRO:7/16\"","parafuso sextavado -> PDM001, grupo FIX01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","item por especificacao tecnica; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","item por especificacao tecnica; referencia nao consta","texto"),
],
46: [
 ("GRUPO_MERCADORIA","SOB01","DEFINIDO","MANDIBULA MOVEL, MODELO EQUIPAMENTO:C140","MANDIBULA MOVEL e substantivo de SOBRESSALENTES (PDM110)","pdm"),
 ("FABRICANTE","METSO","DEFINIDO","coluna FAB=METSO; texto sem marca; EQUIP C140, PN N36237717","C140 e britador de mandibulas Metso; PN com prefixo N padrao Metso","coluna"),
 ("REFERENCIA_FABRICANTE","N36237717","DEFINIDO","PN:N36237717","PN no texto; coluna confirma","texto"),
],
47: [
 ("GRUPO_MERCADORIA","VAL01","DEFINIDO","VALV ESF, TIPO CONEXAO:RSC NPT, CLASSE PRESSAO:800#","VALV ESF = valvula esfera -> PDM040, grupo VAL01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","valvula por especificacao; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","referencia nao consta no registro","texto"),
],
48: [
 ("GRUPO_MERCADORIA","ROL01","DEFINIDO","ROLAMENTO RIG ESF, MODELO:6212 2RS/C3","rolamento rigido de esferas -> PDM020, grupo ROL01","pdm"),
 ("FABRICANTE","FAG","DEFINIDO","coluna FAB=FAG; texto sem marca","designacao 6212-2RS e generica e nao contradiz; coluna e a unica fonte","coluna"),
 ("REFERENCIA_FABRICANTE","62122RSC3","DEFINIDO","MODELO:6212 2RS/C3","designacao do rolamento = referencia (cf. exemplo do PDM); sem separadores","texto"),
],
49: [
 ("GRUPO_MERCADORIA","VAL01","DEFINIDO","VALVULA GAV BITOLA DE DN150 150# ... CASTELO APARAFUSADO","VALV GAV = valvula gaveta -> PDM041, grupo VAL01","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","valvula por especificacao; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","referencia nao consta no registro","texto"),
],
50: [
 ("GRUPO_MERCADORIA","ELE01","DEFINIDO","TERMINAL ELETRICO, PRE-ISOLADO FORQUILHA; coluna GRUPO=VED01","descricao contradiz coluna: terminal eletrico -> ELE01 (PDM061); coluna errada","pdm"),
 ("FABRICANTE","","AUSENTE","sem marca no texto; colunas FAB/REF vazias","terminal por especificacao; fabricante nao consta no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; coluna REF vazia","referencia nao consta no registro","texto"),
],
# ---------------- ANCORA_COM_COLUNA (51-70): FABRICANTE|REFERENCIA ----------------
51: [
 ("FABRICANTE","SANDVIK","DEFINIDO","FAB:SANDVIK","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","433853800","DEFINIDO","REF FABRICANTE:433.853800; coluna 4338538-00","mesmos digitos no texto e na coluna; -00 integra o PN Sandvik (NNN.NNNN-NN)","texto"),
],
52: [
 ("FABRICANTE","EPIROC","DEFINIDO","FLEXIROC T45, EPIROC","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","7388541992","DEFINIDO","REFERENCIA FABRICANTE 7388 5419 92","PN Epiroc 10 digitos; espacos removidos","texto"),
],
53: [
 ("FABRICANTE","SANDVIK","DEFINIDO","CABECOTE DP1500 PN 180.4331-01 SANDVIK","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","180433101","DEFINIDO","PN 180.4331-01; coluna 180.433101","mesmos digitos; separadores removidos","texto"),
],
54: [
 ("FABRICANTE","METSO","DEFINIDO","EQUIP:MB 5.0X7.6, METSO","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","N87512446","DEFINIDO","REF FABRICANTE:N87512446","PN no texto; coluna confirma","texto"),
],
55: [
 ("FABRICANTE","METSO","DEFINIDO","LEVANTADOR MOOINHO BOLAS ... METSO","marca no texto (typo MOOINHO nao afeta); coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","N58502G07","DEFINIDO","PN N58502G07 REV A","REV A e revisao; registro aponta codigo substituto, mas o item e este PN","texto"),
],
56: [
 ("FABRICANTE","KSB","DEFINIDO","MODELO EQUIPAMENTO: MEGANORM 100-315; FABRICANTE: KSB","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","90151958","DEFINIDO","REFERENCIA FABRICANTE: 90151958","PN no texto; coluna confirma","texto"),
],
57: [
 ("FABRICANTE","SANDVIK","DEFINIDO","MODELO EQUIPAMENTO CJ615 MARCA DE SANDVIK","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","199400938","DEFINIDO","P/N 199.4009-38","PN Sandvik sem separadores; coluna confirma","texto"),
],
58: [
 ("FABRICANTE","KOMATSU","DEFINIDO","EIXO PN 157-13-63369 KOMATSU","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","1571363369","DEFINIDO","PN 157-13-63369","PN Komatsu sem separadores; coluna confirma","texto"),
],
59: [
 ("FABRICANTE","SANDVIK","DEFINIDO","EQUIP:CH440, FABR:SANDVIK","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","071629891","DEFINIDO","PART NUMBER:071.6298-91; coluna 0716298-91","PN Sandvik sem separadores, zero inicial mantido","texto"),
],
60: [
 ("FABRICANTE","FRAM","DEFINIDO","coluna FAB=FRAM; texto P/N:CA18490-00 sem marca","prefixo CA e da linha de filtros de ar FRAM; coluna coerente","coluna"),
 ("REFERENCIA_FABRICANTE","CA18490","DEFINIDO","texto P/N:CA18490-00; coluna REF=CA18490","sufixo -00 apos PN completo e revisao (padrao do conjunto); coluna confirma","coluna"),
],
61: [
 ("FABRICANTE","FLENDER","DEFINIDO","EIXO SAIDA REDUTOR PN H5724-617345 FLENDER","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","H5724617345","DEFINIDO","PN H5724-617345","PN sem separador; coluna confirma","texto"),
],
62: [
 ("FABRICANTE","HAVER","DEFINIDO","T CLASS 3.0X7.3 PN HB-907889 HAVER","marca explicita no texto (Haver & Boecker); coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","HB907889","DEFINIDO","PN HB-907889","PN sem separador; coluna confirma","texto"),
],
63: [
 ("FABRICANTE","WEIR","DEFINIDO","MOD WARMAN 6/4 D AH COM FABRICANTE WEIR","marca explicita no texto (Warman e linha da Weir); coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","A7953B68","DEFINIDO","P/N A7953B68","PN no texto; coluna confirma","texto"),
],
64: [
 ("FABRICANTE","FLSMIDTH","DEFINIDO","MODELO EQUIPAMENTO: RAPTOR 450; FABRICANTE: FLSMIDTH","marca explicita no texto; coluna confirma (GRUPO=FER01 errado nao afeta)","texto"),
 ("REFERENCIA_FABRICANTE","7962108526","DEFINIDO","REFERENCIA FABRICANTE: 7962108526","PN no texto; coluna confirma","texto"),
],
65: [
 ("FABRICANTE","VOITH","DEFINIDO","TURBINA HIDRAULICA, KAPLAN 8MW, FAB VOITH","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","546288052","DEFINIDO","texto PN 546.288.052-00; coluna 546.288.052","-00 final e revisao (formato Voith e NNN.NNN.NNN); coluna confirma","texto"),
],
66: [
 ("FABRICANTE","METSO","DEFINIDO","PN: N17910Z50, METSO, MOD: C106","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","N17910Z50","DEFINIDO","PN: N17910Z50 (ITEM CRITICO e nota)","PN no texto; coluna confirma","texto"),
],
67: [
 ("FABRICANTE","SANDVIK","DEFINIDO","ANEL VEDACAO, P/N:708.9961-42, MARCA:SANDVIK","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","708996142","DEFINIDO","P/N:708.9961-42","PN Sandvik sem separadores; coluna confirma","texto"),
],
68: [
 ("FABRICANTE","FLSMIDTH","DEFINIDO","coluna FAB=FLSMIDTH; texto so MODELO:LUDOWICI 3.6X8.5","LUDOWICI e marca de peneiras incorporada pela FLSmidth; coluna coerente","coluna"),
 ("REFERENCIA_FABRICANTE","2411614777","DEFINIDO","COD FABRICANTE:2411614777","PN no texto; coluna confirma","texto"),
],
69: [
 ("FABRICANTE","METSO","DEFINIDO","MODELO EQUIPAMENTO: LH 8X20, MARCA: METSO","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","N90432T61","DEFINIDO","P/N: N90432T61","PN no texto; coluna confirma","texto"),
],
70: [
 ("FABRICANTE","METSO","DEFINIDO","VIGA, MOD:LH 8X20 ... METSO","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","N52276M47","DEFINIDO","P/N:N52276M47","PN no texto; coluna confirma","texto"),
],
# ---------------- ANCORA_COLUNA_VAZIA (71-88): FABRICANTE|REFERENCIA ----------------
71: [
 ("FABRICANTE","METSO","DEFINIDO","FAB:METSO (coluna FAB vazia)","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","N05972H27","DEFINIDO","REFERENCIA FABRICANTE:N05972H27","PN no texto; coluna confirma","texto"),
],
72: [
 ("FABRICANTE","WEG","DEFINIDO","FABR:WEG (coluna FAB vazia)","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","43675422","DEFINIDO","COD FABRICANTE:43675422","PN no texto; coluna confirma","texto"),
],
73: [
 ("FABRICANTE","METSO","DEFINIDO","MODELO EQUIPAMENTO:MP800, MARCA:METSO (colunas vazias)","marca explicita no texto; MP800 e britador conico Metso","texto"),
 ("REFERENCIA_FABRICANTE","MM6873619","DEFINIDO","P/N:MM6873619 (coluna REF vazia)","PN Metso (prefixo MM) so no texto","texto"),
],
74: [
 ("FABRICANTE","ATLAS COPCO","DEFINIDO","MODELO EQUIPAMENTO: ZR250; FABRICANTE: ATLAS COPCO","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","0682032350","DEFINIDO","REFERENCIA FABRICANTE: 0682 0323 50 (coluna REF vazia)","PN Atlas Copco 10 digitos; espacos removidos","texto"),
],
75: [
 ("FABRICANTE","SANDVIK","DEFINIDO","MODELO EQUIPAMENTO: DI550; FABRICANTE: SANDVIK","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","105161507","DEFINIDO","REFERENCIA FABRICANTE: 105.1615-07 (coluna REF vazia)","PN Sandvik sem separadores","texto"),
],
76: [
 ("FABRICANTE","CATERPILLAR","DEFINIDO","BUCHA 6015B PN 480-0954 CATERPILLAR (colunas vazias)","marca explicita no texto; 6015B e escavadeira Cat","texto"),
 ("REFERENCIA_FABRICANTE","4800954","DEFINIDO","PN 480-0954 (coluna REF vazia)","PN Cat (formato NNN-NNNN) sem separador","texto"),
],
77: [
 ("FABRICANTE","SANDVIK","DEFINIDO","CABECOTE DP1500 PN 4867981-40 SANDVIK (coluna FAB vazia)","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","486798140","DEFINIDO","texto PN 4867981-40; coluna 486.7981-40-00","-00 extra na coluna e revisao; texto traz o PN completo Sandvik","texto"),
],
78: [
 ("FABRICANTE","HITACHI","DEFINIDO","MOD:EX2600, FABRICANTE:HITACHI","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","8452508","DEFINIDO","PN:8452508 (coluna REF vazia)","PN no texto","texto"),
],
79: [
 ("FABRICANTE","KOMATSU","DEFINIDO","BUCHA; ESCAVADEIRA HIDRAULICA; KOMATSU; PC2000","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","9699377942","DEFINIDO","PART NUMBER: 9699377942 (coluna REF vazia)","PN no texto","texto"),
],
80: [
 ("FABRICANTE","HITACHI","DEFINIDO","EQUIP:EX2600, MARCA:HITACHI","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","3585436","DEFINIDO","COD FABRICANTE:3585436, CONF AMOSTRA","CONF AMOSTRA e nota, nao integra o PN","texto"),
],
81: [
 ("FABRICANTE","METSO","DEFINIDO","MODELO:C106, METSO","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","N96275812","DEFINIDO","COD FABRICANTE:N96275812 (coluna REF vazia)","PN Metso no texto","texto"),
],
82: [
 ("FABRICANTE","METSO","DEFINIDO","HP400 PN MM1686521 REV A METSO (coluna FAB vazia)","marca explicita no fim do texto; HP400 e britador Metso","texto"),
 ("REFERENCIA_FABRICANTE","MM1686521","DEFINIDO","PN MM1686521 REV A; coluna REF=MM1686521","REV A e revisao, fora da referencia; coluna confirma","texto"),
],
83: [
 ("FABRICANTE","SANDVIK","DEFINIDO","MOD: CH440, FABR: SANDVIK (coluna FAB vazia)","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","596849953","DEFINIDO","REFERENCIA FABRICANTE: 596.8499-53","PN Sandvik sem separadores; coluna confirma","texto"),
],
84: [
 ("FABRICANTE","METSO","DEFINIDO","MODELO EQUIPAMENTO: TS 3.6X7.3; FABRICANTE: METSO","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","N34076729","DEFINIDO","REFERENCIA FABRICANTE: N34076729 (coluna REF vazia)","PN Metso no texto","texto"),
],
85: [
 ("FABRICANTE","MANN","DEFINIDO","FILTRO OLEO LUBRIF, FAB MANN","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","W87581","DEFINIDO","PART NUMBER W 875/81 (coluna REF vazia)","PN estilo MANN; separadores removidos","texto"),
],
86: [
 ("FABRICANTE","FLENDER","DEFINIDO","EIXO SAIDA REDUTOR PN V8739-882779 FLENDER","marca explicita no texto; coluna confirma","texto"),
 ("REFERENCIA_FABRICANTE","V8739882779","DEFINIDO","PN V8739-882779 (coluna REF vazia)","PN sem separador","texto"),
],
87: [
 ("FABRICANTE","","AUSENTE","SENSOR INDUTIVO, ROSCA:M-12, SN:4 MM ... (colunas vazias)","sensor por especificacao tecnica; nenhuma marca no registro","texto"),
 ("REFERENCIA_FABRICANTE","","AUSENTE","sem part number no texto; colunas FAB/REF vazias","referencia do fabricante nao consta no registro","texto"),
],
88: [
 ("FABRICANTE","CONTINENTAL","DEFINIDO","FAB DE CONTINENTAL (coluna FAB vazia)","marca explicita no texto, canonica na base","texto"),
 ("REFERENCIA_FABRICANTE","CT6110181","DEFINIDO","P/N CT6110181; coluna 'CT6110181 REV A'","REV A na coluna e revisao, fora da referencia","texto"),
],
}

# ---- validacao e gravacao ----
import re
ok_status = {"DEFINIDO","AUSENTE","INDEFINIVEL"}
ok_fonte = {"texto","coluna","pdm","dominio","web"}
rows_out = []
for idx in range(0, 89):
    r = df.iloc[idx]
    alvo = r['campos_alvo'].split('|')
    assert idx in D, f'linha {idx} sem decisao'
    campos = [c for c,_,_,_,_,_ in D[idx]]
    assert campos == alvo, f'linha {idx}: campos {campos} != alvo {alvo}'
    for campo, y, st, ev, ju, fo in D[idx]:
        assert st in ok_status and fo in ok_fonte, (idx, campo)
        assert len(ev) <= 160, (idx, campo, 'evidencia', len(ev))
        assert len(ju) <= 120, (idx, campo, 'justificativa', len(ju))
        if st == 'DEFINIDO':
            assert y, (idx, campo, 'y_gold vazio')
            if campo == 'NCM':
                assert re.fullmatch(r'\d{8}', y), (idx, y)
            if campo == 'REFERENCIA_FABRICANTE':
                assert re.fullmatch(r'[A-Z0-9]+', y), (idx, y)
            if campo in ('FABRICANTE','GRUPO_MERCADORIA'):
                assert y == y.upper() and not any(unicodedata.combining(ch) for ch in unicodedata.normalize('NFD', y)), (idx, y)
        else:
            assert y == '', (idx, campo, 'y_gold deveria ser vazio')
        rows_out.append({
            "CODIGO_MATERIAL": str(r['CODIGO_MATERIAL']),
            "campo": campo, "y_gold": y, "status": st,
            "evidencia": ev, "justificativa": ju, "fonte": fo,
        })

out = f'{BASE}/avaliacao/anotacoes_A1.jsonl'
with open(out, 'w', encoding='utf-8') as f:
    for row in rows_out:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')

# conferencia final: todos os itens do lote com todos os campos
import collections
cnt = collections.Counter()
for row in rows_out:
    cnt[row['CODIGO_MATERIAL']] += 1
exp = {str(df.iloc[i]['CODIGO_MATERIAL']): len(df.iloc[i]['campos_alvo'].split('|')) for i in range(89)}
faltando = {k: (cnt.get(k,0), v) for k,v in exp.items() if cnt.get(k,0) != v}
print('itens no lote:', len(exp), '| itens anotados:', len(cnt), '| divergencias:', faltando)
print('total de rotulos:', len(rows_out))
print('por status:', collections.Counter(r['status'] for r in rows_out))
print('por campo:', collections.Counter(r['campo'] for r in rows_out))
print('por fonte:', collections.Counter(r['fonte'] for r in rows_out))
