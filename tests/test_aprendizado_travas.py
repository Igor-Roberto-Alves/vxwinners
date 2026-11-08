# -*- coding: utf-8 -*-
"""Travas de aplicacao do dicionario aprendido (G1 a G5).

Cada teste nomeia o caso real que a trava pega, medido contra
avaliacao/gold_caracteristicas.csv.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from saneamento.aprendizado import (Aprendizado, Entrada,  # noqa: E402
                                    MARCA_INTERPRETACAO, _aponta_um_valor)
from saneamento.pdm import Atributo  # noqa: E402


def atr(nome, valores, id_pdm="PDM040"):
    return Atributo(id_pdm=id_pdm, ordem=1, nome=nome, obrigatorio=True,
                    quando="sempre", formato="lista de valores", valores=valores)


ACIONAMENTO_ESFERA = atr("ACIONAMENTO", ["ALAVANCA", "ATUADOR PNEUMATICO", "REDUTOR"])
ACIONAMENTO_GLOBO = atr("ACIONAMENTO", ["VOLANTE"], id_pdm="PDM042")
CONEXAO = atr("CONEXAO", ["FLANGE FF", "FLANGE RF", "ROSCA BSP", "ROSCA NPT",
                          "SOLDA ENCAIXE SW", "SOLDA TOPO BW"])
TERMINAL_A = atr("TERMINAL A", ["FEMEA CURVA 45 GRAUS JIC", "FEMEA CURVA 90 GRAUS DKO",
                                "FEMEA CURVA 90 GRAUS JIC", "FEMEA RETA BSP",
                                "FEMEA RETA DKO", "FEMEA RETA JIC", "MACHO RETO NPT"],
                 id_pdm="PDM011")
MATERIAL_PARAFUSO = atr("MATERIAL", ["ACO CARBONO", "ACO INOX 304", "ACO INOX 316"],
                        id_pdm="PDM001")


# ----------------------------------------------- G1: traducao x interpretacao
@pytest.mark.parametrize("atributo,termo,valor", [
    (TERMINAL_A, "FEMEA 90 JIC", "FEMEA CURVA 90 GRAUS JIC"),   # enum composto
    (TERMINAL_A, "FEMEA BSP", "FEMEA RETA BSP"),                # unico BSP femea
    (MATERIAL_PARAFUSO, "AISI 316", "ACO INOX 316"),            # notacao do fabricante
    (ACIONAMENTO_ESFERA, "CAIXA REDUTORA", "REDUTOR"),          # radical comum
    (CONEXAO, "BSP", "ROSCA BSP"),
])
def test_traducao_passa(atributo, termo, valor):
    assert _aponta_um_valor(atributo, termo, valor)


@pytest.mark.parametrize("atributo,termo,valor", [
    (CONEXAO, "FLANGES", "FLANGE RF"),                   # serve a FF e RF
    (CONEXAO, "FLANGEADA", "FLANGE FF"),                 # idem, e o par discorda
    (TERMINAL_A, "FEMEA DKO", "FEMEA RETA DKO"),         # reta ou curva 90
    (MATERIAL_PARAFUSO, "ACO ESPECIAL", "ACO CARBONO"),  # so o generico casa
    (ACIONAMENTO_ESFERA, "MANUAL", "ALAVANCA"),          # alavanca ou redutor
    (ACIONAMENTO_ESFERA, "VOLANTE", "ALAVANCA"),         # nada aponta
])
def test_interpretacao_reprova(atributo, termo, valor):
    assert not _aponta_um_valor(atributo, termo, valor)


def test_aprender_marca_interpretacao_e_nao_promove_por_repeticao():
    ap = Aprendizado(confirmacoes_para_confiar=2)
    for _ in range(5):
        ap.aprender(ACIONAMENTO_ESFERA, "MANUAL", "ALAVANCA", "llm", "PDM040")
    e = ap.entradas["ACIONAMENTO|MANUAL"]
    assert MARCA_INTERPRETACAO in e.fonte
    assert e.confirmacoes >= 2 and e.revisar, "sorteio confirmado continua sorteio"
    assert ap.consultar(ACIONAMENTO_ESFERA, "VALVULA ESFERA ACIONAMENTO MANUAL") is None

    ap.aprender(TERMINAL_A, "FEMEA 90 JIC", "FEMEA CURVA 90 GRAUS JIC", "llm", "PDM011")
    ap.aprender(TERMINAL_A, "FEMEA 90 JIC", "FEMEA CURVA 90 GRAUS JIC", "llm", "PDM011")
    t = ap.entradas["TERMINAL A|FEMEA 90 JIC"]
    assert not t.revisar and MARCA_INTERPRETACAO not in t.fonte


# ------------------------------------- G1 na aplicacao: o que vale onde
def test_g1_barra_interpretacao_na_hora_de_aplicar():
    """'VOLANTE' -> 'ALAVANCA' com 6 confirmacoes, caso 27542120 do gold.

    O item e uma gaveta classificada como esfera; a classe da entrada e a do
    item coincidem, entao guarda de classe nao resolveria. Quem barra e a
    verificacao lexica contra o enum, feita no uso.
    """
    ap = Aprendizado()
    ap.entradas["ACIONAMENTO|VOLANTE"] = Entrada(
        atributo="ACIONAMENTO", termo="VOLANTE", valor="ALAVANCA", fonte="llm",
        confirmacoes=6, classes=["PDM040"], revisar=False)
    assert ap.consultar(ACIONAMENTO_ESFERA, " VALV GAV ACIONAMENTO VOLANTE ") is None
    assert ap.bloqueados[0]["motivo"] == "termo nao aponta um unico valor do enum"


def test_traducao_vale_em_classe_irma_onde_continua_verificavel():
    """'PRETO' -> OXIDADO PRETO, aprendido em PDM001, servindo um PDM002.

    Guarda de classe cega custava 7 acertos no gold por casos como este; a
    verificacao no uso mantem o valor porque o termo continua apontando um
    unico valor do enum da classe nova.
    """
    ap = Aprendizado()
    ap.entradas["ACABAMENTO|PRETO"] = Entrada(
        atributo="ACABAMENTO", termo="PRETO", valor="OXIDADO PRETO", fonte="llm",
        confirmacoes=9, classes=["PDM001"], revisar=False)
    acab_002 = atr("ACABAMENTO", ["NATURAL", "OXIDADO PRETO", "ZINCADO BRANCO"],
                   id_pdm="PDM002")
    assert ap.consultar(acab_002, " PARAF SEXT INTERNO 12.9 TRATAMENTO PRETO ") \
        == "OXIDADO PRETO"


def test_confirmacao_unica_nao_impede_traducao():
    """'PONTAS CHANFRADAS' -> SOLDA TOPO BW tinha uma confirmacao so e estava
    certa nos dois itens do gold em que apareceu."""
    ap = Aprendizado()
    ap.entradas["CONEXAO|SOLDA TOPO"] = Entrada(
        atributo="CONEXAO", termo="SOLDA TOPO", valor="SOLDA TOPO BW", fonte="llm",
        confirmacoes=1, classes=["PDM041"], revisar=True)
    assert ap.consultar(CONEXAO, " VALVULA LIGACAO SOLDA TOPO ") == "SOLDA TOPO BW"
    # 'PONTAS CHANFRADAS' nao usa palavra nenhuma do enum: continua sugestao,
    # e o caminho dela e sinonimos.py, nao o dicionario
    ap2 = Aprendizado()
    ap2.entradas["CONEXAO|PONTAS CHANFRADAS"] = Entrada(
        atributo="CONEXAO", termo="PONTAS CHANFRADAS", valor="SOLDA TOPO BW",
        fonte="llm", confirmacoes=1, classes=["PDM041"], revisar=True)
    assert ap2.consultar(CONEXAO, " VALV GAV CONEXAO PONTAS CHANFRADAS ") is None


# -------------------------------------------------------------- G5: contexto
def test_g5_dois_valores_no_mesmo_texto_abstem():
    """O gazetteer recebe o texto INTEIRO: sem esta trava, 'FEM CURVA 90 JIC'
    do terminal B decidia o terminal A (casos 27430680 e 29700768 do gold)."""
    ap = Aprendizado()
    for termo, valor in (("FEMEA BSP", "FEMEA RETA BSP"),
                         ("FEM CURVA 90 JIC", "FEMEA CURVA 90 GRAUS JIC")):
        ap.entradas[f"TERMINAL A|{termo}"] = Entrada(
            atributo="TERMINAL A", termo=termo, valor=valor, fonte="llm",
            confirmacoes=5, classes=["PDM011"], revisar=False)
    texto = " MANG HIDRAULICA MONTADA TERM A FEMEA BSP TERMINAL B FEM CURVA 90 JIC "
    assert ap.consultar(TERMINAL_A, texto) is None
    assert all("contexto alcanca" in b["motivo"] for b in ap.bloqueados)


def test_travas_desligadas_reproduzem_o_comportamento_antigo():
    ap = Aprendizado(travas=False)
    ap.entradas["CONEXAO|FLANGES"] = Entrada(
        atributo="CONEXAO", termo="FLANGES", valor="FLANGE RF", fonte="llm",
        confirmacoes=1, classes=["PDM040"], revisar=True)
    assert ap.consultar(CONEXAO, " VALVULA ESFERA FLANGES ") == "FLANGE RF"
    assert ap.bloqueados == []


def test_enum_continua_sendo_a_primeira_barreira():
    """A trava mais antiga do modulo nao foi afrouxada: valor fora do enum do
    atributo consultado continua recusado antes de qualquer G."""
    ap = Aprendizado()
    ap.entradas["TIPO|MINI DISJUNTOR"] = Entrada(
        atributo="TIPO", termo="MINI DISJUNTOR", valor="MINIDISJUNTOR DIN",
        fonte="llm", confirmacoes=9, classes=["PDM062"], revisar=False)
    tipo_retentor = atr("TIPO", ["B1", "BA", "BAB", "BASL"], id_pdm="PDM032")
    assert ap.consultar(tipo_retentor, " RETENTOR MINI DISJUNTOR ") is None
    assert ap.contador["recusados_pelo_enum"] == 1


# ------------------------------- limpeza do ruido do termo e isencao de grandeza
MONTAGEM = atr("MONTAGEM", ["FACEADO", "NAO FACEADO"], id_pdm="PDM066")
ROSCA = atr("ROSCA", ["METRICA FINA", "METRICA GROSSA", "UNC", "UNF"], id_pdm="PDM001")
BITOLA = Atributo(id_pdm="PDM001", ordem=2, nome="BITOLA", obrigatorio=True,
                  quando="sempre",
                  formato="rosca metrica: M + diametro em mm (M12)",
                  valores=["M10", "M12", "1/2POL", "7/8POL"])


@pytest.mark.parametrize("atributo,termo,valor", [
    # o LLM devolve o trecho com o nome da caixa; isso nao e interpretacao
    (MONTAGEM, "MONTAGEM NAO FACEADO", "NAO FACEADO"),
    (ROSCA, "ROSCA METRICA FINA", "METRICA FINA"),
    (TERMINAL_A, "FEM RETA JIC", "FEMEA RETA JIC"),
    # atributo de grandeza e isento: termo != valor e o esperado
    (BITOLA, "DIAMETRO 7/8 POL", "7/8POL"),
    (BITOLA, "1/2", "1/2POL"),
])
def test_ruido_do_termo_nao_conta_como_interpretacao(atributo, termo, valor):
    assert _aponta_um_valor(atributo, termo, valor)


@pytest.mark.parametrize("atributo,termo,valor", [
    (ROSCA, "ROSCA METRICA", "METRICA GROSSA"),   # fina ou grossa: nao decide
    (MONTAGEM, "MONTAGEM", "FACEADO"),            # so o nome da caixa
])
def test_termo_generico_segue_reprovado(atributo, termo, valor):
    assert not _aponta_um_valor(atributo, termo, valor)
