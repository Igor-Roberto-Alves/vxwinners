"""Contrato HTTP de ponta a ponta, com permissões e erros em application/problem+json."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api import deps
from app.main import cria_app
from app.ncm import tabela

CENTRO = "1100 - MINA SERRA AZUL"
ANA = {"X-Usuario": "ana", "X-Papel": "analista"}
BIA = {"X-Usuario": "bia", "X-Papel": "revisor"}
LEO = {"X-Usuario": "leo", "X-Papel": "leitor"}
ADM = {"X-Usuario": "adm", "X-Papel": "admin_pdm"}


@pytest.fixture(scope="module")
def cliente(banco, base_teste, tmp_path_factory):
    codigos = ["7318.15.00", "8482.10.10", "8421.23.00", "4016.93.00", "8481.80.95"]
    arq = tmp_path_factory.mktemp("ncm") / "ncm.json"
    arq.write_text(json.dumps({"Ato": "t", "Data_Ultima_Atualizacao_NCM": "t", "Nomenclaturas": [
        {"Codigo": c, "Descricao": "x", "Data_Inicio": "01/01/2020", "Data_Fim": "31/12/9999"} for c in codigos]}))
    with banco.begin() as c:
        tabela.importa(c, arq)
    app = cria_app(verifica_migracoes=False, carrega_modelos=False)  # banco e modelos de teste são montados aqui

    def conexao_teste():
        with banco.begin() as conn:
            yield conn

    app.dependency_overrides[deps.conexao] = conexao_teste
    deps.limpa_contexto()
    with TestClient(app) as c:
        yield c
    deps.limpa_contexto()


@pytest.fixture(autouse=True)
def limpa(banco):
    with banco.begin() as c:
        for t in ("erp_envio", "cadastro_pergunta", "cadastro_excecao", "pdm_proposta", "cadastro", "pedido", "area_contato"):
            c.execute(text(f"delete from {t}"))


def problema(r, status, codigo):
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["title"] == codigo, r.json()


def test_saude_e_openapi(cliente):
    assert cliente.get("/saude").json()["status"] == "ok"
    spec = cliente.get("/openapi.json").json()
    assert "/api/v1/cadastros/{cid}/aprovar" in spec["paths"] and "CadastroView" in spec["components"]["schemas"]


def test_sem_identidade_e_sem_permissao(cliente):
    problema(cliente.get("/api/v1/pdm/nomes?q=paraf"), 401, "nao_autenticado")
    problema(cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020"}, headers=LEO), 403, "sem_permissao")
    problema(cliente.get("/api/v1/pdm/nomes?q=x", headers={"X-Usuario": "x", "X-Papel": "chefe"}), 400, "erro_http")
    # analista nao revisa excecao; so revisor
    r = cliente.post("/api/v1/cadastros/00000000-0000-0000-0000-000000000000/revisao", json={"aprovar": True}, headers=ANA)
    problema(r, 403, "sem_permissao")
    problema(cliente.post("/api/v1/pdm/versoes/recarregar", headers=ANA), 403, "sem_permissao")


def test_autocomplete_de_substantivo(cliente):
    r = cliente.get("/api/v1/pdm/nomes", params={"q": "paraf sext"}, headers=LEO).json()
    assert r["itens"][0]["id_pdm"] == "PDM001" and not r["fora_do_pdm"]
    luva = cliente.get("/api/v1/pdm/nomes", params={"q": "luva"}, headers=LEO).json()
    assert luva["ambiguo"] and {i["id_pdm"] for i in luva["itens"]} >= {"PDM050", "PDM070", "PDM110"}
    fora = cliente.get("/api/v1/pdm/nomes", params={"q": "cadeira giratoria"}, headers=LEO).json()
    assert fora["itens"] == [] and fora["fora_do_pdm"]


def test_schema_da_classe(cliente):
    c = cliente.get("/api/v1/pdm/classes/PDM040", headers=LEO).json()
    assert c["criterio_identidade"] == "ESPECIFICACAO" and c["atributos"][0]["nome"] == "DIAMETRO NOMINAL"
    problema(cliente.get("/api/v1/pdm/classes/PDM999", headers=LEO), 404, "nao_encontrado")


def test_fluxo_completo_busca_preenche_aprova(cliente):
    r = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA)
    assert r.status_code == 201
    v = r.json()
    assert v["estado"] == "RASCUNHO" and v["classe"]["confirmada"]
    # sugestoes: nada vem preenchido; part number nao tem opcoes
    s = cliente.get(f"/api/v1/cadastros/{v['id']}/sugestoes/VEDACAO", headers=ANA).json()
    assert s["opcoes"] and s["valores_permitidos"] == ["ABERTO", "BORRACHA AMBOS LADOS", "METALICA AMBOS LADOS"]
    r2 = cliente.get(f"/api/v1/cadastros/{v['id']}/sugestoes/REFERENCIA", headers=ANA).json()
    assert r2["opcoes"] == [] and r2["sem_opcoes_motivo"]
    # escolhe a opcao (origem OPCAO) e digita o resto
    opcao = s["opcoes"][0]["valor"]
    v = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": v["versao"], "valores": {
        "VEDACAO": {"valor": opcao, "origem": "OPCAO"}, "REFERENCIA": "SKF 6307-2RSH/C3", "FOLGA": "C3"}}).json()
    campo = {c["atributo"]: c for c in v["campos"]}
    assert campo["VEDACAO"]["origem"] == "OPCAO" and campo["REFERENCIA"]["valor"] == "6307-2RS/C3"
    assert v["pronto_para_aprovar"] and v["duplicidade"]["candidatos"] == []
    ok = cliente.post(f"/api/v1/cadastros/{v['id']}/aprovar", json={"versao": v["versao"]}, headers=ANA)
    assert ok.status_code == 200 and ok.json()["estado"] == "APROVADO"
    h = cliente.get(f"/api/v1/cadastros/{v['id']}/historico", headers=LEO).json()
    assert [e["acao"] for e in h] == ["criou", "atualizou", "aprovou"]
    assert cliente.get("/api/v1/erp/envios", headers=ANA).json()[0]["estado"] == "PENDENTE"


def test_erros_em_problem_json(cliente):
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA).json()
    r = cliente.post(f"/api/v1/cadastros/{v['id']}/aprovar", json={"versao": v["versao"]}, headers=ANA)
    problema(r, 422, "bloqueios")
    assert {b["atributo"] for b in r.json()["bloqueios"] if b["codigo"] == "OBRIGATORIO_VAZIO"} == {"REFERENCIA", "VEDACAO", "FOLGA"}
    stale = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": 999, "valores": {"FOLGA": "C3"}})
    problema(stale, 409, "versao_desatualizada")
    assert stale.json()["versao_atual"] == v["versao"]
    problema(cliente.get("/api/v1/cadastros/nao-e-uuid", headers=LEO), 404, "nao_encontrado")
    invalido = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"valores": {"FOLGA": "C3"}})  # sem versao
    problema(invalido, 422, "requisicao_invalida")


def test_excecao_e_segundo_analista_pela_api(cliente):
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA).json()
    v = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": v["versao"], "valores": {
        "REFERENCIA": "6205-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}}).json()
    assert v["duplicidade"]["candidatos"][0]["nivel"] == "IGUAL"
    exc = v["excecoes_previstas"][0]
    assert exc["id"] == "DUPLICIDADE_IGUAL|" and exc["exige_revisor"]
    problema(cliente.post(f"/api/v1/cadastros/{v['id']}/aprovar", json={"versao": v["versao"]}, headers=ANA), 422, "justificativa_obrigatoria")
    em_rev = cliente.post(f"/api/v1/cadastros/{v['id']}/aprovar", headers=ANA, json={
        "versao": v["versao"], "justificativas": {exc["id"]: "item do outro centro, estoque separado por contrato"}}).json()
    assert em_rev["estado"] == "EM_REVISAO"
    fila = cliente.get("/api/v1/excecoes", headers=BIA).json()
    assert fila[0]["tipo"] == "DUPLICIDADE_IGUAL" and fila[0]["autor"] == "ana"
    problema(cliente.get("/api/v1/excecoes", headers=ANA), 403, "sem_permissao")
    problema(cliente.post(f"/api/v1/cadastros/{v['id']}/revisao", json={"aprovar": True}, headers={"X-Usuario": "ana", "X-Papel": "revisor"}),
             403, "revisor_deve_ser_outra_pessoa")
    final = cliente.post(f"/api/v1/cadastros/{v['id']}/revisao", json={"aprovar": True, "comentario": "ok"}, headers=BIA).json()
    assert final["estado"] == "APROVADO"


def test_pedidos_fila_assumir_e_devolucao(cliente, banco):
    with banco.begin() as c:
        c.execute(text("""insert into pedido (id, data_solicitacao, centro, area, canal, urgencia, texto) values
            ('SC-A', '2026-01-02', :c, 'PCM', 'EMAIL', 'NORMAL', 'PARAFUSO SEXTAVADO M12X50 ZINCADO'),
            ('SC-B', '2026-01-02', :c, 'PCM', 'PORTAL', 'EMERGENCIAL', 'retentor 75 mm 100 mm 13 mm ba nbr pra bomba')"""), {"c": CENTRO})
    fila = cliente.get("/api/v1/pedidos", headers=LEO).json()
    assert fila["total"] == 2 and fila["itens"][0]["id"] == "SC-B"  # emergencial primeiro
    assert cliente.get("/api/v1/pedidos", params={"q": "parafuso"}, headers=LEO).json()["total"] == 1
    v = cliente.post("/api/v1/pedidos/SC-A/assumir", headers=ANA).json()
    assert v["pedido_id"] == "SC-A" and v["proposta_de_classe"]["id_pdm"] == "PDM001" and not v["classe"]["confirmada"]
    problema(cliente.post("/api/v1/pedidos/SC-A/assumir", headers={"X-Usuario": "beto", "X-Papel": "analista"}), 409, "pedido_em_andamento")
    v = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": v["versao"], "classe": {"id_pdm": "PDM001"}}).json()
    d = cliente.post(f"/api/v1/cadastros/{v['id']}/devolver", json={}, headers=ANA).json()
    assert d["estado"] == "AGUARDANDO_SOLICITANTE" and "CLASSE RESISTENCIA" in d["devolucao"]["pergunta"]
    assert d["devolucao"]["enviada"] is False  # sem contato da area cadastrado: nao finge envio
    assert cliente.get("/api/v1/pedidos", params={"estado": "DEVOLVIDO"}, headers=LEO).json()["total"] == 1


def test_importacao_de_pedidos_e_idempotente(cliente):
    corpo = {"pedidos": [{"id": "SC-X1", "texto": "mangueira hidraulica 3/4 215bar", "area": "PCM"}]}
    assert cliente.post("/api/v1/importacoes/pedidos", json=corpo, headers=ANA).json() == {"recebidos": 1, "novos": 1, "ignorados": 0}
    assert cliente.post("/api/v1/importacoes/pedidos", json=corpo, headers=ANA).json()["novos"] == 0


def test_llm_indisponivel_nao_trava_o_cadastro(cliente, monkeypatch):
    from app.llm import extrator
    monkeypatch.setattr(extrator, "chama", lambda *a, **k: extrator.Resposta(None, "modelo-x", erro="ThrottlingError"))
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM001", "centro": CENTRO, "texto": "parafuso m12x50 8.8"}, headers=ANA).json()
    r = cliente.post(f"/api/v1/cadastros/{v['id']}/ler-pedido", headers=ANA)
    assert r.status_code == 200 and r.json()["llm"]["estado"] == "indisponivel" and r.json()["estado"] == "RASCUNHO"


def test_leitura_por_llm_so_preenche_vazios_e_valida_a_saida(cliente, monkeypatch):
    from app.llm import extrator
    saida = {"classe": "PDM001", "nome": "PARAFUSO SEXTAVADO", "atributos": [
        {"atributo": "CLASSE RESISTENCIA", "valor": "8.8", "trecho": "8.8"},
        {"atributo": "ACABAMENTO", "valor": "COR DE ROSA", "trecho": "rosa"},      # fora da lista: nao entra como valido
        {"atributo": "NORMA", "valor": "DIN 933", "trecho": "din 933"}]}           # trecho que nao existe no texto
    monkeypatch.setattr(extrator, "chama", lambda *a, **k: extrator.Resposta(saida, "modelo-x", 100, 50, ms=10))
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM001", "centro": CENTRO, "texto": "parafuso sextavado 8.8 galvanizado"}, headers=ANA).json()
    v = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": v["versao"], "valores": {"MATERIAL": "ACO CARBONO"}}).json()
    r = cliente.post(f"/api/v1/cadastros/{v['id']}/ler-pedido", headers=ANA).json()
    campo = {c["atributo"]: c for c in r["campos"]}
    assert campo["CLASSE RESISTENCIA"]["valor"] == "8.8" and campo["CLASSE RESISTENCIA"]["origem"] == "PEDIDO_LLM"
    assert campo["MATERIAL"]["origem"] == "DIGITADO"           # o que a pessoa digitou nao e sobrescrito
    assert campo["ACABAMENTO"]["valor"] is None
    assert r["classe"]["confirmada"] and r["llm"]["estado"] == "ok"


def test_material_da_base_com_classe_e_atributos(cliente):
    r = cliente.get("/api/v1/materiais/90000001", headers=LEO).json()
    assert r["classificacao"]["id_pdm"] == "PDM020" and any(a["atributo"] == "FOLGA" for a in r["atributos"])
    problema(cliente.get("/api/v1/materiais/00000000", headers=LEO), 404, "nao_encontrado")


def test_pdm_recarregar_e_idempotente(cliente):
    r = cliente.post("/api/v1/pdm/versoes/recarregar", headers=ADM).json()
    assert r["nova"] is False and r["avisos"] == []


def test_api_recusa_subir_com_banco_desatualizado(banco, monkeypatch):
    """O banco de dev ficou sem a migracao 0003 e a falha apareceu no meio de uma requisicao: agora e na partida."""
    from app import main

    monkeypatch.setattr(main, "engine", lambda: banco)
    with banco.begin() as c:
        c.execute(text("update alembic_version set version_num = '0002'"))
    try:
        with pytest.raises(RuntimeError, match="migrar"):
            main.confere_migracoes()
    finally:
        with banco.begin() as c:
            c.execute(text("update alembic_version set version_num = '0004'"))
    main.confere_migracoes()  # no head: passa


def test_painel_de_desenvolvimento_e_servido_so_em_dev(cliente):
    r = cliente.get("/painel")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "versão isolada do cadastro" in r.text


# ------------------------------------------------------------------ integração com o serviço de sugestão do time
class ModelosFalsos:
    def pronto(self):
        return True

    def similares(self, texto):
        return [{"codigo": "90000002", "similaridade": 0.8}, {"codigo": "90000003", "similaridade": 0.3}]


def test_commit_acontece_antes_da_resposta(banco, base_teste):
    """Sem isto, o cliente ouve "criado" antes da gravação e a chamada seguinte recebe 404 (visto no navegador)."""
    ordem = []
    app = cria_app(verifica_migracoes=False, carrega_modelos=False)

    def conexao_que_anota():
        with banco.begin() as conn:
            yield conn
        ordem.append("commit")

    app.dependency_overrides[deps.conexao] = conexao_que_anota

    async def espia(scope, receive, send):
        async def envia(msg):
            if msg["type"] == "http.response.start":
                ordem.append("resposta")
            await send(msg)
        await app(scope, receive, envia)

    deps.limpa_contexto()
    with TestClient(espia) as c:
        r = c.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA)
    deps.limpa_contexto()
    assert r.status_code == 201 and ordem == ["commit", "resposta"]


def test_toda_rota_da_api_usa_a_conexao_que_grava_antes_de_responder():
    from app.api import rotas

    fonte = open(rotas.__file__, encoding="utf-8").read()
    assert "Depends(conexao" not in fonte  # usar deps.Conexao: com o padrão do FastAPI, a resposta sai antes do COMMIT


def test_navegador_confere_a_versao_do_frontend_antes_de_usar(cliente):
    for caminho in ("/", "/painel", "/frontend/cadastro.js", "/frontend/cadastro.css"):
        assert cliente.get(caminho).headers["cache-control"] == "no-cache", caminho
    assert "cache-control" not in cliente.get("/saude").headers


def test_frontend_do_time_e_servido_na_raiz_com_o_cadastro_real(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "frontend/cadastro.js" in r.text and "frontend/cadastro.css" in r.text
    assert 'src="/painel?embutido=1"' in r.text   # a tela de cadastro é o próprio painel
    assert "const PDM=" not in r.text and "SC-202600002" not in r.text.split('id="m-cadastro"')[0]  # nada de dado fixo nas telas reais
    js = cliente.get("/frontend/cadastro.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    assert cliente.get("/frontend/cadastro.css").status_code == 200
    antigo = cliente.get("/mockup", follow_redirects=False)
    assert antigo.status_code == 307 and antigo.headers["location"] == "/"


def _conta(banco):
    with banco.connect() as c:
        return tuple(c.execute(text(f"select count(*) from {t}")).scalar() for t in ("cadastro", "evento_auditoria"))


def test_busca_le_o_texto_compara_e_nao_grava_nada(cliente, banco):
    antes = _conta(banco)
    r = cliente.post("/api/v1/busca", headers=LEO, json={"texto": "parafuso sextavado m12x50 8.8 aco carbono zincado din 933"}).json()
    assert r["classe"]["id_pdm"] == "PDM001" and not r["classe"]["confirmada"]  # lida do texto: continua sendo proposta
    lido = {i["atributo"]: i["valor"] for i in r["interpretacao"]}
    assert lido["BITOLA"] == "M12" and lido["COMPRIMENTO"] == "50MM" and lido["CLASSE RESISTENCIA"] == "8.8"
    assert {c["codigo"] for c in r["duplicidade"]["candidatos"]} & {f"9000010{i}" for i in range(5)}
    assert _conta(banco) == antes


def test_busca_com_classe_escolhida_e_refino_da_pessoa(cliente):
    base = {"texto": "rolamento 6205 c3", "id_pdm": "PDM020", "nome": "ROLAMENTO RIGIDO ESFERAS"}
    r = cliente.post("/api/v1/busca", headers=LEO, json=base).json()
    assert r["classe"]["confirmada"] and {c["atributo"]: c["valor"] for c in r["campos"]}["FOLGA"] == "C3"
    ref = cliente.post("/api/v1/busca", headers=LEO, json={**base, "valores": {"FOLGA": "NORMAL", "ATRIBUTO INEXISTENTE": "x"}}).json()
    campo = {c["atributo"]: c for c in ref["campos"]}
    assert campo["FOLGA"]["valor"] == "NORMAL" and campo["FOLGA"]["origem"] == "DIGITADO"
    assert "FOLGA" not in {i["atributo"] for i in ref["interpretacao"]}  # o que a pessoa ajustou não é "lido do texto"


def test_busca_sem_classe_oferece_saidas_em_vez_de_falhar(cliente):
    fora = cliente.post("/api/v1/busca", headers=LEO, json={"texto": "cadeira giratoria"}).json()
    assert fora["classe"] is None and fora["fora_do_pdm"] and fora["campos"] == []
    assert fora["duplicidade"]["candidatos"] == []
    varias = cliente.post("/api/v1/busca", headers=LEO, json={"texto": "filtro"}).json()
    assert len({a["id_pdm"] for a in varias["alternativas"]}) >= 1 and not varias["fora_do_pdm"]
    problema(cliente.post("/api/v1/busca", headers=LEO, json={"texto": "x", "id_pdm": "PDM999"}), 422, "classe_invalida")
    assert cliente.post("/api/v1/busca", json={"texto": "x"}).status_code == 401


def test_usar_codigo_que_diverge_exige_justificativa(cliente):
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA).json()
    v = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": v["versao"], "valores": {
        "REFERENCIA": "6205-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}}).json()
    problema(cliente.post(f"/api/v1/cadastros/{v['id']}/usar-existente", json={"codigo": "90000003"}, headers=ANA), 422, "justificativa_obrigatoria")
    ok = cliente.post(f"/api/v1/cadastros/{v['id']}/usar-existente", headers=ANA,
                      json={"codigo": "90000003", "justificativa": "vedacao metalica aceita, confirmado com o PCM"})
    assert ok.status_code == 200 and ok.json()["estado"] == "JA_EXISTE" and "PCM" in ok.json()["motivo"]


def test_cadastro_em_revisao_nao_e_duplicata_de_si_mesmo(cliente):
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA).json()
    v = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": v["versao"], "valores": {
        "REFERENCIA": "6305-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}, "campos": {"ncm": "4016.93.00"}}).json()
    j = {e["id"]: "NCM confirmado pelo fiscal" for e in v["excecoes_previstas"]}
    r = cliente.post(f"/api/v1/cadastros/{v['id']}/aprovar", json={"versao": v["versao"], "justificativas": j}, headers=ANA).json()
    assert r["estado"] == "EM_REVISAO"
    visto = cliente.get(f"/api/v1/cadastros/{v['id']}", headers=ANA).json()
    assert not [c for c in visto["duplicidade"]["candidatos"] if c["origem"] == "cadastro"]
    assert "DUPLICIDADE_CADASTRO_APROVADO" not in [b["codigo"] for b in visto["bloqueios"]]
    # mas outro rascunho com a mesma chave continua vendo o primeiro
    w = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA).json()
    w = cliente.patch(f"/api/v1/cadastros/{w['id']}", headers=ANA, json={"versao": w["versao"], "valores": {
        "REFERENCIA": "6305-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}}).json()
    assert "DUPLICIDADE_CADASTRO_APROVADO" in [b["codigo"] for b in w["bloqueios"]]


def test_texto_colado_vira_rascunho_com_classe_so_proposta(cliente):
    v = cliente.post("/api/v1/cadastros", headers=ANA, json={"texto": "parafuso sextavado m12x50 8.8", "ler": True, "centro": CENTRO}).json()
    assert v["classe"]["id_pdm"] == "PDM001" and not v["classe"]["confirmada"]
    assert "CLASSE_NAO_CONFIRMADA" in [b["codigo"] for b in v["bloqueios"]]
    assert {c["atributo"]: c["valor"] for c in v["campos"]}["BITOLA"] == "M12"
    fora = cliente.post("/api/v1/cadastros", headers=ANA, json={"texto": "cadeira giratoria", "ler": True, "centro": CENTRO}).json()
    assert fora["classe"] is None and fora["texto_inicial"]


def test_usar_codigo_igual_nao_pede_justificativa(cliente):
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM020", "centro": CENTRO}, headers=ANA).json()
    v = cliente.patch(f"/api/v1/cadastros/{v['id']}", headers=ANA, json={"versao": v["versao"], "valores": {
        "REFERENCIA": "6205-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}}).json()
    r = cliente.post(f"/api/v1/cadastros/{v['id']}/usar-existente", json={"codigo": "90000001"}, headers=ANA)
    assert r.status_code == 200 and r.json()["usar_codigo"] == "90000001"


def test_resumo_pedido_e_perguntas_para_o_frontend(cliente):
    cliente.post("/api/v1/importacoes/pedidos", headers=ANA, json={"pedidos": [
        {"id": "SC-T1", "texto": "rolamento 6205", "area": "PCM", "urgencia": "ALTA", "conteudo_anexo": "FICHA TECNICA", "tipo_anexo": "ficha"}]})
    r = cliente.get("/api/v1/resumo", headers=LEO).json()
    assert r["pedidos"]["NOVO"] == 1 and r["excecoes_pendentes"] == 0
    d = cliente.get("/api/v1/pedidos/SC-T1", headers=LEO).json()
    assert d["texto"] == "rolamento 6205" and d["conteudo_anexo"] == "FICHA TECNICA" and d["tem_anexo"]
    problema(cliente.get("/api/v1/pedidos/SC-X", headers=LEO), 404, "pedido_nao_encontrado")
    v = cliente.post("/api/v1/pedidos/SC-T1/assumir", headers=ANA).json()
    assert v["texto_inicial"]
    v = cliente.post(f"/api/v1/cadastros/{v['id']}/devolver", json={"pergunta": "Qual a folga?"}, headers=ANA).json()
    p = cliente.get(f"/api/v1/cadastros/{v['id']}/perguntas", headers=LEO).json()
    assert [x["pergunta"] for x in p] == ["Qual a folga?"] and p[0]["resposta"] is None
    assert cliente.get("/api/v1/resumo", headers=LEO).json()["pedidos"]["DEVOLVIDO"] == 1
    v = cliente.post(f"/api/v1/cadastros/{v['id']}/responder", json={"pergunta_id": p[0]["id"], "resposta": "C3"}, headers=ANA).json()
    assert v["estado"] == "RASCUNHO"


def test_sem_modelos_o_contrato_do_servico_responde_503_e_o_cadastro_segue(cliente):
    from app.sugestoes import modelos

    assert not modelos.pronto()
    problema(cliente.post("/sugestao/sugerir", json={"descricao": "parafuso"}), 503, "modelos_indisponiveis")
    assert cliente.get("/sugestao/saude").json()["ok"] is False
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM001", "centro": CENTRO, "texto": "parafuso"}, headers=ANA).json()
    r = cliente.get(f"/api/v1/cadastros/{v['id']}/sugestoes-modelo", headers=ANA).json()
    assert r["estado"] == "indisponivel"
    assert cliente.post("/sugestao/sugerir", json={"descricao": "   "}).status_code == 422


def test_sugestoes_de_modelo_so_propoem_nao_aplicam(cliente, monkeypatch):
    from app.sugestoes import modelos

    resposta = {"grupo": {"sugestoes": [{"valor": "FIX01", "conf": 0.9}]},
                "ncm": {"sugestoes": [{"valor": "73181500", "valor_formatado": "7318.15.00", "conf": 0.91}]},
                "fabricante": {"origem": "lexico", "sugestoes": [{"valor": "SKF", "conf": 0.99}]},
                "referencia": {"valor": "ABC123", "conf": 0.85, "origem": "extracao"}, "similares": []}
    monkeypatch.setattr(modelos, "pronto", lambda: True)
    monkeypatch.setattr(modelos, "sugerir", lambda *a, **k: resposta)
    monkeypatch.setattr(modelos, "similares", lambda *a, **k: [])
    v = cliente.post("/api/v1/cadastros", json={"id_pdm": "PDM001", "centro": CENTRO, "texto": "parafuso skf abc123"}, headers=ANA).json()
    r = cliente.get(f"/api/v1/cadastros/{v['id']}/sugestoes-modelo", headers=ANA).json()
    assert r["estado"] == "ok" and r["ncm"][0]["valor_formatado"] == "7318.15.00" and r["referencia"]["valor"] == "ABC123"
    depois = cliente.get(f"/api/v1/cadastros/{v['id']}", headers=ANA).json()
    assert depois["fabricante"] is None and depois["fiscal"]["ncm"]["personalizado"] is False  # nada foi aplicado


def test_vizinhos_de_texto_entram_como_parecido_e_nunca_como_igual(banco, base_teste):
    from app.identidade import candidatos

    pdm = base_teste["pdm"]
    with banco.connect() as c:
        r = candidatos.busca(c, pdm, "PDM020", "ROLAMENTO RIGIDO ESFERAS", {"REFERENCIA": "6307-2RS/C3", "VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"})
        r = candidatos.acrescenta_vizinhos(c, r, [{"codigo": "90000002", "similaridade": 0.8}, {"codigo": "90000003", "similaridade": 0.3}])
    assert [(x.codigo, x.nivel) for x in r.candidatos] == [("90000002", "PARECIDO")]  # 0,3 fica abaixo do corte
    assert "80%" in r.candidatos[0].motivo


def test_preenchimento_entra_como_sugestao_e_nao_mexe_na_identidade(banco, base_teste):
    from sqlalchemy import text as t

    from app.estruturacao import preenchimento

    with banco.begin() as c:
        c.execute(t("delete from material_sugestao"))
        antes = c.execute(t("select count(*) from material_identidade where completa")).scalar()
        r = preenchimento.importa(c)  # so ha codigos de teste no banco: os demais sao ignorados
        depois = c.execute(t("select count(*) from material_identidade where completa")).scalar()
    assert antes == depois and sum(r.values()) == 0
