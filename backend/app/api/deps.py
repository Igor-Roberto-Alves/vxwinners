"""Dependências da API: transação por requisição, contexto do PDM e identidade do usuário.

Autenticação: só o modo `dev` existe (cabeçalhos X-Usuario e X-Papel). O modo OIDC descrito no
plano AINDA NÃO está implementado e a API recusa subir com ele, em vez de fingir proteção.
As permissões são conferidas aqui, no servidor, nunca na interface.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator

from fastapi import Depends, Header, HTTPException
from sqlalchemy import Connection, text

from ..classes.resolver import IndiceClasses
from ..config import settings
from ..db import engine
from ..pdm import repositorio
from ..pdm.modelo import Pdm

# papel → o que pode fazer (revisor inclui analista; analista inclui leitor)
PAPEIS = {
    "leitor": {"leitor"},
    "analista": {"leitor", "analista"},
    "revisor": {"leitor", "analista", "revisor"},
    "admin_pdm": {"leitor", "admin_pdm"},
}


@dataclass(frozen=True)
class Principal:
    usuario: str
    papel: str

    def pode(self, capacidade: str) -> bool:
        return capacidade in PAPEIS[self.papel]


def principal(x_usuario: str | None = Header(None), x_papel: str | None = Header(None)) -> Principal:
    if settings().auth_modo != "dev":
        raise HTTPException(501, "autenticação OIDC ainda não implementada; use AUTH_MODO=dev apenas em desenvolvimento")
    if not x_usuario or not x_usuario.strip():
        raise HTTPException(401, "informe o usuário no cabeçalho X-Usuario")
    papel = (x_papel or "analista").lower()
    if papel not in PAPEIS:
        raise HTTPException(400, f"papel inválido; use um de {', '.join(PAPEIS)}")
    return Principal(x_usuario.strip(), papel)


def exige(capacidade: str):
    def dep(p: Principal = Depends(principal)) -> Principal:
        if not p.pode(capacidade):
            raise HTTPException(403, f"o papel {p.papel} não pode executar esta operação (exige {capacidade})")
        return p
    return dep


def conexao() -> Iterator[Connection]:
    """Uma transação por requisição: confirma ao final, desfaz se a rota falhar."""
    with engine().begin() as conn:
        yield conn


# scope="function": o COMMIT acontece ANTES de a resposta sair. No padrão ("request") o cliente ouve "criado" antes de
# o dado estar gravado, e a chamada seguinte pode não encontrar o que acabou de criar.
Conexao = Depends(conexao, scope="function")


_ctx: dict = {"indice": None, "versao": None, "quando": 0.0}


def contexto(conn: Connection = Conexao) -> tuple[Pdm, IndiceClasses]:
    pdm = repositorio.ativo(conn)
    if _ctx["versao"] != pdm.versao_id or time.time() - _ctx["quando"] > 600:
        freq = {(r[0], r[1]): r[2] for r in conn.execute(text(
            "select id_pdm, nome, count(*) from material_classificacao where id_pdm is not null group by 1, 2"))}
        _ctx.update(indice=IndiceClasses(pdm, freq), versao=pdm.versao_id, quando=time.time())
    return pdm, _ctx["indice"]


def limpa_contexto() -> None:
    _ctx.update(indice=None, versao=None, quando=0.0)
