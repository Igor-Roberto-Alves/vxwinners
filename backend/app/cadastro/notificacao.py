"""Devolução ao solicitante por e-mail.

Os pedidos só identificam centro e área (não a pessoa), então o destino é o contato cadastrado
por área. Nesta versão o envio grava o e-mail numa caixa de saída em arquivo: a integração com o
Amazon SES ainda NÃO existe. A interface é `enviar`; trocar a implementação não afeta o resto.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from ..config import settings


def enviar(destino: str, assunto: str, corpo: str) -> str:
    """Grava o e-mail na caixa de saída e devolve o identificador da mensagem."""
    pasta = Path(settings().erp_dir_saida) / "emails"
    pasta.mkdir(parents=True, exist_ok=True)
    msg_id = f"{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
    seguro = re.sub(r"[^A-Za-z0-9@._-]", "_", destino)
    (pasta / f"{msg_id}_{seguro}.txt").write_text(f"Para: {destino}\nAssunto: {assunto}\n\n{corpo}\n", encoding="utf-8")
    return msg_id
