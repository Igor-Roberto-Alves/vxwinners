"""Mesmo contrato do serviço do time (`servico/api.py`, porta 8700), servido por este backend.

É o que o mockup chama. Sem autenticação porque só existe no modo de desenvolvimento.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from ..cadastro.modelo import ErroNegocio
from ..sugestoes import modelos

router = APIRouter(prefix="/sugestao", tags=["sugestao"])


class ReqSimilares(BaseModel):
    descricao: str

    @field_validator("descricao")
    @classmethod
    def nao_vazia(cls, v: str) -> str:
        if not str(v or "").strip():
            raise ValueError("descricao vazia: informe a descricao do material")
        return v


class ReqSugerir(ReqSimilares):
    grupo: str | None = None


def _exige_modelos() -> None:
    if not modelos.pronto():
        raise ErroNegocio("modelos_indisponiveis", modelos.estado()["erro"] or "modelos nao carregados", 503)


@router.get("/saude")
def saude():
    return {"ok": modelos.pronto(), "linhas_base": modelos.linhas_base(), **modelos.estado()}


@router.post("/sugerir")
def sugerir(req: ReqSugerir):
    _exige_modelos()
    return modelos.sugerir(req.descricao, req.grupo)


@router.post("/similares")
def similares(req: ReqSimilares):
    _exige_modelos()
    return {"similares": modelos.similares(req.descricao)}
