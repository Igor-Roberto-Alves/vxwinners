"""Regras de negócio do cadastro de materiais (docs/06-plano-modo-cadastro.md).

Princípios que este módulo garante:
 - a classe é sempre confirmada por uma pessoa; nenhum valor vindo do histórico entra sozinho;
 - o PDM é a referência, mas a palavra final é da pessoa: tudo que contraria o PDM vira EXCEÇÃO
   com justificativa, e exceção passa por um segundo analista (só duplicidade provável dispensa);
 - o que não tem remédio bloqueia: obrigatório vazio, NCM inexistente, classe não confirmada;
 - dois analistas não aprovam o mesmo item (índice único na chave) e toda mudança deixa rastro.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import Connection, text
from sqlalchemy.exc import IntegrityError

from .. import auditoria
from ..classes.resolver import IndiceClasses
from ..estruturacao.canonicalizar import canonicaliza_atributo
from ..estruturacao.regras import extrai_para_classe
from ..identidade import candidatos as cand_mod
from ..identidade.chave import chave_identidade
from ..identidade.referencias import fabricante_canonico
from ..leitura.regras import campos_do_cadastro, le_pedido
from ..ncm import tabela as ncm_tabela
from ..ncm.regras import formata_ncm, ncm_esperado
from ..pdm.modelo import Pdm
from ..sugestoes import modelos
from ..tabelas import rolamentos as tabelas_rolamentos
from . import descricao as desc
from . import modelo as M
from .modelo import ErroNegocio

COLUNAS_FISCAIS = ("unidade", "grupo", "ncm", "centro")


# ================================================================== acesso
def _linha(conn: Connection, cid: str, trava: bool = False) -> dict:
    try:
        r = conn.execute(text("select * from cadastro where id = cast(:i as uuid)" + (" for update" if trava else "")),
                         {"i": cid}).mappings().first()
    except Exception as e:  # uuid malformado
        raise ErroNegocio("nao_encontrado", "cadastro não encontrado", 404) from e
    if not r:
        raise ErroNegocio("nao_encontrado", "cadastro não encontrado", 404)
    d = dict(r)
    d["id"] = str(d["id"])
    d["valores"] = d["valores"] if isinstance(d["valores"], dict) else json.loads(d["valores"] or "{}")
    return d


def _plano(cad: dict) -> dict[str, str]:
    return {a: e["valor"] for a, e in cad["valores"].items() if e.get("valor")}


def _entrada(a, texto: str, origem: str, trecho: str | None = None, id_pdm: str | None = None) -> dict | None:
    """Canonicaliza o que a pessoa (ou a leitura) informou. Texto fora do PDM é guardado como está,
    marcado `valido: false`: a palavra final é da pessoa, mas vira exceção com justificativa."""
    texto = (texto or "").strip()
    if not texto:
        return None
    c = canonicaliza_atributo(a, texto, id_pdm)
    if c.valor:
        return {"valor": c.valor, "bruto": texto, "origem": origem, "trecho": trecho, "valido": True,
                "confianca": c.confianca, "motivo": c.motivo}
    return {"valor": texto.upper(), "bruto": texto, "origem": origem, "trecho": trecho, "valido": False,
            "confianca": 0.0, "motivo": c.motivo, "candidatos": list(c.candidatos)}


def _aplica_tabelas(pdm: Pdm, cad: dict) -> None:
    """Atributos OPCIONAIS deduzidos de tabela técnica local (regra 7 do PDM), sempre com a fonte.
    O que a pessoa digitou nunca é sobrescrito; só valores vindos da tabela são recalculados."""
    if cad["id_pdm"] != "PDM020":
        return
    ref = (cad["valores"].get("REFERENCIA") or {}).get("valor")
    dims = tabelas_rolamentos.dimensoes(ref)
    for atr in ("DIAMETRO INTERNO", "DIAMETRO EXTERNO", "LARGURA"):
        atual = cad["valores"].get(atr)
        if atual and atual.get("origem") != "TABELA_LOCAL":
            continue
        if atr in dims:
            valor, fonte = dims[atr]
            cad["valores"][atr] = {"valor": valor, "bruto": valor, "origem": "TABELA_LOCAL", "trecho": fonte,
                                   "valido": True, "confianca": 0.95, "motivo": "deduzido da referencia"}
        elif atual:  # a referência mudou e a série não está na tabela: o valor antigo deixou de valer
            del cad["valores"][atr]


def _regrava_derivados(pdm: Pdm, cad: dict) -> None:
    """Descrição e chave sempre refletem o estado atual do rascunho."""
    _aplica_tabelas(pdm, cad)
    if not cad["id_pdm"]:
        cad["descricao_longa"] = cad["descricao_curta"] = cad["chave"] = None
        return
    plano = _plano(cad)
    nome = cad["nome"] or ""
    cad["descricao_longa"] = desc.monta_longa(pdm, cad["id_pdm"], nome, plano) if nome else None
    cad["descricao_curta"] = desc.monta_curta(pdm, cad["id_pdm"], nome, plano) if nome else None
    ch = chave_identidade(pdm, cad["id_pdm"], nome, plano)
    cad["chave"] = ch.texto


def _grava(conn: Connection, cad: dict, esperada: int | None = None) -> dict:
    """Persiste o rascunho com bloqueio otimista pela coluna `versao`."""
    r = conn.execute(text("""
        update cadastro set estado=:estado, id_pdm=:id_pdm, nome=:nome, pdm_versao_id=:pv, valores=cast(:valores as jsonb),
            grupo=:grupo, unidade=:unidade, ncm=:ncm, fabricante=:fabricante, referencia_fabricante=:ref, centro=:centro,
            descricao_longa=:dl, descricao_curta=:dc, chave=:chave, analista=:analista, codigo_erp=:codigo_erp,
            usar_codigo=:usar, motivo=:motivo, classe_confirmada=:cc, proposta=cast(:proposta as jsonb),
            resumo_leitura=cast(:resumo as jsonb), versao=versao+1, atualizado_em=now()
        where id=cast(:id as uuid) and (cast(:esp as int) is null or versao = cast(:esp as int)) returning versao"""),
        {"estado": cad["estado"], "id_pdm": cad["id_pdm"], "nome": cad["nome"], "pv": cad["pdm_versao_id"],
         "valores": json.dumps(cad["valores"], ensure_ascii=False), "grupo": cad["grupo"], "unidade": cad["unidade"],
         "ncm": cad["ncm"], "fabricante": cad["fabricante"], "ref": cad["referencia_fabricante"], "centro": cad["centro"],
         "dl": cad["descricao_longa"], "dc": cad["descricao_curta"], "chave": cad["chave"], "analista": cad["analista"],
         "codigo_erp": cad["codigo_erp"], "usar": cad["usar_codigo"], "motivo": cad["motivo"], "cc": cad["classe_confirmada"],
         "proposta": json.dumps(cad["proposta"]) if cad.get("proposta") is not None else None,
         "resumo": json.dumps(cad["resumo_leitura"]) if cad.get("resumo_leitura") is not None else None,
         "id": cad["id"], "esp": esperada})
    novo = r.scalar()
    if novo is None:
        raise ErroNegocio("versao_desatualizada", "o rascunho foi alterado por outra pessoa; recarregue", 409)
    cad["versao"] = novo
    return cad


# ================================================================== análise
@dataclass
class Analise:
    bloqueios: list[dict] = field(default_factory=list)
    excecoes: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _esperados(pdm: Pdm, cad: dict) -> dict:
    classe = pdm.classes[cad["id_pdm"]]
    ncm, regra = ncm_esperado(pdm, classe.id_pdm, cad["nome"] or "", _plano(cad))
    return {"unidade": classe.unidade, "grupo": classe.grupo, "ncm": ncm, "regra_ncm": regra}


def _busca(conn: Connection, pdm: Pdm, cad: dict, limite: int = 8) -> cand_mod.Resultado | None:
    if not cad["id_pdm"]:
        return None
    texto = cad.get("descricao_longa") or cad.get("texto_inicial")
    r = cand_mod.busca(conn, pdm, cad["id_pdm"], cad["nome"] or None, _plano(cad), limite=limite, texto=texto, ignorar_cadastro=cad.get("id"))
    return cand_mod.acrescenta_vizinhos(conn, r, modelos.similares(texto or ""), limite=limite)


def analisa(conn: Connection, pdm: Pdm, cad: dict, busca: cand_mod.Resultado | None) -> Analise:
    a = Analise()
    if not cad["id_pdm"]:
        a.bloqueios.append({"codigo": "CLASSE_NAO_DEFINIDA", "mensagem": "escolha a classe do material"})
        return a
    classe = pdm.classes[cad["id_pdm"]]
    if not cad["classe_confirmada"]:
        a.bloqueios.append({"codigo": "CLASSE_NAO_CONFIRMADA", "mensagem": "a classe precisa ser confirmada por uma pessoa"})
    if len(classe.nomes) > 1 and not cad["nome"]:
        a.bloqueios.append({"codigo": "NOME_NAO_DEFINIDO", "mensagem": "escolha o nome do material (" + ", ".join(classe.nomes[:4]) + "...)"})
    if not cad["centro"]:
        a.bloqueios.append({"codigo": "CENTRO_NAO_DEFINIDO", "mensagem": "informe o centro do solicitante"})

    plano = _plano(cad)
    for atr, aplica in pdm.aplicaveis(cad["id_pdm"], cad["nome"] or "", plano):
        e = cad["valores"].get(atr.nome)
        if aplica is True and atr.obrigatorio and not (e and e.get("valor")):
            a.bloqueios.append({"codigo": "OBRIGATORIO_VAZIO", "atributo": atr.nome,
                                "mensagem": f"{atr.nome} é obrigatório e está vazio"})
        if aplica is True and e and e.get("valor") and not e.get("valido", True):
            tipo = "FORA_DA_LISTA" if atr.tipo == "LISTA" else "FORMATO_FORA_DO_PDM"
            a.excecoes.append({"id": f"{tipo}|{atr.nome}", "tipo": tipo, "atributo": atr.nome, "padrao": None,
                               "usado": e["valor"], "exige_revisor": M.EXCECOES_EXIGEM_REVISOR[tipo]})

    # fiscal e logístico
    esp = _esperados(pdm, cad)
    un = cad["unidade"] or esp["unidade"]
    if un not in pdm.unidades:
        a.bloqueios.append({"codigo": "UNIDADE_INVALIDA", "mensagem": f"unidade {un} não existe no PDM ({', '.join(pdm.unidades)})"})
    elif un != esp["unidade"]:
        a.excecoes.append({"id": "UNIDADE_DIFERENTE_DO_PADRAO|", "tipo": "UNIDADE_DIFERENTE_DO_PADRAO", "atributo": None,
                           "padrao": esp["unidade"], "usado": un, "exige_revisor": True})
    gr = cad["grupo"] or esp["grupo"]
    if gr != esp["grupo"]:
        a.excecoes.append({"id": "GRUPO_DIFERENTE_DO_PADRAO|", "tipo": "GRUPO_DIFERENTE_DO_PADRAO", "atributo": None,
                           "padrao": esp["grupo"], "usado": gr, "exige_revisor": True})
    ncm = formata_ncm(cad["ncm"]) if cad["ncm"] else esp["ncm"]
    if cad["ncm"] and not ncm:
        a.bloqueios.append({"codigo": "NCM_INVALIDO", "mensagem": f"NCM {cad['ncm']} fora do formato 0000.00.00"})
    elif not ncm:
        a.bloqueios.append({"codigo": "NCM_NAO_DETERMINADO", "mensagem": f"NCM ainda não determinado ({esp['regra_ncm']}); informe o NCM"})
    else:
        v = ncm_tabela.valida(conn, ncm)
        if not v.ok:
            msg = f"NCM {ncm}: {v.motivo}"
            if v.sucessores:
                msg += f". Códigos vigentes próximos: {', '.join(v.sucessores)}"
            a.bloqueios.append({"codigo": "NCM_INVALIDO", "mensagem": msg, "sucessores": list(v.sucessores)})
        elif esp["ncm"] and ncm != esp["ncm"]:
            a.excecoes.append({"id": "NCM_DIFERENTE_DA_REGRA|", "tipo": "NCM_DIFERENTE_DA_REGRA", "atributo": None,
                               "padrao": esp["ncm"], "usado": ncm, "exige_revisor": True})

    # duplicidade: só os níveis que pedem decisão
    if busca:
        for c in busca.candidatos:
            if c.nivel == "IGUAL" and c.origem == "cadastro":
                a.bloqueios.append({"codigo": "DUPLICIDADE_CADASTRO_APROVADO",
                                    "mensagem": "já existe um cadastro novo aprovado com esta chave; aguarde o código do ERP ou cancele este rascunho"})
            elif c.nivel == "IGUAL" and c.status == "ATIVO":
                a.excecoes.append({"id": "DUPLICIDADE_IGUAL|", "tipo": "DUPLICIDADE_IGUAL", "atributo": None, "padrao": c.codigo,
                                   "usado": "criar item novo", "exige_revisor": True})
            elif c.nivel == "IGUAL":
                a.excecoes.append({"id": "DUPLICIDADE_BLOQUEADO_IGUAL|", "tipo": "DUPLICIDADE_BLOQUEADO_IGUAL", "atributo": None,
                                   "padrao": f"{c.codigo} ({c.status})", "usado": "criar item novo", "exige_revisor": True})
            elif c.nivel == "PROVAVEL" and not any(x["tipo"] == "DUPLICIDADE_PROVAVEL" for x in a.excecoes):
                a.excecoes.append({"id": "DUPLICIDADE_PROVAVEL|", "tipo": "DUPLICIDADE_PROVAVEL", "atributo": None, "padrao": c.codigo,
                                   "usado": "criar item novo", "exige_revisor": False})
        # uma exceção de duplicidade por tipo
        vistos, unicas = set(), []
        for x in a.excecoes:
            if x["id"] not in vistos:
                vistos.add(x["id"])
                unicas.append(x)
        a.excecoes = unicas
        if busca.comparaveis < busca.total_classe:
            a.avisos.append(f"só {busca.comparaveis} de {busca.total_classe} registros desta classe puderam ser comparados por atributos; "
                            "esta lista não garante que o item não exista")
    return a


# ================================================================== visão
def visao(conn: Connection, pdm: Pdm, cad: dict, busca: cand_mod.Resultado | None = None, com_candidatos: bool = True) -> dict:
    if busca is None and com_candidatos:
        busca = _busca(conn, pdm, cad)
    analise = analisa(conn, pdm, cad, busca)
    classe = pdm.classes.get(cad["id_pdm"]) if cad["id_pdm"] else None
    campos = []
    plano = _plano(cad)
    if classe:
        for atr, aplica in pdm.aplicaveis(classe.id_pdm, cad["nome"] or "", plano):
            e = cad["valores"].get(atr.nome) or {}
            campos.append({
                "atributo": atr.nome, "ordem": atr.ordem, "obrigatorio": atr.obrigatorio, "aplica": aplica,
                "condicao": None if atr.quando.lower() == "sempre" else atr.quando,
                "tipo": atr.tipo, "formato": atr.formato, "valores_permitidos": list(atr.valores),
                "valor": e.get("valor"), "origem": e.get("origem"), "trecho": e.get("trecho"),
                "valido": e.get("valido", True) if e.get("valor") else None, "motivo": e.get("motivo"),
                "candidatos": e.get("candidatos", []),
            })
    esp = _esperados(pdm, cad) if classe else {}
    ncm_usado = (formata_ncm(cad["ncm"]) or cad["ncm"]) if cad["ncm"] else esp.get("ncm")
    ncm_val = None
    if ncm_usado:
        v = ncm_tabela.valida(conn, ncm_usado)
        ncm_val = {"ok": v.ok, "motivo": v.motivo, "descricao": v.descricao, "sucessores": list(v.sucessores)}
    ch = chave_identidade(pdm, cad["id_pdm"], cad["nome"] or "", plano) if classe else None
    return {
        "id": cad["id"], "estado": cad["estado"], "versao": cad["versao"], "pedido_id": cad["pedido_id"],
        "analista": cad["analista"], "pdm_versao_id": cad["pdm_versao_id"],
        "classe": None if not classe else {
            "id_pdm": classe.id_pdm, "nome": cad["nome"], "nomes_possiveis": list(classe.nomes), "grupo": classe.grupo,
            "grupo_descricao": pdm.grupos.get(classe.grupo), "criterio_identidade": classe.criterio,
            "confirmada": cad["classe_confirmada"]},
        "proposta_de_classe": cad.get("proposta"),
        "campos": campos,
        "fiscal": None if not classe else {
            "unidade": {"padrao": esp["unidade"], "usado": cad["unidade"] or esp["unidade"], "personalizado": bool(cad["unidade"])},
            "grupo": {"padrao": esp["grupo"], "usado": cad["grupo"] or esp["grupo"], "personalizado": bool(cad["grupo"])},
            "ncm": {"esperado": esp["ncm"], "regra": esp["regra_ncm"], "usado": ncm_usado, "personalizado": bool(cad["ncm"]),
                    "validacao": ncm_val},
        },
        "fabricante": cad["fabricante"], "referencia_fabricante": cad["referencia_fabricante"], "centro": cad["centro"],
        "descricao": {"longa": cad["descricao_longa"], "curta": cad["descricao_curta"],
                      "curta_tamanho": len(cad["descricao_curta"] or ""), "curta_limite": desc.LIMITE_CURTA},
        "chave": None if not ch else {"texto": ch.texto, "completa": ch.completa, "faltando": list(ch.faltando)},
        "bloqueios": analise.bloqueios, "excecoes_previstas": analise.excecoes, "avisos": analise.avisos,
        "pronto_para_aprovar": not analise.bloqueios and cad["estado"] == M.RASCUNHO,
        "codigo_erp": cad["codigo_erp"], "usar_codigo": cad["usar_codigo"], "motivo": cad["motivo"],
        "duplicidade": None if busca is None else {
            "candidatos": [_cand_dict(c) for c in busca.candidatos],
            "comparaveis": busca.comparaveis, "total_classe": busca.total_classe},
        "resumo_leitura": cad.get("resumo_leitura"), "texto_inicial": cad.get("texto_inicial"),
    }


def _cand_dict(c: cand_mod.Candidato) -> dict:
    return {"codigo": c.codigo, "nivel": c.nivel, "pontos": c.pontos, "origem": c.origem, "status": c.status, "centro": c.centro,
            "estoque": c.estoque, "descricao": c.descricao, "comparacao": c.comparacao, "motivo": c.motivo,
            "permite_uso_direto": c.permite_uso_direto}


def obtem(conn: Connection, pdm: Pdm, cid: str) -> dict:
    return visao(conn, pdm, _linha(conn, cid))


# ================================================================== criação
def _vazio(autor: str) -> dict:
    return {"id": None, "pedido_id": None, "estado": M.RASCUNHO, "id_pdm": None, "nome": None, "pdm_versao_id": None, "valores": {},
            "grupo": None, "unidade": None, "ncm": None, "fabricante": None, "referencia_fabricante": None, "centro": None,
            "descricao_longa": None, "descricao_curta": None, "chave": None, "versao": 1, "analista": autor,
            "codigo_erp": None, "usar_codigo": None, "motivo": None, "texto_inicial": None, "classe_confirmada": False,
            "proposta": None, "resumo_leitura": None}


def _insere(conn: Connection, cad: dict) -> str:
    cid = conn.execute(text("""insert into cadastro (pedido_id, estado, id_pdm, nome, pdm_versao_id, valores, centro, analista,
            texto_inicial, classe_confirmada, proposta, resumo_leitura, fabricante, referencia_fabricante)
        values (:p, :e, :i, :n, :v, cast(:val as jsonb), :c, :a, :t, :cc, cast(:pr as jsonb), cast(:rl as jsonb), :f, :r) returning id::text"""),
        {"p": cad["pedido_id"], "e": cad["estado"], "i": cad["id_pdm"], "n": cad["nome"], "v": cad["pdm_versao_id"],
         "val": json.dumps(cad["valores"], ensure_ascii=False), "c": cad["centro"], "a": cad["analista"],
         "t": cad["texto_inicial"], "cc": cad["classe_confirmada"],
         "pr": json.dumps(cad["proposta"]) if cad["proposta"] is not None else None,
         "rl": json.dumps(cad["resumo_leitura"]) if cad["resumo_leitura"] is not None else None,
         "f": cad["fabricante"], "r": cad["referencia_fabricante"]}).scalar_one()
    return cid


def cria(conn: Connection, pdm: Pdm, indice: IndiceClasses, autor: str, *, id_pdm: str | None = None, nome: str | None = None,
         texto: str | None = None, centro: str | None = None, pedido_id: str | None = None, ler: bool = False) -> dict:
    """Cria um rascunho: vazio, a partir de uma classe escolhida, ou a partir de um pedido."""
    cad = _vazio(autor)
    cad["pdm_versao_id"], cad["centro"], cad["texto_inicial"] = pdm.versao_id, centro, texto
    if pedido_id:
        ped = conn.execute(text("select * from pedido where id = :i for update"), {"i": pedido_id}).mappings().first()
        if not ped:
            raise ErroNegocio("pedido_nao_encontrado", "pedido não encontrado", 404)
        ja = conn.execute(text("select id::text from cadastro where pedido_id = :p and estado <> 'CANCELADO' order by criado_em desc limit 1"),
                          {"p": pedido_id}).scalar()
        if ja:
            return obtem(conn, pdm, ja)
        cad["pedido_id"], cad["centro"] = pedido_id, ped["centro"]
        ex, preparado, campos = le_pedido(pdm, indice, ped["texto"], ped["conteudo_anexo"])
        cad["texto_inicial"] = preparado
        _aplica_leitura(pdm, cad, ex, campos)
        conn.execute(text("update pedido set estado = 'EM_ANDAMENTO', analista = :a where id = :i"), {"a": autor, "i": pedido_id})
    elif id_pdm:
        classe = pdm.classes.get(id_pdm)
        if not classe:
            raise ErroNegocio("classe_invalida", f"classe {id_pdm} não existe no PDM", 422)
        cad["id_pdm"] = id_pdm
        cad["nome"] = _nome_valido(classe, nome)
        cad["classe_confirmada"] = True  # a própria pessoa escolheu
    elif ler and texto:
        ex, preparado, campos = le_pedido(pdm, indice, texto)
        cad["texto_inicial"] = preparado
        _aplica_leitura(pdm, cad, ex, campos)
    _regrava_derivados(pdm, cad)
    cid = _insere(conn, cad)
    auditoria.registra(conn, autor, "cadastro", cid, "criou", None, {"pedido_id": pedido_id, "id_pdm": cad["id_pdm"], "nome": cad["nome"]})
    cad = _linha(conn, cid)
    _regrava_derivados(pdm, cad)
    _grava(conn, cad)
    return obtem(conn, pdm, cid)


def _nome_valido(classe, nome: str | None) -> str | None:
    if len(classe.nomes) == 1:
        return classe.nomes[0]
    if not nome:
        return None
    mapa = {n.upper(): n for n in classe.nomes}
    if nome.upper() not in mapa:
        raise ErroNegocio("nome_invalido", f"{nome} não é um nome da classe {classe.id_pdm}", 422, {"nomes": list(classe.nomes)})
    return mapa[nome.upper()]


def _aplica_leitura(pdm: Pdm, cad: dict, ex, campos: dict[str, str]) -> None:
    """Coloca o que a leitura achou no rascunho. A classe fica como PROPOSTA até a pessoa confirmar;
    valores lidos do pedido entram com origem e trecho (a pessoa pode alterar qualquer um)."""
    if ex.id_pdm:
        cad["id_pdm"], cad["nome"], cad["classe_confirmada"] = ex.id_pdm, ex.nome, False
        cad["proposta"] = {"id_pdm": ex.id_pdm, "nome": ex.nome, "confianca": ex.confianca_classe,
                           "alternativas": [{"nome": n, "id_pdm": i} for n, i in ex.ambiguas]}
        classe = pdm.classes[ex.id_pdm]
        for atr, v in ex.valores.items():
            a = classe.atributo(atr)
            if a is None or not v.valor or v.confianca < 0.8:
                continue
            e = _entrada(a, v.valor, v.origem, v.trecho, ex.id_pdm)
            if e:
                cad["valores"][atr] = e
    elif ex.ambiguas:
        cad["proposta"] = {"id_pdm": None, "nome": None, "confianca": 0.0,
                           "alternativas": [{"nome": n, "id_pdm": i} for n, i in ex.ambiguas]}
    if campos.get("fabricante"):
        cad["fabricante"] = campos["fabricante"]
    if campos.get("referencia_fabricante"):
        cad["referencia_fabricante"] = campos["referencia_fabricante"]
    cad["resumo_leitura"] = {"metodo": ex.metodo, "avisos": ex.avisos}


# ================================================================== busca antes do rascunho
def busca_material(conn: Connection, pdm: Pdm, indice: IndiceClasses, texto: str, *, id_pdm: str | None = None,
                   nome: str | None = None, valores: dict[str, str | None] | None = None, limite: int = 6) -> dict:
    """Lê o texto, compara com a base e devolve o mesmo retrato de um rascunho, SEM gravar nada.
    Só `id_pdm` informado conta como classe escolhida pela pessoa; a lida do texto continua sendo proposta."""
    cad = _vazio("busca")
    cad["pdm_versao_id"], cad["texto_inicial"] = pdm.versao_id, texto
    if id_pdm:
        classe = pdm.classes.get(id_pdm)
        if not classe:
            raise ErroNegocio("classe_invalida", f"classe {id_pdm} não existe no PDM", 422)
        nome = _nome_valido(classe, nome)
        ex = extrai_para_classe(pdm, id_pdm, nome, texto)
        ex.id_pdm, ex.nome = id_pdm, nome
        campos = campos_do_cadastro(texto)
    else:
        ex, _, campos = le_pedido(pdm, indice, texto)
    _aplica_leitura(pdm, cad, ex, campos)
    if id_pdm:
        cad["classe_confirmada"], cad["proposta"] = True, None

    classe = pdm.classes.get(cad["id_pdm"]) if cad["id_pdm"] else None
    for atr, bruto in (valores or {}).items():
        a = classe.atributo(atr) if classe else None
        if a is None:
            continue  # valor de outra classe: a pessoa trocou de classe depois de refinar
        e = _entrada(a, bruto or "", "DIGITADO", None, cad["id_pdm"])
        cad["valores"].pop(atr, None) if e is None else cad["valores"].__setitem__(atr, e)
    _regrava_derivados(pdm, cad)

    r = (cand_mod.busca(conn, pdm, cad["id_pdm"], cad["nome"] or None, _plano(cad), limite=limite, texto=texto)
         if cad["id_pdm"] else cand_mod.Resultado([], 0, 0))
    r = cand_mod.acrescenta_vizinhos(conn, r, modelos.similares(texto), limite=limite)
    v = visao(conn, pdm, cad, r)
    itens = indice.buscar(texto, limite=limite)
    return {"consulta": texto, "classe": v["classe"], "campos": v["campos"], "descricao": v["descricao"], "chave": v["chave"],
            "duplicidade": v["duplicidade"], "fabricante": v["fabricante"], "referencia_fabricante": v["referencia_fabricante"],
            "interpretacao": [{"atributo": c["atributo"], "valor": c["valor"], "trecho": c["trecho"]}
                              for c in v["campos"] if c["valor"] and c["origem"] != "DIGITADO"],
            "alternativas": [{"nome": i.nome, "id_pdm": i.id_pdm, "grupo": i.grupo, "grupo_descricao": i.grupo_descricao,
                              "pontos": i.pontos, "resto": list(i.resto)} for i in itens],
            "ambiguo": any(i.ambiguo for i in itens), "fora_do_pdm": not cad["id_pdm"] and not itens}


# ================================================================== edição
def atualiza(conn: Connection, pdm: Pdm, cid: str, versao: int, autor: str, *, classe: dict | None = None,
             valores: dict | None = None, campos: dict | None = None) -> dict:
    cad = _linha(conn, cid, trava=True)
    if cad["estado"] not in M.EDITAVEIS:
        raise ErroNegocio("nao_editavel", f"cadastro em {cad['estado']} não pode mais ser alterado", 409)
    if cad["versao"] != versao:
        raise ErroNegocio("versao_desatualizada", "o rascunho foi alterado por outra pessoa; recarregue", 409,
                          {"versao_atual": cad["versao"]})
    antes = {"id_pdm": cad["id_pdm"], "nome": cad["nome"], "valores": {k: v.get("valor") for k, v in cad["valores"].items()}}

    if classe:
        idp = classe.get("id_pdm")
        c = pdm.classes.get(idp)
        if not c:
            raise ErroNegocio("classe_invalida", f"classe {idp} não existe no PDM", 422)
        cad["id_pdm"], cad["nome"], cad["classe_confirmada"] = idp, _nome_valido(c, classe.get("nome")), True
        cad["valores"] = {k: v for k, v in cad["valores"].items() if c.atributo(k)}  # só o que existe na nova classe
        cad["proposta"] = None
    if not cad["id_pdm"] and valores:
        raise ErroNegocio("classe_nao_definida", "escolha a classe antes de preencher atributos", 422)

    for atr, bruto in (valores or {}).items():
        a = pdm.classes[cad["id_pdm"]].atributo(atr)
        if a is None:
            raise ErroNegocio("atributo_invalido", f"{atr} não é atributo da classe {cad['id_pdm']}", 422)
        origem, texto = "DIGITADO", bruto
        if isinstance(bruto, dict):
            origem, texto = bruto.get("origem", "DIGITADO"), bruto.get("valor")
            if origem not in ("DIGITADO", "OPCAO"):
                raise ErroNegocio("origem_invalida", "origem só pode ser DIGITADO ou OPCAO", 422)
        e = _entrada(a, texto or "", origem, None, cad["id_pdm"])
        if e is None:
            cad["valores"].pop(atr, None)
        else:
            cad["valores"][atr] = e

    for k, v in (campos or {}).items():
        if k not in ("unidade", "grupo", "ncm", "fabricante", "referencia_fabricante", "centro"):
            raise ErroNegocio("campo_invalido", f"campo {k} não pode ser alterado", 422)
        v = (v or "").strip() or None
        if k == "ncm" and v:
            v = formata_ncm(v) or v
        if k in ("unidade", "grupo") and v:
            v = v.upper()
        if cad["id_pdm"] and k in ("fabricante", "referencia_fabricante") and pdm.classes[cad["id_pdm"]].por_referencia:
            atr = "FABRICANTE" if k == "fabricante" else "REFERENCIA FABRICANTE"  # nas classes de referência são atributos
            a = pdm.classes[cad["id_pdm"]].atributo(atr)
            e = _entrada(a, v or "", "DIGITADO", None, cad["id_pdm"])
            cad["valores"].pop(atr, None) if e is None else cad["valores"].__setitem__(atr, e)
            continue
        cad[k] = v

    _regrava_derivados(pdm, cad)
    _grava(conn, cad, versao)
    depois = {"id_pdm": cad["id_pdm"], "nome": cad["nome"], "valores": {k: v.get("valor") for k, v in cad["valores"].items()}}
    auditoria.registra(conn, autor, "cadastro", cid, "atualizou", antes, depois)
    return visao(conn, pdm, cad)


def interpretar(conn: Connection, pdm: Pdm, cid: str, versao: int, autor: str, texto: str) -> dict:
    """Texto extra (`M12X50 galvanizado 8.8`) preenche, por regra, só os atributos ainda vazios."""
    cad = _linha(conn, cid)
    if not cad["id_pdm"]:
        raise ErroNegocio("classe_nao_definida", "escolha a classe antes", 422)
    ex = extrai_para_classe(pdm, cad["id_pdm"], cad["nome"], texto)
    novos = {}
    for atr, v in ex.valores.items():
        if v.valor and v.confianca >= 0.8 and not (cad["valores"].get(atr) or {}).get("valor"):
            novos[atr] = {"valor": v.valor, "origem": "DIGITADO"}  # a pessoa digitou o texto; a regra só o separou
    out = atualiza(conn, pdm, cid, versao, autor, valores=novos) if novos else obtem(conn, pdm, cid)
    out["interpretacao"] = {"preenchidos": list(novos), "texto": texto}
    return out


def confirma_leitura_llm(conn: Connection, pdm: Pdm, cid: str, autor: str, final, resposta) -> dict:
    """Aplica a leitura por LLM só onde o rascunho ainda está vazio. Nunca confirma a classe."""
    cad = _linha(conn, cid, trava=True)
    if cad["estado"] != M.RASCUNHO:
        raise ErroNegocio("nao_editavel", "só rascunhos podem receber leitura", 409)
    mudou = []
    if final.id_pdm and not cad["id_pdm"]:  # sem classe: vira PROPOSTA, a pessoa confirma
        cad["id_pdm"], cad["nome"], cad["classe_confirmada"] = final.id_pdm, final.nome, False
        cad["proposta"] = {"id_pdm": final.id_pdm, "nome": final.nome, "confianca": final.confianca_classe, "alternativas": []}
    if final.id_pdm and cad["id_pdm"] == final.id_pdm:  # mesma classe (confirmada ou não): preenche só o que está vazio
        if not cad["nome"] and final.nome:
            cad["nome"] = final.nome
        classe = pdm.classes[final.id_pdm]
        for atr, v in final.valores.items():
            a = classe.atributo(atr)
            if a and v.valor and v.confianca >= 0.8 and not (cad["valores"].get(atr) or {}).get("valor"):
                e = _entrada(a, v.valor, v.origem, v.trecho, final.id_pdm)
                if e:
                    cad["valores"][atr] = e
                    mudou.append(atr)
    cad["resumo_leitura"] = {"metodo": final.metodo, "avisos": final.avisos, "llm": {"modelo": resposta.modelo, "ms": resposta.ms,
                             "tokens_entrada": resposta.tokens_entrada, "tokens_saida": resposta.tokens_saida}}
    _regrava_derivados(pdm, cad)
    _grava(conn, cad)
    auditoria.registra(conn, autor, "cadastro", cid, "leitura_llm", None, {"atributos": mudou, "modelo": resposta.modelo})
    return visao(conn, pdm, cad)


# ================================================================== sugestões e candidatos
def candidatos(conn: Connection, pdm: Pdm, cid: str) -> dict:
    cad = _linha(conn, cid)
    r = _busca(conn, pdm, cad)
    if r is None:
        return {"candidatos": [], "comparaveis": 0, "total_classe": 0}
    return {"candidatos": [_cand_dict(c) for c in r.candidatos], "comparaveis": r.comparaveis, "total_classe": r.total_classe}


def sugestoes_modelo(conn: Connection, cid: str) -> dict:
    """NCM, fabricante, referência e grupo sugeridos pelos modelos do time, a partir do texto do item.
    Só propõem: nada é aplicado sem um clique, e o NCM da regra do PDM continua sendo a referência."""
    cad = _linha(conn, cid)
    texto = " ".join(x for x in (cad.get("texto_inicial"), cad.get("descricao_longa")) if x)
    if not modelos.pronto():
        return {"estado": "indisponivel", "motivo": modelos.estado()["erro"] or "modelos ainda nao carregados"}
    r = modelos.sugerir(texto, cad.get("grupo"))
    if r is None:
        return {"estado": "sem_texto"}
    return {"estado": "ok", "ncm": r["ncm"]["sugestoes"], "fabricante": r["fabricante"], "referencia": r["referencia"], "grupo": r["grupo"]["sugestoes"]}


# ================================================================== decisões
def _exige_estado(cad: dict, *estados: str) -> None:
    if cad["estado"] not in estados:
        raise ErroNegocio("estado_invalido", f"operação não permitida em {cad['estado']}", 409)


def aprova(conn: Connection, pdm: Pdm, cid: str, versao: int, autor: str, justificativas: dict[str, str] | None = None) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.RASCUNHO)
    if cad["versao"] != versao:
        raise ErroNegocio("versao_desatualizada", "o rascunho foi alterado por outra pessoa; recarregue", 409, {"versao_atual": cad["versao"]})
    _regrava_derivados(pdm, cad)
    busca = _busca(conn, pdm, cad)
    analise = analisa(conn, pdm, cad, busca)
    if analise.bloqueios:
        raise ErroNegocio("bloqueios", "o item não pode ser aprovado enquanto houver bloqueios", 422, {"bloqueios": analise.bloqueios})
    just = justificativas or {}
    faltam = [x["id"] for x in analise.excecoes if len((just.get(x["id"]) or "").strip()) < 10]
    if faltam:
        raise ErroNegocio("justificativa_obrigatoria", "toda exceção exige justificativa (mínimo 10 caracteres)", 422,
                          {"excecoes": [x for x in analise.excecoes if x["id"] in faltam]})
    esp = _esperados(pdm, cad)
    cad["unidade"] = cad["unidade"] or esp["unidade"]
    cad["grupo"] = cad["grupo"] or esp["grupo"]
    cad["ncm"] = formata_ncm(cad["ncm"]) or esp["ncm"]
    cad["pdm_versao_id"] = pdm.versao_id

    for x in analise.excecoes:
        conn.execute(text("""insert into cadastro_excecao (cadastro_id, tipo, atributo, padrao, usado, justificativa, autor)
            values (cast(:c as uuid), :t, :a, :p, :u, :j, :au)"""),
                     {"c": cid, "t": x["tipo"], "a": x["atributo"], "p": x["padrao"], "u": x["usado"],
                      "j": just[x["id"]].strip(), "au": autor})
    precisa_revisor = any(x["exige_revisor"] for x in analise.excecoes)
    cad["estado"] = M.EM_REVISAO if precisa_revisor else M.APROVADO
    _grava_aprovacao(conn, cad, versao)
    auditoria.registra(conn, autor, "cadastro", cid, "aprovou" if not precisa_revisor else "enviou_para_revisao", {"estado": M.RASCUNHO},
                       {"estado": cad["estado"], "chave": cad["chave"], "excecoes": [x["id"] for x in analise.excecoes],
                        "candidatos": [{"codigo": c.codigo, "nivel": c.nivel} for c in (busca.candidatos if busca else [])]})
    if cad["estado"] == M.APROVADO:
        conn.execute(text("insert into erp_envio (cadastro_id, tipo) values (cast(:c as uuid), 'ITEM_NOVO')"), {"c": cid})
        _fecha_pedido(conn, cad, "CADASTRADO_EM_ANDAMENTO")
    return visao(conn, pdm, cad)


def _grava_aprovacao(conn: Connection, cad: dict, versao: int) -> None:
    """Grava com SAVEPOINT: se outro analista aprovou o mesmo item, o índice único recusa."""
    try:
        with conn.begin_nested():
            _grava(conn, cad, versao)
    except IntegrityError as e:
        if "cadastro_chave_aprovada" in str(e):
            outro = conn.execute(text("select id::text from cadastro where chave=:c and estado in ('APROVADO','AGUARDANDO_REATIVACAO','CADASTRADO') limit 1"),
                                 {"c": cad["chave"]}).scalar()
            raise ErroNegocio("duplicidade_aprovada", "outro analista acabou de aprovar este mesmo item", 409, {"cadastro_existente": outro}) from e
        raise


def _fecha_pedido(conn: Connection, cad: dict, estado: str) -> None:
    if cad.get("pedido_id"):
        conn.execute(text("update pedido set estado = :e where id = :i"), {"e": estado, "i": cad["pedido_id"]})


def decide_revisao(conn: Connection, pdm: Pdm, cid: str, revisor: str, aprovar: bool, comentario: str | None) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.EM_REVISAO)
    autores = {r[0] for r in conn.execute(text("select autor from cadastro_excecao where cadastro_id = cast(:c as uuid) and decisao is null"), {"c": cid})}
    if revisor == cad["analista"] or revisor in autores:
        raise ErroNegocio("revisor_deve_ser_outra_pessoa", "a exceção precisa ser decidida por outro analista", 403)
    if not aprovar and not (comentario or "").strip():
        raise ErroNegocio("comentario_obrigatorio", "ao rejeitar, explique o motivo", 422)
    conn.execute(text("""update cadastro_excecao set revisor=:r, decisao=:d, decidido_em=now()
        where cadastro_id = cast(:c as uuid) and decisao is null"""), {"r": revisor, "d": "APROVADA" if aprovar else "REJEITADA", "c": cid})
    reativacao = bool(conn.execute(text("select 1 from cadastro_excecao where cadastro_id = cast(:c as uuid) and tipo = 'REATIVACAO'"), {"c": cid}).scalar())
    if aprovar:
        cad["estado"] = M.AGUARDANDO_REATIVACAO if reativacao else M.APROVADO
        cad["motivo"] = comentario if reativacao else cad["motivo"]
        _grava_aprovacao(conn, cad, None)
        conn.execute(text("insert into erp_envio (cadastro_id, tipo) values (cast(:c as uuid), :t)"),
                     {"c": cid, "t": "REATIVACAO" if reativacao else "ITEM_NOVO"})
        _fecha_pedido(conn, cad, "CADASTRADO_EM_ANDAMENTO")
    else:
        cad["estado"], cad["motivo"] = M.RASCUNHO, comentario
        _grava(conn, cad)
    auditoria.registra(conn, revisor, "cadastro", cid, "revisou", {"estado": M.EM_REVISAO},
                       {"estado": cad["estado"], "decisao": "APROVADA" if aprovar else "REJEITADA", "comentario": comentario})
    return visao(conn, pdm, cad)


def _diverge_do_rascunho(conn: Connection, pdm: Pdm, cad: dict, codigo: str) -> bool:
    busca = _busca(conn, pdm, cad, limite=50)
    achado = next((c for c in (busca.candidatos if busca else []) if c.codigo == codigo), None)
    return bool(achado) and any(x["estado"] == "diverge" and not x.get("opcional") for x in achado.comparacao)


def usa_existente(conn: Connection, pdm: Pdm, cid: str, autor: str, codigo: str, justificativa: str | None = None) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.RASCUNHO)
    just = (justificativa or "").strip()
    m = conn.execute(text("select status from material where codigo = :c"), {"c": codigo}).first()
    if not m:
        raise ErroNegocio("codigo_inexistente", f"código {codigo} não existe na base", 404)
    if m[0] != "ATIVO":
        raise ErroNegocio("codigo_inativo", f"código {codigo} está {m[0]}: só pode ser usado por reativação", 409,
                          {"use": f"/cadastros/{cid}/reativar"})
    if len(just) < 10 and _diverge_do_rascunho(conn, pdm, cad, codigo):
        raise ErroNegocio("justificativa_obrigatoria", "este código diverge do rascunho em atributo de identidade: justifique (mínimo 10 caracteres)", 422)
    cad["estado"], cad["usar_codigo"], cad["motivo"] = M.JA_EXISTE, codigo, just or None
    _grava(conn, cad)
    _fecha_pedido(conn, cad, "JA_EXISTE")
    auditoria.registra(conn, autor, "cadastro", cid, "usou_existente", {"estado": M.RASCUNHO},
                       {"estado": M.JA_EXISTE, "codigo": codigo, "justificativa": just or None})
    return visao(conn, pdm, cad, com_candidatos=False)


def reativa(conn: Connection, pdm: Pdm, cid: str, autor: str, codigo: str, justificativa: str) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.RASCUNHO)
    if len((justificativa or "").strip()) < 10:
        raise ErroNegocio("justificativa_obrigatoria", "a reativação exige justificativa (mínimo 10 caracteres)", 422)
    m = conn.execute(text("select status from material where codigo = :c"), {"c": codigo}).first()
    if not m:
        raise ErroNegocio("codigo_inexistente", f"código {codigo} não existe na base", 404)
    if m[0] == "ATIVO":
        raise ErroNegocio("codigo_ativo", "o código já está ativo: use-o diretamente", 409)
    conn.execute(text("""insert into cadastro_excecao (cadastro_id, tipo, atributo, padrao, usado, justificativa, autor)
        values (cast(:c as uuid), 'REATIVACAO', null, :p, :u, :j, :a)"""),
                 {"c": cid, "p": f"{codigo} ({m[0]})", "u": "reativar codigo", "j": justificativa.strip(), "a": autor})
    cad["estado"], cad["usar_codigo"], cad["motivo"] = M.EM_REVISAO, codigo, justificativa.strip()
    _grava(conn, cad)
    auditoria.registra(conn, autor, "cadastro", cid, "pediu_reativacao", {"estado": M.RASCUNHO}, {"estado": M.EM_REVISAO, "codigo": codigo})
    return visao(conn, pdm, cad, com_candidatos=False)


def devolve(conn: Connection, pdm: Pdm, cid: str, autor: str, pergunta: str | None = None) -> dict:
    """Devolve ao solicitante com a lista exata do que falta (ou uma pergunta específica)."""
    from . import notificacao

    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.RASCUNHO)
    if not pergunta:
        pend = [b for b in analisa(conn, pdm, cad, None).bloqueios if b["codigo"] == "OBRIGATORIO_VAZIO"]
        if not pend:
            raise ErroNegocio("nada_a_perguntar", "não há pendência de informacao; informe uma pergunta", 422)
        pergunta = "Para cadastrar este item faltam as seguintes informações: " + ", ".join(b["atributo"] for b in pend) + "."
    contato = None
    if cad["pedido_id"]:
        contato = conn.execute(text("select c.email from pedido p join area_contato c on c.area = p.area where p.id = :i"),
                               {"i": cad["pedido_id"]}).scalar()
    conn.execute(text("""insert into cadastro_pergunta (cadastro_id, destinatario, pergunta) values (cast(:c as uuid), :d, :p)"""),
                 {"c": cid, "d": contato, "p": pergunta})
    enviado = None
    if contato:
        enviado = notificacao.enviar(contato, f"Pedido {cad['pedido_id']}: faltam informacoes", pergunta)
    cad["estado"] = M.AGUARDANDO_SOLICITANTE
    _grava(conn, cad)
    if cad["pedido_id"]:
        conn.execute(text("update pedido set estado='DEVOLVIDO' where id=:i"), {"i": cad["pedido_id"]})
    auditoria.registra(conn, autor, "cadastro", cid, "devolveu", {"estado": M.RASCUNHO},
                       {"estado": cad["estado"], "pergunta": pergunta, "email": contato, "mensagem": enviado})
    out = visao(conn, pdm, cad, com_candidatos=False)
    out["devolucao"] = {"pergunta": pergunta, "destinatario": contato, "enviada": bool(enviado),
                        "aviso": None if contato else "nenhum contato cadastrado para a área do pedido: a pergunta ficou registrada, mas nada foi enviado"}
    return out


def responde(conn: Connection, pdm: Pdm, cid: str, autor: str, pergunta_id: int, resposta: str) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.AGUARDANDO_SOLICITANTE)
    n = conn.execute(text("""update cadastro_pergunta set resposta=:r, respondida_em=now()
        where id=:p and cadastro_id=cast(:c as uuid) and resposta is null"""), {"r": resposta, "p": pergunta_id, "c": cid}).rowcount
    if not n:
        raise ErroNegocio("pergunta_nao_encontrada", "pergunta inexistente ou já respondida", 404)
    cad["estado"] = M.RASCUNHO
    _grava(conn, cad)
    if cad["pedido_id"]:
        conn.execute(text("update pedido set estado='EM_ANDAMENTO' where id=:i"), {"i": cad["pedido_id"]})
    auditoria.registra(conn, autor, "cadastro", cid, "recebeu_resposta", {"estado": M.AGUARDANDO_SOLICITANTE}, {"estado": M.RASCUNHO, "resposta": resposta})
    return obtem(conn, pdm, cid)


def recusa(conn: Connection, pdm: Pdm, cid: str, autor: str, motivo: str) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.RASCUNHO, M.AGUARDANDO_CLASSE)
    if len((motivo or "").strip()) < 5:
        raise ErroNegocio("motivo_obrigatorio", "informe o motivo da recusa", 422)
    cad["estado"], cad["motivo"] = M.FORA_DO_PDM, motivo.strip()
    _grava(conn, cad)
    _fecha_pedido(conn, cad, "FORA_DO_PDM")
    auditoria.registra(conn, autor, "cadastro", cid, "recusou", {"estado": M.RASCUNHO}, {"estado": cad["estado"], "motivo": motivo})
    return visao(conn, pdm, cad, com_candidatos=False)


def propoe_classe(conn: Connection, pdm: Pdm, cid: str, autor: str, descricao: dict) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.RASCUNHO)
    if not (descricao.get("nome_sugerido") and descricao.get("justificativa")):
        raise ErroNegocio("proposta_incompleta", "informe nome_sugerido e justificativa", 422)
    conn.execute(text("insert into pdm_proposta (tipo, cadastro_id, descricao, autor) values ('CLASSE_NOVA', cast(:c as uuid), cast(:d as jsonb), :a)"),
                 {"c": cid, "d": json.dumps(descricao, ensure_ascii=False), "a": autor})
    cad["estado"] = M.AGUARDANDO_CLASSE
    _grava(conn, cad)
    auditoria.registra(conn, autor, "cadastro", cid, "propos_classe", {"estado": M.RASCUNHO}, {"estado": cad["estado"], "proposta": descricao})
    return visao(conn, pdm, cad, com_candidatos=False)


def retoma_apos_classe(conn: Connection, pdm: Pdm, cid: str, autor: str) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.AGUARDANDO_CLASSE)
    cad["estado"] = M.RASCUNHO
    _grava(conn, cad)
    auditoria.registra(conn, autor, "cadastro", cid, "retomou", {"estado": M.AGUARDANDO_CLASSE}, {"estado": M.RASCUNHO})
    return obtem(conn, pdm, cid)


def cancela(conn: Connection, pdm: Pdm, cid: str, autor: str, motivo: str | None = None) -> dict:
    cad = _linha(conn, cid, trava=True)
    _exige_estado(cad, M.RASCUNHO, M.AGUARDANDO_SOLICITANTE, M.AGUARDANDO_CLASSE)
    cad["estado"], cad["motivo"] = M.CANCELADO, motivo
    _grava(conn, cad)
    _fecha_pedido(conn, cad, "CANCELADO")
    auditoria.registra(conn, autor, "cadastro", cid, "cancelou", None, {"motivo": motivo})
    return visao(conn, pdm, cad, com_candidatos=False)
