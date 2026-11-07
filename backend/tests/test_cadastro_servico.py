import json
import threading
import time

import pytest
from sqlalchemy import text

from app import auditoria
from app.cadastro import servico as S
from app.cadastro.modelo import ErroNegocio
from app.erp.conector import ConectorArquivo
from app.erp.sincroniza import envia_pendentes, processa_retornos
from app.ncm import tabela

CENTRO = "1100 - MINA SERRA AZUL"
ROL = "ROLAMENTO RIGIDO ESFERAS"


@pytest.fixture(scope="module", autouse=True)
def ncm_de_teste(banco, tmp_path_factory, base_teste):
    codigos = ["7318.15.00", "8482.10.10", "8421.23.00", "7306.30.10", "7306.30.90", "4016.93.00", "8481.80.95"]
    doc = {"Ato": "teste", "Data_Ultima_Atualizacao_NCM": "teste", "Nomenclaturas": [
        {"Codigo": c, "Descricao": "x", "Data_Inicio": "01/01/2020", "Data_Fim": "31/12/9999"} for c in codigos]}
    arq = tmp_path_factory.mktemp("ncm") / "ncm.json"
    arq.write_text(json.dumps(doc))
    with banco.begin() as c:
        tabela.importa(c, arq)
    yield
    tabela._cache.clear()


@pytest.fixture(autouse=True)
def limpa(banco):
    with banco.begin() as c:
        for t in ("erp_envio", "cadastro_pergunta", "cadastro_excecao", "pdm_proposta", "cadastro", "pedido", "area_contato"):
            c.execute(text(f"delete from {t}"))
    yield


def novo_rolamento(c, base, ref="6207-2RS/C3", centro=CENTRO, autor="ana"):
    cad = S.cria(c, base["pdm"], base["indice"], autor, id_pdm="PDM020", nome=ROL, centro=centro)
    return cad


def preenche_rolamento(c, base, cad, ref="6207-2RS/C3", autor="ana"):
    return S.atualiza(c, base["pdm"], cad["id"], cad["versao"], autor, valores={
        "REFERENCIA": ref, "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3", "DIAMETRO INTERNO": "35 mm"})


def bloqueios(v):
    return {b["codigo"] for b in v["bloqueios"]}


# ------------------------------------------------------------------ criação e edição
def test_rascunho_novo_lista_obrigatorios_pendentes(banco, base_teste):
    with banco.begin() as c:
        v = novo_rolamento(c, base_teste)
    assert v["estado"] == "RASCUNHO" and v["classe"]["confirmada"] and v["classe"]["nome"] == ROL
    assert {x["atributo"] for x in v["campos"] if x["obrigatorio"]} == {"REFERENCIA", "VEDACAO", "FOLGA"}
    assert "OBRIGATORIO_VAZIO" in bloqueios(v) and not v["pronto_para_aprovar"]
    assert v["fiscal"]["unidade"]["padrao"] == "PC" and v["fiscal"]["ncm"]["esperado"] == "8482.10.10"


def test_valores_canonicalizados_e_descricao_gerada(banco, base_teste):
    with banco.begin() as c:
        v = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="SKF 6207-2RSH/C3")
    campo = {x["atributo"]: x for x in v["campos"]}
    assert campo["REFERENCIA"]["valor"] == "6207-2RS/C3"
    assert campo["DIAMETRO INTERNO"]["valor"] == "35MM" and campo["DIAMETRO INTERNO"]["origem"] == "DIGITADO"
    # DE e largura vieram da tabela ISO 15 (serie 6207); o DI foi digitado
    assert v["descricao"]["longa"].startswith(
        f"{ROL}; REFERENCIA: 6207-2RS/C3; DIAMETRO INTERNO: 35MM; DIAMETRO EXTERNO: 72MM; LARGURA: 17MM; VEDACAO:")
    assert v["chave"]["completa"] and v["descricao"]["curta_tamanho"] <= 40


def test_bloqueio_otimista_dois_editores(banco, base_teste):
    with banco.begin() as c:
        cad = novo_rolamento(c, base_teste)
    with banco.begin() as c:
        S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", valores={"FOLGA": "C3"})
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:
        S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "beto", valores={"FOLGA": "NORMAL"})
    assert e.value.codigo == "versao_desatualizada" and e.value.status == 409


def test_atributo_de_outra_classe_e_recusado(banco, base_teste):
    with banco.begin() as c:
        cad = novo_rolamento(c, base_teste)
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:
        S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", valores={"BITOLA": "M12"})
    assert e.value.codigo == "atributo_invalido"


def test_trocar_de_classe_descarta_so_o_que_nao_existe(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste))
    with banco.begin() as c:
        v = S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", classe={"id_pdm": "PDM021"})
    campos = {x["atributo"]: x["valor"] for x in v["campos"]}
    assert campos.get("DIAMETRO INTERNO") == "35MM"  # existe nas duas classes
    assert "VEDACAO" not in campos                      # PDM021 nao tem esse atributo


def test_interpretar_texto_so_preenche_o_que_esta_vazio(banco, base_teste):
    with banco.begin() as c:
        cad = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", id_pdm="PDM001", centro=CENTRO)
    with banco.begin() as c:
        v = S.interpretar(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", "M12X50 8.8 DIN 933")
    campo = {x["atributo"]: x["valor"] for x in v["campos"]}
    assert campo["BITOLA"] == "M12" and campo["COMPRIMENTO"] == "50MM" and campo["ROSCA"] == "METRICA GROSSA"
    assert campo["CLASSE RESISTENCIA"] == "8.8" and campo["NORMA"] == "DIN 933"
    assert campo["ACABAMENTO"] is None  # nada foi dito sobre acabamento


# ------------------------------------------------------------------ aprovação, bloqueios e exceções
def test_aprovacao_limpa_vai_direto_ao_erp(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste))
    with banco.begin() as c:
        v = S.aprova(c, base_teste["pdm"], cad["id"], cad["versao"], "ana")
    assert v["estado"] == "APROVADO" and v["excecoes_previstas"] == []
    with banco.begin() as c:
        assert c.execute(text("select count(*) from erp_envio where tipo='ITEM_NOVO'")).scalar() == 1
        row = c.execute(text("select unidade, grupo, ncm, chave from cadastro")).one()
    assert row[:3] == ("PC", "ROL01", "8482.10.10") and row[3]


def test_aprovar_com_pendencia_e_bloqueado_com_a_lista_exata(banco, base_teste):
    with banco.begin() as c:
        cad = novo_rolamento(c, base_teste)
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:
        S.aprova(c, base_teste["pdm"], cad["id"], cad["versao"], "ana")
    assert e.value.codigo == "bloqueios"
    assert {b["atributo"] for b in e.value.detalhes["bloqueios"] if b["codigo"] == "OBRIGATORIO_VAZIO"} == {"REFERENCIA", "VEDACAO", "FOLGA"}


def test_classe_vinda_de_pedido_so_vale_depois_de_confirmada(banco, base_teste):
    with banco.begin() as c:
        c.execute(text("""insert into pedido (id, centro, area, canal, texto) values ('SC-T1', :c, 'PCM', 'PORTAL',
            'preciso de 10 parafuso sextavado m16 x 60 galvanizado 8.8 din 933 pra peneira')"""), {"c": CENTRO})
        v = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", pedido_id="SC-T1")
    assert v["classe"]["id_pdm"] == "PDM001" and not v["classe"]["confirmada"]
    assert "CLASSE_NAO_CONFIRMADA" in bloqueios(v)
    campo = {x["atributo"]: x for x in v["campos"]}
    assert campo["BITOLA"]["valor"] == "M16" and campo["BITOLA"]["origem"] == "PEDIDO_REGRA" and campo["BITOLA"]["trecho"]
    assert campo["ACABAMENTO"]["valor"] is None  # "galvanizado" ambiguo
    with banco.begin() as c:
        v2 = S.atualiza(c, base_teste["pdm"], v["id"], v["versao"], "ana", classe={"id_pdm": "PDM001"})
    assert v2["classe"]["confirmada"] and "CLASSE_NAO_CONFIRMADA" not in bloqueios(v2)
    with banco.begin() as c:  # idempotente: o mesmo pedido devolve o mesmo cadastro
        assert S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", pedido_id="SC-T1")["id"] == v["id"]


def test_ncm_desdobrado_bloqueia_e_aponta_os_sucessores(banco, base_teste):
    with banco.begin() as c:
        cad = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", id_pdm="PDM051", centro=CENTRO)
        v = S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", valores={
            "DIAMETRO NOMINAL": "2POL", "SCHEDULE": "SCH 40", "MATERIAL": "ACO GALVANIZADO NBR 5580",
            "COSTURA": "COM COSTURA", "EXTREMIDADES": "ROSCADAS"})
    ncm = v["fiscal"]["ncm"]
    assert ncm["esperado"] == "7306.30.00" and not ncm["validacao"]["ok"]
    b = next(b for b in v["bloqueios"] if b["codigo"] == "NCM_INVALIDO")
    assert b["sucessores"] == ["7306.30.10", "7306.30.90"]
    with banco.begin() as c:  # a pessoa corrige para um codigo vigente: vira excecao (difere da regra do PDM)
        v2 = S.atualiza(c, base_teste["pdm"], v["id"], v["versao"], "ana", campos={"ncm": "73063090"})
    assert "NCM_INVALIDO" not in bloqueios(v2)
    assert [x["tipo"] for x in v2["excecoes_previstas"]] == ["NCM_DIFERENTE_DA_REGRA"]


def test_excecao_exige_justificativa_e_segundo_analista(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6205-2RS/C3")  # igual ao 90000001
    with banco.begin() as c:
        v = S.obtem(c, base_teste["pdm"], cad["id"])
    assert {x["tipo"] for x in v["excecoes_previstas"]} == {"DUPLICIDADE_IGUAL"}
    assert v["duplicidade"]["candidatos"][0]["nivel"] == "IGUAL" and v["duplicidade"]["candidatos"][0]["permite_uso_direto"]
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:
        S.aprova(c, base_teste["pdm"], cad["id"], v["versao"], "ana")
    assert e.value.codigo == "justificativa_obrigatoria"
    with banco.begin() as c:
        em_rev = S.aprova(c, base_teste["pdm"], cad["id"], v["versao"], "ana",
                          {"DUPLICIDADE_IGUAL|": "o item existente e do centro 1100 e este e para o terminal portuario"})
    assert em_rev["estado"] == "EM_REVISAO"
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:  # quem pediu a excecao nao a aprova
        S.decide_revisao(c, base_teste["pdm"], cad["id"], "ana", True, None)
    assert e.value.codigo == "revisor_deve_ser_outra_pessoa" and e.value.status == 403
    with banco.begin() as c:
        final = S.decide_revisao(c, base_teste["pdm"], cad["id"], "bia", True, "ok, centros diferentes")
    assert final["estado"] == "APROVADO"
    with banco.begin() as c:
        assert c.execute(text("select count(*) from cadastro_excecao where decisao='APROVADA' and revisor='bia'")).scalar() == 1
        assert c.execute(text("select count(*) from erp_envio")).scalar() == 1


def test_revisor_pode_rejeitar_e_o_rascunho_volta(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6205-2RS/C3")
    with banco.begin() as c:
        S.aprova(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", {"DUPLICIDADE_IGUAL|": "preciso de um codigo separado para o outro centro"})
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:
        S.decide_revisao(c, base_teste["pdm"], cad["id"], "bia", False, " ")
    assert e.value.codigo == "comentario_obrigatorio"
    with banco.begin() as c:
        v = S.decide_revisao(c, base_teste["pdm"], cad["id"], "bia", False, "use o codigo 90000001")
    assert v["estado"] == "RASCUNHO" and v["motivo"] == "use o codigo 90000001"


def test_valor_fora_da_lista_e_excecao_nao_bloqueio(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste, ref="6208-2RS/C3"), ref="6208-2RS/C3")
    with banco.begin() as c:
        v = S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", valores={"FOLGA": "C9 ESPECIAL"})
    assert {x["tipo"] for x in v["excecoes_previstas"]} == {"FORA_DA_LISTA"} and not v["bloqueios"]
    assert next(x for x in v["campos"] if x["atributo"] == "FOLGA")["valido"] is False


def test_unidade_diferente_do_padrao_e_excecao(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste, ref="6209-2RS/C3"), ref="6209-2RS/C3")
        v = S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", campos={"unidade": "pr"})
    assert {x["tipo"] for x in v["excecoes_previstas"]} == {"UNIDADE_DIFERENTE_DO_PADRAO"}
    with banco.begin() as c:
        v2 = S.atualiza(c, base_teste["pdm"], cad["id"], v["versao"], "ana", campos={"unidade": "CX"})
    assert "UNIDADE_INVALIDA" in bloqueios(v2)  # CX nao existe no PDM: nao ha excecao que a salve


# ------------------------------------------------------------------ concorrência
def test_dois_analistas_aprovando_o_mesmo_item_so_um_vence(banco, base_teste):
    pdm, indice = base_teste["pdm"], base_teste["indice"]
    ids = []
    for autor in ("ana", "beto"):
        with banco.begin() as c:
            cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste, autor=autor), ref="6210-2RS/C3", autor=autor)
            ids.append((cad["id"], cad["versao"], autor))
    resultado, a_aprovou = {}, threading.Event()

    def analista_a():
        with banco.connect() as c:
            t = c.begin()
            S.aprova(c, pdm, ids[0][0], ids[0][1], "ana")
            a_aprovou.set()
            time.sleep(0.6)   # mantém a transação aberta: B vai esbarrar no índice único
            t.commit()
        resultado["a"] = "ok"

    def analista_b():
        a_aprovou.wait(5)
        try:
            with banco.begin() as c:
                S.aprova(c, pdm, ids[1][0], ids[1][1], "beto")
            resultado["b"] = "ok"
        except ErroNegocio as e:
            resultado["b"] = e.codigo

    ta, tb = threading.Thread(target=analista_a), threading.Thread(target=analista_b)
    ta.start(); tb.start(); ta.join(10); tb.join(10)
    assert resultado["a"] == "ok" and resultado["b"] == "duplicidade_aprovada"
    with banco.begin() as c:
        assert c.execute(text("select count(*) from cadastro where estado='APROVADO'")).scalar() == 1


def test_segundo_cadastro_igual_a_um_aprovado_e_bloqueado_no_painel(banco, base_teste):
    with banco.begin() as c:
        a = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6211-2RS/C3")
        S.aprova(c, base_teste["pdm"], a["id"], a["versao"], "ana")
    with banco.begin() as c:
        b = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste, autor="beto"), ref="6211-2RS/C3", autor="beto")
    assert "DUPLICIDADE_CADASTRO_APROVADO" in bloqueios(b)


# ------------------------------------------------------------------ outras saídas
def test_usar_existente_ativo_e_bloqueado(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6205-2RS/C3")
    with banco.begin() as c:
        v = S.usa_existente(c, base_teste["pdm"], cad["id"], "ana", "90000001")
    assert v["estado"] == "JA_EXISTE" and v["usar_codigo"] == "90000001"
    with banco.begin() as c:
        c2 = novo_rolamento(c, base_teste)
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:
        S.usa_existente(c, base_teste["pdm"], c2["id"], "ana", "90000004")  # BLOQUEADO
    assert e.value.codigo == "codigo_inativo"


def test_reativacao_de_codigo_bloqueado_passa_por_segundo_analista(banco, base_teste, tmp_path):
    with banco.begin() as c:
        cad = novo_rolamento(c, base_teste)
    with pytest.raises(ErroNegocio):
        with banco.begin() as c:
            S.reativa(c, base_teste["pdm"], cad["id"], "ana", "90000004", "curto")
    with banco.begin() as c:
        v = S.reativa(c, base_teste["pdm"], cad["id"], "ana", "90000004", "o codigo foi bloqueado por engano em 2024")
    assert v["estado"] == "EM_REVISAO"
    with banco.begin() as c:
        v = S.decide_revisao(c, base_teste["pdm"], cad["id"], "bia", True, "confirmado com o almoxarifado")
    assert v["estado"] == "AGUARDANDO_REATIVACAO"
    con = ConectorArquivo(tmp_path / "saida", tmp_path / "entrada")
    with banco.begin() as c:
        assert envia_pendentes(c, con)["enviados"] == 1
    arq = json.loads((tmp_path / "saida" / f"REATIVACAO_{cad['id']}.json").read_text())
    assert arq["codigo"] == "90000004" and arq["tipo"] == "REATIVACAO"


def test_devolucao_lista_o_que_falta_e_envia_para_o_contato_da_area(banco, base_teste, monkeypatch):
    enviados = []
    monkeypatch.setattr("app.cadastro.notificacao.enviar", lambda d, a, b: enviados.append((d, a, b)) or "msg-1")
    with banco.begin() as c:
        c.execute(text("insert into area_contato (area, email) values ('PCM', 'pcm@serraazul.example')"))
        c.execute(text("insert into pedido (id, centro, area, canal, texto) values ('SC-T2', :c, 'PCM', 'EMAIL', 'PARAFUSO SEXTAVADO M12X50 ZINCADO')"), {"c": CENTRO})
        v = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", pedido_id="SC-T2")
        v = S.atualiza(c, base_teste["pdm"], v["id"], v["versao"], "ana", classe={"id_pdm": "PDM001"})
    with banco.begin() as c:
        d = S.devolve(c, base_teste["pdm"], v["id"], "ana")
    assert d["estado"] == "AGUARDANDO_SOLICITANTE" and d["devolucao"]["enviada"]
    assert enviados[0][0] == "pcm@serraazul.example"
    assert "CLASSE RESISTENCIA" in enviados[0][2] and "NORMA" in enviados[0][2] and "BITOLA" not in enviados[0][2]
    with banco.begin() as c:
        pid = c.execute(text("select id from cadastro_pergunta")).scalar()
        r = S.responde(c, base_teste["pdm"], v["id"], "ana", pid, "e 8.8, zincado branco, DIN 933")
        assert r["estado"] == "RASCUNHO"
        assert c.execute(text("select estado from pedido where id='SC-T2'")).scalar() == "EM_ANDAMENTO"


def test_devolucao_sem_contato_nao_finge_que_enviou(banco, base_teste, monkeypatch):
    monkeypatch.setattr("app.cadastro.notificacao.enviar", lambda *a: pytest.fail("nao devia enviar"))
    with banco.begin() as c:
        c.execute(text("insert into pedido (id, centro, area, canal, texto) values ('SC-T3', :c, 'AREA SEM CONTATO', 'EMAIL', 'PARAFUSO SEXTAVADO M12X50')"), {"c": CENTRO})
        v = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", pedido_id="SC-T3")
        v = S.atualiza(c, base_teste["pdm"], v["id"], v["versao"], "ana", classe={"id_pdm": "PDM001"})
        d = S.devolve(c, base_teste["pdm"], v["id"], "ana")
    assert d["devolucao"]["enviada"] is False and "nenhum contato" in d["devolucao"]["aviso"]


def test_fora_do_pdm_e_proposta_de_classe(banco, base_teste):
    with banco.begin() as c:
        c.execute(text("insert into pedido (id, centro, area, canal, texto) values ('SC-T4', :c, 'PCM', 'PORTAL', 'Cadeira de escritorio giratoria')"), {"c": CENTRO})
        v = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", pedido_id="SC-T4")
    assert v["classe"] is None and "CLASSE_NAO_DEFINIDA" in bloqueios(v)
    with banco.begin() as c:
        r = S.recusa(c, base_teste["pdm"], v["id"], "ana", "mobiliario nao e material de manutencao")
    assert r["estado"] == "FORA_DO_PDM"
    with banco.begin() as c:
        v2 = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", centro=CENTRO)
        S.propoe_classe(c, base_teste["pdm"], v2["id"], "ana", {"nome_sugerido": "CHAVE DE FENDA", "justificativa": "ferramenta sem classe no PDM"})
        assert c.execute(text("select estado from cadastro where id = cast(:i as uuid)"), {"i": v2["id"]}).scalar() == "AGUARDANDO_CLASSE"
        assert c.execute(text("select count(*) from pdm_proposta where estado='ABERTA'")).scalar() == 1


# ------------------------------------------------------------------ rastro e ERP
def test_toda_mudanca_deixa_rastro_imutavel(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6212-2RS/C3")
        S.aprova(c, base_teste["pdm"], cad["id"], cad["versao"], "ana")
        h = auditoria.historico(c, "cadastro", cad["id"])
    assert [e["acao"] for e in h] == ["criou", "atualizou", "aprovou"]
    assert h[-1]["autor"] == "ana" and h[-1]["depois"]["estado"] == "APROVADO"
    with pytest.raises(Exception, match="apenas inser"), banco.begin() as c:
        c.execute(text("delete from evento_auditoria"))


def test_aprovado_nao_pode_mais_ser_alterado(banco, base_teste):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6213-2RS/C3")
        v = S.aprova(c, base_teste["pdm"], cad["id"], cad["versao"], "ana")
    with pytest.raises(ErroNegocio) as e, banco.begin() as c:
        S.atualiza(c, base_teste["pdm"], cad["id"], v["versao"], "ana", valores={"FOLGA": "NORMAL"})
    assert e.value.codigo == "nao_editavel"


def test_erp_envia_idempotente_e_recebe_o_codigo(banco, base_teste, tmp_path):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6214-2RS/C3")
        S.aprova(c, base_teste["pdm"], cad["id"], cad["versao"], "ana")
    con = ConectorArquivo(tmp_path / "saida", tmp_path / "entrada")
    with banco.begin() as c:
        assert envia_pendentes(c, con) == {"enviados": 1, "erros": 0}
        assert envia_pendentes(c, con) == {"enviados": 0, "erros": 0}  # nada pendente: nao reenvia
    item = json.loads((tmp_path / "saida" / f"ITEM_{cad['id']}.json").read_text())
    assert item["descricao_longa"].startswith(ROL) and item["ncm"] == "8482.10.10" and item["unidade"] == "PC"
    (tmp_path / "entrada").mkdir()
    (tmp_path / "entrada" / "RET_1.json").write_text(json.dumps({"cadastro_id": cad["id"], "codigo": "12345678", "status": "OK"}))
    with banco.begin() as c:
        assert processa_retornos(c, con)["processados"] == 1
        row = c.execute(text("select estado, codigo_erp from cadastro")).one()
        assert c.execute(text("select estado from erp_envio")).scalar() == "CONCLUIDO"
    assert tuple(row) == ("CADASTRADO", "12345678")
    assert not (tmp_path / "entrada" / "RET_1.json").exists()  # processado: nao le duas vezes


def test_erp_com_erro_fica_visivel_e_pode_reenviar(banco, base_teste, tmp_path):
    with banco.begin() as c:
        cad = preenche_rolamento(c, base_teste, novo_rolamento(c, base_teste), ref="6215-2RS/C3")
        S.aprova(c, base_teste["pdm"], cad["id"], cad["versao"], "ana")
    con = ConectorArquivo(tmp_path / "saida", tmp_path / "entrada")
    with banco.begin() as c:
        envia_pendentes(c, con)
    (tmp_path / "entrada").mkdir()
    (tmp_path / "entrada" / "RET_2.json").write_text(json.dumps({"cadastro_id": cad["id"], "status": "ERRO", "mensagem": "NCM rejeitado"}))
    with banco.begin() as c:
        assert processa_retornos(c, con)["erros"] == 1
        row = c.execute(text("select estado, motivo from cadastro")).one()
    assert tuple(row) == ("ERRO_ERP", "NCM rejeitado")


# ------------------------------------------------------------------ tabela técnica local
def test_dimensoes_do_rolamento_vem_da_tabela_com_a_fonte(banco, base_teste):
    with banco.begin() as c:
        v = preenche_rolamento(c, base_teste, S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", id_pdm="PDM020", nome=ROL, centro=CENTRO),
                               ref="SKF 6206-2RSH/C3")
    campo = {x["atributo"]: x for x in v["campos"]}
    # a pessoa digitou o diametro interno (35 mm no helper): nao e sobrescrito pela tabela
    assert campo["DIAMETRO INTERNO"]["origem"] == "DIGITADO" and campo["DIAMETRO INTERNO"]["valor"] == "35MM"
    assert (campo["DIAMETRO EXTERNO"]["valor"], campo["DIAMETRO EXTERNO"]["origem"]) == ("62MM", "TABELA_LOCAL")
    assert campo["LARGURA"]["valor"] == "16MM" and "ISO 15" in campo["LARGURA"]["trecho"]
    assert "6206" in campo["LARGURA"]["trecho"]


def test_trocar_a_referencia_recalcula_so_o_que_veio_da_tabela(banco, base_teste):
    with banco.begin() as c:
        cad = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", id_pdm="PDM020", nome=ROL, centro=CENTRO)
        v = S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", valores={"REFERENCIA": "6205-2RS/C3"})
    campo = {x["atributo"]: x["valor"] for x in v["campos"]}
    assert (campo["DIAMETRO INTERNO"], campo["DIAMETRO EXTERNO"], campo["LARGURA"]) == ("25MM", "52MM", "15MM")  # exemplo do PDM
    with banco.begin() as c:
        v = S.atualiza(c, base_teste["pdm"], cad["id"], v["versao"], "ana", valores={"LARGURA": "99MM"})
        v = S.atualiza(c, base_teste["pdm"], cad["id"], v["versao"], "ana", valores={"REFERENCIA": "6310-ZZ/C3"})
    campo = {x["atributo"]: (x["valor"], x["origem"]) for x in v["campos"]}
    assert campo["DIAMETRO INTERNO"] == ("50MM", "TABELA_LOCAL") and campo["DIAMETRO EXTERNO"] == ("110MM", "TABELA_LOCAL")
    assert campo["LARGURA"] == ("99MM", "DIGITADO")  # o que a pessoa digitou fica


def test_serie_desconhecida_nao_inventa_dimensao(banco, base_teste):
    with banco.begin() as c:
        cad = S.cria(c, base_teste["pdm"], base_teste["indice"], "ana", id_pdm="PDM020", nome=ROL, centro=CENTRO)
        v = S.atualiza(c, base_teste["pdm"], cad["id"], cad["versao"], "ana", valores={"REFERENCIA": "6205-2RS/C3"})
        v = S.atualiza(c, base_teste["pdm"], cad["id"], v["versao"], "ana", valores={"REFERENCIA": "6999-2RS/C3"})
    campo = {x["atributo"]: x["valor"] for x in v["campos"]}
    assert campo["DIAMETRO INTERNO"] is None and campo["LARGURA"] is None  # os da 6205 deixaram de valer
