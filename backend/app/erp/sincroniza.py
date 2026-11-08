"""Worker do ERP: envia o que está pendente e processa os retornos (código gerado ou erro)."""
from __future__ import annotations

from sqlalchemy import Connection, text

from .. import auditoria
from ..cadastro import modelo as M
from .conector import ConectorERP, conector_padrao


def envia_pendentes(conn: Connection, conector: ConectorERP | None = None) -> dict:
    conector = conector or conector_padrao()
    rows = conn.execute(text("""select e.id, e.cadastro_id::text, e.tipo, c.id_pdm, c.nome, c.descricao_longa, c.descricao_curta,
              c.grupo, c.unidade, c.ncm, c.fabricante, c.referencia_fabricante, c.centro, c.usar_codigo, c.motivo
        from erp_envio e join cadastro c on c.id = e.cadastro_id
        where e.estado in ('PENDENTE', 'ERRO') order by e.id for update of e skip locked""")).mappings().all()
    ok = erro = 0
    for r in rows:
        try:
            if r["tipo"] == "ITEM_NOVO":
                proto = conector.enviar_item({
                    "cadastro_id": r["cadastro_id"], "classe": r["id_pdm"], "nome": r["nome"],
                    "descricao_longa": r["descricao_longa"], "descricao_curta": r["descricao_curta"],
                    "grupo": r["grupo"], "unidade": r["unidade"], "ncm": r["ncm"], "fabricante": r["fabricante"],
                    "referencia_fabricante": r["referencia_fabricante"], "centro": r["centro"]})
            else:
                proto = conector.solicitar_reativacao(r["cadastro_id"], r["usar_codigo"], r["motivo"] or "")
            conn.execute(text("update erp_envio set estado='ENVIADO', protocolo=:p, tentativas=tentativas+1, atualizado_em=now() where id=:i"),
                         {"p": proto, "i": r["id"]})
            ok += 1
        except Exception as e:  # noqa: BLE001 - uma falha não pode travar os demais envios
            conn.execute(text("update erp_envio set estado='ERRO', tentativas=tentativas+1, retorno=cast(:r as jsonb), atualizado_em=now() where id=:i"),
                         {"r": f'{{"erro": "{type(e).__name__}"}}', "i": r["id"]})
            erro += 1
    return {"enviados": ok, "erros": erro}


def processa_retornos(conn: Connection, conector: ConectorERP | None = None) -> dict:
    conector = conector or conector_padrao()
    ok = erro = ignorados = 0
    for nome, ret in conector.retornos():
        cid, status, codigo = ret.get("cadastro_id"), ret.get("status"), ret.get("codigo")
        row = conn.execute(text("select estado, chave from cadastro where id = cast(:i as uuid) for update"), {"i": cid}).first() if cid else None
        if not row:
            ignorados += 1
            conector.confirmar_retorno(nome)
            continue
        estado = row[0]
        if status == "OK" and codigo:
            if estado == M.APROVADO:
                conn.execute(text("update cadastro set estado=:e, codigo_erp=:c, atualizado_em=now() where id=cast(:i as uuid)"),
                             {"e": M.CADASTRADO, "c": codigo, "i": cid})
            elif estado == M.AGUARDANDO_REATIVACAO:
                conn.execute(text("update cadastro set estado=:e, atualizado_em=now() where id=cast(:i as uuid)"), {"e": M.JA_EXISTE, "i": cid})
            conn.execute(text("update erp_envio set estado='CONCLUIDO', retorno=cast(:r as jsonb), atualizado_em=now() where cadastro_id=cast(:i as uuid)"),
                         {"r": __import__("json").dumps(ret), "i": cid})
            auditoria.registra(conn, "erp", "cadastro", cid, "retorno_erp", {"estado": estado}, {"codigo": codigo})
            ok += 1
        else:
            if estado in (M.APROVADO, M.AGUARDANDO_REATIVACAO):
                conn.execute(text("update cadastro set estado=:e, motivo=:m, atualizado_em=now() where id=cast(:i as uuid)"),
                             {"e": M.ERRO_ERP, "m": str(ret.get("mensagem") or status), "i": cid})
            conn.execute(text("update erp_envio set estado='ERRO', retorno=cast(:r as jsonb), atualizado_em=now() where cadastro_id=cast(:i as uuid)"),
                         {"r": __import__("json").dumps(ret), "i": cid})
            auditoria.registra(conn, "erp", "cadastro", cid, "erro_erp", {"estado": estado}, ret)
            erro += 1
        conector.confirmar_retorno(nome)
    return {"processados": ok, "erros": erro, "ignorados": ignorados}
