# -*- coding: utf-8 -*-
"""Procedencia da regra aprendida e o que a tela de IA publica.

Duas coisas valem teste aqui:

1. o dicionario passou a gravar a LINHA de onde o termo veio (Entrada.origens).
   Sem isso, uma regra que decide 255 registros nao tem como ser auditada: nao
   da para voltar ao texto que a originou.
2. o publicado liga cada regra as linhas em que ela decidiu, e e essa ligacao
   que o fluxo de derrubada usa para dizer "esta regra tambem decidiu em N
   outras linhas".
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento.aprendizado import MAXIMO_ORIGENS, Aprendizado, Entrada  # noqa: E402


class AtributoFake:
    """O minimo que Aprendizado.aprender espera de um atributo do PDM."""

    def __init__(self, nome="ACABAMENTO", valores=("GALVANIZADO A FOGO", "NATURAL")):
        self.nome = nome
        self.valores = list(valores)
        self.fechado = True
        self.obrigatorio = True
        self.sempre = True
        self.id_pdm = "PDM001"

    @property
    def chaves(self):
        return {v.replace(" ", " ").upper(): v for v in self.valores}


@pytest.fixture
def dic(tmp_path):
    return Aprendizado(tmp_path / "aprendizado.json", travas=False)


def test_aprender_guarda_a_linha_de_origem(dic):
    at = AtributoFake()
    assert dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001",
                        codigos="10263349")
    e = dic.entradas["ACABAMENTO|GALV FOGO"]
    assert e.origens == ["10263349"]


def test_confirmar_acumula_origens_sem_repetir(dic):
    at = AtributoFake()
    dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001", codigos="111")
    dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001", codigos="222")
    dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001", codigos="222")
    e = dic.entradas["ACABAMENTO|GALV FOGO"]
    assert e.origens == ["111", "222"]
    assert e.confirmacoes == 3        # repeticao conta, origem duplicada nao


def test_origens_tem_teto(dic):
    at = AtributoFake()
    for i in range(MAXIMO_ORIGENS + 15):
        dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001",
                     codigos=f"cod{i}")
    e = dic.entradas["ACABAMENTO|GALV FOGO"]
    assert len(e.origens) == MAXIMO_ORIGENS
    assert e.confirmacoes == MAXIMO_ORIGENS + 15


def test_conflito_tambem_registra_a_linha_que_discordou(dic):
    """A linha do conflito e a mais importante de todas: e a que prova o erro."""
    at = AtributoFake()
    dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001", codigos="111")
    assert not dic.aprender(at, "GALV FOGO", "NATURAL", "llm", "PDM001", codigos="999")
    e = dic.entradas["ACABAMENTO|GALV FOGO"]
    assert e.origens == ["111", "999"]
    assert e.revisar and "conflito" in e.fonte


def test_lista_de_codigos_de_uma_vez(dic):
    """O 11_canonizar_termos resolve por TERMO: a regra nasce de varias linhas."""
    at = AtributoFake()
    dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001",
                 codigos=["111", "222", "333"])
    assert dic.entradas["ACABAMENTO|GALV FOGO"].origens == ["111", "222", "333"]


def test_origem_sobrevive_ao_disco(dic, tmp_path):
    at = AtributoFake()
    dic.aprender(at, "GALV FOGO", "GALVANIZADO A FOGO", "llm", "PDM001", codigos="10263349")
    dic.salvar()
    de_novo = Aprendizado(tmp_path / "aprendizado.json")
    assert de_novo.entradas["ACABAMENTO|GALV FOGO"].origens == ["10263349"]


def test_dicionario_antigo_sem_origens_continua_carregando(tmp_path):
    """Arquivo gravado antes deste campo existir nao pode derrubar a carga."""
    arq = tmp_path / "aprendizado.json"
    arq.write_text(json.dumps({"versao": 1, "limiar_confianca": 2, "entradas": [
        {"atributo": "ACABAMENTO", "termo": "GALV FOGO", "valor": "GALVANIZADO A FOGO",
         "fonte": "llm", "confirmacoes": 9, "classes": ["PDM001"], "revisar": False},
    ]}), encoding="utf-8")
    d = Aprendizado(arq)
    assert d.entradas["ACABAMENTO|GALV FOGO"].origens == []


def test_campo_desconhecido_e_ignorado_em_vez_de_estourar(tmp_path):
    """E o inverso: arquivo de uma versao mais nova nao derruba esta.

    Era por esse risco que `+interpretacao` foi parar dentro de `fonte`.
    """
    arq = tmp_path / "aprendizado.json"
    arq.write_text(json.dumps({"versao": 2, "entradas": [
        {"atributo": "ACABAMENTO", "termo": "GALV FOGO", "valor": "GALVANIZADO A FOGO",
         "fonte": "llm", "campo_do_futuro": {"qualquer": "coisa"}},
    ]}), encoding="utf-8")
    d = Aprendizado(arq)
    assert "ACABAMENTO|GALV FOGO" in d.entradas


def test_entrada_aceita_origens_nomeadas():
    e = Entrada(atributo="A", termo="t", valor="V", fonte="llm", origens=["1", "2"])
    assert e.chave == "A|t" and e.origens == ["1", "2"]


# ------------------------------------------------------------------ publicado

def carrega_publicador():
    spec = importlib.util.spec_from_file_location(
        "regras_ia", RAIZ / "scripts/22_regras_ia.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["regras_ia"] = m
    spec.loader.exec_module(m)
    return m


def test_publicador_declara_as_fontes_de_ia():
    m = carrega_publicador()
    assert "aprendido" in m.FONTES_IA and "llm" in m.FONTES_IA
    # `aprendido` e a unica com regra por tras: e nela que o fluxo de derrubada age
    assert m.FONTES_IA["aprendido"].startswith("regra do dicionario")


@pytest.fixture(scope="module")
def publicado():
    arq = RAIZ / "frontend/dados/regras_ia.json"
    if not arq.exists():
        pytest.skip("rode scripts/22_regras_ia.py para publicar a tela")
    return json.loads(arq.read_text(encoding="utf-8"))


def test_resumo_bate_com_a_lista_de_regras(publicado):
    r, regras = publicado["resumo"], publicado["regras"]
    assert r["regras"] == len(regras)
    assert r["regras_usadas"] == sum(1 for x in regras if x["n_aplicacoes"])
    assert r["aplicacoes"] == sum(x["n_aplicacoes"] for x in regras)
    assert r["regras_uma_confirmacao"] == sum(1 for x in regras if x["confirmacoes"] == 1)


def test_cada_regra_lista_todas_as_linhas_que_decidiu(publicado):
    """O numero que a pergunta mostra ("decidiu em N outras linhas") e esta lista.

    Se n_aplicacoes nao for len(aplicacoes), a tela promete revisar N e exporta
    outra quantidade - e a derrubada deixa linhas erradas em producao.
    """
    for r in publicado["regras"]:
        assert r["n_aplicacoes"] == len(r["aplicacoes"]), r["id"]
        assert r["capital"] == pytest.approx(
            sum(x["capital"] for x in r["aplicacoes"]), abs=0.01), r["id"]
        codigos = [x["codigo"] for x in r["aplicacoes"]]
        assert len(codigos) == len(set(codigos)), f"{r['id']} repete codigo"


def test_toda_regra_tem_procedencia_rotulada(publicado):
    """Derivada e pista, registrada e registro: a tela precisa poder dizer qual."""
    tipos = {"registrada", "desempate", "derivada", "ausente"}
    for r in publicado["regras"]:
        assert r["origem_tipo"] in tipos, r["id"]
        if r["origem_tipo"] == "ausente":
            assert not r["origens"]
        else:
            assert r["origens"], r["id"]
        assert r["n_origens"] == len(r["origens"])
    soma = publicado["resumo"]["origem"]
    assert sum(soma.values()) == len(publicado["regras"])


def test_decisoes_diretas_nao_repetem_as_de_regra(publicado):
    """A aba de decisoes diretas e o que NAO tem regra: `aprendido` fica de fora."""
    assert all(x["fonte"] != "aprendido" for x in publicado["decisoes_ia"])
    assert publicado["resumo"]["decisoes_ia_publicadas"] == len(publicado["decisoes_ia"])
