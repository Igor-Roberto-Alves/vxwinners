import pytest

from app.ncm.regras import formata_ncm, ncm_esperado
from app.pdm import condicoes


def test_pdm_completo(pdm):
    assert len(pdm.classes) == 44
    assert sum(len(c.atributos) for c in pdm.classes.values()) == 229
    assert len(pdm.todos_os_nomes()) == 119
    assert pdm.avisos() == []  # toda condicional do PDM tem predicado


def test_nomes_ambiguos_apontam_para_classes_diferentes(pdm):
    assert pdm.classe_do_nome("LUVA").id_pdm == "PDM050"
    assert pdm.classe_do_nome("LUVA SEGURANCA").id_pdm == "PDM070"
    assert pdm.classe_do_nome("LUVA EIXO").id_pdm == "PDM110"
    assert pdm.classe_do_nome("valvula esfera").id_pdm == "PDM040"


def test_criterio_de_identidade(pdm):
    assert pdm.classes["PDM100"].por_referencia and pdm.classes["PDM110"].por_referencia
    assert not pdm.classes["PDM020"].por_referencia


def test_condicionais_obrigatorios_aplicaveis(pdm):
    # PDM062 disjuntor: depende do TIPO
    ob = {a.nome for a in pdm.obrigatorios_aplicaveis("PDM062", "DISJUNTOR", {"TIPO": "MOTOR"})}
    assert "FAIXA AJUSTE" in ob and "CURVA" not in ob and "CORRENTE NOMINAL" not in ob
    ob = {a.nome for a in pdm.obrigatorios_aplicaveis("PDM062", "DISJUNTOR", {"TIPO": "MINIDISJUNTOR DIN"})}
    assert {"CURVA", "CORRENTE NOMINAL", "CAPACIDADE INTERRUPCAO"} <= ob and "FAIXA AJUSTE" not in ob
    # sem o TIPO preenchido, as condicionais ainda dependem dele (None), nao entram
    assert "CURVA" not in {a.nome for a in pdm.obrigatorios_aplicaveis("PDM062", "DISJUNTOR", {})}


def test_cabo_cor_so_para_um_condutor(pdm):
    com = {a.nome for a in pdm.obrigatorios_aplicaveis("PDM060", "CABO ELETRICO", {"NUMERO CONDUTORES": "1"})}
    sem = {a.nome for a in pdm.obrigatorios_aplicaveis("PDM060", "CABO ELETRICO", {"NUMERO CONDUTORES": "3"})}
    assert "COR" in com and "COR" not in sem


def test_conexoes_flange_e_topo(pdm):
    fl = {a.nome for a in pdm.obrigatorios_aplicaveis("PDM050", "FLANGE", {})}
    assert {"TIPO", "FACE", "CLASSE PRESSAO"} <= fl and "CONEXAO" not in fl and "SCHEDULE" not in fl
    bw = {a.nome for a in pdm.obrigatorios_aplicaveis("PDM050", "COTOVELO 90 GRAUS", {"CONEXAO": "SOLDA TOPO BW"})}
    assert "SCHEDULE" in bw and "CLASSE PRESSAO" not in bw


def test_condicao_desconhecida_e_acusada():
    classes = {"PDM999": {"atributos": [{"nome": "X", "quando": "somente quando chover"}]}}
    assert condicoes.lacunas(classes) == [("PDM999", "X", "somente quando chover")]


@pytest.mark.parametrize("bruto,esperado", [
    ("73181500", "7318.15.00"), ("7318.1500", "7318.15.00"), ("7318.15.00", "7318.15.00"),
    ("0000.0000", "0000.00.00"), ("7318", None), ("", None), (None, None), ("abcdefgh", None),
])
def test_formata_ncm(bruto, esperado):
    assert formata_ncm(bruto) == esperado


def test_ncm_unico_da_classe(pdm):
    assert ncm_esperado(pdm, "PDM001", "PARAFUSO SEXTAVADO", {}) == ("7318.15.00", "unico para a classe")
    assert ncm_esperado(pdm, "PDM040", "VALVULA ESFERA", {})[0] == "8481.80.95"


def test_ncm_pelo_briefing_porca_nao_e_parafuso(pdm):
    # briefing: PORCA com NCM de parafuso (7318.15.00) esta errado; o correto e 7318.16.00
    assert ncm_esperado(pdm, "PDM003", "PORCA", {})[0] == "7318.16.00"


def test_ncm_condicional(pdm):
    assert ncm_esperado(pdm, "PDM100", "FILTRO AR", {})[0] == "8421.31.00"
    assert ncm_esperado(pdm, "PDM100", "FILTRO HIDRAULICO", {})[0] == "8421.29.90"
    assert ncm_esperado(pdm, "PDM081", "DISCO ABRASIVO", {"TIPO": "FLAP"})[0] == "6805.10.00"
    assert ncm_esperado(pdm, "PDM081", "DISCO ABRASIVO", {})[0] is None
    assert ncm_esperado(pdm, "PDM030", "CORREIA TRAPEZOIDAL", {"COMPRIMENTO EXTERNO": "1500MM"})[0] == "4010.32.00"
    assert ncm_esperado(pdm, "PDM030", "CORREIA TRAPEZOIDAL", {"COMPRIMENTO EXTERNO": "2500MM"})[0] == "4010.39.00"
    assert ncm_esperado(pdm, "PDM070", "LUVA SEGURANCA", {"MATERIAL": "VAQUETA"})[0] == "4203.29.00"
    assert ncm_esperado(pdm, "PDM071", "CALCADO SEGURANCA", {"BIQUEIRA": "COMPOSITE"})[0] == "6403.99.90"


def test_ncm_sobressalente_segue_equipamento_e_excecoes(pdm):
    assert ncm_esperado(pdm, "PDM110", "BUCHA EXCENTRICO", {"APLICACAO": "BRITADOR CONICO"})[0] == "8474.90.00"
    assert ncm_esperado(pdm, "PDM110", "BUCHA EXCENTRICO", {})[0] is None
    assert ncm_esperado(pdm, "PDM110", "PASTILHA FREIO", {"APLICACAO": "CAMINHAO FORA DE ESTRADA"})[0] == "8708.30.11"
    assert ncm_esperado(pdm, "PDM110", "DISCO FREIO", {})[0] == "8708.30.90"


def test_ncm_conexoes(pdm):
    r = ncm_esperado(pdm, "PDM050", "COTOVELO 90 GRAUS", {"MATERIAL": "ACO INOX A403 WP316", "CONEXAO": "ROSCA NPT"})
    assert r[0] == "7307.22.00"
    r = ncm_esperado(pdm, "PDM050", "TE", {"MATERIAL": "ACO CARBONO FORJADO A105", "CONEXAO": "SOLDA ENCAIXE SW"})
    assert r[0] == "7307.99.00"
    assert ncm_esperado(pdm, "PDM050", "FLANGE", {"MATERIAL": "ACO CARBONO FORJADO A105"})[0] == "7307.91.00"
    assert ncm_esperado(pdm, "PDM050", "TE", {})[0] is None
