from alembic import context
from sqlalchemy import create_engine

from app.config import settings


def _url() -> str:
    # Testes passam a URL por atributo; senão usa a configuração.
    url = context.config.attributes.get("url") or settings().database_url
    if not url:
        from app.devdb import url_dev

        url = url_dev(settings().database_nome)
    return url


def run_migrations_online() -> None:
    engine = create_engine(_url(), future=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
