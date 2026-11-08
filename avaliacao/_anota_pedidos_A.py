# -*- coding: utf-8 -*-
"""PASSADA A do gabarito de pedidos - persona: ANALISTA DE CADASTRO.

Regra de decisao desta persona (o PDM ao pe da letra):
  - so fecha um valor de lista quando o texto nomeia aquele valor sem ambiguidade,
    ou quando o termo do texto so admite UM valor da lista;
  - diante de termo que a lista nao decide ("aco inox" sem 304/316, "zinc plated"
    sem a cor), marca INDEFINIVEL, nao escolhe o mais comum;
  - NAO deduz atributo de conhecimento externo ao texto: se o pedido da o modelo
    do equipamento (H3SH 9) mas nao diz o tipo (REDUTOR), APLICACAO fica AUSENTE,
    porque ligar modelo a tipo exige o catalogo do fabricante, que nao esta no
    pedido;
  - contexto de uso ("para a parada programada", "pra bomba da barragem") nao e
    atributo em classe de especificacao tecnica.

Lido para anotar: so avaliacao/candidatos_pedidos.csv (linha crua do pedido) e
dados/03_padrao_cadastro_PDM.xlsx. Nenhum artefato do pipeline.

Uso: backend/.venv/bin/python avaliacao/_anota_pedidos_A.py
Saida: avaliacao/anotacoes_pedidos_A.jsonl
"""
from pathlib import Path

from _anota_pedidos_comum import expande

# Conexoes PDM050 que nao sao flange nem reducao: os quatro condicionais caem fora.
_PDM050_SIMPLES = ["TIPO", "DIAMETRO REDUZIDO", "SCHEDULE", "FACE"]

DECISOES = {
    # ---------------------------------------------------------------- PDM011 ---
    "SC-202600020": dict(classe="PDM011", ev="mangueira hidráulica montada", vals={
        "NORMA": "EN 856 4SP", "DIAMETRO INTERNO": ("1/2POL", "1/2 pol"),
        "COMPRIMENTO": ("500MM", "500 mm"),
        "TERMINAL A": "FEMEA CURVA 45 GRAUS JIC", "TERMINAL B": "FEMEA RETA ORFS",
        "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600028": dict(classe="PDM011", ev="mangueira hidráulica montada", vals={
        "NORMA": ("EN 853 2SN", "en 853 2sn"), "DIAMETRO INTERNO": ("5/8POL", "5/8 pol"),
        "COMPRIMENTO": ("1000MM", "1000mm"),
        "TERMINAL A": "FEMEA CURVA 90 GRAUS JIC", "TERMINAL B": "FEMEA RETA ORFS",
        "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600462": dict(classe="PDM011", ev="mangueira hidráulica montada", vals={
        "NORMA": ("EN 856 4SH", "en 856 4sh"),
        "DIAMETRO INTERNO": ("1.1/2POL", '1 1/2"', "fração mista -> inteiro.fração+POL"),
        "COMPRIMENTO": ("900MM", "900 mm"),
        "TERMINAL A": "MACHO RETO JIC", "TERMINAL B": "FEMEA RETA JIC",
        "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600078": dict(classe="PDM011", ev="mangueira hidráulica montada", vals={
        "NORMA": ("EN 856 4SP", "en 856 4sp"), "DIAMETRO INTERNO": ("1/2POL", "1/2 pol"),
        "COMPRIMENTO": ("1200MM", "1200 mm"), "TERMINAL A": "FEMEA RETA JIC",
        "TERMINAL B": ("", "", "o pedido lista só o terminal a"),
        "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600152": dict(classe="PDM011", ev="Produto: Mangueira Hidráulica Montada", vals={
        "NORMA": ("EN 853 2SN", "en 853 2sn"), "DIAMETRO INTERNO": ("1/2POL", '1/2"'),
        "COMPRIMENTO": ("2200MM", "2200 mm"), "TERMINAL A": "MACHO RETO BSP",
        "TERMINAL B": "FEMEA RETA JIC", "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600385": dict(classe="PDM011", ev="mangueira hidráulica montada", vals={
        "NORMA": "EN 853 2SN", "DIAMETRO INTERNO": ("1/2POL", "1/2 pol"),
        "COMPRIMENTO": ("1800MM", "1800mm"), "TERMINAL A": "FEMEA CURVA 90 GRAUS JIC",
        "TERMINAL B": "FEMEA RETA BSP", "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600141": dict(classe="PDM011", ev="Hydraulic hose assembly", vals={
        "NORMA": ("EN 856 4SH", "en 856 4sh"), "DIAMETRO INTERNO": "1.1/2POL",
        "COMPRIMENTO": "1200MM",
        "TERMINAL A": ("FEMEA RETA JIC", "JIC female swivel",
                       "swivel sem ângulo = reta; a lista não tem 'giratória'"),
        "TERMINAL B": ("FEMEA CURVA 90 GRAUS JIC", "JIC female 90° elbow"),
        "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600217": dict(classe="PDM011", ev="Hydraulic hose assembly", vals={
        "NORMA": ("EN 853 1SN", "en 853 1sn"), "DIAMETRO INTERNO": "1/4POL",
        "COMPRIMENTO": "3000MM", "TERMINAL A": "FEMEA CURVA 90 GRAUS ORFS",
        "TERMINAL B": ("FEMEA RETA ORFS", "ORFS female", "sem ângulo = reta"),
        "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600232": dict(classe="PDM011", ev="mangueira hidráulica montada", vals={
        "NORMA": "EN 853 2SN", "DIAMETRO INTERNO": ("3/4POL", '3/4" (19 mm)'),
        "COMPRIMENTO": ("2000MM", "2000 mm"), "TERMINAL A": "FEMEA CURVA 90 GRAUS JIC",
        "TERMINAL B": "MACHO RETO NPT", "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),
    "SC-202600279": dict(classe="PDM011", ev="Hydraulic hose assembly", vals={
        "NORMA": ("EN 856 4SP", "en 856 4sp"), "DIAMETRO INTERNO": "3/8POL",
        "COMPRIMENTO": "3000MM",
        "TERMINAL A": ("FEMEA RETA DKO", "DKOL female", "DKOL = DKO leve, reta"),
        "TERMINAL B": ("FEMEA RETA DKO", "DKOL female"),
        "MATERIAL TERMINAIS": "ACO CARBONO ZINCADO"}),

    # ---------------------------------------------------------------- PDM001 ---
    "SC-202600433": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": ("METRICA FINA", "metrica fina"), "BITOLA": "M10X1,25",
        "COMPRIMENTO": ("", "", "o pedido não traz comprimento"),
        "CLASSE RESISTENCIA": "10.9", "MATERIAL": ("ACO CARBONO", "aco carbono"),
        "ACABAMENTO": ("ZINCADO BRANCO", "zincado branco"), "NORMA": "DIN 933"}),
    "SC-202600300": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA FINA", "BITOLA": ("M18X1,5", "m18x1,5"),
        "COMPRIMENTO": ("50MM", "50 mm"), "CLASSE RESISTENCIA": "10.9",
        "MATERIAL": "ACO CARBONO", "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}),
    "SC-202600035": dict(classe="PDM001", ev="Produto: Parafuso Sextavado", vals={
        "ROSCA": "METRICA FINA", "BITOLA": "M8X1", "COMPRIMENTO": ("40MM", "40 mm"),
        "CLASSE RESISTENCIA": ("A2-70", "a2-70"), "MATERIAL": ("ACO INOX 304", "aco inox 304"),
        "ACABAMENTO": ("NATURAL", "natural"), "NORMA": ("DIN 933", "din 933")}),
    "SC-202600355": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA FINA", "BITOLA": "M30X2", "COMPRIMENTO": ("180MM", "180 mm"),
        "CLASSE RESISTENCIA": "10.9", "MATERIAL": "ACO CARBONO",
        "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 931"}),
    "SC-202600286": dict(classe="PDM001", ev="Hex head bolt",
                         just="catálogo em inglês: 'hex head bolt' = parafuso sextavado",
                         vals={
        "ROSCA": "UNC", "BITOLA": "1.1/8POL",
        "COMPRIMENTO": ("4.1/2POL", "4.1/2POL", "rosca em polegada: comprimento em POL"),
        "CLASSE RESISTENCIA": ("SAE GRAU 8", "sae grau 8"),
        "MATERIAL": ("ACO CARBONO", "carbon steel"),
        "ACABAMENTO": ("GALVANIZADO A FOGO", "HDG", "HDG = hot dip galvanized"),
        "NORMA": ("ASME B18.2.1", "asme b18.2.1")}),
    "SC-202600370": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA FINA", "BITOLA": "M24X2", "COMPRIMENTO": ("60MM", "60 mm"),
        "CLASSE RESISTENCIA": "8.8", "MATERIAL": "ACO CARBONO",
        "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}),
    "SC-202600037": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": ("METRICA GROSSA", "metrica grossa"), "BITOLA": ("M12", "m12"),
        "COMPRIMENTO": ("150MM", "150 mm"), "CLASSE RESISTENCIA": "5.8",
        "MATERIAL": "ACO CARBONO", "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}),
    "SC-202600453": dict(classe="PDM001", ev="Hex head bolt", vals={
        "ROSCA": ("METRICA GROSSA", "metrica grossa"), "BITOLA": "M18",
        "COMPRIMENTO": "100MM", "CLASSE RESISTENCIA": "8.8",
        "MATERIAL": ("ACO CARBONO", "carbon steel"),
        "ACABAMENTO": ("?", "zinc plated",
                       "zincado sem a cor: a lista tem ZINCADO BRANCO e ZINCADO AMARELO"),
        "NORMA": ("DIN 931", "din 931")}),
    "SC-202600038": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA GROSSA", "BITOLA": "M6", "COMPRIMENTO": ("80MM", "80mm"),
        "CLASSE RESISTENCIA": "10.9", "MATERIAL": ("ACO CARBONO", "aco carbono"),
        "ACABAMENTO": ("", "", "o pedido não lista acabamento"), "NORMA": "DIN 933"}),
    "SC-202600101": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "UNC", "BITOLA": ("3/4POL", '3/4"'),
        "COMPRIMENTO": ("2.1/2POL", '2 1/2"'), "CLASSE RESISTENCIA": ("SAE GRAU 5", "sae grau 5"),
        "MATERIAL": "ACO CARBONO", "ACABAMENTO": "ZINCADO BRANCO",
        "NORMA": ("ASME B18.2.1", "asme b18.2.1")}),
    "SC-202600237": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA GROSSA", "BITOLA": "M24", "COMPRIMENTO": ("80MM", "80 mm"),
        "CLASSE RESISTENCIA": "10.9", "MATERIAL": "ACO CARBONO",
        "ACABAMENTO": "OXIDADO PRETO", "NORMA": "DIN 931"}),
    "SC-202600041": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA FINA", "BITOLA": ("M10X1,25", "m10x1,25"),
        "COMPRIMENTO": ("140MM", "140mm"), "CLASSE RESISTENCIA": "A2-70",
        "MATERIAL": "ACO INOX 304", "ACABAMENTO": "NATURAL", "NORMA": "DIN 933"}),
    "SC-202600473": dict(classe="PDM001", ev="Hex head bolt", vals={
        "ROSCA": "METRICA FINA", "BITOLA": "M16X1,5", "COMPRIMENTO": "90MM",
        "CLASSE RESISTENCIA": "8.8", "MATERIAL": ("ACO CARBONO", "carbon steel"),
        "ACABAMENTO": ("OXIDADO PRETO", "black oxide"), "NORMA": ("DIN 931", "din 931")}),
    "SC-202600261": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA FINA", "BITOLA": "M16X1,5", "COMPRIMENTO": ("90MM", "90mm"),
        "CLASSE RESISTENCIA": "A2-70", "MATERIAL": "ACO INOX 304",
        "ACABAMENTO": "NATURAL", "NORMA": ("DIN 933", "din 933")}),
    "SC-202600517": dict(classe="PDM001", ev="Produto: Parafuso Sextavado", vals={
        "ROSCA": "UNC", "BITOLA": ("3/8POL", '3/8"'),
        "COMPRIMENTO": ("1.3/4POL", '1 3/4"'), "CLASSE RESISTENCIA": "SAE GRAU 2",
        "MATERIAL": "ACO CARBONO", "ACABAMENTO": ("ZINCADO AMARELO", "zincado amarelo"),
        "NORMA": ("ASME B18.2.1", "asme b18.2.1")}),
    "SC-202600235": dict(classe="PDM001", ev="Produto: Parafuso Sextavado", vals={
        "ROSCA": ("UNC", "unc"),
        "BITOLA": ("5/16POL", '5/16" (7,9 mm)', "o mm entre parênteses é conversão, não bitola"),
        "COMPRIMENTO": ("1.1/4POL", '1 1/4"'), "CLASSE RESISTENCIA": "SAE GRAU 8",
        "MATERIAL": "ACO CARBONO", "ACABAMENTO": "SEM ACABAMENTO", "NORMA": "ASME B18.2.1"}),
    "SC-202600245": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA FINA", "BITOLA": ("M16X1,5", "m16x1,5"),
        "COMPRIMENTO": ("50MM", "50mm"), "CLASSE RESISTENCIA": "8.8",
        "MATERIAL": "ACO CARBONO", "ACABAMENTO": "OXIDADO PRETO", "NORMA": "DIN 933"}),
    "SC-202600325": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": ("UNC", "unc"), "BITOLA": ("3/4POL", '3/4"'),
        "COMPRIMENTO": ("2.1/4POL", '2.1/4" (57,1 mm)'),
        "CLASSE RESISTENCIA": "SAE GRAU 5", "MATERIAL": "ACO CARBONO",
        "ACABAMENTO": ("", "", "o pedido não traz acabamento"), "NORMA": "ASME B18.2.1"}),
    "SC-202600337": dict(classe="PDM001", ev="parafuso sextavado", vals={
        "ROSCA": "METRICA GROSSA", "BITOLA": "M20", "COMPRIMENTO": ("55MM", "55mm"),
        "CLASSE RESISTENCIA": ("A2-70", "a2-70"), "MATERIAL": "ACO INOX 304",
        "ACABAMENTO": "NATURAL", "NORMA": "DIN 933"}),

    # ---------------------------------------------------------------- PDM002 ---
    "SC-202600456": dict(classe="PDM002", ev="Produto: Parafuso Sextavado Interno", vals={
        "TIPO CABECA": ("ESCAREADA", "escareada"), "BITOLA": "M3",
        "COMPRIMENTO": ("8MM", "8mm"), "CLASSE RESISTENCIA": "12.9",
        "MATERIAL": ("ACO LIGA", "aco liga"), "ACABAMENTO": ("OXIDADO PRETO", "oxidado preto")}),
    "SC-202600338": dict(classe="PDM002", ev="Produto: Parafuso Sextavado Interno", vals={
        "TIPO CABECA": ("CILINDRICA", "cilindrica"), "BITOLA": "M16",
        "COMPRIMENTO": ("100MM", "100 mm"), "CLASSE RESISTENCIA": "A4-70",
        "MATERIAL": ("ACO INOX 316", "aco inox 316"), "ACABAMENTO": "NATURAL"}),
    "SC-202600519": dict(classe="PDM002", ev="Produto: Parafuso Sextavado Interno", vals={
        "TIPO CABECA": "ESCAREADA", "BITOLA": "M10", "COMPRIMENTO": ("45MM", "45mm"),
        "CLASSE RESISTENCIA": "12.9", "MATERIAL": ("ACO LIGA", "aco liga"),
        "ACABAMENTO": ("OXIDADO PRETO", "oxidado preto")}),
    "SC-202600480": dict(classe="PDM002", ev="Socket head cap screw",
                         just="'socket head cap screw' = parafuso sextavado interno", vals={
        "TIPO CABECA": ("CILINDRICA", "cilindrica"), "BITOLA": "M12",
        "COMPRIMENTO": "25MM", "CLASSE RESISTENCIA": ("A2-70", "a2-70"),
        "MATERIAL": ("ACO INOX 304", "SS304"), "ACABAMENTO": ("NATURAL", "natural")}),
    "SC-202600336": dict(classe="PDM002", ev="Produto: Parafuso Sextavado Interno", vals={
        "TIPO CABECA": "CILINDRICA", "BITOLA": "M4", "COMPRIMENTO": ("20MM", "20mm"),
        "CLASSE RESISTENCIA": "A2-70", "MATERIAL": "ACO INOX 304",
        "ACABAMENTO": ("NATURAL", "natural")}),
    "SC-202600252": dict(classe="PDM002", ev="parafuso sextavado interno", vals={
        "TIPO CABECA": ("", "", "o pedido não diz o tipo de cabeça"), "BITOLA": "M4",
        "COMPRIMENTO": ("25MM", "25 mm"), "CLASSE RESISTENCIA": ("A4-70", "a4-70"),
        "MATERIAL": "ACO INOX 316", "ACABAMENTO": "NATURAL"}),

    # ------------------------------------------------- PDM003 / 030 / 031 / 032 ---
    "SC-202600403": dict(classe="PDM003", ev="porca", vals={
        "TIPO": ("", "", "'porca' sozinho não decide entre SEXTAVADA, AUTOTRAVANTE, "
                 "CASTELO e SEXTAVADA FLANGEADA"),
        "ROSCA": "METRICA GROSSA", "BITOLA": ("M22", "m22"), "CLASSE RESISTENCIA": "8",
        "MATERIAL": "ACO CARBONO", "ACABAMENTO": "ZINCADO BRANCO"}),
    "SC-202600500": dict(classe="PDM030", ev="Produto: Correia Trapezoidal", vals={
        "PERFIL": ("SPB", "spb"), "REFERENCIA": "SPB 3650"}),
    "SC-202600034": dict(classe="PDM030", ev="correia trapezoidal", vals={
        "PERFIL": ("B", "b"), "REFERENCIA": ("B146", "b146")}),
    "SC-202600033": dict(classe="PDM030", ev="Produto: Correia Trapezoidal", vals={
        "PERFIL": ("A", "a"), "REFERENCIA": "A157"}),
    "SC-202600520": dict(classe="PDM031", ev="O-ring", vals={
        "DIAMETRO INTERNO": "24MM", "SECAO": "2,5MM", "MATERIAL": ("NBR", "nbr"),
        "DUREZA": ("70 SHORE A", "70 shore a")}),
    "SC-202600050": dict(classe="PDM031", ev="O-ring", vals={
        "DIAMETRO INTERNO": "65MM", "SECAO": "7MM",
        "MATERIAL": ("FKM (VITON)", "fkm (viton)"), "DUREZA": ("70 SHORE A", "70 shore a")}),
    "SC-202600495": dict(classe="PDM031", ev="Produto: Anel O-Ring", vals={
        "DIAMETRO INTERNO": ("", "", "a ficha traz só seção, material e dureza"),
        "SECAO": ("2,5MM", "2,5 mm"), "MATERIAL": ("NBR", "nbr"),
        "DUREZA": ("70 SHORE A", "70 shore a")}),
    "SC-202600212": dict(classe="PDM031", ev="anel o-ring", vals={
        "DIAMETRO INTERNO": ("42MM", "42 mm"), "SECAO": ("2MM", "2 mm"),
        "MATERIAL": ("EPDM", "epdm"), "DUREZA": ("70 SHORE A", "70 shore a")}),
    "SC-202600026": dict(classe="PDM032", ev="Produto: Retentor", vals={
        "DIAMETRO EIXO": ("32MM", "32 mm"), "DIAMETRO ALOJAMENTO": ("57MM", "57mm"),
        "LARGURA": ("15MM", "15mm"), "TIPO": ("B1", "b1"), "MATERIAL": ("NBR", "nbr")}),
    "SC-202600160": dict(classe="PDM032", ev="Produto: Retentor", vals={
        "DIAMETRO EIXO": ("80MM", "80 mm"), "DIAMETRO ALOJAMENTO": ("95MM", "95 mm"),
        "LARGURA": ("10MM", "10mm"), "TIPO": ("BA", "ba"), "MATERIAL": "NBR"}),
    "SC-202600382": dict(classe="PDM032", ev="retentor", vals={
        "DIAMETRO EIXO": ("65MM", "65 mm"), "DIAMETRO ALOJAMENTO": ("77MM", "77mm"),
        "LARGURA": ("12MM", "12 mm"), "TIPO": ("BA", "ba"), "MATERIAL": ("NBR", "nbr")}),
    "SC-202600096": dict(classe="PDM032", ev="Oil seal", vals={
        "DIAMETRO EIXO": "35MM", "DIAMETRO ALOJAMENTO": "50MM", "LARGURA": "7MM",
        "TIPO": ("BA", "ba"), "MATERIAL": ("NBR", "nbr")}),
    "SC-202600259": dict(classe="PDM032", ev="retentor", vals={
        "DIAMETRO EIXO": ("35MM", "35 mm"), "DIAMETRO ALOJAMENTO": ("60MM", "60 mm"),
        "LARGURA": ("10MM", "10mm"), "TIPO": ("BAB", "bab"),
        "MATERIAL": ("FKM (VITON)", "fkm (viton)")}),
    "SC-202600003": dict(classe="PDM032", ev="retentor", vals={
        "DIAMETRO EIXO": ("75MM", "75 mm"), "DIAMETRO ALOJAMENTO": ("100MM", "100 mm"),
        "LARGURA": ("13MM", "13 mm"), "TIPO": ("BA", "ba"), "MATERIAL": ("NBR", "nbr")}),

    # ------------------------------------------------------- PDM033 / PDM034 ---
    "SC-202600410": dict(classe="PDM033", ev="Produto: Junta Espiralada", vals={
        "DIAMETRO NOMINAL": ("1.1/2POL", "1.1/2 pol"), "CLASSE PRESSAO": "900#",
        "MATERIAL FITA": ("ACO INOX 316", "aco inox 316"),
        "ENCHIMENTO": ("GRAFITE FLEXIVEL", "grafite flexivel"),
        "ANEL INTERNO": ("SEM ANEL INTERNO", "sem anel interno")}),
    "SC-202600331": dict(classe="PDM034", ev="Produto: Junta Plana", vals={
        "DIAMETRO NOMINAL": ("2POL", "2 pol"), "CLASSE PRESSAO": "300#",
        "MATERIAL": ("EPDM", "epdm"), "ESPESSURA": ("3,2MM", "3,2mm"),
        "TIPO FACE": ("RF", "rf")}),
    "SC-202600468": dict(classe="PDM034", ev="Flat gasket", vals={
        "DIAMETRO NOMINAL": "10POL", "CLASSE PRESSAO": "300#",
        "MATERIAL": ("EPDM", "epdm"), "ESPESSURA": "1,6MM", "TIPO FACE": ("RF", "rf")}),

    # ------------------------------------------- PDM040 / 041 / 043 / 044 ------
    "SC-202600103": dict(classe="PDM040", ev="válvula esfera", vals={
        "DIAMETRO NOMINAL": ("2POL", "2 pol"), "CLASSE PRESSAO": "800#",
        "MATERIAL CORPO": ("ACO INOX FORJADO A182 F316", "aco inox forjado a182 f316"),
        "CONEXAO": ("SOLDA ENCAIXE SW", "solda encaixe sw"), "PASSAGEM": ("PLENA", "plena"),
        "VEDACAO SEDE": ("PTFE", "ptfe"), "ACIONAMENTO": ("ALAVANCA", "alavanca")}),
    "SC-202600163": dict(classe="PDM040", ev="válvula esfera", vals={
        "DIAMETRO NOMINAL": ("2POL", '2" (dn 50)'),
        "CLASSE PRESSAO": ("PN 16", "pn 16", "PN 16 aqui é pressão nominal, não part number"),
        "MATERIAL CORPO": ("FERRO FUNDIDO NODULAR", "ferro fundido nodular"),
        "CONEXAO": ("FLANGE FF", "flange ff"), "PASSAGEM": "PLENA",
        "VEDACAO SEDE": ("METAL-METAL", "metal-metal"), "ACIONAMENTO": "ALAVANCA"}),
    "SC-202600092": dict(classe="PDM040", ev="Produto: Válvula Esfera", vals={
        "DIAMETRO NOMINAL": ("3/4POL", '3/4" (DN 20)'), "CLASSE PRESSAO": "800#",
        "MATERIAL CORPO": "ACO INOX FORJADO A182 F316", "CONEXAO": "SOLDA ENCAIXE SW",
        "PASSAGEM": ("REDUZIDA", "reduzida"), "VEDACAO SEDE": ("PTFE", "ptfe"),
        "ACIONAMENTO": "ALAVANCA"}),
    "SC-202600301": dict(classe="PDM040", ev="Produto: Válvula Esfera", vals={
        "DIAMETRO NOMINAL": ("2POL", '2"'), "CLASSE PRESSAO": "800#",
        "MATERIAL CORPO": "ACO INOX FORJADO A182 F316", "CONEXAO": "ROSCA NPT",
        "PASSAGEM": "REDUZIDA", "VEDACAO SEDE": ("RPTFE", "rptfe"),
        "ACIONAMENTO": ("ATUADOR PNEUMATICO", "atuador pneumatico")}),
    "SC-202600233": dict(classe="PDM040", ev="válvula esfera", vals={
        "DIAMETRO NOMINAL": ("3POL", '3"'), "CLASSE PRESSAO": ("PN 16", "pn 16"),
        "MATERIAL CORPO": "FERRO FUNDIDO NODULAR", "CONEXAO": "FLANGE FF",
        "PASSAGEM": "REDUZIDA", "VEDACAO SEDE": "PTFE", "ACIONAMENTO": "ALAVANCA"}),
    "SC-202600241": dict(classe="PDM041", ev="válvula gaveta", vals={
        "DIAMETRO NOMINAL": ("2.1/2POL", '2 1/2"'), "CLASSE PRESSAO": "600#",
        "MATERIAL CORPO": ("ACO INOX FUNDIDO A351 CF8M", "aco inox fundido a351 cf8m"),
        "CONEXAO": ("FLANGE RF", "flange rf"), "CASTELO": ("ROSCADO", "roscado"),
        "ACIONAMENTO": ("VOLANTE", "volante")}),
    "SC-202600305": dict(classe="PDM041", ev="Gate valve", vals={
        "DIAMETRO NOMINAL": "1.1/4POL", "CLASSE PRESSAO": "150#",
        "MATERIAL CORPO": ("ACO CARBONO FUNDIDO A216 WCB", "A216 WCB"),
        "CONEXAO": ("SOLDA TOPO BW", "butt weld"), "CASTELO": ("ROSCADO", "roscado"),
        "ACIONAMENTO": ("VOLANTE", "volante")}),
    "SC-202600143": dict(classe="PDM041", ev="válvula gaveta", vals={
        "DIAMETRO NOMINAL": ("1POL", "1 pol"), "CLASSE PRESSAO": "150#",
        "MATERIAL CORPO": "ACO INOX FUNDIDO A351 CF8M", "CONEXAO": "SOLDA TOPO BW",
        "CASTELO": ("APARAFUSADO", "aparafusado"), "ACIONAMENTO": "VOLANTE"}),
    "SC-202600330": dict(classe="PDM043", ev="Check valve", vals={
        "DIAMETRO NOMINAL": "1/4POL", "CLASSE PRESSAO": ("PN 25", "pn 25"),
        "MATERIAL CORPO": ("LATAO", "latao"), "CONEXAO": ("ROSCA BSP", "rosca bsp"),
        "TIPO": ("ESFERA", "esfera")}),
    "SC-202600196": dict(classe="PDM043", ev="válvula retencao", vals={
        "DIAMETRO NOMINAL": ("4POL", '4"'), "CLASSE PRESSAO": "150#",
        "MATERIAL CORPO": ("ACO CARBONO FUNDIDO A216 WCB", "aco carbono fundido a216 wcb"),
        "CONEXAO": ("SOLDA TOPO BW", "solda topo bw"), "TIPO": ("ESFERA", "esfera")}),
    "SC-202600182": dict(classe="PDM043", ev="Produto: Válvula Retencao", vals={
        "DIAMETRO NOMINAL": ("1.1/2POL", '1 1/2"'), "CLASSE PRESSAO": "PN 25",
        "MATERIAL CORPO": ("", "", "a ficha não traz o material do corpo"),
        "CONEXAO": ("ROSCA BSP", "rosca bsp"), "TIPO": ("ESFERA", "esfera")}),
    "SC-202600014": dict(classe="PDM044", ev="válvula borboleta", vals={
        "DIAMETRO NOMINAL": ("10POL", '10" (DN 250)'), "TIPO CORPO": ("WAFER", "wafer"),
        "MATERIAL CORPO": ("ACO INOX FUNDIDO A351 CF8M", "aco inox fundido a351 cf8m"),
        "MATERIAL DISCO": ("ACO INOX FUNDIDO A351 CF8M", "aco inox fundido a351 cf8m"),
        "VEDACAO SEDE": ("EPDM", "epdm"), "ACIONAMENTO": "ATUADOR ELETRICO"}),
    "SC-202600046": dict(classe="PDM044", ev="Produto: Válvula Borboleta", vals={
        "DIAMETRO NOMINAL": ("2POL", '2" (DN 50)'), "TIPO CORPO": ("LUG", "lug"),
        "MATERIAL CORPO": "ACO INOX FUNDIDO A351 CF8M",
        "MATERIAL DISCO": "ACO INOX FUNDIDO A351 CF8M",
        "VEDACAO SEDE": ("PTFE", "ptfe"), "ACIONAMENTO": "ATUADOR PNEUMATICO"}),
    "SC-202600290": dict(classe="PDM044", ev="Produto: Válvula Borboleta", vals={
        "DIAMETRO NOMINAL": ("6POL", '6" (DN 150)'), "TIPO CORPO": ("WAFER", "wafer"),
        "MATERIAL CORPO": ("ACO INOX FUNDIDO A351 CF8M", "aco inox fundido a351 cf8m"),
        "MATERIAL DISCO": "ACO INOX FUNDIDO A351 CF8M",
        "VEDACAO SEDE": ("NBR", "nbr"), "ACIONAMENTO": "ALAVANCA"}),

    # ---------------------------------------------------------------- PDM050 ---
    "SC-202600342": dict(classe="PDM050", ev="luva reducao", nao_aplica=["TIPO", "SCHEDULE", "FACE"],
                         just="luva redução: DIAMETRO REDUZIDO se aplica; não é flange nem BW",
                         vals={
        "DIAMETRO NOMINAL": ("3/4POL", '3/4"'), "DIAMETRO REDUZIDO": ("1/2POL", '1/2"'),
        "CLASSE PRESSAO": "3000#",
        "MATERIAL": ("ACO CARBONO FORJADO A105", "aco carbono forjado a105"),
        "CONEXAO": ("SOLDA ENCAIXE SW", "solda encaixe sw")}),
    "SC-202600087": dict(classe="PDM050", ev="Pipe fitting",
                         just="'pipe fitting' é genérico: a classe é conexão de tubulação, "
                              "mas o substantivo exato não está no texto. 'socket weld' "
                              "exclui flange, e só um diâmetro exclui redução",
                         nao_aplica=_PDM050_SIMPLES, vals={
        "DIAMETRO NOMINAL": "3/8POL", "CLASSE PRESSAO": "6000#",
        "MATERIAL": ("ACO CARBONO FORJADO A105", "A105 forged"),
        "CONEXAO": ("SOLDA ENCAIXE SW", "socket weld")}),
    "SC-202600359": dict(classe="PDM050", ev="Produto: Cap", nao_aplica=_PDM050_SIMPLES, vals={
        "DIAMETRO NOMINAL": ("1POL", '1"'), "CLASSE PRESSAO": "6000#",
        "MATERIAL": ("ACO INOX FORJADO A182 F316", "aco inox forjado a182 f316"),
        "CONEXAO": ("ROSCA NPT", "rosca npt")}),
    "SC-202600332": dict(classe="PDM050", ev="te", nao_aplica=_PDM050_SIMPLES,
                         just="'te' simples, não 'te reducao': DIAMETRO REDUZIDO não se aplica",
                         vals={
        "DIAMETRO NOMINAL": ("1.1/2POL", "1.1/2 pol"), "CLASSE PRESSAO": "6000#",
        "MATERIAL": ("ACO CARBONO FORJADO A105", "aco carbono forjado a105"),
        "CONEXAO": ("SOLDA ENCAIXE SW", "solda encaixe sw")}),

    # ----------------------------------------------- eletricos / instrumentos ---
    "SC-202600005": dict(classe="PDM060", ev="cabo elétrico", vals={
        "TIPO": ("FLEXIVEL", "flexivel"), "SECAO": ("1,5MM2", "1,5mm2"),
        "NUMERO CONDUTORES": ("1", "1"), "TENSAO ISOLAMENTO": ("450/750V", "450/750v"),
        "ISOLACAO": ("PVC", "pvc"), "COR": ("AZUL", "azul")}),
    "SC-202600065": dict(classe="PDM060", ev="Electric cable", vals={
        "TIPO": ("FLEXIVEL", "flexivel"), "SECAO": "95MM2", "NUMERO CONDUTORES": "1",
        "TENSAO ISOLAMENTO": ("450/750V", "450/750v"), "ISOLACAO": ("PVC", "pvc"),
        "COR": ("AZUL", "azul")}),
    "SC-202600352": dict(classe="PDM062", ev="Produto: Disjuntor",
                         nao_aplica=["FAIXA AJUSTE"], vals={
        "TIPO": "MINIDISJUNTOR DIN", "POLOS": ("3P", "3p"), "CORRENTE NOMINAL": "50A",
        "CURVA": "B", "CAPACIDADE INTERRUPCAO": "10KA"}),
    "SC-202600165": dict(classe="PDM062", ev="disjuntor minidisjuntor din",
                         nao_aplica=["FAIXA AJUSTE"], vals={
        "TIPO": ("MINIDISJUNTOR DIN", "minidisjuntor din"), "POLOS": ("3P", "3p"),
        "CORRENTE NOMINAL": ("16A", "16a"), "CURVA": ("C", "c"),
        "CAPACIDADE INTERRUPCAO": ("4,5KA", "4,5ka")}),
    "SC-202600323": dict(classe="PDM064", ev="fusível", vals={
        "TIPO": ("CARTUCHO", "cartucho"), "TAMANHO": "22X58MM",
        "CORRENTE NOMINAL": ("6A", "6A")}),

    # ------------------------------------------------------------------- EPI ---
    "SC-202600400": dict(classe="PDM070", ev="luva segurança",
                         just="LUVA aqui é EPI, não a luva de conexão de tubulação", vals={
        "MATERIAL": ("MALHA REVESTIDA PU", "malha revestida pu"), "TAMANHO": "8",
        "CA": "24382"}),
    "SC-202600269": dict(classe="PDM070", ev="Safety glove", vals={
        "MATERIAL": ("MALHA REVESTIDA PU", "malha revestida pu"), "TAMANHO": "9",
        "CA": "17131"}),
    "SC-202600516": dict(classe="PDM070", ev="luva segurança", vals={
        "MATERIAL": ("RASPA", "raspa"), "TAMANHO": ("UNICO", "unico"), "CA": "29892"}),
    "SC-202600104": dict(classe="PDM071", ev="Safety boot", vals={
        "TIPO": ("BOTINA ELASTICO", "botina elastico"), "TAMANHO": "34",
        "BIQUEIRA": ("ACO", "aco"), "SOLADO": ("PU BIDENSIDADE", "pu bidensidade"),
        "CA": "14659"}),
    "SC-202600173": dict(classe="PDM071", ev="calçado segurança", vals={
        "TIPO": ("BOTINA ELASTICO", "botina elastico"), "TAMANHO": "43",
        "BIQUEIRA": ("COMPOSITE", "composite"), "SOLADO": "NBR", "CA": "37918"}),
    "SC-202600158": dict(classe="PDM072", ev="oculos segurança", vals={
        "LENTE": ("", "", "'AMPLA VISAO' é modelo comercial, não cor de lente"),
        "TRATAMENTO": ("ANTIRRISCO", "antirrisco"), "CA": "33645"}),

    # ------------------------------------------------------- ferramenta / broca ---
    "SC-202600175": dict(classe="PDM082", ev="Twist drill", vals={
        "TIPO": ("HSS COBALTO", "hss cobalto"), "DIAMETRO": "1,5MM",
        "HASTE": ("CILINDRICA", "cilindrica"), "NORMA": ("DIN 340", "din 340")}),

    # ------------------------------------------------------- rolamentos -------
    "SC-202600291": dict(classe="PDM021", ev="Spherical roller bearing",
                         just="rolamento autocompensador de rolos", vals={
        "REFERENCIA": "22213E", "FURO": ("CILINDRICO", "cilindrico"),
        "FOLGA": ("NORMAL", "normal")}),
    "SC-202600186": dict(classe="PDM020", ev="rolamento rígido esferas", vals={
        "REFERENCIA": "6300-2RS", "VEDACAO": ("BORRACHA AMBOS LADOS", "borracha ambos lados"),
        "FOLGA": "NORMAL"}),
    "SC-202600074": dict(classe="PDM020", ev="rolamento rígido esferas", vals={
        "REFERENCIA": "6309", "VEDACAO": ("ABERTO", "aberto"), "FOLGA": ("NORMAL", "normal")}),
    "SC-202600131": dict(classe="PDM020", ev="rolamento rígido esferas", vals={
        "REFERENCIA": ("6211-ZZ", "6211-zz"),
        "VEDACAO": ("METALICA AMBOS LADOS", "metalica ambos lados"),
        "FOLGA": ("NORMAL", "normal")}),

    # ---------------------------------------------------------------- PDM100 ---
    "SC-202600424": dict(classe="PDM100", ev="filtro separador ar/óleo", vals={
        "FABRICANTE": "MANN", "REFERENCIA FABRICANTE": "LE 3269"}),
    "SC-202600345": dict(classe="PDM100", ev="Produto: Filtro Combustivel", vals={
        "FABRICANTE": "FRAM", "REFERENCIA FABRICANTE": "G1892"}),
    "SC-202600466": dict(classe="PDM100", ev="Produto: Filtro Ar", vals={
        "FABRICANTE": ("MANN", "mann"), "REFERENCIA FABRICANTE": "C 65 343"}),
    "SC-202600418": dict(classe="PDM100", ev="filtro ar", vals={
        "FABRICANTE": "MANN", "REFERENCIA FABRICANTE": "C 83 416"}),
    "SC-202600010": dict(classe="PDM100", ev="filtro combustivel", vals={
        "FABRICANTE": ("FRAM", "fram"), "REFERENCIA FABRICANTE": ("G2021", "g2021")}),

    # ---------------------------------------------------------------- PDM110 ---
    "SC-202600251": dict(classe="PDM110", ev="barra tensora peneira vibratoria", vals={
        "APLICACAO": ("PENEIRA VIBRATORIA", "peneira vibratoria"),
        "MODELO EQUIPAMENTO": ("F-CLASS 2.4X6.1", "f-class 2.4x6.1"),
        "FABRICANTE": ("HAVER", "haver"), "REFERENCIA FABRICANTE": ("HB-467508", "hb-467508")}),
    "SC-202600472": dict(classe="PDM110", ev="adaptador escavadeira hidraulica", vals={
        "APLICACAO": ("ESCAVADEIRA HIDRAULICA", "escavadeira hidraulica"),
        "MODELO EQUIPAMENTO": "EX1200", "FABRICANTE": ("HITACHI", "hitachi"),
        "REFERENCIA FABRICANTE": ("", "", "o pedido não traz o código do fabricante; "
                                  "sem ele a identidade da regra 10 não fecha")}),
    "SC-202600366": dict(classe="PDM110", ev="anel vedacao BRITADOR CONICO", vals={
        "APLICACAO": "BRITADOR CONICO", "MODELO EQUIPAMENTO": "HP400",
        "FABRICANTE": ("METSO", "metso"), "REFERENCIA FABRICANTE": "N61196004"}),
    "SC-202600144": dict(classe="PDM110", ev="tampa succao", vals={
        "APLICACAO": ("COMPRESSOR", "compressor"), "MODELO EQUIPAMENTO": "GA160",
        "FABRICANTE": ("ATLAS COPCO", "atlas copco"),
        "REFERENCIA FABRICANTE": "0956 2763 34"}),
    "SC-202600081": dict(classe="PDM110", ev="Produto: Mandibula Movel", vals={
        "APLICACAO": "BRITADOR MANDIBULA", "MODELO EQUIPAMENTO": "CJ615",
        "FABRICANTE": "SANDVIK", "REFERENCIA FABRICANTE": "575.2066-45"}),
    "SC-202600195": dict(classe="PDM110", ev="Produto: Tampa Succao", vals={
        "APLICACAO": "COMPRESSOR", "MODELO EQUIPAMENTO": "GA75",
        "FABRICANTE": ("ATLAS COPCO", "atlas copco"),
        "REFERENCIA FABRICANTE": "1855 6303 27"}),
    "SC-202600464": dict(classe="PDM110", ev="Produto: Carcaca", vals={
        "APLICACAO": ("COMPRESSOR", "compressor"), "MODELO EQUIPAMENTO": "GA90",
        "FABRICANTE": ("ATLAS COPCO", "atlas copco"),
        "REFERENCIA FABRICANTE": "6214 5895 05"}),
    "SC-202600489": dict(classe="PDM110", ev="Produto: Barra Tensora", vals={
        "APLICACAO": "PENEIRA VIBRATORIA", "MODELO EQUIPAMENTO": "LUDOWICI 3.6X8.5",
        "FABRICANTE": ("FLSMIDTH", "flsmidth"), "REFERENCIA FABRICANTE": "9545985877"}),
    "SC-202600120": dict(classe="PDM110", ev="eixo saida FLENDER ... do H3SH 9", vals={
        "APLICACAO": ("", "", "o pedido dá o modelo (H3SH 9) mas não diz que é REDUTOR; "
                      "ligar modelo a tipo exige o catálogo, que não está no pedido"),
        "MODELO EQUIPAMENTO": "H3SH 9", "FABRICANTE": "FLENDER",
        "REFERENCIA FABRICANTE": "T6593-468134"}),
    "SC-202600335": dict(classe="PDM110", ev="placa traseira WEIR ... do WARMAN 8/6 AH", vals={
        "APLICACAO": ("", "", "o modelo WARMAN 8/6 AH não vem acompanhado do tipo de "
                      "equipamento no texto"),
        "MODELO EQUIPAMENTO": "WARMAN 8/6 AH", "FABRICANTE": "WEIR",
        "REFERENCIA FABRICANTE": "N3966B38"}),
    "SC-202600383": dict(classe="PDM110", ev="Produto: Raspador Primario", vals={
        "APLICACAO": "CORREIA TRANSPORTADORA", "MODELO EQUIPAMENTO": "TC-04",
        "FABRICANTE": "CONTINENTAL", "REFERENCIA FABRICANTE": "CT8363160"}),
    "SC-202600239": dict(classe="PDM110", ev="dente cacamba escavadeira hidraulica", vals={
        "APLICACAO": ("ESCAVADEIRA HIDRAULICA", "escavadeira hidraulica"),
        "MODELO EQUIPAMENTO": "6015B", "FABRICANTE": "CATERPILLAR",
        "REFERENCIA FABRICANTE": "561-7310"}),
    "SC-202600503": dict(classe="PDM110", ev="Produto: Tampa Pressao", vals={
        "APLICACAO": "BOMBA CENTRIFUGA", "MODELO EQUIPAMENTO": "AHLSTAR A22-80",
        "FABRICANTE": ("SULZER", "sulzer"), "REFERENCIA FABRICANTE": "188126-242"}),
    "SC-202600110": dict(classe="PDM110", ev="chapa lateral britador mandibula", vals={
        "APLICACAO": ("BRITADOR MANDIBULA", "britador mandibula"),
        "MODELO EQUIPAMENTO": "CJ412", "FABRICANTE": ("SANDVIK", "sandvik"),
        "REFERENCIA FABRICANTE": "340.4962-00"}),
    "SC-202600023": dict(classe="PDM110", ev="bucha CATERPILLAR ... do 6030",
                         just="BUCHA aqui é sobressalente de equipamento, não bucha de "
                              "redução de tubulação: o texto dá fabricante e modelo", vals={
        "APLICACAO": ("", "", "'6030' é modelo; o texto não diz o tipo de equipamento"),
        "MODELO EQUIPAMENTO": "6030", "FABRICANTE": "CATERPILLAR",
        "REFERENCIA FABRICANTE": "879-7407"}),
    "SC-202600426": dict(classe="PDM110", ev="pino", vals={
        "APLICACAO": ("BRITADOR CONICO", "britador conico"), "MODELO EQUIPAMENTO": "CH440",
        "FABRICANTE": "SANDVIK", "REFERENCIA FABRICANTE": "837.6620-54"}),
    "SC-202600380": dict(classe="PDM110", ev="Produto: Barra Tensora", vals={
        "APLICACAO": ("PENEIRA VIBRATORIA", "peneira vibratoria"),
        "MODELO EQUIPAMENTO": "TS 3.6X7.3", "FABRICANTE": ("METSO", "metso"),
        "REFERENCIA FABRICANTE": "MM8024131"}),
    "SC-202600518": dict(classe="PDM110", ev="Produto: Amortecedor", vals={
        "APLICACAO": "PENEIRA VIBRATORIA", "MODELO EQUIPAMENTO": "LH 8X20",
        "FABRICANTE": "METSO", "REFERENCIA FABRICANTE": "N36213710"}),
    "SC-202600348": dict(classe="PDM110", ev="rolete retorno CONTINENTAL ... do TC-04", vals={
        "APLICACAO": ("", "", "TC-04 é modelo de correia, mas o texto não nomeia o "
                      "equipamento"),
        "MODELO EQUIPAMENTO": "TC-04", "FABRICANTE": "CONTINENTAL",
        "REFERENCIA FABRICANTE": "CT3546571"}),
    "SC-202600243": dict(classe="PDM110", ev="eixo SULZER ... do AHLSTAR A31-100", vals={
        "APLICACAO": ("", "", "o texto dá o modelo da bomba, não o tipo de equipamento"),
        "MODELO EQUIPAMENTO": "AHLSTAR A31-100", "FABRICANTE": "SULZER",
        "REFERENCIA FABRICANTE": "16812-820"}),
    "SC-202600414": dict(classe="PDM110", ev="placa succao", vals={
        "APLICACAO": "BOMBA POLPA", "MODELO EQUIPAMENTO": "MM300",
        "FABRICANTE": ("METSO", "metso"), "REFERENCIA FABRICANTE": "MM0809137"}),

    # ----------------------------------------------------------- FORA_DO_PDM ---
    "SC-202600437": dict(classe="FORA_DO_PDM", ev="notebook 16gb ram",
                         just="equipamento de TI: nenhuma classe do PDM cobre"),
    "SC-202600168": dict(classe="FORA_DO_PDM", ev="Serviço de calibração de manômetros",
                         just="serviço, não material: o PDM cadastra item físico"),
    "SC-202600169": dict(classe="FORA_DO_PDM", ev="Serviço de calibração de manômetros",
                         just="serviço, não material"),
    "SC-202600052": dict(classe="FORA_DO_PDM", ev="Serviço de calibração de manômetros",
                         just="serviço, não material"),
    "SC-202600267": dict(classe="FORA_DO_PDM", ev="manutenção corretiva do ar-condicionado",
                         just="serviço, não material"),
    "SC-202600187": dict(classe="FORA_DO_PDM", ev="camisa polo do uniforme",
                         just="uniforme não é EPI de nenhuma classe do PDM (070/071/072)"),
    "SC-202600394": dict(classe="FORA_DO_PDM", ev="toner para impressora",
                         just="suprimento de escritório"),
    "SC-202600270": dict(classe="FORA_DO_PDM", ev="café em pó 500g",
                         just="gênero alimentício"),
}

if __name__ == "__main__":
    expande(DECISOES, "A", Path(__file__).resolve().parent / "anotacoes_pedidos_A.jsonl")
