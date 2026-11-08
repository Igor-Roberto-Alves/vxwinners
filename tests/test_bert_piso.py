# -*- coding: utf-8 -*-
"""Decodificacao BIO e o piso de probabilidade por palavra (src/saneamento/bert.py).

`agrupar_bio` vive fora da classe para poder ser testada sem torch e sem o
modelo de 500 MB: e ela que decide o que vira valor.

O que o piso resolve: o limiar que o pipeline ja tinha (LIMIAR_BERT = 0,60) e
sobre a MEDIA do span, e media esconde a palavra fraca. O recorte real
'INOX 316 EXTREMIDADES', com 0,88 / 0,99 / 0,31, da 0,73 e passa o limiar - o
que o barrou foi o enum do PDM, nao a confianca. Em caixa LIVRE (part number,
modelo) nao existe enum, e ali o piso e a unica trava.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

# importa o modulo direto: saneamento/__init__ puxa o ExtratorBert, que importa
# torch no __init__ da classe - e o teste nao precisa dele
import importlib.util

spec = importlib.util.spec_from_file_location(
    "bert_mod", RAIZ / "src/saneamento/bert.py")
bert_mod = importlib.util.module_from_spec(spec)
sys.modules["bert_mod"] = bert_mod
spec.loader.exec_module(bert_mod)
agrupar_bio = bert_mod.agrupar_bio


def rotular(pares):
    """[('3/8','B-DIAMETRO NOMINAL',0.97), ...] -> (tokens, por_palavra)."""
    tokens = [t for t, _, _ in pares]
    por_palavra = {i: (rot, p) for i, (_, rot, p) in enumerate(pares)}
    return tokens, por_palavra


def test_i_continua_o_span_do_b():
    tokens, pp = rotular([
        ("3/8", "B-DIAMETRO NOMINAL", 0.97),
        ("POL", "I-DIAMETRO NOMINAL", 0.88),
    ])
    (p,) = agrupar_bio(tokens, pp)
    assert p.atributo == "DIAMETRO NOMINAL"
    assert p.valor == "3/8 POL"
    assert p.confianca == (0.97 + 0.88) / 2


def test_b_fecha_o_span_anterior_do_mesmo_atributo():
    """Dois valores do mesmo atributo colados: e para isso que o B serve."""
    tokens, pp = rotular([
        ("FEMEA", "B-TERMINAL B", 0.77),
        ("BSP", "I-TERMINAL B", 0.84),
        ("FLANGE", "B-TERMINAL B", 0.35),
        ("6000PSI", "I-TERMINAL B", 0.42),
    ])
    a, b = agrupar_bio(tokens, pp)
    assert (a.valor, b.valor) == ("FEMEA BSP", "FLANGE 6000PSI")


def test_o_fecha_o_span():
    tokens, pp = rotular([
        ("INOX", "B-MATERIAL", 0.9),
        ("316", "I-MATERIAL", 0.9),
        ("ASME", "O", 1.0),
        ("SW", "B-CONEXAO", 0.8),
    ])
    a, b = agrupar_bio(tokens, pp)
    assert (a.valor, a.atributo) == ("INOX 316", "MATERIAL")
    assert (b.valor, b.atributo) == ("SW", "CONEXAO")


def test_sem_piso_a_palavra_fraca_entra_no_span():
    """Comportamento historico, que o piso 0 tem de preservar."""
    tokens, pp = rotular([
        ("INOX", "B-MATERIAL", 0.88),
        ("316", "I-MATERIAL", 0.99),
        ("EXTREMIDADES", "I-MATERIAL", 0.31),
    ])
    (p,) = agrupar_bio(tokens, pp, corte=0.0)
    assert p.valor == "INOX 316 EXTREMIDADES"
    # e passa o limiar de 0,60 do arbitro, porque a media dilui o 0,31
    assert round(p.confianca, 2) == 0.73


def test_piso_encurta_o_span_em_vez_de_engolir_a_palavra():
    tokens, pp = rotular([
        ("INOX", "B-MATERIAL", 0.88),
        ("316", "I-MATERIAL", 0.99),
        ("EXTREMIDADES", "I-MATERIAL", 0.31),
    ])
    (p,) = agrupar_bio(tokens, pp, corte=0.5)
    assert p.valor == "INOX 316"
    assert round(p.confianca, 3) == 0.935


def test_piso_derruba_o_span_que_abre_fraco():
    """B- abaixo do piso nao abre span: nada e afirmado."""
    tokens, pp = rotular([("MATERIAL", "B-FABRICANTE", 0.22)])
    assert agrupar_bio(tokens, pp, corte=0.5) == []
    assert len(agrupar_bio(tokens, pp, corte=0.0)) == 1


def test_piso_separa_o_que_estava_grudado():
    """Palavra fraca no meio: o span nao encurta, parte em dois."""
    tokens, pp = rotular([
        ("FEMEA", "B-TERMINAL A", 0.9),
        ("RETA", "I-TERMINAL A", 0.2),
        ("JIC", "I-TERMINAL A", 0.9),
    ])
    inteiro = agrupar_bio(tokens, pp, corte=0.0)
    assert inteiro[0].valor == "FEMEA RETA JIC"
    partido = agrupar_bio(tokens, pp, corte=0.5)
    assert [p.valor for p in partido] == ["FEMEA", "JIC"]


def test_i_sem_b_antes_ainda_abre_span():
    """Robustez do decodificador: o modelo as vezes emite I- sem B-."""
    tokens, pp = rotular([("A", "I-TERMINAL A", 0.83), ("JIC", "I-TERMINAL A", 0.86)])
    (p,) = agrupar_bio(tokens, pp)
    assert p.valor == "A JIC" and p.atributo == "TERMINAL A"
