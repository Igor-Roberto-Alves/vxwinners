"""Regressões vindas da comparação entre o backend e o pipeline da branch Expli (2026-11-07).

Os dois pipelines rodaram sobre a mesma base; cada divergência apontou um erro de um dos lados.
"""
import pytest

from app.classes.resolver import IndiceClasses
from app.estruturacao.canonicalizar import canonicaliza
from app.estruturacao.regras import extrai_por_regras
from app.identidade.chave import chave_identidade
from app.identidade.referencias import referencia_correia, referencia_generica
from app.normalizacao import formatos, grandezas
from app.normalizacao.vocabulario import acha_no_texto, casa_lista


@pytest.fixture(scope="module")
def indice(pdm):
    return IndiceClasses(pdm)


def ex(pdm, indice, longa, grupo):
    return extrai_por_regras(pdm, indice, {"descricao_longa": longa, "grupo": grupo, "fabricante": None, "referencia_fabricante": None})


@pytest.mark.parametrize("a,b", [
    ("5751 9508 65 REV A", "5751950865"), ("36146, CARBETO TUNGSTENIO", "36146"), ("05307 P/ MANUTENCAO", "05307"),
    ("02099", "2099"), ("362-88-67868-00", "362-88-67868"), ("N75323456 ITEM CRITICO", "N75323456"), ("1R-1808", "1R1808"),
])
def test_referencia_sem_ruido_de_cadastro_fecha_a_mesma_chave(pdm, a, b):
    assert referencia_generica(a) == referencia_generica(b)
    va = {"FABRICANTE": "CATERPILLAR", "REFERENCIA FABRICANTE": a}
    vb = {"FABRICANTE": "CATERPILLAR", "REFERENCIA FABRICANTE": b}
    assert chave_identidade(pdm, "PDM110", "EIXO", va).texto == chave_identidade(pdm, "PDM110", "EIXO", vb).texto


def test_referencias_diferentes_continuam_diferentes():
    assert referencia_generica("6205 REV A") != referencia_generica("6206 REV A")
    assert referencia_generica("A100") != referencia_generica("A1000")


def test_valor_gravado_da_referencia_fica_legivel(pdm):
    assert canonicaliza(pdm, "PDM110", "REFERENCIA FABRICANTE", "5751 9508 65 REV A").valor == "5751 9508 65"


@pytest.mark.parametrize("bruto,esperado", [("7,0MM", "7MM"), ("16,250MM", "16,25MM"), ("16,25MM", "16,25MM"), ("10MM", "10MM"), ("1,50MM2", "1,5MM2"), ("215,0BAR", "215BAR")])
def test_zero_decimal_nao_cria_medida_diferente(bruto, esperado):
    tipo = "MM2" if bruto.endswith("MM2") else "BAR" if bruto.endswith("BAR") else "MM"
    assert formatos.normaliza_valor(tipo, bruto).valor == esperado


@pytest.mark.parametrize("texto,esperado", [
    ("A DENTADA AX41", "AX41"), ("A A153", "A153"), ("SPB 2325", "SPB 2325"), ("B54", "B54"), ("A DENTADA 4546", None),
])
def test_referencia_de_correia_e_o_codigo_escrito_nao_perfil_mais_comprimento(texto, esperado):
    assert referencia_correia(texto) == esperado


def test_correia_le_o_codigo_do_texto_e_recusa_o_que_o_modelo_compos(pdm, indice):
    e = ex(pdm, indice, "CORREIA TRAPEZOIDAL PERFIL DE A DENTADA, REF. AX177, COMPRIMENTO DE 4546 MM", "TRA01")
    assert e.valores["REFERENCIA"].valor == "AX177"
    assert canonicaliza(pdm, "PDM030", "REFERENCIA", "A DENTADA 4546").valor is None


def test_mangueira_com_terminais_e_montada_mesmo_sem_a_palavra(pdm, indice):
    e = ex(pdm, indice, "MANGUEIRA HIDRAULICA C/TERMINAIS, NORMA: EN 853 2SN, DIAM INTERNO: 1/2\", C: 500MM, "
                        "TERMINAL A: FEMEA RETA JIC, TERMINAL B: MACHO RETO NPT, MATERIAL TERMINAIS: ACO CARBONO ZINCADO", "MAN01")
    assert e.id_pdm == "PDM011" and e.nome == "MANGUEIRA HIDRAULICA MONTADA"


def test_mangueira_avulsa_continua_avulsa(pdm, indice):
    e = ex(pdm, indice, "MANGUEIRA HIDRAULICA; NORMA: EN 853 2SN; DIAMETRO INTERNO: 1/2POL; PRESSAO TRABALHO: 215BAR", "MAN01")
    assert e.id_pdm == "PDM010"


def test_polegada_composta(pdm, indice):
    r = grandezas.rosca_composta("PARAFUSO HEXAGONAL UNC 1/2POLX3 1/2POL")
    assert (r["BITOLA"].valor, r["COMPRIMENTO"].valor) == ("1/2POL", "3.1/2POL")


@pytest.mark.parametrize("variante,canonico,lista", [
    ("MA", "METRICA GROSSA", ("METRICA FINA", "METRICA GROSSA", "UNC", "UNF")),
    ("GF", "GALVANIZADO A FOGO", ("GALVANIZADO A FOGO", "ZINCADO BRANCO")),
    ("FLUORELASTOMERO", "FKM (VITON)", ("FKM (VITON)", "NBR")),
    ("ASTM A105", "ACO CARBONO FORJADO A105", ("ACO CARBONO FORJADO A105", "ACO INOX FORJADO A182 F316")),
])
def test_dicionario_curado_da_equipe_e_a_fonte(variante, canonico, lista):
    assert casa_lista(lista, variante).valor == canonico


def test_sigla_curta_nao_dispara_em_texto_corrido():
    assert acha_no_texto(("ROSCA BSP", "ROSCA NPT"), "valvula para gas natural").valor is None


@pytest.mark.parametrize("consulta,nome", [("joelho 90", "COTOVELO 90 GRAUS"), ("tampao", "CAP"), ("botina", "CALCADO SEGURANCA"), ("vedador", "RETENTOR"), ("chave contatora", "CONTATOR")])
def test_sinonimos_de_substantivo(indice, consulta, nome):
    assert indice.buscar(consulta)[0].nome == nome


@pytest.mark.parametrize("texto", ["PARAFUSO SEXTAVADO ALLEN TIPO CABECA CILINDRICA M3", "PARAF. CAB SEXTAVADA ALLEN M4", "PARAFUSO ALLEN M8X20"])
def test_parafuso_allen_e_sextavado_interno(pdm, indice, texto):
    assert ex(pdm, indice, texto, "FIX01").id_pdm == "PDM002"
