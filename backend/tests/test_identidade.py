import pytest

from app.identidade.chave import chave_identidade
from app.identidade.referencias import deduz_vedacao_folga, fabricante_canonico, referencia_generica, referencia_rolamento
from app.normalizacao.vocabulario import acha_no_texto, casa_lista


# ---------------------------------------------------------------- referências
@pytest.mark.parametrize("texto", ["SKF 6205-2RSH/C3", "FAG 6205-C-2HRS-C3", "NSK 6205DDUC3", "6205-2RS/C3"])
def test_rolamento_6205_tres_fabricantes_mesma_referencia(texto):
    assert referencia_rolamento(texto) == "6205-2RS/C3"


@pytest.mark.parametrize("texto", ["SKF 6310-2Z/C3", "FAG 6310-C-2Z-C3", "NTN 6310ZZC3"])
def test_rolamento_6310_mesma_referencia(texto):
    assert referencia_rolamento(texto) == "6310-2Z/C3"


def test_rolamentos_diferentes_nao_colidem():
    assert referencia_rolamento("6205-2RS/C3") != referencia_rolamento("6205-ZZ/C3")  # vedação difere
    assert referencia_rolamento("6205-2RS/C3") != referencia_rolamento("6205-2RS")  # folga difere
    assert referencia_rolamento("6206-2RS/C3") != referencia_rolamento("6205-2RS/C3")


def test_deduz_vedacao_e_folga_da_referencia():
    assert deduz_vedacao_folga("6205DDUC3") == {"VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"}
    assert deduz_vedacao_folga("6310-C-2Z-C3")["VEDACAO"] == "METALICA AMBOS LADOS"
    assert deduz_vedacao_folga("6205") == {}  # sem sufixo nao afirma nada


@pytest.mark.parametrize("a,b", [("1R-1808", "1R1808"), ("1R 1808", "1r1808"), ("LF 9009", "LF9009")])
def test_referencia_generica_ignora_separadores(a, b):
    assert referencia_generica(a) == referencia_generica(b)


def test_fabricante_canonico_com_alias():
    lista = ("BALDWIN", "CATERPILLAR", "DONALDSON", "FLEETGUARD")
    assert fabricante_canonico("CAT", lista) == "CATERPILLAR"
    assert fabricante_canonico("Donaldson", lista) == "DONALDSON"
    assert fabricante_canonico(None, lista) is None


# ---------------------------------------------------------------- chave (regra 10 e 13)
def _rol(ref, vedacao="BORRACHA AMBOS LADOS", folga="C3"):
    return {"REFERENCIA": ref, "VEDACAO": vedacao, "FOLGA": folga}


def test_caso_6205_une(pdm):
    c = [chave_identidade(pdm, "PDM020", "ROLAMENTO RIGIDO ESFERAS", _rol(r)) for r in
         ("SKF 6205-2RSH/C3", "FAG 6205-C-2HRS-C3", "NSK 6205DDUC3")]
    assert all(x.completa for x in c)
    assert len({x.texto for x in c}) == 1


def test_rolamento_com_folga_diferente_nao_une(pdm):
    a = chave_identidade(pdm, "PDM020", "ROLAMENTO RIGIDO ESFERAS", _rol("6205-2RS/C3"))
    b = chave_identidade(pdm, "PDM020", "ROLAMENTO RIGIDO ESFERAS", _rol("6205-2RS", folga="NORMAL"))
    assert a.texto != b.texto


def test_caso_filtro_equivalente_nao_une(pdm):
    """Regra 13: CAT 1R-1808 e DONALDSON P551808 se substituem, mas são itens distintos."""
    nome = "FILTRO OLEO LUBRIFICANTE"
    cat = chave_identidade(pdm, "PDM100", nome, {"FABRICANTE": "CATERPILLAR", "REFERENCIA FABRICANTE": "1R-1808"})
    don = chave_identidade(pdm, "PDM100", nome, {"FABRICANTE": "DONALDSON", "REFERENCIA FABRICANTE": "P551808"})
    assert cat.completa and don.completa and cat.texto != don.texto


def test_filtro_mesmo_fabricante_e_referencia_une(pdm):
    nome = "FILTRO OLEO LUBRIFICANTE"
    a = chave_identidade(pdm, "PDM100", nome, {"FABRICANTE": "CAT", "REFERENCIA FABRICANTE": "1R-1808"})
    b = chave_identidade(pdm, "PDM100", nome, {"FABRICANTE": "CATERPILLAR", "REFERENCIA FABRICANTE": "1R1808"})
    assert a.texto == b.texto


def test_chave_incompleta_acusa_o_que_falta(pdm):
    ch = chave_identidade(pdm, "PDM001", "PARAFUSO SEXTAVADO",
                          {"ROSCA": "METRICA GROSSA", "BITOLA": "M12", "COMPRIMENTO": "50MM", "ACABAMENTO": "ZINCADO BRANCO"})
    assert not ch.completa and ch.texto is None
    assert "CLASSE RESISTENCIA" in ch.faltando and "NORMA" in ch.faltando  # exatamente o caso do briefing


def test_condicional_obrigatorio_entra_na_chave(pdm):
    """Bug que a equipe encontrou: cabos iguais exceto pela cor não podem fechar a mesma chave."""
    base = {"TIPO": "FLEXIVEL", "SECAO": "35MM2", "NUMERO CONDUTORES": "1", "TENSAO ISOLAMENTO": "0,6/1KV", "ISOLACAO": "PVC"}
    a = chave_identidade(pdm, "PDM060", "CABO ELETRICO", {**base, "COR": "VERDE"})
    b = chave_identidade(pdm, "PDM060", "CABO ELETRICO", {**base, "COR": "AZUL"})
    assert a.completa and b.completa and a.texto != b.texto


# ---------------------------------------------------------------- vocabulário
ACABAMENTO = ("GALVANIZADO A FOGO", "NATURAL", "OXIDADO PRETO", "SEM ACABAMENTO", "ZINCADO AMARELO", "ZINCADO BRANCO", "ORGANOMETALICO")
MATERIAL = ("ACO CARBONO", "ACO INOX 304", "ACO INOX 316")
VEDACAO = ("ABERTO", "BORRACHA AMBOS LADOS", "METALICA AMBOS LADOS")


def test_casa_lista_exato_sinonimo_e_confianca():
    assert casa_lista(MATERIAL, "aço inox 316").valor == "ACO INOX 316"
    r = casa_lista(MATERIAL, "AISI 316")
    assert r.valor == "ACO INOX 316" and r.confianca == 0.95
    assert casa_lista(MATERIAL, "SS304").valor == "ACO INOX 304"
    assert casa_lista(VEDACAO, "2RSH").valor == "BORRACHA AMBOS LADOS"
    assert casa_lista(VEDACAO, "ddu").valor == "BORRACHA AMBOS LADOS"
    assert casa_lista(VEDACAO, "ZZ").valor == "METALICA AMBOS LADOS"


def test_galvanizado_sozinho_e_ambiguo():
    r = casa_lista(ACABAMENTO, "galvanizado")
    assert r.valor is None and "ZINCADO BRANCO" in r.candidatos and "GALVANIZADO A FOGO" in r.candidatos


def test_zincado_sozinho_tem_confianca_menor():
    r = casa_lista(ACABAMENTO, "zincado")
    assert r.valor == "ZINCADO BRANCO" and r.confianca < 0.9


def test_inox_316_nao_escolhe_entre_forjado_e_fundido():
    corpo = ("ACO INOX FORJADO A182 F316", "ACO INOX FUNDIDO A351 CF8M", "ACO CARBONO FORJADO A105")
    assert casa_lista(corpo, "INOX 316").valor is None  # exatamente o caso do briefing
    assert casa_lista(corpo, "A105").valor == "ACO CARBONO FORJADO A105"
    assert casa_lista(corpo, "CF8M").valor == "ACO INOX FUNDIDO A351 CF8M"


def test_acha_no_texto_livre_sem_falso_positivo():
    classe = ("5.8", "8.8", "10.9", "A2-70", "A4-70", "SAE GRAU 2")
    assert acha_no_texto(classe, "parafuso m16 x 60 galvanizado 8.8 din 933").valor == "8.8"
    assert acha_no_texto(classe, "m16 x 60").valor is None  # '8' solto nao vira valor
    norma = ("ASME B18.2.1", "DIN 931", "DIN 933")
    assert acha_no_texto(norma, "porca din 933 pra peneira").valor == "DIN 933"
    assert acha_no_texto(norma, "din 931 ou din 933").valor is None  # ambiguo
