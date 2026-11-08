from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Connection, Engine, create_engine

from .config import settings


@lru_cache
def engine() -> Engine:
    s = settings()
    url = s.database_url
    if not url:
        from .devdb import url_dev

        url = url_dev(s.database_nome)
    return create_engine(url, pool_pre_ping=True, future=True)


@contextmanager
def transacao() -> Iterator[Connection]:
    """Uma transação por unidade de trabalho; confirma ao sair, desfaz em exceção."""
    with engine().begin() as conn:
        yield conn


def reinicia_engine() -> None:
    engine.cache_clear()
