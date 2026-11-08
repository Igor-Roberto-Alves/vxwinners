from app.cadastro.descricao import monta_curta, monta_longa


def test_exemplo_rolamento_das_regras_gerais(pdm):
    """Exemplo literal da regra 2 do PDM."""
    v = {"REFERENCIA": "6205-2RS/C3", "DIAMETRO INTERNO": "25MM", "DIAMETRO EXTERNO": "52MM",
         "LARGURA": "15MM", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}
    esperado = ("ROLAMENTO RIGIDO ESFERAS; REFERENCIA: 6205-2RS/C3; DIAMETRO INTERNO: 25MM; "
                "DIAMETRO EXTERNO: 52MM; LARGURA: 15MM; VEDACAO: BORRACHA AMBOS LADOS; FOLGA: C3")
    assert monta_longa(pdm, "PDM020", "ROLAMENTO RIGIDO ESFERAS", v) == esperado


def test_exemplo_parafuso_das_regras_gerais(pdm):
    v = {"ROSCA": "METRICA GROSSA", "BITOLA": "M12", "COMPRIMENTO": "50MM", "CLASSE RESISTENCIA": "8.8",
         "MATERIAL": "ACO CARBONO", "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}
    esperado = ("PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12; COMPRIMENTO: 50MM; "
                "CLASSE RESISTENCIA: 8.8; MATERIAL: ACO CARBONO; ACABAMENTO: ZINCADO BRANCO; NORMA: DIN 933")
    assert monta_longa(pdm, "PDM001", "PARAFUSO SEXTAVADO", v) == esperado


def test_ordem_e_do_pdm_nao_da_entrada(pdm):
    a = {"BITOLA": "M12", "ROSCA": "METRICA GROSSA"}
    assert monta_longa(pdm, "PDM001", "PARAFUSO SEXTAVADO", a) == "PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12"


def test_pendentes_marcados_so_quando_pedido(pdm):
    v = {"ROSCA": "METRICA GROSSA"}
    assert "?" not in monta_longa(pdm, "PDM001", "PARAFUSO SEXTAVADO", v)
    assert "CLASSE RESISTENCIA: ?" in monta_longa(pdm, "PDM001", "PARAFUSO SEXTAVADO", v, marca_pendentes=True)


def test_atributo_condicional_nao_aplicavel_fica_de_fora(pdm):
    v = {"TIPO": "MOTOR", "POLOS": "3P", "FAIXA AJUSTE": "1-1,6A", "CURVA": "C"}
    d = monta_longa(pdm, "PDM062", "DISJUNTOR", v)
    assert "FAIXA AJUSTE: 1-1,6A" in d and "CURVA" not in d  # CURVA so vale para minidisjuntor


def test_fabricante_aparece_so_nas_classes_de_referencia(pdm):
    ref = monta_longa(pdm, "PDM100", "FILTRO AR", {"FABRICANTE": "DONALDSON", "REFERENCIA FABRICANTE": "P551808"})
    assert "FABRICANTE: DONALDSON" in ref and "REFERENCIA FABRICANTE: P551808" in ref
    esp = monta_longa(pdm, "PDM032", "RETENTOR", {"DIAMETRO EIXO": "60MM"})
    assert "FABRICANTE" not in esp  # regra 8: fora da descrição nas classes de especificação


def test_descricao_curta_ate_40_caracteres_em_palavra_inteira(pdm):
    v = {"ROSCA": "METRICA GROSSA", "BITOLA": "M12", "COMPRIMENTO": "50MM", "CLASSE RESISTENCIA": "8.8",
         "MATERIAL": "ACO CARBONO", "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}
    c = monta_curta(pdm, "PDM001", "PARAFUSO SEXTAVADO", v)
    assert len(c) <= 40 and c.startswith("PARAFUSO SEXTAVADO")
    assert not c.endswith(" ") and c in "PARAFUSO SEXTAVADO METRICA GROSSA M12 50MM 8.8 ACO CARBONO"
