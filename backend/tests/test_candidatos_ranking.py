from app.identidade import candidatos
from app.sugestoes import ranking

NOME_ROL = "ROLAMENTO RIGIDO ESFERAS"
ROL = {"REFERENCIA": "6205-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}


def niveis(res):
    return {c.codigo: c.nivel for c in res.candidatos}


def test_base_de_teste_estruturada(base_teste, banco):
    with banco.connect() as c:
        n = c.exec_driver_sql("select count(*) from material_identidade where completa").scalar()
    assert n >= 11


def test_igual_quando_a_chave_fecha(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", NOME_ROL, ROL)
    n = niveis(r)
    assert n["90000001"] == "IGUAL"
    assert r.candidatos[0].codigo == "90000001" and r.candidatos[0].permite_uso_direto


def test_vedacao_diferente_e_divergente_e_mostra_qual(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", NOME_ROL, ROL)
    assert niveis(r).get("90000003") == "DIVERGENTE"
    d = next(c for c in r.candidatos if c.codigo == "90000003")
    assert "VEDACAO" in d.motivo or "REFERENCIA" in d.motivo
    assert d.pontos <= 0.85  # atributo de identidade divergente limita a confianca


def test_cadastro_existente_incompleto_e_provavel(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", NOME_ROL, {"REFERENCIA": "6205-2RS/C3", "FOLGA": "C3"})
    # sem VEDACAO no rascunho a chave nao fecha: o item igual aparece como PROVAVEL, nunca como IGUAL
    assert niveis(r).get("90000001") == "PROVAVEL"


def test_cobertura_informa_o_ponto_cego(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", NOME_ROL, ROL)
    assert r.total_classe >= r.comparaveis >= 1


def test_codigo_bloqueado_aparece_com_status_e_sem_uso_direto(base_teste, banco):
    pdm = base_teste["pdm"]
    v = {"REFERENCIA": "6206-2RS/C3", "DIAMETRO INTERNO": "30MM", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", NOME_ROL, v)
    b = next((x for x in r.candidatos if x.codigo == "90000004"), None)
    assert b is not None and b.status == "BLOQUEADO" and not b.permite_uso_direto and b.estoque == 7


def test_filtro_equivalente_nao_une_e_igual_une(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM100", "FILTRO OLEO LUBRIFICANTE",
                             {"FABRICANTE": "CATERPILLAR", "REFERENCIA FABRICANTE": "1R1808"})
    n = niveis(r)
    assert n["90000010"] == "IGUAL"          # mesmo fabricante e referencia (sem separador)
    assert n["90000011"] == "EQUIVALENTE"    # DONALDSON P551808: intercambiavel, item distinto
    assert next(c for c in r.candidatos if c.codigo == "90000011").permite_uso_direto  # existe, mas nao e "igual"


def test_mesma_referencia_outro_fabricante_e_so_parecido(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM100", "FILTRO OLEO LUBRIFICANTE",
                             {"FABRICANTE": "FLEETGUARD", "REFERENCIA FABRICANTE": "P551808"})
    assert niveis(r)["90000011"] == "PARECIDO"


# ---------------------------------------------------------------- sugestões
PARAF = "PARAFUSO SEXTAVADO"


def test_opcoes_vem_do_historico_por_nome_sem_preencher(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        o = ranking.opcoes(c, pdm, "PDM001", PARAF, "CLASSE RESISTENCIA", {})
    assert [x.valor for x in o.opcoes][:2] == ["8.8", "10.9"]
    assert o.opcoes[0].n == 5 and o.base == 9
    assert all(x.pct is None for x in o.opcoes)  # base pequena: nao mostra percentual


def test_contexto_dos_outros_atributos_refina(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        o = ranking.opcoes(c, pdm, "PDM001", PARAF, "CLASSE RESISTENCIA", {"BITOLA": "M12"})
    assert o.contexto == ["BITOLA"] and [x.valor for x in o.opcoes] == ["8.8"]


def test_sem_suporte_recua_o_contexto(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        o = ranking.opcoes(c, pdm, "PDM001", PARAF, "CLASSE RESISTENCIA", {"BITOLA": "M20"})
    assert o.contexto == []  # so 1 item com M20: recua para o nome inteiro


def test_part_number_nao_tem_opcoes(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        o = ranking.opcoes(c, pdm, "PDM100", "FILTRO OLEO LUBRIFICANTE", "REFERENCIA FABRICANTE", {})
    assert o.opcoes == [] and "livre" in o.sem_opcoes_motivo


def test_opcoes_so_com_valores_validos_do_pdm(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        o = ranking.opcoes(c, pdm, "PDM001", PARAF, "ACABAMENTO", {})
    assert all(x.valor in pdm.classes["PDM001"].atributo("ACABAMENTO").valores for x in o.opcoes)


def test_rolamento_de_outra_serie_nao_vira_divergente_so_porque_vedacao_e_folga_coincidem(base_teste, banco):
    """Vedacao e folga tem poucos valores: coincidir prova pouco. A serie (6307 x 6205) pesa mais."""
    pdm = base_teste["pdm"]
    v = {"REFERENCIA": "6307-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", NOME_ROL, v)
    assert r.candidatos == []


def test_mesma_serie_com_vedacao_diferente_e_divergente_com_a_serie_como_evidencia(base_teste, banco):
    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", NOME_ROL, ROL)
    d = next(x for x in r.candidatos if x.codigo == "90000003")
    serie = next(x for x in d.comparacao if x["atributo"] == "REFERENCIA (serie)")
    assert serie["estado"] == "igual" and serie["rascunho"] == "6205"


def _extra(banco, base, itens):
    """Insere itens de apoio só para um teste e os remove depois (a base de teste é compartilhada)."""
    from sqlalchemy import text

    from app.estruturacao import persistir
    from app.estruturacao.regras import extrai_por_regras

    mats = []
    with banco.begin() as c:
        for cod, longa, status in itens:
            c.execute(text("insert into material (codigo, descricao_longa, grupo, status, estoque, centro) values (:c, :l, 'ROL01', :s, 1, '1100')"),
                      {"c": cod, "l": longa, "s": status})
            m = {"codigo": cod, "descricao_longa": longa, "descricao_curta": longa[:40], "grupo": "ROL01", "status": status,
                 "fabricante": None, "referencia_fabricante": None}
            mats.append((m, extrai_por_regras(base["pdm"], base["indice"], m)))
        persistir.grava(c, base["pdm"], mats, "teste")
    return [m["codigo"] for m, _ in mats]


def test_medida_opcional_diferente_desmente_o_provavel(base_teste, banco):
    """Um rolamento sem referencia, mas com diametro externo de 150 mm, nao e o 6205 (52 mm)."""
    from sqlalchemy import text

    base = base_teste
    cods = _extra(banco, base, [
        ("90009001", "ROLAMENTO RIGIDO ESFERAS; DIAMETRO INTERNO: 25MM; DIAMETRO EXTERNO: 150MM; VEDACAO: BORRACHA AMBOS LADOS; FOLGA: C3", "ATIVO"),
        ("90009002", "ROLAMENTO RIGIDO ESFERAS; DIAMETRO INTERNO: 25MM; DIAMETRO EXTERNO: 52MM; VEDACAO: BORRACHA AMBOS LADOS; FOLGA: C3", "ATIVO"),
    ])
    try:
        v = {"REFERENCIA": "6205-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3",
             "DIAMETRO INTERNO": "25MM", "DIAMETRO EXTERNO": "52MM", "LARGURA": "15MM"}
        with banco.connect() as c:
            r = candidatos.busca(c, base["pdm"], "PDM020", NOME_ROL, v)
        n = niveis(r)
        assert "90009001" not in n or n["90009001"] != "PROVAVEL"   # 150 mm desmente
        assert n.get("90009002") == "PROVAVEL"                        # mesmas medidas: continua provavel
    finally:
        with banco.begin() as c:
            c.execute(text("delete from material where codigo = any(:c)"), {"c": cods})


def test_valor_fora_do_pdm_no_texto_do_existente_vira_divergencia(base_teste, banco):
    """Parafuso M3 (bitola fora da lista do PDM, guardada como valor bruto) nao e provavel duplicata de um M12."""
    from sqlalchemy import text

    from app.estruturacao import persistir
    from app.estruturacao.regras import extrai_por_regras

    base, pdm = base_teste, base_teste["pdm"]
    longa = ("PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M3; COMPRIMENTO: 50MM; CLASSE RESISTENCIA: 8.8; "
             "MATERIAL: ACO CARBONO; ACABAMENTO: ZINCADO BRANCO; NORMA: DIN 933")
    with banco.begin() as c:
        c.execute(text("insert into material (codigo, descricao_longa, grupo, status, estoque, centro) values ('90009003', :l, 'FIX01', 'ATIVO', 1, '1100')"), {"l": longa})
        m = {"codigo": "90009003", "descricao_longa": longa, "descricao_curta": longa[:40], "grupo": "FIX01", "status": "ATIVO",
             "fabricante": None, "referencia_fabricante": None}
        ex = extrai_por_regras(pdm, base["indice"], m)
        assert ex.valores["BITOLA"].valor is None and ex.valores["BITOLA"].bruto == "M3"   # fora da lista: so o bruto
        persistir.grava(c, pdm, [(m, ex)], "teste")
    try:
        v = {"ROSCA": "METRICA GROSSA", "BITOLA": "M12", "COMPRIMENTO": "50MM", "CLASSE RESISTENCIA": "8.8",
             "MATERIAL": "ACO CARBONO", "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}
        with banco.connect() as c:
            r = candidatos.busca(c, pdm, "PDM001", "PARAFUSO SEXTAVADO", v)
        n = niveis(r)
        assert n.get("90009003") == "DIVERGENTE"          # nao e "provavel": a bitola existe e e outra
        item = next(x for x in r.candidatos if x.codigo == "90009003")
        bitola = next(x for x in item.comparacao if x["atributo"] == "BITOLA")
        assert bitola["estado"] == "diverge" and "fora do PDM" in bitola["candidato"]
    finally:
        with banco.begin() as c:
            c.execute(text("delete from material where codigo = '90009003'"))
