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


@pytest.fixture(scope="session")
def base_teste(banco, pdm):
    """Pequena base no banco de teste, estruturada pelo mesmo caminho da base real."""
    import json
    from sqlalchemy import text

    from app import ingestao
    from app.classes.resolver import IndiceClasses
    from app.config import settings
    from app.estruturacao import persistir
    from app.estruturacao.regras import extrai_por_regras
    from app.pdm import repositorio

    indice = IndiceClasses(pdm)
    with banco.begin() as c:
        vid = repositorio.publica(c, settings().pdm_xlsx)
        ingestao.semeia_equivalencias(c)
    pdm_ativo = Pdm.de_dict(carregador.carrega(settings().pdm_xlsx), vid)
    rol = "ROLAMENTO RIGIDO ESFERAS; REFERENCIA: {r}; DIAMETRO INTERNO: 25MM; DIAMETRO EXTERNO: 52MM; LARGURA: 15MM; VEDACAO: {v}; FOLGA: {f}"
    paraf = ("PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12; COMPRIMENTO: 50MM; CLASSE RESISTENCIA: {cr}; "
             "MATERIAL: ACO CARBONO; ACABAMENTO: ZINCADO BRANCO; NORMA: DIN 933")
    mats = [
        ("90000001", rol.format(r="6205-2RS/C3", v="BORRACHA AMBOS LADOS", f="C3"), "ROL01", "ATIVO", 5, "1100 - MINA SERRA AZUL"),
        ("90000002", "ROLAMENTO 6205 SEM VEDACAO INFORMADA", "ROL01", "ATIVO", 2, "1200 - USINA DE BENEFICIAMENTO"),
        ("90000003", rol.format(r="6205-ZZ/C3", v="METALICA AMBOS LADOS", f="C3"), "ROL01", "ATIVO", 1, "9000 - CD CENTRAL"),
        ("90000004", rol.format(r="6205-2RS/C3", v="BORRACHA AMBOS LADOS", f="C3").replace("6205", "6206").replace("25MM", "30MM"), "ROL01", "BLOQUEADO", 7, "1100 - MINA SERRA AZUL"),
        ("90000010", "FILTRO OLEO LUBRIFICANTE; FABRICANTE: CATERPILLAR; REFERENCIA FABRICANTE: 1R-1808", "FIL01", "ATIVO", 3, "1100 - MINA SERRA AZUL"),
        ("90000011", "FILTRO OLEO LUBRIFICANTE; FABRICANTE: DONALDSON; REFERENCIA FABRICANTE: P551808", "FIL01", "ATIVO", 4, "1200 - USINA DE BENEFICIAMENTO"),
    ] + [(f"9000010{i}", paraf.format(cr="8.8"), "FIX01", "ATIVO", 1, "1100 - MINA SERRA AZUL") for i in range(5)] \
      + [(f"9000011{i}", paraf.format(cr="10.9").replace("M12", f"M{14+i}"), "FIX01", "ATIVO", 1, "1100 - MINA SERRA AZUL") for i in range(3)] \
      + [("90000120", paraf.format(cr="A2-70").replace("ACO CARBONO", "ACO INOX 304").replace("M12", "M20"), "FIX01", "ATIVO", 1, "1100 - MINA SERRA AZUL")]
    itens = []
    with banco.begin() as c:
        for cod, longa, grupo, status, estoque, centro in mats:
            c.execute(text("""insert into material (codigo, descricao_curta, descricao_longa, grupo, status, estoque, centro, unidade, ncm)
                values (:c, :s, :l, :g, :st, :e, :ce, 'PC', null) on conflict (codigo) do nothing"""),
                      {"c": cod, "s": longa[:40], "l": longa, "g": grupo, "st": status, "e": estoque, "ce": centro})
            m = {"codigo": cod, "descricao_longa": longa, "descricao_curta": longa[:40], "grupo": grupo, "status": status,
                 "fabricante": None, "referencia_fabricante": None}
            itens.append((m, extrai_por_regras(pdm_ativo, indice, m)))
        persistir.grava(c, pdm_ativo, itens, "teste")
        persistir.atualiza_estatisticas(c)
    return {"pdm": pdm_ativo, "indice": indice, "versao": vid}
