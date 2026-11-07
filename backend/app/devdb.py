"""PostgreSQL embutido para desenvolvimento e testes (pacote pgserver). Não é usado em produção."""
from __future__ import annotations

from pathlib import Path

from .config import RAIZ_BACKEND


def servidor(diretorio: Path | None = None):
    import pgserver

    return pgserver.get_server((diretorio or RAIZ_BACKEND / ".pgdata").resolve(), cleanup_mode=None)


def url_dev(nome_banco: str, diretorio: Path | None = None) -> str:
    """Garante o banco `nome_banco` e devolve a URL SQLAlchemy (socket unix)."""
    srv = servidor(diretorio)
    existe = srv.psql(f"select 1 from pg_database where datname = '{nome_banco}';")
    if "(0 rows)" in existe:
        srv.psql(f'create database "{nome_banco}";')
    host = str((diretorio or RAIZ_BACKEND / ".pgdata").resolve())
    return f"postgresql+psycopg://postgres:@/{nome_banco}?host={host}"
