"""Testes das invariantes de formato do PDM.

Estes testes sao o que sustenta "o resultado e reproduzivel" diante da banca.
Cada caso vem de uma linha real da base ou de um pedido real.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from saneamento.texto import (  # noqa: E402
    expandir, fmt_bar, fmt_mm, fmt_mm2, fmt_pol, juntar, normalizar,
    normalizar_estrutura, parse_numero, referencia_canonica, sem_acento, separar_rosca_metrica,
)


# ----------------------------------------------------------------- texto

def test_sem_acento_e_cedilha():
    # regra 3 do PDM
    assert sem_acento("VEDAÇÃO HIDRÁULICA") == "VEDACAO HIDRAULICA"
    assert sem_acento("Mangueira pneumática") == "Mangueira pneumatica"


@pytest.mark.parametrize("cru,esperado", [
    ("ANEL EXPULSOR, APLIC: BOMBA POLPA", "ANEL EXPULSOR APLIC BOMBA POLPA"),
    ("RET. 110MM 15MM BASL NBR", "RET 110MM 15MM BASL NBR"),
    ("retentor, 16,25mm", "RETENTOR 16,25MM"),          # virgula decimal preservada
    ("uniao 1.1/4pol", "UNIAO 1.1/4POL"),               # ponto de polegada preservado
    ("norma asme b16.11", "NORMA ASME B16.11"),         # ponto de norma preservado
    ("6.000 psi", "6.000 PSI"),                         # ponto de milhar preservado
])
def test_normalizar_limpa_pontuacao_solta_sem_quebrar_numero(cru, esperado):
    assert normalizar(cru) == esperado


def test_normalizar_estrutura_preserva_delimitador_de_par():
    # os rotulos de treino saem destes dois sinais: nao podem ser removidos
    s = normalizar_estrutura("ANEL EXPULSOR, APLIC: BOMBA POLPA; MODELO: MM400")
    assert ":" in s and ";" in s and "," in s


def test_expandir_resolve_abreviacao_com_ponto():
    assert expandir("PARAF. SEXT") == "PARAFUSO SEXTAVADO"
    assert expandir("RET. BASL") == "RETENTOR BASL"
    assert "ACO CARBONO" in expandir("MATERIAL ACO CARB")


def test_juntar_nao_duplica_truncamento():
    # DESCRICAO_CURTA e truncamento da LONGA: o texto repetido quebraria a
    # contagem de grandezas da classe RETENTOR (3 atributos em MM)
    longa = "RETENTOR DIAMETRO EIXO 90MM DIAMETRO ALOJAMENTO 112MM LARGURA 8MM"
    curta = "RETENTOR DIAMETRO EIXO 90MM DIAMETRO"
    assert juntar(longa, curta).count("90MM") == 1


# ----------------------------------------------------------------- numeros

@pytest.mark.parametrize("cru,esperado", [
    ("16,25", 16.25),      # virgula e sempre decimal
    ("3.650", 3650.0),     # ponto + 3 digitos e milhar
    ("6.000", 6000.0),     # '6.000 psi' do pedido e seis mil, nao seis
    ("1.5", 1.5),          # ponto + 1 digito e decimal
    ("16.25", 16.25),
    ("0.591", 0.591),      # parte inteira zero nunca e milhar
    ("1.1/4", 1.25),       # notacao de polegada do PDM
    ("3/4", 0.75),
    ("1 1/2", 1.5),
])
def test_parse_numero(cru, esperado):
    assert parse_numero(cru) == pytest.approx(esperado)


# ----------------------------------------------------------------- grandezas

@pytest.mark.parametrize("entrada,esperado", [
    (16.25, "16,25MM"),    # regra 5: decimal com virgula
    (50, "50MM"),
    ("15mm", "15MM"),
    ("15.0", "15MM"),
])
def test_fmt_mm(entrada, esperado):
    assert fmt_mm(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    (2, "2POL"),
    (1.25, "1.1/4POL"),           # regra 5: inteiro separado por ponto
    (0.5, "1/2POL"),
    ("1 1/4", "1.1/4POL"),
    ('3/4"', "3/4POL"),
    ("DN 50", "2POL"),            # a duplicidade do briefing: 2POL == DN 50
    ("DN 32", "1.1/4POL"),
])
def test_fmt_pol(entrada, esperado):
    assert fmt_pol(entrada) == esperado


@pytest.mark.parametrize("valor,unidade,esperado", [
    (215, "BAR", "215BAR"),
    (1960, "PSI", "135,1BAR"),    # mangueira SAE 100R1AT da base
    (3650, "PSI", "251,7BAR"),    # pedido: '3.650 psi'
    (6000, "PSI", "413,7BAR"),    # pedido: '6.000 psi'
    (17.3, "MPA", "173BAR"),      # pressao de ruptura da regra de NCM
])
def test_fmt_bar_converte_para_bar(valor, unidade, esperado):
    # regra 6: pressao sempre em BAR
    assert fmt_bar(valor, unidade) == esperado


def test_fmt_mm2_secao_de_cabo():
    assert fmt_mm2("1,5") == "1,5MM2"
    assert fmt_mm2(4) == "4MM2"


# ----------------------------------------------------------------- rosca

def test_separar_notacao_compacta():
    # regra 2: M12X50 junta dois atributos e deve ser desmembrado
    r = separar_rosca_metrica("PARAFUSO SEXTAVADO M12X50 8.8")
    assert r["BITOLA"] == "M12"
    assert r["COMPRIMENTO"] == "50MM"
    assert r["ROSCA"] == "METRICA GROSSA"   # passo ausente => grossa


def test_bitola_com_hifen_da_base():
    assert separar_rosca_metrica("BITOLA M-8")["BITOLA"] == "M8"


def test_passo_explicito_indica_metrica_fina():
    assert separar_rosca_metrica("M12X1,5X50")["ROSCA"] == "METRICA FINA"



# ---- regressoes encontradas comparando este pipeline com o backend (2026-11-07)

def test_passo_da_rosca_nao_vira_comprimento():
    """Bug: M12X1,5 virava COMPRIMENTO=1,5MM e parafusos de 35, 60 e 150 mm fechavam a mesma chave."""
    r = separar_rosca_metrica("BITOLA: M12X1,5")
    assert r["BITOLA"] == "M12X1,5" and "COMPRIMENTO" not in r and r["ROSCA"] == "METRICA FINA"
    r = separar_rosca_metrica("PARAFUSO M12X1,5X60 A2-70")
    assert (r["BITOLA"], r["COMPRIMENTO"], r["ROSCA"]) == ("M12X1,5", "60MM", "METRICA FINA")
    r = separar_rosca_metrica("M12X50")
    assert (r["BITOLA"], r["COMPRIMENTO"], r["ROSCA"]) == ("M12", "50MM", "METRICA GROSSA")


def test_notacao_composta_em_polegada():
    """Bug: `1/2POLX3 1/2POL` ficava com COMPRIMENTO=1/2POL e unia itens diferentes."""
    r = separar_rosca_metrica("PARAFUSO HEXAGONAL UNC 1/2POLX3 1/2POL SAE GRAU 8")
    assert r == {"BITOLA": "1/2POL", "COMPRIMENTO": "3.1/2POL"}


def test_referencia_canonica_tira_ruido_de_cadastro():
    assert referencia_canonica("5751 9508 65 REV A") == referencia_canonica("5751950865")
    assert referencia_canonica("05307 P/ MANUTENCAO") == referencia_canonica("05307") == "5307"
    assert referencia_canonica("36146, CARBETO TUNGSTENIO") == "36146"
    assert referencia_canonica("362-88-67868-00") == referencia_canonica("362-88-67868")
    assert referencia_canonica("02099") == referencia_canonica("2099")
    assert referencia_canonica("N75323456 ITEM CRITICO") == "N75323456"
    assert referencia_canonica("1R-1808") == "1R1808"
    assert referencia_canonica("") == ""
