"""Testes da camada de enriquecimento: cada tabela e cada formula.

Os valores esperados sao de catalogo publico, nao derivados do proprio codigo.
O 6205 (25 x 52 x 15 mm) e o 6310 (50 x 110 x 27 mm) estao no enunciado do
desafio e em qualquer catalogo de rolamento, e por isso sao o gabarito.

Alem das tabelas, os testes travam as tres invariantes da camada, porque sao
elas que tornam o resultado defensavel: procedencia obrigatoria, validacao pelo
enum do PDM, e nunca sobrescrever extracao.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from saneamento import Pdm  # noqa: E402
from saneamento.enriquecimento import (  # noqa: E402
    ACRESCIMO_EXTERNO_CORREIA, CABECA_SEXTAVADA, HASTE_POR_NORMA_BROCA,
    ISO15_ESFERAS, ISO15_ROLOS_CONICOS, ISO15_ROLOS_ESFERICOS,
    NCM_POR_TIPO_FILTRO, NORMA_BROCA_POR_HASTE, NORMA_POR_TIPO_PORCA,
    PASSO_METRICO_GROSSO, PORCA_SEXTAVADA, PREFIXO_FILTRO, TIPO_ENRIQUECIDO,
    TIPO_PORCA_POR_NORMA, Enriquecedor, Procedencia, Sugestao, TabelaNcm,
    analisar_bitola, analisar_rolamento, circunferencia_correia,
    codigo_furo_por_diametro, comprimento_rosca_din931,
    designacao_por_dimensoes, diametro_interno_por_codigo,
    fabricante_por_part_number, formata_ncm, ncm_correia,
    norma_parafuso_sextavado, norma_porca, tipo_filtro_por_texto,
)
from saneamento.texto import AWG_PARA_MM2, DN_PARA_POL, fmt_pol  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pdm():
    arq = RAIZ / "artefatos/pdm.json"
    if not arq.exists():
        pytest.skip("rode scripts/01_compilar_pdm.py antes")
    return Pdm.carregar(arq)


@pytest.fixture(scope="module")
def enr(pdm):
    return Enriquecedor(pdm)


# ================================================== procedencia (invariante 1)

def test_procedencia_completa_exige_os_quatro_campos():
    ok = Procedencia("iso15_rolamento", "ISO 15:2017", "2026-11-07", 0.97)
    assert ok.completa
    assert not Procedencia("", "ISO 15", "2026-11-07", 0.9).completa
    assert not Procedencia("iso15", "", "2026-11-07", 0.9).completa
    assert not Procedencia("iso15", "ISO 15", "", 0.9).completa
    assert not Procedencia("iso15", "ISO 15", "2026-11-07", 0.0).completa
    assert not Procedencia("iso15", "ISO 15", "2026-11-07", 1.5).completa


def test_sugestao_sem_procedencia_nao_consegue_existir():
    # o dado sem rastro tem de ser impossivel, nao apenas desencorajado
    with pytest.raises(ValueError):
        Sugestao(atributo="LARGURA", valor="15MM",
                 procedencia=Procedencia("", "", "", 0.0))
    with pytest.raises(ValueError):
        Sugestao(atributo="LARGURA", valor="",
                 procedencia=Procedencia("iso15", "ISO 15", "2026-11-07", 0.9))


def test_sugestao_sai_marcada_como_enriquecida():
    s = Sugestao(atributo="LARGURA", valor="15MM",
                 procedencia=Procedencia("iso15_rolamento", "ISO 15:2017",
                                         "2026-11-07", 0.97))
    d = s.como_dict()
    assert d["TIPO"] == TIPO_ENRIQUECIDO
    # os quatro campos de procedencia tem de aparecer na saida
    assert d["FONTE"] and d["URL_OU_REFERENCIA"] and d["DATA_CONSULTA"]
    assert d["CONFIANCA"] == 0.97


# ============================================ formula do furo do rolamento

@pytest.mark.parametrize("codigo,esperado", [
    (0, 10), (1, 12), (2, 15), (3, 17),      # as quatro excecoes tabeladas
    (4, 20), (5, 25), (6, 30), (10, 50), (12, 60), (20, 100), (96, 480),
])
def test_diametro_interno_por_codigo_de_furo(codigo, esperado):
    assert diametro_interno_por_codigo(codigo) == esperado


def test_codigo_de_furo_fora_da_faixa_da_norma():
    assert diametro_interno_por_codigo(97) is None
    assert diametro_interno_por_codigo(-1) is None


@pytest.mark.parametrize("d,cod", [(10, "00"), (12, "01"), (15, "02"), (17, "03"),
                                   (20, "04"), (25, "05"), (50, "10"), (100, "20")])
def test_codigo_furo_por_diametro_e_inverso_da_formula(d, cod):
    assert codigo_furo_por_diametro(d) == cod
    assert diametro_interno_por_codigo(int(cod)) == d


# ====================================== tabela ISO 15 - rolamento de esferas

def test_6205_tem_as_medidas_de_catalogo():
    # gabarito do enunciado: 6205 = DI 25mm, DE 52mm, largura 15mm
    r = analisar_rolamento("6205")
    assert r["DIAMETRO INTERNO"] == 25
    assert r["DIAMETRO EXTERNO"] == 52
    assert r["LARGURA"] == 15
    assert r["serie"] == "02"


def test_6310_tem_as_medidas_de_catalogo():
    # gabarito do enunciado: 6310 = DI 50mm, DE 110mm, largura 27mm
    r = analisar_rolamento("6310")
    assert r["DIAMETRO INTERNO"] == 50
    assert r["DIAMETRO EXTERNO"] == 110
    assert r["LARGURA"] == 27
    assert r["serie"] == "03"


@pytest.mark.parametrize("designacao,d,de,b", [
    ("6000", 10, 26, 8), ("6005", 25, 47, 12), ("6010", 50, 80, 16),
    ("6200", 10, 30, 9), ("6203", 17, 40, 12), ("6205", 25, 52, 15),
    ("6210", 50, 90, 20), ("6220", 100, 180, 34),
    ("6300", 10, 35, 11), ("6303", 17, 47, 14), ("6305", 25, 62, 17),
    ("6310", 50, 110, 27), ("6320", 100, 215, 47),
    ("6405", 25, 80, 21), ("6410", 50, 130, 31),
])
def test_tabela_iso15_esferas(designacao, d, de, b):
    r = analisar_rolamento(designacao)
    assert (r["DIAMETRO INTERNO"], r["DIAMETRO EXTERNO"], r["LARGURA"]) == (d, de, b)


@pytest.mark.parametrize("designacao,d,de,b", [
    ("22205", 25, 52, 18), ("22212", 60, 110, 28), ("22220", 100, 180, 46),
    ("22308", 40, 90, 33), ("22310", 50, 110, 40), ("22315", 75, 160, 55),
])
def test_tabela_iso15_rolos_esfericos(designacao, d, de, b):
    r = analisar_rolamento(designacao)
    assert r["familia"] == "rolos_esfericos"
    assert (r["DIAMETRO INTERNO"], r["DIAMETRO EXTERNO"], r["LARGURA"]) == (d, de, b)


@pytest.mark.parametrize("designacao,d,de,t", [
    ("30203", 17, 40, 13.25), ("30205", 25, 52, 16.25), ("30212", 60, 110, 23.75),
    ("30305", 25, 62, 18.25), ("30310", 50, 110, 29.25),
    ("32205", 25, 52, 19.25), ("32212", 60, 110, 29.75),
])
def test_tabela_iso15_rolos_conicos(designacao, d, de, t):
    r = analisar_rolamento(designacao)
    assert r["familia"] == "rolos_conicos"
    assert (r["DIAMETRO INTERNO"], r["DIAMETRO EXTERNO"], r["LARGURA"]) == (d, de, t)


def test_tabelas_iso15_sao_coerentes_com_a_formula_do_furo():
    # toda chave de linha tem de ser um diametro que a formula produz
    for tabela in (ISO15_ESFERAS, ISO15_ROLOS_ESFERICOS, ISO15_ROLOS_CONICOS):
        for serie, linhas in tabela.items():
            for d, (de, b) in linhas.items():
                assert codigo_furo_por_diametro(d), f"{serie}/{d} sem codigo de furo"
                assert de > d, f"{serie}/{d}: externo tem de ser maior que o interno"
                assert 0 < b < de, f"{serie}/{d}: largura implausivel"


# ====================================== sufixos de designacao de fabricante

@pytest.mark.parametrize("designacao,vedacao,folga", [
    ("6205-2RSH/C3", "BORRACHA AMBOS LADOS", "C3"),      # SKF
    ("6205-C-2HRS-C3", "BORRACHA AMBOS LADOS", "C3"),    # FAG
    ("6205DDUC3", "BORRACHA AMBOS LADOS", "C3"),         # NSK
    ("6205LLUC3", "BORRACHA AMBOS LADOS", "C3"),         # NTN
    ("6310-2Z/C3", "METALICA AMBOS LADOS", "C3"),        # SKF
    ("6310-C-2Z-C3", "METALICA AMBOS LADOS", "C3"),      # FAG
    ("6310ZZC3", "METALICA AMBOS LADOS", "C3"),          # NTN
    ("6205-2ZR", "METALICA AMBOS LADOS", None),          # FAG, sem folga escrita
])
def test_sufixo_de_vedacao_e_folga_dos_seis_fabricantes(designacao, vedacao, folga):
    r = analisar_rolamento(designacao)
    assert r["VEDACAO"] == vedacao
    assert r.get("FOLGA") == folga


def test_ausencia_de_sufixo_nao_vira_valor():
    # a regra de projeto: so evidencia positiva. '6205' sem sufixo nao e ABERTO
    # nem folga NORMAL - e caixa que fica vazia.
    r = analisar_rolamento("6205")
    assert "VEDACAO" not in r
    assert "FOLGA" not in r


def test_sufixo_mais_longo_ganha_do_mais_curto():
    # '2RSH' nao pode ser lido como 'RS' nem '2Z' como 'Z'
    assert analisar_rolamento("6205-2RSH/C3")["sufixo_vedacao"] == "2RSH"
    assert analisar_rolamento("6205-2HRS")["sufixo_vedacao"] == "2HRS"


def test_furo_conico_do_autocompensador():
    assert analisar_rolamento("22212EK/C3")["FURO"] == "CONICO"
    assert "FURO" not in analisar_rolamento("22212E/C3")   # sem K: nao afirma nada


def test_designacao_desconhecida_devolve_none():
    assert analisar_rolamento("") is None
    assert analisar_rolamento("FILTRO LF9009") is None
    assert analisar_rolamento("63022") is None             # 5 digitos sem familia


def test_designacao_achada_dentro_da_descricao_original():
    # o caso 16303905 da base: a caixa REFERENCIA ficou vazia, a designacao
    # continua escrita na descricao
    r = analisar_rolamento("ROLAMENTO NTN 6310ZZC3")
    assert r["DIAMETRO INTERNO"] == 50 and r["DIAMETRO EXTERNO"] == 110
    assert r["LARGURA"] == 27 and r["VEDACAO"] == "METALICA AMBOS LADOS"


# ============================== busca inversa: medidas -> designacao ISO 15

@pytest.mark.parametrize("familia,d,de,b,esperado", [
    ("esferas", 25, 52, 15, "6205"),
    ("esferas", 50, 110, 27, "6310"),
    ("esferas", 25, None, 15, "6205"),          # duas medidas bastam
    ("rolos_esfericos", 60, 110, 28, "22212"),
    ("rolos_conicos", 25, 52, 16.25, "30205"),
])
def test_busca_inversa_na_iso15(familia, d, de, b, esperado):
    assert designacao_por_dimensoes(familia, d, de, b)[0] == esperado


def test_busca_inversa_recusa_quando_nao_e_unica():
    # uma medida so casa em varias series
    assert designacao_por_dimensoes("esferas", 25, None, None) is None
    # 52 x 15 serve ao 6205 (d=25) e ao 6304 (d=20): ambiguo, nao preenche
    assert designacao_por_dimensoes("esferas", None, 52, 15) is None
    # medida que a norma nao tem
    assert designacao_por_dimensoes("esferas", 25, 53, 15) is None


def test_busca_inversa_fecha_o_ciclo_com_a_ida():
    for designacao in ("6205", "6310", "6008", "22212", "30205"):
        r = analisar_rolamento(designacao)
        familia = r["familia"]
        volta = designacao_por_dimensoes(familia, r["DIAMETRO INTERNO"],
                                         r["DIAMETRO EXTERNO"], r["LARGURA"])
        assert volta and volta[0] == designacao


# ======================================= tabelas de rosca e cabeca (DIN/ISO)

@pytest.mark.parametrize("bitola,passo,rosca", [
    ("M6", 1.0, "METRICA GROSSA"),
    ("M8", 1.25, "METRICA GROSSA"),
    ("M12", 1.75, "METRICA GROSSA"),
    ("M16", 2.0, "METRICA GROSSA"),
    ("M20", 2.5, "METRICA GROSSA"),
    ("M12X1,5", 1.5, "METRICA FINA"),
    ("M20X1,5", 1.5, "METRICA FINA"),
    ("M8X1", 1.0, "METRICA FINA"),
])
def test_passo_iso261_e_a_rosca_que_ele_implica(bitola, passo, rosca):
    b = analisar_bitola(bitola)
    assert b["passo"] == passo
    assert b["rosca"] == rosca


@pytest.mark.parametrize("bitola,chave,altura", [
    ("M6", 10.0, 4.0), ("M8", 13.0, 5.3), ("M10", 16.0, 6.4), ("M12", 18.0, 7.5),
    ("M14", 21.0, 8.8), ("M16", 24.0, 10.0), ("M20", 30.0, 12.5), ("M24", 36.0, 15.0),
])
def test_dimensoes_de_cabeca_do_din931_933(bitola, chave, altura):
    b = analisar_bitola(bitola)
    assert b["chave_cabeca"] == chave
    assert b["altura_cabeca"] == altura


@pytest.mark.parametrize("bitola,chave,m934,m985", [
    ("M8", 13.0, 6.8, 8.0), ("M10", 16.0, 8.4, 10.0), ("M12", 18.0, 10.8, 12.0),
    ("M16", 24.0, 14.8, 16.0), ("M20", 30.0, 18.0, 20.0),
])
def test_dimensoes_de_porca_din934_e_din985(bitola, chave, m934, m985):
    b = analisar_bitola(bitola)
    assert (b["chave_porca"], b["altura_porca_din934"], b["altura_porca_din985"]) \
        == (chave, m934, m985)


def test_bitola_nao_metrica_devolve_none():
    assert analisar_bitola("1/2POL") is None
    assert analisar_bitola("") is None


def test_tabelas_de_fixador_cobrem_as_mesmas_bitolas_da_cabeca():
    for d in CABECA_SEXTAVADA:
        assert d in PASSO_METRICO_GROSSO, f"M{d} sem passo na ISO 261"
    for d in PORCA_SEXTAVADA:
        assert d in PASSO_METRICO_GROSSO, f"M{d} sem passo na ISO 261"


# ======================================= formula do comprimento de rosca DIN 931

@pytest.mark.parametrize("d,L,b", [
    (12, 50, 30), (12, 125, 30),       # ate 125: b = 2d + 6
    (12, 150, 36), (12, 200, 36),      # 125 a 200: b = 2d + 12
    (12, 250, 49),                     # acima de 200: b = 2d + 25
    (20, 60, 46), (8, 40, 22),
])
def test_comprimento_de_rosca_din931(d, L, b):
    assert comprimento_rosca_din931(d, L) == b


# =============================================== norma do parafuso e da porca

def test_rosca_em_polegada_e_asme_nao_din():
    # DIN 931 e DIN 933 sao normas de rosca metrica: UNC/UNF nao podem ser nenhuma
    assert norma_parafuso_sextavado("UNC", "1/2POL", "50MM")[0] == "ASME B18.2.1"
    assert norma_parafuso_sextavado("UNF", "", "")[0] == "ASME B18.2.1"


@pytest.mark.parametrize("bitola,comprimento", [
    ("M8", "20MM"),      # 20 <= 2*8+6 = 22
    ("M12", "30MM"),     # 30 <= 30
    ("M20", "40MM"),     # 40 <= 46
    ("M27", "30MM"),
])
def test_comprimento_curto_so_pode_ser_din933(bitola, comprimento):
    r = norma_parafuso_sextavado("METRICA GROSSA", bitola, comprimento)
    assert r[0] == "DIN 933"


@pytest.mark.parametrize("bitola,comprimento", [
    ("M12", "50MM"),     # 50 > 30: as duas normas existem no catalogo
    ("M8", "60MM"),
    ("M16", "100MM"),
])
def test_faixa_ambigua_nao_escolhe_norma(bitola, comprimento):
    assert norma_parafuso_sextavado("METRICA GROSSA", bitola, comprimento) is None


@pytest.mark.parametrize("bitola,comprimento", [
    ("M20", "1,5MM"),    # o passo caiu no campo de comprimento (caso real da base)
    ("M8", "2MM"),
    ("M12", ""),
])
def test_comprimento_implausivel_nao_deriva_norma(bitola, comprimento):
    assert norma_parafuso_sextavado("METRICA GROSSA", bitola, comprimento) is None


@pytest.mark.parametrize("tipo,norma", [
    ("SEXTAVADA", "DIN 934"),
    ("AUTOTRAVANTE", "DIN 985"),
    ("SEXTAVADA FLANGEADA", "DIN 6923"),
    ("CASTELO", "DIN 935"),
])
def test_norma_da_porca_sai_do_tipo(tipo, norma):
    assert norma_porca(tipo)[0] == norma


def test_mapa_tipo_norma_de_porca_e_bijetivo():
    assert len(TIPO_PORCA_POR_NORMA) == len(NORMA_POR_TIPO_PORCA)
    for tipo, norma in NORMA_POR_TIPO_PORCA.items():
        assert TIPO_PORCA_POR_NORMA[norma] == tipo


def test_tipo_de_porca_desconhecido_nao_vira_norma():
    assert norma_porca("PORCA BORBOLETA") is None
    assert norma_porca("") is None


# ================================================================ broca

def test_norma_e_haste_de_broca_se_determinam():
    assert NORMA_BROCA_POR_HASTE["CONE MORSE"] == "DIN 345"
    assert HASTE_POR_NORMA_BROCA["DIN 345"] == "CONE MORSE"
    assert HASTE_POR_NORMA_BROCA["DIN 338"] == "CILINDRICA"
    assert HASTE_POR_NORMA_BROCA["DIN 340"] == "CILINDRICA"
    # a cilindrica empata entre 338 e 340: nao decide a norma
    assert "CILINDRICA" not in NORMA_BROCA_POR_HASTE


# ================================================================ correia

@pytest.mark.parametrize("perfil,referencia,circunferencia", [
    ("B", "2347MM", 2347.0),                      # comprimento ja em mm
    ("A", "A54", 54 * 25.4 + 33),                 # classico: interno em polegada
    ("B", "B54", 54 * 25.4 + 46),
    ("C", "C120", 120 * 25.4 + 74),
    ("SPB", "SPB 2000", 2022.0),                  # SP: primitivo em mm
    ("SPA", "SPA1500", 1518.0),
    ("5V", "5V1150", 115.0 * 25.4),               # decimos de polegada
])
def test_circunferencia_externa_da_correia(perfil, referencia, circunferencia):
    c, _ = circunferencia_correia(perfil, referencia)
    assert c == pytest.approx(circunferencia, abs=0.01)


def test_correia_sem_referencia_devolve_none():
    assert circunferencia_correia("B", "") is None
    assert circunferencia_correia("", "XYZ") is None


@pytest.mark.parametrize("circunferencia_mm,ncm", [
    (400.0, "40103900"),       # <= 60 cm
    (600.0, "40103900"),       # exatamente 60 cm ainda e a residual
    (601.0, "40103200"),       # > 60 cm
    (1417.6, "40103200"),      # B54
    (1800.0, "40103200"),      # exatamente 180 cm
    (1801.0, "40103400"),      # > 180 cm
    (2400.0, "40103400"),      # exatamente 240 cm
    (2401.0, "40103900"),      # > 240 cm volta para a residual
])
def test_ncm_da_correia_por_faixa_de_circunferencia(circunferencia_mm, ncm):
    assert ncm_correia(circunferencia_mm)[0] == ncm


def test_todo_perfil_do_pdm_tem_acrescimo_tabelado(pdm):
    atributo = next(a for a in pdm.classes["PDM030"].atributos if a.nome == "PERFIL")
    for v in atributo.valores:
        assert v in ACRESCIMO_EXTERNO_CORREIA, f"perfil {v} sem acrescimo ISO 4184"


# ================================================================ filtro

@pytest.mark.parametrize("referencia,fabricante,tipo", [
    ("LF9009", "FLEETGUARD", "OLEO LUBRIFICANTE"),
    ("LF3970", "FLEETGUARD", "OLEO LUBRIFICANTE"),
    ("FS4317", "FLEETGUARD", "COMBUSTIVEL"),
    ("AF51124", "FLEETGUARD", "AR"),
    ("HF6177", "FLEETGUARD", "HIDRAULICO"),
    ("DBL7300", "DONALDSON", "OLEO LUBRIFICANTE"),
    ("P551808", "DONALDSON", ""),
    ("B40142", "BALDWIN", "OLEO LUBRIFICANTE"),
    ("BF5544", "BALDWIN", "COMBUSTIVEL"),
    ("PA6146", "BALDWIN", "AR"),
    ("PH5511", "FRAM", "OLEO LUBRIFICANTE"),
    ("CA36284", "FRAM", "AR"),
    ("W 056/70", "MANN", "OLEO LUBRIFICANTE"),
    ("PSL 926", "TECFIL", "OLEO LUBRIFICANTE"),
    ("ARL8401", "TECFIL", "AR"),
    ("1R-1808", "CATERPILLAR", "OLEO LUBRIFICANTE"),
    ("1R1808", "CATERPILLAR", "OLEO LUBRIFICANTE"),
])
def test_prefixo_de_part_number_diz_o_fabricante(referencia, fabricante, tipo):
    fab, t, _ = fabricante_por_part_number(referencia)
    assert fab == fabricante
    assert t == tipo


@pytest.mark.parametrize("referencia", ["", "N82569E70", "MM4151305", "CT6284449",
                                        "2445 4214 96", "640878W"])
def test_part_number_desconhecido_nao_inventa_fabricante(referencia):
    assert fabricante_por_part_number(referencia) is None


def test_fabricante_sugerido_pertence_ao_enum_do_pdm(pdm):
    permitidos = set(next(a for a in pdm.classes["PDM100"].atributos
                          if a.nome == "FABRICANTE").valores)
    for _, fab, _ in PREFIXO_FILTRO:
        assert fab in permitidos, f"{fab} nao esta no enum FABRICANTE de PDM100"


@pytest.mark.parametrize("texto,tipo", [
    ("FILTRO OLEO LUBRIFICANTE FLEETGUARD LF 9009", "OLEO LUBRIFICANTE"),
    ("FILTRO LUBR B40142 BALDWIN", "OLEO LUBRIFICANTE"),
    ("FILTRO COMBUSTIVEL DIESEL", "COMBUSTIVEL"),
    ("FILTRO AR", "AR"),
    ("FILTRO SEPARADOR AR/OLEO", "SEPARADOR AR/OLEO"),
    ("FILTRO HIDRAULICO", "HIDRAULICO"),
    ("FILTRO P551808 DONALDSON", ""),           # a descricao nao diz o tipo
])
def test_tipo_do_filtro_pela_palavra_da_descricao(texto, tipo):
    assert tipo_filtro_por_texto(texto) == tipo


def test_ncm_do_filtro_por_tipo_segue_a_aba_ncm_referencia(pdm):
    permitidos = set(pdm.classes["PDM100"].ncm)
    for tipo, ncm in NCM_POR_TIPO_FILTRO.items():
        assert ncm in permitidos, f"{tipo} -> {ncm} fora da lista de PDM100"


# ============================================ tabelas ampliadas de texto.py

@pytest.mark.parametrize("dn,pol", [(15, "1/2"), (50, "2"), (300, "12"),
                                    (700, "28"), (1000, "40"), (1200, "48")])
def test_dn_para_polegada_ampliado(dn, pol):
    assert DN_PARA_POL[dn] == pol
    assert fmt_pol(f"DN {dn}") == f"{pol}POL"


def test_dn_para_polegada_e_monotonico():
    from fractions import Fraction

    def para_fracao(pol: str) -> Fraction:
        # '2' -> 2; '1/2' -> 1/2; '1.1/4' -> 1 + 1/4 (notacao do PDM)
        return sum((Fraction(p) for p in pol.replace(".", " ").split()), Fraction(0))

    polegadas = [para_fracao(p) for _, p in sorted(DN_PARA_POL.items())]
    assert polegadas == sorted(polegadas), "DN maior tem de dar polegada maior"


@pytest.mark.parametrize("awg,mm2", [(24, "0,2"), (20, "0,5"), (14, "2,5"),
                                     (8, "10"), (0, "70"), (-1, "95"), (-3, "150")])
def test_awg_para_mm2_ampliado(awg, mm2):
    assert AWG_PARA_MM2[awg] == mm2


def test_awg_menor_significa_secao_maior():
    from saneamento.texto import parse_numero
    itens = sorted(AWG_PARA_MM2.items(), reverse=True)
    secoes = [parse_numero(v) for _, v in itens]
    assert secoes == sorted(secoes), "AWG decrescente tem de dar secao crescente"


# ============================================== tabela oficial da NCM (fonte a)

@pytest.fixture(scope="module")
def ncm():
    t = TabelaNcm.local(RAIZ / "dados" / "referencia")
    if t is None:
        pytest.skip("rode scripts/09_enriquecer.py --baixar-ncm antes")
    return t


def test_formata_ncm():
    assert formata_ncm("84821010") == "8482.10.10"
    assert formata_ncm("8482.10.10") == "8482.10.10"


def test_tabela_oficial_traz_o_ato_e_a_vigencia(ncm):
    assert ncm.meta["ato"]
    assert ncm.meta["vigencia_declarada"]
    assert ncm.meta["url"].startswith("https://portalunico.siscomex.gov.br/")
    assert ncm.meta["codigos_8_digitos"] > 9000


@pytest.mark.parametrize("codigo", ["8482.10.10", "7318.15.00", "7318.16.00",
                                    "8421.23.00", "8421.31.00", "4010.32.00",
                                    "4016.93.00", "2710.19.32"])
def test_ncm_usado_pelo_pdm_existe_e_esta_vigente(ncm, codigo):
    assert ncm.existe(codigo)
    assert ncm.vigente(codigo)
    assert ncm.descricao(codigo)


@pytest.mark.parametrize("codigo", ["7306.30.00", "8539.50.00", "9999.99.99"])
def test_codigo_revogado_ou_inexistente_e_recusado(ncm, codigo):
    # os dois primeiros estao na base legada, passam pelo formato e pela classe,
    # e nao existem na tabela oficial: e exatamente o que a regra 12 proibe
    assert not ncm.existe(codigo)
    assert not ncm.vigente(codigo)


def test_sucessor_so_sai_quando_a_subposicao_decide(ncm):
    # 7306.30 ficou com dois codigos; um deles e o residual 'Outros'
    suc = ncm.sucessor("7306.30.00")
    assert suc and suc[0] == "73063090"
    # 8539.50 inteiro deixou de existir: nao ha sucessor a afirmar
    assert ncm.sucessor("8539.50.00") is None
    # codigo vigente nao tem sucessor
    assert ncm.sucessor("8482.10.10") is None


def test_vigencia_respeita_a_data_de_inicio(ncm):
    # antes de 1900 nenhum codigo da tabela atual estava em vigor
    assert not ncm.vigente("8482.10.10", em=date(1900, 1, 1))


def test_procedencia_da_tabela_oficial_e_completa(ncm):
    p = ncm.procedencia()
    assert p.completa
    assert "portalunico.siscomex.gov.br" in p.url_ou_referencia


# ================================================ invariantes 2 e 3 no fluxo

def test_enriquecimento_nao_sobrescreve_valor_extraido(enr):
    # a largura do cadastro diz 14MM; a ISO 15 diz 15MM para o 6205. O cadastro
    # vence: enriquecimento so preenche caixa vazia.
    r = enr.enriquecer("teste", "PDM020",
                       {"REFERENCIA": "6205-2RSH/C3", "LARGURA": "14MM"})
    assert "LARGURA" not in r.atributos
    assert "DIAMETRO INTERNO" in r.atributos


def test_valor_fora_do_enum_do_pdm_e_recusado(pdm):
    # a tabela tecnica tambem erra: o enum e o portao, igual para toda camada
    e = Enriquecedor(pdm)
    classe = pdm.classes["PDM020"]
    sug = []
    assert not e._propor(sug, classe, {}, "VEDACAO", "VEDACAO DE FELTRO",
                         Procedencia("teste", "inventado", "2026-11-07", 0.9),
                         "teste", "teste")
    assert sug == []
    assert e.contador["recusadas_pelo_validador"] == 1


def test_atributo_que_nao_existe_na_classe_nao_entra(pdm):
    e = Enriquecedor(pdm)
    sug = []
    assert not e._propor(sug, pdm.classes["PDM020"], {}, "VISCOSIDADE", "ISO VG 46",
                         Procedencia("teste", "inventado", "2026-11-07", 0.9),
                         "teste", "teste")
    assert sug == []


def test_enriquecimento_do_6205_completo(enr):
    r = enr.enriquecer("20866024", "PDM020", {"REFERENCIA": "6205-2RSH/C3"})
    valores = {s.atributo: s.valor for s in r.sugestoes}
    assert valores["DIAMETRO INTERNO"] == "25MM"
    assert valores["DIAMETRO EXTERNO"] == "52MM"
    assert valores["LARGURA"] == "15MM"
    assert valores["VEDACAO"] == "BORRACHA AMBOS LADOS"
    assert valores["FOLGA"] == "C3"
    # toda sugestao com procedencia completa e marcada como enriquecida
    for s in r.sugestoes:
        assert s.procedencia.completa
        assert s.tipo == TIPO_ENRIQUECIDO
        assert s.derivado_de and s.metodo


def test_enriquecimento_do_6310_completo(enr):
    r = enr.enriquecer("29364361", "PDM020", {"REFERENCIA": "6310-2Z/C3"})
    valores = {s.atributo: s.valor for s in r.sugestoes}
    assert valores["DIAMETRO INTERNO"] == "50MM"
    assert valores["DIAMETRO EXTERNO"] == "110MM"
    assert valores["LARGURA"] == "27MM"
    assert valores["VEDACAO"] == "METALICA AMBOS LADOS"
    assert valores["FOLGA"] == "C3"


def test_filtro_sem_fabricante_fecha_pelo_part_number(enr):
    r = enr.enriquecer("27841570", "PDM100",
                       {"REFERENCIA FABRICANTE": "LF9009", "FABRICANTE": None},
                       texto="FILTRO LF9009")
    valores = {s.atributo: s.valor for s in r.sugestoes}
    assert valores["FABRICANTE"] == "FLEETGUARD"


def test_ncm_condicional_do_filtro_e_resolvido_e_conferido(pdm):
    t = TabelaNcm.local(RAIZ / "dados" / "referencia")
    if t is None:
        pytest.skip("rode scripts/09_enriquecer.py --baixar-ncm antes")
    e = Enriquecedor(pdm, tabela_ncm=t)
    r = e.enriquecer("16031971", "PDM100",
                     {"FABRICANTE": "FLEETGUARD", "REFERENCIA FABRICANTE": "LF9009"},
                     texto="FILTRO OLEO LUBRIFICANTE FLEETGUARD LF 9009", ncm_atual="")
    assert r.ncm_veredito == "AUSENTE"
    assert r.ncm and r.ncm.valor == "8421.23.00"
    assert r.ncm.procedencia.completa


def test_ncm_nao_vigente_e_apontado_com_sucessor_para_revisao(pdm):
    t = TabelaNcm.local(RAIZ / "dados" / "referencia")
    if t is None:
        pytest.skip("rode scripts/09_enriquecer.py --baixar-ncm antes")
    e = Enriquecedor(pdm, tabela_ncm=t)
    r = e.enriquecer("x", "PDM051", {}, ncm_atual="7306.30.00")
    assert r.ncm_veredito == "NAO_VIGENTE"
    assert r.ncm and r.ncm.valor == "7306.30.90"
    assert r.ncm.revisar, "sucessor de NCM nunca entra sem revisao humana"


def test_sem_tabela_de_ncm_a_camada_diz_que_nao_validou(pdm):
    e = Enriquecedor(pdm, tabela_ncm=None)
    r = e.enriquecer("x", "PDM020", {"REFERENCIA": "6205"}, ncm_atual="8482.10.10")
    assert r.ncm_veredito == "SEM_TABELA"
    assert "NAO foram verificadas" in r.ncm_motivo
