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
    normalizar_estrutura, parse_numero, sem_acento, separar_rosca_metrica,
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


# ------------------------------------------- abreviacao ambigua (docs/07)

@pytest.mark.parametrize("cru,esperado", [
    # PN + pressao nominal e VALOR do PDM (CLASSE PRESSAO de PDM040-043)
    ("FLANGE CEGO 2POL PN 16 ACO CARBONO", "FLANGE CEGO 2POL PN 16 ACO CARBONO"),
    ("VALV ESF CL PN 25", "VALVULA ESFERA CLASSE PN 25"),
    # PN seguido de codigo continua sendo part number
    ("FILTRO METSO PN 5959848968", "FILTRO METSO PART NUMBER 5959848968"),
    ("ROLAMENTO SKF PN", "ROLAMENTO SKF PART NUMBER"),
])
def test_pn_pressao_nominal_nao_vira_part_number(cru, esperado):
    assert expandir(cru) == esperado


@pytest.mark.parametrize("cru,esperado", [
    ("FILTRO CAT 1R-1808 REV A", "FILTRO CAT 1R-1808 REV A"),     # revisao de desenho
    ("BUCHA 762-9053 REV", "BUCHA 762-9053 REV"),                 # revisao no fim
    ("TUBO REV EPOXI", "TUBO REVESTIDO EPOXI"),                   # sentido padrao
])
def test_rev_de_revisao_nao_vira_revestido(cru, esperado):
    assert expandir(cru) == esperado


def test_ret_depois_de_valvula_e_retencao():
    assert expandir("VALV RET 1POL PORTINHOLA") == "VALVULA RETENCAO 1POL PORTINHOLA"
    assert expandir("VALVULA RET. 2POL") == "VALVULA RETENCAO 2POL"
    # sem valvula antes, continua retentor
    assert expandir("RET NBR 110MM 15MM") == "RETENTOR NBR 110MM 15MM"
    assert expandir("NITRILICA RET D 40MM") == "NITRILICA RETENTOR D 40MM"


def test_ind_depois_de_sensor_e_indutivo():
    assert expandir("SENSOR IND M18 PNP") == "SENSOR INDUTIVO M18 PNP"
    assert expandir("SENS IND M12") == "SENSOR INDUTIVO M12"
    assert expandir("MANG IND MULTIUSO") == "MANGUEIRA INDUSTRIAL MULTIUSO"


@pytest.mark.parametrize("cru,esperado", [
    ("PARAF SEXT S/ACAB", "PARAFUSO SEXTAVADO SEM ACABAMENTO"),
    ("ARRUELA S/ACABAMENTO", "ARRUELA SEM ACABAMENTO"),
    ("MANG HIDR C/TERMINAIS", "MANGUEIRA HIDRAULICA COM TERMINAIS"),
    # P/N fica intacto: expandido, mudava a entrada do BERT e ele passava a
    # etiquetar FABRICANTE como MATERIAL (docs/07, secao 5)
    ("CAT P/N 1R-1808", "CAT P/N 1R-1808"),
    ("GRAXA P/ ROLAMENTO", "GRAXA PARA ROLAMENTO"),
    ("MOTOR S/N 12345", "MOTOR S/N 12345"),                       # numero de serie
])
def test_prefixo_de_barra(cru, esperado):
    assert expandir(cru) == esperado


@pytest.mark.parametrize("truncado", ["S/AC", "S/ACA", "S/A", "C/T"])
def test_barra_truncada_fica_intacta(truncado):
    # DESCRICAO_CURTA corta em 40 caracteres: 'S/ACAB' chega como 'S/AC'.
    # Expandido viraria 'SEM AC', e 'AC' e sinonimo de ACO CARBONO -> MATERIAL
    # inventado (regressao real do registro 27031887).
    assert expandir(f"PARAF SEXT {truncado}") == f"PARAFUSO SEXTAVADO {truncado}"


@pytest.mark.parametrize("intocado", [
    "UNIAO 1/2POL",                 # fracao
    "ROLAMENTO 6205-2RS/C3",        # codigo de peca com barra
    "CABO 1/0 AWG",
])
def test_barra_nao_toca_fracao_nem_codigo(intocado):
    assert expandir(intocado) == intocado


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


# ------------------------------------------------- rosca fina (regra 2 do PDM)

@pytest.mark.parametrize("cru,bitola,comprimento,rosca", [
    ("M12X50", "M12", "50MM", "METRICA GROSSA"),
    ("BITOLA:M12X1,5", "M12X1,5", None, "METRICA FINA"),     # passo, nao comprimento
    ("M10X1,25X70", "M10X1,25", "70MM", "METRICA FINA"),     # era M10 + 1,25MM
    ("M16 X 1,5 X 100", "M16X1,5", "100MM", "METRICA FINA"),
    ("M8X1", "M8X1", None, "METRICA FINA"),
    ("M8X1,25X40", "M8", "40MM", "METRICA GROSSA"),          # passo grosso escrito
    ("M3X3", "M3", "3MM", "METRICA GROSSA"),                 # parafuso miudo: comprimento
])
def test_regra2_distingue_passo_de_comprimento(cru, bitola, comprimento, rosca):
    r = separar_rosca_metrica(cru)
    assert r["BITOLA"] == bitola
    assert r.get("COMPRIMENTO") == comprimento
    assert r["ROSCA"] == rosca


# ------------------------------------------- camada 0: virgula decimal

@pytest.mark.parametrize("cru,esperado", [
    ("RETENTOR; DIAMETRO EIXO:16,25MM; LARGURA: 7MM",
     [("DIAMETRO EIXO", "16,25MM"), ("LARGURA", "7MM")]),
    ("CABO, SECAO:1,5MM2, COR:AZUL", [("SECAO", "1,5MM2"), ("COR", "AZUL")]),
    ("PARAFUSO, BITOLA:M12X1,5, COMPR:120MM", [("BITOLA", "M12X1,5"), ("COMPRIMENTO", "120MM")]),
    ("PARAF, ROSCA:M12,COMP:50MM", [("ROSCA", "M12"), ("COMPRIMENTO", "50MM")]),
])
def test_par_rotulado_nao_corta_na_virgula_decimal(cru, esperado):
    # 'SECAO:1,5MM2' virava 1MM2 e era aceito com confianca 0,99: item errado.
    from saneamento.rotulos import pares
    assert pares(cru) == esperado


def test_regra2_comprimento_em_metro_nao_vira_mm():
    # 'BARRA ROSCADA M16X1M' e barra de 1 metro: nem passo de rosca (bitola M16X1)
    # nem 1MM. A bitola fica M16 e o comprimento fica para a gramatica.
    r = separar_rosca_metrica("BARRA ROSCADA M16X1M ACO CARB ZINCADO")
    assert r["BITOLA"] == "M16"
    assert "COMPRIMENTO" not in r


@pytest.mark.parametrize("cru,esperado", [
    ('VALVULA RET 2" 300#', "VALVULA RET 2POL 300#"),
    ('UNIAO 1/2"', "UNIAO 1/2POL"),
    ('TUBO 1 1/4" SCH 40', "TUBO 1.1/4POL SCH 40"),         # fracao mista: regra 5
    ('PARAF 7/8"X2 1/4POL', "PARAF 7/8POL X 2.1/4POL"),     # bitola X comprimento
    ('COTOV GRAUS 90 1/4POL NPT', "COTOV GRAUS 90 1/4POL NPT"),  # angulo nao e inteiro
    ('TUBO SCH 40 1/2"', "TUBO SCH 40 1/2POL"),                # schedule nao e inteiro
])
def test_aspas_de_polegada_viram_pol(cru, esperado):
    # 1.273 registros escrevem polegada com aspas; normalizar() as apagava.
    assert normalizar(cru) == esperado


@pytest.mark.parametrize("cru,esperado", [
    ("VALVULA ESFERA 1 IN CL 150#", "VALVULA ESFERA 1POL CL 150#"),
    ("TE 1.1/4 IN 3000#", "TE 1.1/4POL 3000#"),
    ("LUVA 1 1/2 IN NPT", "LUVA 1.1/2POL NPT"),
    ("BROCA 2 INCH", "BROCA 2POL"),
    ("DISJUNTOR 3P IN 25A CURVA C", "DISJUNTOR 3P IN 25A CURVA C"),   # IN de corrente
])
def test_polegada_em_ingles(cru, esperado):
    # 1.152 ocorrencias de numero + IN na base; o termo nao reconhecido mais comum.
    assert normalizar(cru) == esperado
