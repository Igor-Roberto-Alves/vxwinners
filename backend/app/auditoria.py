"""Trilha de auditoria somente de inclusão (o banco recusa UPDATE e DELETE nesta tabela)."""
from __future__ import annotations

import json

from sqlalchemy import Connection, text


def registra(conn: Connection, autor: str | None, entidade: str, entidade_id: str, acao: str,
             antes: dict | None = None, depois: dict | None = None) -> None:
    conn.execute(text("""insert into evento_auditoria (autor, entidade, entidade_id, acao, antes, depois)
        values (:a, :e, :i, :acao, cast(:antes as jsonb), cast(:depois as jsonb))"""),
                 {"a": autor, "e": entidade, "i": str(entidade_id), "acao": acao,
                  "antes": json.dumps(antes, default=str, ensure_ascii=False) if antes is not None else None,
                  "depois": json.dumps(depois, default=str, ensure_ascii=False) if depois is not None else None})


def historico(conn: Connection, entidade: str, entidade_id: str) -> list[dict]:
    rows = conn.execute(text("""select quando, autor, acao, antes, depois from evento_auditoria
        where entidade = :e and entidade_id = :i order by id"""), {"e": entidade, "i": str(entidade_id)}).all()
    return [dict(r._mapping) for r in rows]
