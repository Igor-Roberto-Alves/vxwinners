"""Regras de classe aprendidas pelo LLM (artefatos/sujeito_aprendido.json)."""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import sinonimos  # noqa: E402
from saneamento.pdm import Pdm  # noqa: E402
from saneamento.regras import ClassificadorLexico  # noqa: E402


@pytest.fixture
def regras(tmp_path):
    def gravar(d):
        arq = tmp_path / "sujeito_aprendido.json"
        arq.write_text(json.dumps({"regras": d}), encoding="utf-8")
        return sinonimos.carregar_sujeitos_aprendidos(arq)
    yield gravar
    sinonimos.SUJEITO_APRENDIDO.clear()


@pytest.fixture(scope="module")
def clf():
    return ClassificadorLexico(Pdm.carregar(RAIZ / "artefatos/pdm.json"))


def test_sem_arquivo_nada_muda(tmp_path):
    assert sinonimos.carregar_sujeitos_aprendidos(tmp_path / "nao_existe.json") == 0
    assert sinonimos.SUJEITO_APRENDIDO == {}
    texto = "Generic | Ball valve | 1POL"
    assert sinonimos.expandir_sujeito(texto) == sinonimos.normalizar(texto)


def test_termo_em_ingles_vira_sujeito_do_pdm(regras, clf):
    assert regras({"Ball valve": {"para": "VALVULA ESFERA", "id_pdm": "PDM040"}}) == 1
    texto = "Generic | Ball valve | 1POL, 150#, A216 WCB, RF flanged"
    assert "VALVULA ESFERA" in sinonimos.expandir_sujeito(texto)
    assert clf.classificar(texto, "").classe.id_pdm == "PDM040"


def test_sem_a_regra_o_catalogo_fica_fora_do_pdm(clf):
    sinonimos.SUJEITO_APRENDIDO.clear()
    assert clf.classificar("Generic | Ball valve | 1POL, 150#", "").classe is None


def test_casa_so_a_expressao_inteira(regras):
    regras({"BALL VALVE": {"para": "VALVULA ESFERA", "id_pdm": "PDM040"}})
    # 'BALL' sozinho nao e regra: nao vira 'bola' nem valvula
    assert sinonimos.expandir_sujeito("BALL BEARING 6205") == "BALL BEARING 6205"


def test_curado_tem_precedencia_sobre_aprendido(regras):
    # 'ELEMENTO FILTRANTE' e curado -> FILTRO; uma regra aprendida para a
    # mesma expressao nao pode reescrever a curadoria
    regras({"ELEMENTO FILTRANTE": {"para": "VALVULA ESFERA", "id_pdm": "PDM040"}})
    assert "FILTRO" in sinonimos.expandir_sujeito("ELEMENTO FILTRANTE OLEO LF3970")
    assert "VALVULA" not in sinonimos.expandir_sujeito("ELEMENTO FILTRANTE OLEO LF3970")
