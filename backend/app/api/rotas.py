"""Rotas da API v1 (docs/06-plano-modo-cadastro.md, seção 12)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection, text

from .. import auditoria
from ..cadastro import servico as S
from ..cadastro.modelo import ErroNegocio
from ..classes.resolver import IndiceClasses
from ..config import settings
from ..leitura import llm as leitura_llm
from ..pdm import repositorio
from ..pdm.modelo import Pdm
from ..sugestoes import ranking
from . import esquemas as E
from .deps import Conexao, Principal, contexto, exige, limpa_contexto

router = APIRouter(prefix="/api/v1")
Ctx = tuple[Pdm, IndiceClasses]


# ================================================================== visão geral
@router.get("/resumo", response_model=E.ResumoView, tags=["cadastros"], summary="Contagens por estado para filas e indicadores")
def resumo(conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    conta = lambda t: {e: n for e, n in conn.execute(text(f"select estado, count(*) from {t} group by 1"))}  # noqa: E731
    cadastros = conta("cadastro")
    return E.ResumoView(pedidos=conta("pedido"), cadastros=cadastros, excecoes_pendentes=cadastros.get("EM_REVISAO", 0))


@router.post("/busca", response_model=E.BuscaView, tags=["busca"],
             summary="Lê o texto e compara com a base antes de existir rascunho. Não grava nada")
def busca(corpo: E.Busca, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), _: Principal = Depends(exige("leitor"))):
    return S.busca_material(conn, ctx[0], ctx[1], corpo.texto, id_pdm=corpo.id_pdm, nome=corpo.nome, valores=corpo.valores)


# ================================================================== PDM
@router.get("/pdm/nomes", response_model=E.NomesView, tags=["pdm"], summary="Autocomplete do substantivo (nome do material)")
def nomes(q: str = Query("", max_length=200), grupo: str | None = None, limite: int = Query(5, ge=1, le=20),
          ctx: Ctx = Depends(contexto), _: Principal = Depends(exige("leitor"))):
    _, indice = ctx
    itens = indice.buscar(q, grupo=grupo, limite=limite)
    return E.NomesView(consulta=q, ambiguo=any(i.ambiguo for i in itens),
                       itens=[E.SugestaoClasse(nome=i.nome, id_pdm=i.id_pdm, grupo=i.grupo, grupo_descricao=i.grupo_descricao,
                                               pontos=i.pontos, resto=list(i.resto)) for i in itens],
                       fora_do_pdm=not itens and len(q.strip()) >= 3)


@router.get("/pdm/classes/{id_pdm}", response_model=E.ClassePdmView, tags=["pdm"], summary="Schema de uma classe")
def classe(id_pdm: str, ctx: Ctx = Depends(contexto), _: Principal = Depends(exige("leitor"))):
    c = ctx[0].classes.get(id_pdm)
    if not c:
        raise ErroNegocio("nao_encontrado", f"classe {id_pdm} não existe", 404)
    return E.ClassePdmView(
        id_pdm=c.id_pdm, nomes=list(c.nomes), grupo=c.grupo, unidade_padrao=c.unidade, criterio_identidade=c.criterio,
        atributos=[E.AtributoView(nome=a.nome, ordem=a.ordem, obrigatorio=a.obrigatorio,
                                  condicao=None if a.quando.lower() == "sempre" else a.quando, tipo=a.tipo, formato=a.formato,
                                  valores_permitidos=list(a.valores)) for a in c.atributos])


@router.post("/pdm/versoes/recarregar", tags=["pdm"], summary="Publica o PDM da planilha configurada como nova versão")
def recarrega_pdm(conn: Connection = Conexao, p: Principal = Depends(exige("admin_pdm"))):
    antes = repositorio.versao_ativa_id(conn)
    versao = repositorio.publica(conn, settings().pdm_xlsx)
    limpa_contexto()
    pdm = repositorio.carrega_versao(conn, versao)
    auditoria.registra(conn, p.usuario, "pdm", str(versao), "publicou", {"versao": antes}, {"versao": versao})
    return {"versao": versao, "nova": versao != antes, "avisos": pdm.avisos()}


@router.get("/pdm/propostas", tags=["pdm"], summary="Propostas de classe nova ou valor novo")
def propostas(estado: str = "ABERTA", conn: Connection = Conexao, _: Principal = Depends(exige("admin_pdm"))):
    rows = conn.execute(text("select id, tipo, cadastro_id::text, descricao, estado, autor, criada_em from pdm_proposta where estado = :e order by id"),
                        {"e": estado}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/pdm/propostas/{pid}/decidir", tags=["pdm"])
def decide_proposta(pid: int, corpo: E.DecisaoProposta, conn: Connection = Conexao, p: Principal = Depends(exige("admin_pdm"))):
    n = conn.execute(text("update pdm_proposta set estado = :e, decisao = :d where id = :i and estado = 'ABERTA'"),
                     {"e": "ACEITA" if corpo.aceita else "REJEITADA", "d": corpo.comentario, "i": pid}).rowcount
    if not n:
        raise ErroNegocio("nao_encontrado", "proposta inexistente ou já decidida", 404)
    auditoria.registra(conn, p.usuario, "pdm_proposta", str(pid), "decidiu", None, corpo.model_dump())
    return {"id": pid, "estado": "ACEITA" if corpo.aceita else "REJEITADA"}


# ================================================================== cadastros
@router.post("/cadastros", response_model=E.CadastroView, status_code=201, tags=["cadastros"], summary="Cria um rascunho")
def cria(corpo: E.NovoCadastro, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.cria(conn, ctx[0], ctx[1], p.usuario, id_pdm=corpo.id_pdm, nome=corpo.nome, texto=corpo.texto,
                  centro=corpo.centro, pedido_id=corpo.pedido_id)


@router.get("/cadastros", tags=["cadastros"], summary="Lista de cadastros")
def lista(estado: str | None = None, analista: str | None = None, pedido_id: str | None = None,
          limite: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
          conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    filtros, par = ["true"], {"l": limite, "o": offset}
    for col, val in (("estado", estado), ("analista", analista), ("pedido_id", pedido_id)):
        if val:
            filtros.append(f"{col} = :{col}")
            par[col] = val
    where = " and ".join(filtros)
    total = conn.execute(text(f"select count(*) from cadastro where {where}"), par).scalar()
    rows = conn.execute(text(f"""select id::text, estado, id_pdm, nome, centro, analista, pedido_id, descricao_curta, codigo_erp,
        usar_codigo, atualizado_em from cadastro where {where} order by atualizado_em desc limit :l offset :o"""), par).mappings().all()
    return {"total": total, "itens": [dict(r) for r in rows]}


@router.get("/cadastros/{cid}", response_model=E.CadastroView, tags=["cadastros"])
def obtem(cid: str, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), _: Principal = Depends(exige("leitor"))):
    return S.obtem(conn, ctx[0], cid)


@router.patch("/cadastros/{cid}", response_model=E.CadastroView, tags=["cadastros"],
              summary="Altera classe, atributos ou campos; devolve o estado recalculado")
def atualiza(cid: str, corpo: E.Edicao, conn: Connection = Conexao, ctx: Ctx = Depends(contexto),
             p: Principal = Depends(exige("analista"))):
    return S.atualiza(conn, ctx[0], cid, corpo.versao, p.usuario, classe=corpo.classe, valores=corpo.valores, campos=corpo.campos)


@router.post("/cadastros/{cid}/interpretar", response_model=E.CadastroView, tags=["cadastros"],
             summary="Texto extra (M12X50 galvanizado 8.8) preenche, por regra, atributos ainda vazios")
def interpreta(cid: str, corpo: E.Interpretar, conn: Connection = Conexao, ctx: Ctx = Depends(contexto),
               p: Principal = Depends(exige("analista"))):
    return S.interpretar(conn, ctx[0], cid, corpo.versao, p.usuario, corpo.texto)


@router.post("/cadastros/{cid}/ler-pedido", response_model=E.CadastroView, tags=["cadastros"],
             summary="Complementa a leitura do pedido com LLM (só onde está vazio; nunca confirma a classe)")
def ler_pedido(cid: str, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    pdm, _ = ctx
    cad = S._linha(conn, cid)
    if not settings().llm_habilitado:
        out = S.obtem(conn, pdm, cid)
        out["llm"] = {"estado": "desabilitado"}
        return out
    texto = cad["texto_inicial"] or ""
    if not texto.strip():
        raise ErroNegocio("sem_texto", "este rascunho não tem texto de pedido para ler", 422)
    from ..estruturacao.modelo import Extracao
    base = Extracao(id_pdm=cad["id_pdm"], nome=cad["nome"], confianca_classe=1.0, metodo="REGRA")
    final, resp = leitura_llm.le_com_llm(pdm, texto, base)
    conn.execute(text("""insert into llm_chamada (finalidade, modelo, prompt_versao, entrada_hash, tokens_entrada, tokens_cache, tokens_saida, ms, resultado, erro)
        values ('leitura_pedido', :m, 'extracao-v1', :h, :ti, :tc, :to, :ms, :r, :e)"""),
                 {"m": resp.modelo, "h": __import__("hashlib").sha256(texto.encode()).hexdigest()[:16], "ti": resp.tokens_entrada,
                  "tc": resp.cache_leitura, "to": resp.tokens_saida, "ms": resp.ms, "r": "ok" if final else "erro", "e": resp.erro})
    if final is None:  # falha de LLM nunca trava o cadastro: segue com as regras e a digitação
        out = S.obtem(conn, pdm, cid)
        out["llm"] = {"estado": "indisponivel", "erro": resp.erro}
        return out
    out = S.confirma_leitura_llm(conn, pdm, cid, p.usuario, final, resp)
    out["llm"] = {"estado": "ok", "modelo": resp.modelo, "ms": resp.ms}
    return out


@router.get("/cadastros/{cid}/sugestoes/{atributo}", response_model=E.SugestoesView, tags=["cadastros"],
            summary="Até 3 opções de valor, com a frequência no histórico (nada vem preenchido)")
def sugestoes(cid: str, atributo: str, conn: Connection = Conexao, ctx: Ctx = Depends(contexto),
              _: Principal = Depends(exige("leitor"))):
    pdm, _i = ctx
    cad = S._linha(conn, cid)
    if not cad["id_pdm"]:
        raise ErroNegocio("classe_nao_definida", "escolha a classe antes", 422)
    a = pdm.classes[cad["id_pdm"]].atributo(atributo)
    if a is None:
        raise ErroNegocio("atributo_invalido", f"{atributo} não é atributo da classe", 422)
    plano = {k: v for k, v in S._plano(cad).items() if k != atributo}
    o = ranking.opcoes(conn, pdm, cad["id_pdm"], cad["nome"], atributo, plano)
    return E.SugestoesView(atributo=atributo, opcoes=[E.OpcaoView(valor=x.valor, n=x.n, pct=x.pct, fonte=x.fonte) for x in o.opcoes],
                           base=o.base, contexto=o.contexto, sem_opcoes_motivo=o.sem_opcoes_motivo, valores_permitidos=list(a.valores))


@router.get("/cadastros/{cid}/sugestoes-modelo", tags=["cadastros"],
            summary="NCM, fabricante, referência e grupo sugeridos pelos modelos do texto (só propõem)")
def sugestoes_modelo(cid: str, conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    return S.sugestoes_modelo(conn, cid)


@router.get("/cadastros/{cid}/candidatos", tags=["cadastros"], summary="Itens existentes parecidos (verificação de duplicidade)")
def candidatos(cid: str, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), _: Principal = Depends(exige("leitor"))):
    return S.candidatos(conn, ctx[0], cid)


@router.post("/cadastros/{cid}/usar-existente", response_model=E.CadastroView, tags=["decisoes"])
def usar_existente(cid: str, corpo: E.UsarExistente, conn: Connection = Conexao, ctx: Ctx = Depends(contexto),
                   p: Principal = Depends(exige("analista"))):
    return S.usa_existente(conn, ctx[0], cid, p.usuario, corpo.codigo, corpo.justificativa)


@router.post("/cadastros/{cid}/reativar", response_model=E.CadastroView, tags=["decisoes"],
             summary="Pede a reativação de um código BLOQUEADO/OBSOLETO (passa por segundo analista)")
def reativar(cid: str, corpo: E.Reativar, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.reativa(conn, ctx[0], cid, p.usuario, corpo.codigo, corpo.justificativa)


@router.post("/cadastros/{cid}/devolver", response_model=E.CadastroView, tags=["decisoes"], summary="Devolve ao solicitante com a lista exata do que falta")
def devolver(cid: str, corpo: E.Devolver, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.devolve(conn, ctx[0], cid, p.usuario, corpo.pergunta)


@router.post("/cadastros/{cid}/responder", response_model=E.CadastroView, tags=["decisoes"])
def responder(cid: str, corpo: E.Responder, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.responde(conn, ctx[0], cid, p.usuario, corpo.pergunta_id, corpo.resposta)


@router.post("/cadastros/{cid}/aprovar", response_model=E.CadastroView, tags=["decisoes"],
             summary="Aprova (ou envia para revisão, se houver exceção). Bloqueios impedem; exceções exigem justificativa.")
def aprovar(cid: str, corpo: E.Aprovar, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.aprova(conn, ctx[0], cid, corpo.versao, p.usuario, corpo.justificativas)


@router.post("/cadastros/{cid}/recusar", response_model=E.CadastroView, tags=["decisoes"], summary="Encerra como FORA_DO_PDM, com motivo")
def recusar(cid: str, corpo: E.Recusar, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.recusa(conn, ctx[0], cid, p.usuario, corpo.motivo)


@router.post("/cadastros/{cid}/propor-classe", response_model=E.CadastroView, tags=["decisoes"],
             summary="Propõe classe nova ao administrador do PDM; o pedido aguarda a nova versão")
def propor_classe(cid: str, corpo: E.ProporClasse, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.propoe_classe(conn, ctx[0], cid, p.usuario, corpo.model_dump())


@router.post("/cadastros/{cid}/retomar", response_model=E.CadastroView, tags=["decisoes"], summary="Volta a rascunho depois que o PDM ganhou a classe")
def retomar(cid: str, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.retoma_apos_classe(conn, ctx[0], cid, p.usuario)


@router.post("/cadastros/{cid}/cancelar", response_model=E.CadastroView, tags=["decisoes"])
def cancelar(cid: str, corpo: E.Cancelar, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    return S.cancela(conn, ctx[0], cid, p.usuario, corpo.motivo)


@router.post("/cadastros/{cid}/revisao", response_model=E.CadastroView, tags=["decisoes"], summary="Segundo analista decide as exceções")
def revisao(cid: str, corpo: E.Revisao, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("revisor"))):
    return S.decide_revisao(conn, ctx[0], cid, p.usuario, corpo.aprovar, corpo.comentario)


@router.get("/cadastros/{cid}/perguntas", response_model=list[E.PerguntaView], tags=["cadastros"], summary="Perguntas feitas ao solicitante")
def perguntas(cid: str, conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    S._linha(conn, cid)
    rows = conn.execute(text("""select id, destinatario, pergunta, resposta, enviada_em::text as enviada_em, respondida_em::text as respondida_em
        from cadastro_pergunta where cadastro_id = cast(:c as uuid) order by id"""), {"c": cid}).mappings().all()
    return [E.PerguntaView(**dict(r)) for r in rows]


@router.get("/cadastros/{cid}/historico", tags=["cadastros"], summary="Trilha de auditoria (somente inclusão)")
def historico(cid: str, conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    S._linha(conn, cid)
    return auditoria.historico(conn, "cadastro", cid)


# ================================================================== pedidos e filas
@router.get("/pedidos", response_model=E.PaginaPedidos, tags=["pedidos"], summary="Fila de pedidos de cadastro")
def pedidos(estado: str | None = None, area: str | None = None, urgencia: str | None = None, q: str | None = None,
            limite: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
            conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    filtros, par = ["true"], {"l": limite, "o": offset}
    for col, val in (("estado", estado), ("area", area), ("urgencia", urgencia)):
        if val:
            filtros.append(f"{col} = :{col}")
            par[col] = val
    if q:
        filtros.append("(texto ilike :q or id ilike :q)")
        par["q"] = f"%{q}%"
    where = " and ".join(filtros)
    total = conn.execute(text(f"select count(*) from pedido where {where}"), par).scalar()
    rows = conn.execute(text(f"""select id, data_solicitacao::text as data_solicitacao, centro, area, canal, urgencia, texto, tipo_anexo,
        (conteudo_anexo is not null) as tem_anexo, estado, analista from pedido where {where}
        order by case urgencia when 'EMERGENCIAL' then 0 when 'ALTA' then 1 else 2 end, data_solicitacao, id limit :l offset :o"""), par).mappings().all()
    return E.PaginaPedidos(total=total, itens=[E.PedidoView(**dict(r)) for r in rows])


@router.get("/pedidos/{pid}", response_model=E.PedidoDetalhe, tags=["pedidos"], summary="Pedido com o texto e o anexo originais")
def pedido(pid: str, conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    r = conn.execute(text("""select id, data_solicitacao::text as data_solicitacao, centro, area, canal, urgencia, texto, tipo_anexo,
        (conteudo_anexo is not null) as tem_anexo, conteudo_anexo, estado, analista from pedido where id = :i"""), {"i": pid}).mappings().first()
    if not r:
        raise ErroNegocio("pedido_nao_encontrado", "pedido não encontrado", 404)
    return E.PedidoDetalhe(**dict(r))


@router.post("/pedidos/{pid}/assumir", response_model=E.CadastroView, status_code=201, tags=["pedidos"],
             summary="Cria o rascunho a partir do pedido (lê por regras) e atribui ao analista")
def assumir(pid: str, conn: Connection = Conexao, ctx: Ctx = Depends(contexto), p: Principal = Depends(exige("analista"))):
    dono = conn.execute(text("select analista, estado from pedido where id = :i"), {"i": pid}).first()
    if dono and dono[0] and dono[0] != p.usuario and dono[1] == "EM_ANDAMENTO":
        raise ErroNegocio("pedido_em_andamento", f"o pedido já está com {dono[0]}", 409)
    return S.cria(conn, ctx[0], ctx[1], p.usuario, pedido_id=pid)


@router.post("/importacoes/pedidos", tags=["pedidos"], summary="Importa pedidos (os que já existem são ignorados)")
def importa_pedidos(corpo: E.ImportaPedidos, conn: Connection = Conexao, p: Principal = Depends(exige("analista"))):
    novos = 0
    for x in corpo.pedidos:
        n = conn.execute(text("""insert into pedido (id, data_solicitacao, centro, area, canal, urgencia, texto, tipo_anexo, conteudo_anexo)
            values (:id, cast(:d as date), :c, :a, :ca, :u, :t, :ta, :ca2) on conflict (id) do nothing"""),
                         {"id": x.id, "d": x.data_solicitacao, "c": x.centro, "a": x.area, "ca": x.canal, "u": x.urgencia,
                          "t": x.texto, "ta": x.tipo_anexo, "ca2": x.conteudo_anexo}).rowcount
        novos += n
    auditoria.registra(conn, p.usuario, "pedido", "importacao", "importou", None, {"recebidos": len(corpo.pedidos), "novos": novos})
    return {"recebidos": len(corpo.pedidos), "novos": novos, "ignorados": len(corpo.pedidos) - novos}


@router.get("/excecoes", tags=["revisao"], summary="Fila de exceções aguardando segundo analista")
def excecoes(pendentes: bool = True, conn: Connection = Conexao, _: Principal = Depends(exige("revisor"))):
    # exceção "só justificativa" fica sem decisão para sempre: pendente é o que espera o segundo analista
    filtro = "e.decisao is null and c.estado = 'EM_REVISAO'" if pendentes else "true"
    rows = conn.execute(text(f"""select e.id, e.cadastro_id::text, e.tipo, e.atributo, e.padrao, e.usado, e.justificativa, e.autor,
        e.revisor, e.decisao, e.criada_em, c.nome, c.pedido_id from cadastro_excecao e join cadastro c on c.id = e.cadastro_id
        where {filtro} order by e.id"""))
    return [dict(r) for r in rows.mappings()]


@router.get("/materiais/{codigo}", tags=["materiais"], summary="Material da base, com a classe e os atributos lidos")
def material(codigo: str, conn: Connection = Conexao, _: Principal = Depends(exige("leitor"))):
    m = conn.execute(text("select * from material where codigo = :c"), {"c": codigo}).mappings().first()
    if not m:
        raise ErroNegocio("nao_encontrado", f"material {codigo} não existe", 404)
    k = conn.execute(text("select id_pdm, nome, confianca, metodo from material_classificacao where codigo = :c"), {"c": codigo}).mappings().first()
    a = conn.execute(text("select atributo, valor, origem, trecho, confianca from material_atributo where codigo = :c order by atributo"),
                     {"c": codigo}).mappings().all()
    sug = conn.execute(text("select campo, valor, conf, metodo from material_sugestao where codigo = :c order by campo"), {"c": codigo}).mappings().all()
    return {"material": json.loads(json.dumps(dict(m), default=str)), "classificacao": dict(k) if k else None, "atributos": [dict(x) for x in a],
            "sugestoes_preenchimento": [dict(x) for x in sug]}


@router.get("/erp/envios", tags=["erp"], summary="Envios ao ERP (pendentes e com erro ficam visíveis)")
def erp_envios(estado: str | None = None, conn: Connection = Conexao, _: Principal = Depends(exige("analista"))):
    filtro, par = ("estado = :e", {"e": estado}) if estado else ("true", {})
    rows = conn.execute(text(f"select id, cadastro_id::text, tipo, estado, tentativas, protocolo, retorno, atualizado_em from erp_envio where {filtro} order by id desc limit 200"), par)
    return [dict(r) for r in rows.mappings()]


@router.post("/erp/sincronizar", tags=["erp"], summary="Envia o que está pendente e processa os retornos do ERP")
def erp_sincroniza(conn: Connection = Conexao, _: Principal = Depends(exige("revisor"))):
    from ..erp.sincroniza import envia_pendentes, processa_retornos
    return {"envio": envia_pendentes(conn), "retorno": processa_retornos(conn)}
