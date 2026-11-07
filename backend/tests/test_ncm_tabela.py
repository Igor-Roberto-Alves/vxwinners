import json
from datetime import date

import pytest


@pytest.fixture()
def tabela_pequena(tmp_path, banco):
    from app.ncm import tabela
    doc = {"Ato": "teste", "Data_Ultima_Atualizacao_NCM": "Vigente em teste", "Nomenclaturas": [
        {"Codigo": "7318.15.00", "Descricao": "Outros parafusos", "Data_Inicio": "01/04/2022", "Data_Fim": "31/12/9999"},
        {"Codigo": "7306.30.10", "Descricao": "A", "Data_Inicio": "01/02/2026", "Data_Fim": "31/12/9999"},
        {"Codigo": "7306.30.90", "Descricao": "Outros", "Data_Inicio": "01/02/2026", "Data_Fim": "31/12/9999"},
        {"Codigo": "1111.11.11", "Descricao": "Antigo", "Data_Inicio": "01/01/2010", "Data_Fim": "31/12/2020"},
        {"Codigo": "73", "Descricao": "capitulo", "Data_Inicio": "01/01/2010", "Data_Fim": "31/12/9999"},
    ]}
    arq = tmp_path / "ncm.json"
    arq.write_text(json.dumps(doc))
    with banco.begin() as c:
        tabela.importa(c, arq)
    return tabela


def test_ncm_vigente_ok(banco, tabela_pequena):
    with banco.connect() as c:
        assert tabela_pequena.valida(c, "7318.15.00").ok


def test_ncm_desdobrado_acusa_sucessores(banco, tabela_pequena):
    with banco.connect() as c:
        r = tabela_pequena.valida(c, "7306.30.00")
    assert not r.ok and "inexistente" in r.motivo
    assert r.sucessores == ("7306.30.10", "7306.30.90")


def test_ncm_fora_de_vigencia_e_formato(banco, tabela_pequena):
    with banco.connect() as c:
        assert "vigencia" in tabela_pequena.valida(c, "1111.11.11", em=date(2026, 1, 1)).motivo
        assert not tabela_pequena.valida(c, "73181500").ok  # formato errado
        assert not tabela_pequena.valida(c, None).ok


def test_importacao_e_idempotente(banco, tabela_pequena, tmp_path):
    with banco.begin() as c:
        n = c.exec_driver_sql("select count(*) from ncm_versao").scalar()
    assert n == 1
