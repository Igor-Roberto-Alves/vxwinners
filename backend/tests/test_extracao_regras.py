import pytest

from app.classes.resolver import IndiceClasses
from app.estruturacao.regras import extrai_por_regras


@pytest.fixture(scope="module")
def indice(pdm):
    return IndiceClasses(pdm)


def ex(pdm, indice, longa, grupo, **kw):
    return extrai_por_regras(pdm, indice, {"descricao_longa": longa, "descricao_curta": kw.get("curta"), "grupo": grupo,
                                           "fabricante": kw.get("fab"), "referencia_fabricante": kw.get("ref")})


def v(e, atr):
    return e.valores[atr].valor if atr in e.valores else None


def test_pseudo_pdm_completo(pdm, indice):
    e = ex(pdm, indice, "PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M14; COMPRIMENTO: 30MM; "
                        "CLASSE RESISTENCIA: 8.8; MATERIAL: ACO CARBONO; ACABAMENTO: GALVANIZADO A FOGO; NORMA: DIN 933", "FIX01")
    assert e.id_pdm == "PDM001" and e.faltando(pdm) == []
    assert v(e, "CLASSE RESISTENCIA") == "8.8" and e.valores["BITOLA"].origem == "REGRA_ROTULO"


def test_rotulos_abreviados_e_sem_espaco(pdm, indice):
    e = ex(pdm, indice, "VALV ESFERA;DIAM:1/2POL;CLASSE PRESSAO:800#;CORPO:ACO CARBONO FORJADO A105;ENCAIXE:SOLDA ENCAIXE SW;"
                        "PASSAGEM:REDUZIDA;VEDACAO SEDE:PTFE;ACIONAMENTO:ALAVANCA", "VAL01")
    assert e.id_pdm == "PDM040"
    assert v(e, "DIAMETRO NOMINAL") == "1/2POL" and v(e, "MATERIAL CORPO") == "ACO CARBONO FORJADO A105"
    assert v(e, "CONEXAO") == "SOLDA ENCAIXE SW"


def test_estilo_com_virgulas_e_hifen(pdm, indice):
    e = ex(pdm, indice, "ROLAMENTO RIGIDO ESF, REFERENCIA:6206-ZZ-C3, DIAM INT:30MM, ESPESSURA:16MM, DIAM EXT:62 MM, C3", "ROL01")
    assert e.id_pdm == "PDM020" and v(e, "REFERENCIA") == "6206-ZZ/C3"
    assert v(e, "DIAMETRO INTERNO") == "30MM" and v(e, "DIAMETRO EXTERNO") == "62MM"
    assert v(e, "VEDACAO") == "METALICA AMBOS LADOS" and v(e, "FOLGA") == "C3"  # deduzido da referencia


def test_notacao_composta_sem_rotulo(pdm, indice):
    e = ex(pdm, indice, "PARAF SEXT M12X50 ZINCADO CL 8.8 DIN 933", "FIX01")
    assert e.id_pdm == "PDM001"
    assert (v(e, "BITOLA"), v(e, "COMPRIMENTO"), v(e, "ROSCA")) == ("M12", "50MM", "METRICA GROSSA")
    assert v(e, "NORMA") == "DIN 933"


def test_caso_do_briefing_falta_classe_de_resistencia(pdm, indice):
    e = ex(pdm, indice, "PARAFUSO SEXTAVADO M12X50 ZINCADO", "FIX01")
    assert "CLASSE RESISTENCIA" in e.faltando(pdm) and "NORMA" in e.faltando(pdm)
    assert v(e, "CLASSE RESISTENCIA") is None  # nunca inventa


def test_telegrafico_usa_lista_do_pdm(pdm, indice):
    e = ex(pdm, indice, "RET. 110MM 15MM BASL NBR", "VED01")
    assert e.id_pdm == "PDM032" and v(e, "TIPO") == "BASL" and v(e, "MATERIAL") == "NBR"
    assert v(e, "DIAMETRO EIXO") is None  # medida solta: posicao nao e evidencia


def test_filtro_usa_colunas_do_erp(pdm, indice):
    e = ex(pdm, indice, "FILTRO OLEO LUBRIFICANTE 1R1808 CAT", "FIL01", fab="CAT", ref="1R-1808")
    assert e.id_pdm == "PDM100"
    assert v(e, "FABRICANTE") == "CATERPILLAR" and v(e, "REFERENCIA FABRICANTE") == "1R-1808"
    assert e.valores["FABRICANTE"].origem == "COLUNA_ERP"


def test_sobressalente_com_aplicacao(pdm, indice):
    e = ex(pdm, indice, "DISCO FREIO; P/N:169-20-74921; MOD:830E; KOMATSU; APLIC:CAMINHAO FORA DE ESTRADA", "SOB01")
    assert e.id_pdm == "PDM110" and e.nome == "DISCO FREIO"
    assert v(e, "REFERENCIA FABRICANTE") == "169-20-74921" and v(e, "MODELO EQUIPAMENTO") == "830E"
    assert v(e, "FABRICANTE") == "KOMATSU" and v(e, "APLICACAO") == "CAMINHAO FORA DE ESTRADA"


def test_valor_fora_da_lista_nao_vira_valor(pdm, indice):
    e = ex(pdm, indice, "PARAFUSO SEXTAVADO; ACABAMENTO: GALVANIZADO; BITOLA: M12", "FIX01")
    a = e.valores["ACABAMENTO"]
    assert a.valor is None and "ZINCADO BRANCO" in a.candidatos  # ambiguo: devolve as opcoes


def test_sem_classe_nao_inventa(pdm, indice):
    e = ex(pdm, indice, "TONER PARA IMPRESSORA DA PORTARIA", "SOB01")
    assert e.id_pdm is None and e.valores == {}


def test_grupo_divergente_baixa_a_confianca(pdm, indice):
    e = ex(pdm, indice, "VALVULA ESFERA; DIAMETRO NOMINAL: 2POL", "FIX01")
    assert e.id_pdm == "PDM040" and e.confianca_classe < 0.8 and e.avisos


def test_rolamento_sem_o_tipo_usa_a_serie(pdm, indice):
    for txt, classe in (("ROL 6205-2RSH/C3 SKF", "PDM020"), ("ROLAMENTO FAG 6205-C-2HRS-C3", "PDM020"),
                        ("ROLAMENTO 6205DDUC3", "PDM020"), ("ROLAMENTO NTN 6310ZZC3", "PDM020"),
                        ("ROLAMENTO 30205 ROLOS", "PDM022"), ("ROLAMENTO 22212EK/C3", "PDM021")):
        e = ex(pdm, indice, txt, "ROL01")
        assert e.id_pdm == classe, txt
    e = ex(pdm, indice, "ROL 6205-2RSH/C3 SKF", "ROL01")
    assert v(e, "REFERENCIA") == "6205-2RS/C3" and v(e, "VEDACAO") == "BORRACHA AMBOS LADOS" and v(e, "FOLGA") == "C3"


def test_filtro_de_oleo_nao_vira_filtro_de_ar(pdm, indice):
    e = ex(pdm, indice, "FILTRO OLEO 1R1808 CAT", "FIL01")
    assert e.nome == "FILTRO OLEO LUBRIFICANTE" and v(e, "FABRICANTE") == "CATERPILLAR"
    e = ex(pdm, indice, "ELEMENTO FILTRANTE AR; APLICACAO: COMPRESSOR", "FIL01")
    assert e.nome == "FILTRO AR"


def test_filtro_sem_tipo_deixa_o_nome_em_aberto_sem_palpite(pdm, indice):
    e = ex(pdm, indice, "FILTRO P551808 DONALDSON", "FIL01")
    assert e.id_pdm == "PDM100" and e.nome is None  # nao escolhe "FILTRO AR" por ordem alfabetica
    assert v(e, "FABRICANTE") == "DONALDSON" and len(e.ambiguas) >= 2
