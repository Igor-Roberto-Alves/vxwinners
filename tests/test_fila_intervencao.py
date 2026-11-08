# -*- coding: utf-8 -*-
"""Classificacao da acao na fila de intervencao humana (scripts/19_fila_intervencao.py).

A regra que importa: o que a pessoa vai FAZER com o campo, nao o erro que ele e.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def carrega_modulo():
    # o script tem numero no nome: import normal nao serve
    spec = importlib.util.spec_from_file_location(
        "fila", RAIZ / "scripts/19_fila_intervencao.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["fila"] = m
    spec.loader.exec_module(m)
    return m


fila = carrega_modulo()


@pytest.mark.parametrize("veredito,banda,cands,esperado", [
    # o texto trazia o valor e a leitura perdeu: confirmar e seguir
    ("PERDIDO", "", [["4MM2", 1.0]], "um_clique"),
    # candidato unico, ou provavel acima do limiar
    ("PRESENTE_FORA_DO_PADRAO", "UNICO", [["NBR", 1.0]], "um_clique"),
    ("PRESENTE_FORA_DO_PADRAO", "PROVAVEL", [["ZINCADO BRANCO", 0.96]], "um_clique"),
    # provavel mas abaixo do limiar: quem decide e a pessoa
    ("PRESENTE_FORA_DO_PADRAO", "PROVAVEL", [["ZINCADO BRANCO", 0.80]], "escolher"),
    ("PRESENTE_FORA_DO_PADRAO", "INCLINADA", [["A", 0.8], ["B", 0.2]], "escolher"),
    ("PRESENTE_FORA_DO_PADRAO", "ABERTA", [["A", 0.4], ["B", 0.35]], "escolher"),
    # texto traz algo fora do padrao e nada se sustenta
    ("PRESENTE_FORA_DO_PADRAO", "SEM_CANDIDATO", [], "sem_pista"),
    ("PRESENTE_FORA_DO_PADRAO", "SEM_BASE", [], "sem_pista"),
    # o texto nao traz o dado: nao e trabalho de leitura
    ("AUSENTE", "", [], "enriquecer"),
    ("AUSENTE", "PROVAVEL", [["X", 0.99]], "enriquecer"),
])
def test_acao_por_veredito_e_banda(veredito, banda, cands, esperado):
    assert fila.acao_de(veredito, banda, cands) == esperado


def test_limiar_do_provavel_e_o_documentado():
    """O 90% esta escrito no cabecalho do script e aparece no JSON para a
    interface: mudar aqui sem mudar la deixaria a tela mentindo."""
    assert fila.LIMIAR_PROVAVEL == 0.90
    assert fila.acao_de("PRESENTE_FORA_DO_PADRAO", "PROVAVEL",
                        [["X", fila.LIMIAR_PROVAVEL]], ) == "um_clique"


def test_nota_valido_virou_candidato_de_um_clique():
    """'valido: 4MM2' na deteccao e o valor pronto: a interface mostra um botao."""
    m = fila.RE_VALIDO.search("grandeza MM sobrando · valido: 4MM2")
    assert m and m.group(1).strip() == "4MM2"


# ------------------------------------------------- honestidade da probabilidade
def test_perdido_nao_ganha_probabilidade_inventada():
    """Regressao: a primeira versao desta fila escrevia 1.0 no candidato vindo de
    'valido: X', e a tela mostrava um selo de 100% que nao media nada.

    PERDIDO e conversao de notacao ('SECAO 4MM' -> 4MM2): o candidato existe, a
    probabilidade nao. Quem mede acerto e o teste retroativo por faixa.
    """
    import json
    from pathlib import Path

    arq = Path(__file__).resolve().parents[1] / "artefatos/fila_intervencao.json"
    if not arq.exists():
        pytest.skip("fila_intervencao.json nao gerado nesta arvore")
    d = json.loads(arq.read_text(encoding="utf-8"))
    perdidos = [c for i in d["itens"] for c in i["campos"] if c["veredito"] == "PERDIDO"]
    assert perdidos, "a amostra exportada nao tem campo PERDIDO"
    for c in perdidos:
        for _valor, prob in c["candidatos"]:
            assert prob is None, f"{c['atributo']}: PERDIDO com probabilidade {prob}"

    # e o JSON tem de dizer o que o numero e, para a tela nao chamar de confianca
    cal = d["calibracao"]
    assert "fracao da distribuicao" in cal["o_que_e_a_probabilidade"]
    assert cal["acerto_medido"]["PROVAVEL"]["acerto"] == 0.96
    assert cal["acerto_medido"]["UNICO"]["acerto"] is None
