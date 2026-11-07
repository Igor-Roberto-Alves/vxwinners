from pathlib import Path

import pytest

from app.config import settings
from app.pdm import carregador
from app.pdm.modelo import Pdm


@pytest.fixture(scope="session")
def pdm() -> Pdm:
    return Pdm.de_dict(carregador.carrega(Path(settings().pdm_xlsx)))


@pytest.fixture(scope="session")
def banco():
    """Banco PostgreSQL de teste, recriado do zero com as migrações."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    from app import devdb
    from app.config import RAIZ_BACKEND

    srv = devdb.servidor()
    srv.psql('drop database if exists "cadastro_teste";')
    url = devdb.url_dev("cadastro_teste")
    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ_BACKEND / "migrations"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")
    eng = create_engine(url, future=True)
    yield eng
    eng.dispose()
