"""Conector com o ERP: o ERP é o dono do cadastro e gera o código de 8 dígitos.

`ConectorERP` é a interface; `ConectorArquivo` é a primeira implementação (troca de arquivos JSON)
e pode virar API sem mudar o resto. Envio idempotente: o identificador do cadastro é o protocolo,
então reenviar não cria item duplicado no ERP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class ConectorERP(Protocol):
    def enviar_item(self, item: dict) -> str: ...
    def solicitar_reativacao(self, cadastro_id: str, codigo: str, justificativa: str) -> str: ...
    def retornos(self) -> list[tuple[str, dict]]: ...
    def confirmar_retorno(self, nome: str) -> None: ...


class ConectorArquivo:
    def __init__(self, saida: Path, entrada: Path):
        self.saida, self.entrada = Path(saida), Path(entrada)

    def _grava(self, nome: str, conteudo: dict) -> str:
        self.saida.mkdir(parents=True, exist_ok=True)
        destino = self.saida / nome
        if destino.exists():  # idempotente: o mesmo protocolo não gera outro arquivo
            return nome
        tmp = destino.with_suffix(".tmp")
        tmp.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, destino)
        return nome

    def enviar_item(self, item: dict) -> str:
        return self._grava(f"ITEM_{item['cadastro_id']}.json", {"tipo": "ITEM_NOVO", **item})

    def solicitar_reativacao(self, cadastro_id: str, codigo: str, justificativa: str) -> str:
        return self._grava(f"REATIVACAO_{cadastro_id}.json",
                           {"tipo": "REATIVACAO", "cadastro_id": cadastro_id, "codigo": codigo, "justificativa": justificativa})

    def retornos(self) -> list[tuple[str, dict]]:
        if not self.entrada.exists():
            return []
        out = []
        for p in sorted(self.entrada.glob("RET_*.json")):
            try:
                out.append((p.name, json.loads(p.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):
                out.append((p.name, {"status": "ILEGIVEL"}))
        return out

    def confirmar_retorno(self, nome: str) -> None:
        feito = self.entrada / "processados"
        feito.mkdir(parents=True, exist_ok=True)
        os.replace(self.entrada / nome, feito / nome)


def conector_padrao() -> ConectorERP:
    from ..config import settings

    s = settings()
    return ConectorArquivo(s.erp_dir_saida, s.erp_dir_entrada)
