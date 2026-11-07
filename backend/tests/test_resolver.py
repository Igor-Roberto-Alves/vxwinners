import pytest

from app.classes.resolver import IndiceClasses, prepara


@pytest.fixture(scope="module")
def indice(pdm):
    return IndiceClasses(pdm)


def test_prepara_glossario_abreviacao_e_plural():
    assert prepara("PARAF SEXT") == ["PARAFUSO", "SEXTAVADO"]
    assert prepara("Ball valve 1POL")[:2] == ["VALVULA", "ESFERA"]
    assert prepara("valvulas")[0] == "VALVULA"


def test_autocomplete_abreviado(indice):
    r = indice.buscar("paraf sext")
    assert r[0].nome == "PARAFUSO SEXTAVADO" and r[0].id_pdm == "PDM001"
    assert [s.nome for s in indice.buscar("valv esf")][0] == "VALVULA ESFERA"


def test_autocomplete_prefixo_enquanto_digita(indice):
    nomes = [s.nome for s in indice.buscar("rolam")]
    assert "ROLAMENTO RIGIDO ESFERAS" in nomes and len(nomes) <= 5


def test_luva_e_ambigua_e_mostra_o_contexto_das_tres_classes(indice):
    r = indice.buscar("luva")
    assert {s.id_pdm for s in r} >= {"PDM050", "PDM070", "PDM110"}
    assert all(s.ambiguo for s in r)  # a pessoa precisa escolher
    assert all(s.grupo_descricao for s in r)


def test_autocomplete_em_ingles(indice):
    assert indice.buscar("oil seal")[0].nome == "RETENTOR"
    assert indice.buscar("safety boot")[0].id_pdm == "PDM071"


def test_item_fora_do_pdm_nao_inventa_classe(indice):
    assert indice.buscar("cadeira de escritorio giratoria") == []
    assert indice.detectar_no_texto("Cadeira de escritório giratória com braço") == []
    assert indice.detectar_no_texto("toner para impressora da portaria") == []


def test_detectar_no_texto_longo(indice):
    r = indice.detectar_no_texto("preciso de 10 parafuso sextavado m16 x 60 galvanizado 8.8 din 933 pra peneira")
    assert r[0].id_pdm == "PDM001"
    r = indice.detectar_no_texto("VALV ESF 2\" AISI 316 NPT")
    assert r[0].nome == "VALVULA ESFERA"


def test_nome_mais_longo_vence_no_texto(indice):
    r = indice.detectar_no_texto("PARAFUSO SEXTAVADO INTERNO M8")
    assert r[0].id_pdm == "PDM002"  # e nao PDM001


def test_nome_curto_so_com_grupo_coerente(indice):
    assert indice.detectar_no_texto("te para tubo") == []
    assert indice.detectar_no_texto("TE ROSCA NPT 1/2POL", grupo="TUB01")[0].nome == "TE"


def test_grupo_desempata(indice):
    r = indice.detectar_no_texto("LUVA", grupo="EPI01")
    assert r[0].id_pdm == "PDM070"
