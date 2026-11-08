# -*- coding: utf-8 -*-
"""O que a tela de juncao publica (scripts/21_juncao_ncm.py).

Duas regras valem teste: como uma mudanca de NCM e classificada (reformatar
8431.49.29 nao e trocar de NCM) e o enxugamento do JSON, que nao pode comer
estoque e capital zerados.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def carrega_modulo():
    # o script tem numero no nome: import normal nao serve
    spec = importlib.util.spec_from_file_location(
        "juncao_ncm", RAIZ / "scripts/21_juncao_ncm.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["juncao_ncm"] = m
    spec.loader.exec_module(m)
    return m


jn = carrega_modulo()


@pytest.mark.parametrize("de,para,esperado", [
    # digitos diferentes: muda a tributacao e exige o tributario
    ("8482.80.00", "8482.10.10", "trocado"),
    ("84828000", "8482.10.10", "trocado"),
    # mesmos digitos, pontuacao diferente: cosmetico
    ("84314929", "8431.49.29", "reformatado"),
    ("8431.4929", "8431.49.29", "reformatado"),
    # entrou vazio e a classe deu o NCM
    ("", "7318.15.00", "preenchido"),
    # nada mudou
    ("7318.15.00", "7318.15.00", ""),
    # a classe tem NCM condicional e o item continua sem NCM: fila, nao mudanca
    ("", "", "sem_ncm"),
    # tinha NCM e o pipeline nao produziu saida: nao conta como mudanca
    ("7318.15.00", "", ""),
])
def test_tipo_de_mudanca_de_ncm(de, para, esperado):
    assert jn.tipo_mudanca(de, para) == esperado


def test_digitos_ignora_pontuacao():
    assert jn.digitos("8431.49.29") == jn.digitos("84314929") == "84314929"
    assert jn.digitos("") == ""
    assert jn.digitos(None) == ""


def test_enxuto_tira_vazio_e_mantem_zero():
    """Estoque e capital zerados sao justo os codigos parados que a tela mostra.

    Em Python `0.0 == False`, e um filtro escrito como `v not in ("", [], False)`
    apagaria os dois sem avisar.
    """
    d = jn.enxuto({
        "codigo": "123", "usar": "", "centros": [], "llm": False, "nota": None,
        "estoque": 0.0, "capital": 0.0, "preco": 0, "status": "ATIVO",
    })
    assert d == {"codigo": "123", "estoque": 0.0, "capital": 0.0, "preco": 0,
                 "status": "ATIVO"}


@pytest.fixture(scope="module")
def publicado():
    """O arquivo que a tela baixa (frontend/dados/), nao o artefato interno.

    Esse e versionado de proposito, para a plataforma subir numa maquina limpa:
    e o que precisa estar coerente.
    """
    import json
    arq = RAIZ / "frontend/dados/juncao_ncm.json"
    if not arq.exists():
        pytest.skip("rode scripts/21_juncao_ncm.py para publicar a tela")
    return json.loads(arq.read_text(encoding="utf-8"))


def test_cada_grupo_tem_um_codigo_que_fica(publicado):
    assert len(publicado["grupos"]) == publicado["resumo"]["grupos"]
    for g in publicado["grupos"]:
        fica = [c for c in g["codigos"] if c["acao"] == "mantem"]
        saem = [c for c in g["codigos"] if c["acao"] == "bloqueia"]
        assert len(fica) == 1 and fica[0]["codigo"] == g["fica"]
        assert saem, "grupo de um codigo nao e juncao e nao deveria ser publicado"
        assert sorted(c["codigo"] for c in saem) == sorted(g["saem"])
        # cada bloqueado aponta para o que fica: e o que a tela promete
        assert all(c.get("usar") == g["fica"] for c in saem)


def test_capital_liberado_e_o_dos_codigos_que_saem(publicado):
    """O saldo do codigo que fica continua sendo estoque necessario.

    Somar o grupo inteiro inflaria o numero que o Radar chama de consolidavel.
    """
    total = 0.0
    for g in publicado["grupos"]:
        saem = [c for c in g["codigos"] if c["acao"] == "bloqueia"]
        assert g["capital_liberado"] == pytest.approx(
            sum(c["capital"] for c in saem), abs=0.01)
        total += g["capital_liberado"]
    assert publicado["resumo"]["capital_liberado"] == pytest.approx(total, abs=0.5)


def test_tipo_de_cada_linha_de_ncm_bate_com_o_de_para(publicado):
    contagem = {"trocado": 0, "preenchido": 0, "reformatado": 0}
    for x in publicado["ncm_trocado"]:
        assert jn.tipo_mudanca(x.get("de", ""), x.get("para", "")) == x["tipo"]
        contagem[x["tipo"]] += 1
    n = publicado["resumo"]["ncm"]
    assert contagem["trocado"] == n["trocado"]
    assert contagem["preenchido"] == n["preenchido"]
    # reformatado vai por amostra: a contagem total fica no resumo, ao lado
    assert contagem["reformatado"] == n["reformatado_publicado"] <= n["reformatado"]


def test_publicado_bate_com_o_plano_de_juncao(publicado):
    """Os totais vem do plano. Pulado quando o artefato (ignorado) nao esta la."""
    plano = RAIZ / "artefatos/plano_juncao.csv"
    if not plano.exists():
        pytest.skip("artefatos/plano_juncao.csv ausente: rode scripts/rodar_tudo.sh")
    import csv
    with open(plano, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert publicado["resumo"]["grupos"] == sum(
        1 for r in linhas if r["ACAO"] == "MANTER ATIVO")
    assert publicado["resumo"]["codigos_que_saem"] == sum(
        1 for r in linhas if r["ACAO"] == "BLOQUEADO")
