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
