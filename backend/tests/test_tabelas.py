from app.tabelas.rolamentos import SERIES, dimensoes


def test_exemplos_documentados():
    assert dimensoes("6205-2RS/C3") == {"DIAMETRO INTERNO": ("25MM", "ISO 15, serie 6205 (tabela local)"),
                                        "DIAMETRO EXTERNO": ("52MM", "ISO 15, serie 6205 (tabela local)"),
                                        "LARGURA": ("15MM", "ISO 15, serie 6205 (tabela local)")}   # exemplo do PDM
    assert dimensoes("SKF 6206-2RSH/C3")["DIAMETRO EXTERNO"][0] == "62MM"                          # briefing: DI 30, DE 62
    assert dimensoes("NSK 6310ZZC3")["LARGURA"][0] == "27MM"


def test_so_series_conhecidas():
    assert dimensoes("6999") == {} and dimensoes("30205") == {} and dimensoes(None) == {} and dimensoes("abc") == {}


def test_tabela_e_coerente():
    for serie, (d, D, B) in SERIES.items():
        assert D > d and B < D, serie
        assert serie[:2] in ("60", "62", "63")
