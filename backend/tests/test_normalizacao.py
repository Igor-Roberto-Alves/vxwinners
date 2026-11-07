import pytest

from app.normalizacao import formatos, grandezas as g
from app.normalizacao.numeros import formata, parse_numero
from app.normalizacao.texto import normaliza, tokens


def test_texto_sem_acento_maiusculo():
    assert normaliza("  Diâmetro   Nominal  ção ") == "DIAMETRO NOMINAL CAO"
    assert tokens("VALV. ESF 2\" AISI-316") == ["VALV", "ESF", "2", "AISI", "316"]


@pytest.mark.parametrize("txt,esperado", [
    ("3.650", 3650), ("6.000", 6000), ("1.000.000", 1000000), ("1,5", 1.5),
    ("16,25", 16.25), ("0.591", 0.591), ("2.5", 2.5), ("1.250,75", 1250.75), ("1,250.75", 1250.75),
])
def test_parse_numero_ptbr(txt, esperado):
    assert float(parse_numero(txt)) == esperado


def test_ponto_decimal_forcado_em_polegada():
    assert float(parse_numero("1.250", ponto_decimal=True)) == 1.25


def test_formata_decimal_com_virgula():
    from decimal import Decimal
    assert formata(Decimal("16.25")) == "16,25"
    assert formata(Decimal("25.00")) == "25"


@pytest.mark.parametrize("txt,esperado", [
    ('3/4"', "3/4POL"), ("1/2 pol", "1/2POL"), ('1 1/4"', "1.1/4POL"), ("1-1/4 in", "1.1/4POL"),
    ("1.1/4POL", "1.1/4POL"), ('1.25"', "1.1/4POL"), ("2POL", "2POL"), ("DN 50", "2POL"),
    ("DN50", "2POL"), ("2.1/2 POL", "2.1/2POL"), ('0.75"', "3/4POL"),
])
def test_polegada(txt, esperado):
    assert g.polegada(txt).valor == esperado


def test_polegada_nao_inventa():
    assert g.polegada("tubo grande").valor is None
    assert g.polegada("25").valor is None  # sem unidade


@pytest.mark.parametrize("txt,esperado", [
    ("15mm", "15MM"), ("15 MM", "15MM"), ("15.0mm", "15MM"), ('0.591"', "15MM"),
    ("16,25 mm", "16,25MM"), ("1,5 cm", "15MM"),
])
def test_milimetro(txt, esperado):
    assert g.mm(txt).valor == esperado


def test_metro_so_com_contexto():
    assert g.mm("2 m").valor is None
    assert g.mm("2 m", aceita_metro=True).valor == "2000MM"
    assert g.mm("2,0 M", aceita_metro=True).valor == "2000MM"


@pytest.mark.parametrize("txt,esperado", [
    ("215BAR", "215BAR"), ("215 bar", "215BAR"), ("3.650 psi", "252BAR"), ("6.000 psi", "414BAR"),
    ("21,5 MPa", "215BAR"), ("1960PSI", "135BAR"), ("10 kgf/cm2", "9,8BAR"),
])
def test_pressao_em_bar(txt, esperado):
    assert g.pressao_bar(txt).valor == esperado


def test_psi_com_ponto_de_milhar_nao_vira_decimal():
    assert g.pressao_bar("3.650 psi").valor != "0,3BAR"
    assert g.pressao_bar("6.000 psi").valor == "414BAR"


@pytest.mark.parametrize("txt,esperado", [
    ("1,5mm2", "1,5MM2"), ("1.5 mm²", "1,5MM2"), ("95MM2", "95MM2"),
])
def test_secao(txt, esperado):
    assert g.secao_mm2(txt).valor == esperado


def test_awg_e_aproximado():
    r = g.secao_mm2("AWG 16")
    assert r.valor == "1,5MM2" and r.confianca < 0.8


def test_rosca_composta_metrica_grossa():
    r = g.rosca_composta("m12x50")
    assert r["BITOLA"].valor == "M12" and r["COMPRIMENTO"].valor == "50MM"
    assert r["ROSCA"].valor == "METRICA GROSSA"


def test_rosca_fina_e_sem_comprimento():
    r = g.rosca_composta("M12X1,5X50")
    assert r["BITOLA"].valor == "M12X1,5" and r["ROSCA"].valor == "METRICA FINA"
    assert r["COMPRIMENTO"].valor == "50MM"
    r2 = g.rosca_composta("M12X1,5")
    assert r2["BITOLA"].valor == "M12X1,5" and "COMPRIMENTO" not in r2


def test_bitola_com_hifen_e_sem_notacao_composta():
    r = g.rosca_composta("BITOLA M-8")
    assert r["BITOLA"].valor == "M8" and "ROSCA" not in r  # sem medida composta nao afirma rosca


def test_formatos_classifica_e_valida():
    assert formatos.classifica("número + MM, decimal com vírgula (ex.: 16,25MM)", False) == "MM"
    assert formatos.classifica("polegada em fração + POL (ex.: 1.1/4POL)", False) == "POL"
    assert formatos.classifica("lista de valores", True) == "LISTA"
    assert formatos.valida("MM", "16,25MM") and not formatos.valida("MM", "16.25MM")
    assert formatos.valida("POL", "1.1/4POL") and not formatos.valida("POL", "1 1/4")
    assert formatos.valida("CA", "12345") and not formatos.valida("CA", "1234")


def test_normaliza_valor_por_tipo():
    assert formatos.normaliza_valor("MM", "15 mm").valor == "15MM"
    assert formatos.normaliza_valor("POL", 'DN 50').valor == "2POL"
    assert formatos.normaliza_valor("BAR", "3.650 psi").valor == "252BAR"
    assert formatos.normaliza_valor("MM", "16,25MM").confianca == 1.0


@pytest.mark.parametrize("txt,esperado", [
    ("1 1/2 POL", "1.1/2POL"), ("1 1/4", "1.1/4POL"), ('2 1/2"', "2.1/2POL"), ("3 / 4 POL", "3/4POL"),
])
def test_polegada_com_espaco_nao_vira_numero_colado(txt, esperado):
    """Regressão: remover espaços antes de validar transformava `1 1/2 POL` em `11/2POL`."""
    assert formatos.normaliza_valor("POL", txt).valor == esperado
    assert formatos.normaliza_valor("POL", "1 1/2 POL").valor != "11/2POL"


def test_medida_com_espaco_continua_funcionando():
    assert formatos.normaliza_valor("MM", "16,25 MM").valor == "16,25MM"
    assert formatos.normaliza_valor("MM", "62 MM").valor == "62MM"
    assert formatos.normaliza_valor("BAR", "215 BAR").valor == "215BAR"
