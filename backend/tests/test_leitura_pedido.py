import pytest

from app.classes.resolver import IndiceClasses
from app.leitura.regras import campos_do_cadastro, le_pedido, prepara_texto


@pytest.fixture(scope="module")
def indice(pdm):
    return IndiceClasses(pdm)


def v(e, atr):
    return e.valores[atr].valor if atr in e.valores else None


def test_frase_corrida_do_briefing(pdm, indice):
    e, _, _ = le_pedido(pdm, indice, "preciso de 10 parafuso sextavado m16 x 60 galvanizado 8.8 din 933 pra peneira")
    assert e.id_pdm == "PDM001"
    assert (v(e, "BITOLA"), v(e, "COMPRIMENTO"), v(e, "ROSCA"), v(e, "CLASSE RESISTENCIA"), v(e, "NORMA")) == \
           ("M16", "60MM", "METRICA GROSSA", "8.8", "DIN 933")
    assert v(e, "ACABAMENTO") is None  # "galvanizado" e ambiguo: nao preenche
    assert all(x.origem == "PEDIDO_REGRA" for x in e.valores.values() if x.valor)
    assert "CLASSE RESISTENCIA" not in e.faltando(pdm) and "MATERIAL" in e.faltando(pdm)


def test_email_com_marcadores_e_unidades_misturadas(pdm, indice):
    email = ("Bom dia,\n\nPeço por favor cadastrar mangueira hidráulica montada, com as seguintes características:\n"
             "- Norma: EN 853 2SN\n- Diâmetro interno: 3/4\" (19 mm)\n- Pressão de trabalho: 215BAR\n- Comprimento: 2000 mm\n"
             "- Terminal a: FEMEA CURVA 90 GRAUS JIC\n- Terminal b: MACHO RETO NPT\n- Material terminais: aco carbono zincado\n\nObrigado,\nThiago")
    e, _, _ = le_pedido(pdm, indice, email)
    assert e.id_pdm == "PDM011"
    assert v(e, "DIAMETRO INTERNO") == "3/4POL"      # primeiro valor em polegada, nao "19 mm"
    assert v(e, "PRESSAO TRABALHO") == "215BAR" and v(e, "COMPRIMENTO") == "2000MM"
    assert v(e, "NORMA") == "EN 853 2SN"


def test_ficha_tecnica_so_o_anexo_vale(pdm, indice):
    anexo = "FICHA TÉCNICA\nProduto: Retentor\nDiametro eixo: 60 mm\nDiametro alojamento: 80 mm\nLargura: 15mm\nTipo: ba\nFabricante: FREUDENBERG"
    e, prep, campos = le_pedido(pdm, indice, "Segue ficha técnica em anexo.", anexo)
    assert "SEGUE" not in prep.upper()
    assert e.id_pdm == "PDM032"
    assert (v(e, "DIAMETRO EIXO"), v(e, "DIAMETRO ALOJAMENTO"), v(e, "LARGURA"), v(e, "TIPO")) == ("60MM", "80MM", "15MM", "BA")
    assert campos["fabricante"] == "FREUDENBERG"          # fica no campo proprio: regra 8
    assert "FABRICANTE" not in e.valores                   # RETENTOR e classe de especificacao


def test_catalogo_em_ingles_acha_a_classe(pdm, indice):
    e, _, _ = le_pedido(pdm, indice, "Novo item, linha do catálogo abaixo.",
                        "Generic | Ball valve | 1POL, 150#, A216 WCB, RF flanged, reduced bore, metal-metal, lever")
    assert e.id_pdm == "PDM040"
    assert v(e, "MATERIAL CORPO") == "ACO CARBONO FUNDIDO A216 WCB"


def test_pedido_fora_do_pdm_nao_inventa_classe(pdm, indice):
    e, _, _ = le_pedido(pdm, indice, "Cadeira de escritório giratória com braço, para a sala de controle")
    assert e.id_pdm is None and e.valores == {}


def test_caso_do_briefing_parafuso_sem_classe_de_resistencia(pdm, indice):
    e, _, _ = le_pedido(pdm, indice, "PARAFUSO SEXTAVADO M12X50 ZINCADO")
    assert "CLASSE RESISTENCIA" in e.faltando(pdm)


def test_campos_do_cadastro_ignoram_o_resto():
    assert campos_do_cadastro("Fabricante: SKF; Referencia: 6205-2RSH; Tipo: ba") == \
           {"fabricante": "SKF", "referencia_fabricante": "6205-2RSH"}


def test_prepara_texto_tira_marcadores_e_junta_linhas():
    assert prepara_texto("- a: 1\n• b: 2\n\nGeneric | Ball", None) == "a: 1; b: 2; Generic; Ball"


def test_rotulo_produto_manda_sobre_os_outros_valores(pdm, indice):
    """`Tipo: esfera` descreve a valvula de retencao; o nome do item vem do rotulo Produto."""
    anexo = "FICHA TÉCNICA\nProduto: Válvula Retencao\nDiâmetro nominal: 1 1/2\"\nClasse de pressão: PN 25\nConexão: rosca bsp\nTipo: esfera"
    e, _, _ = le_pedido(pdm, indice, "Segue ficha técnica em anexo.", anexo)
    assert e.id_pdm == "PDM043" and v(e, "DIAMETRO NOMINAL") == "1.1/2POL"


def test_produto_com_nome_curto_vindo_de_rotulo(pdm, indice):
    e, _, _ = le_pedido(pdm, indice, "Segue em anexo.", "FICHA TÉCNICA\nProduto: Cap\nDiâmetro nominal: 1\"\nClasse de pressão: 6000#")
    assert e.id_pdm == "PDM050" and e.nome == "CAP"


@pytest.mark.parametrize("linha,classe", [
    ("Generic | Hex head bolt | metrica grossa, M18, 100MM, 8.8, carbon steel, zinc plated, din 931", "PDM001"),
    ("DORMER | Twist drill | hss cobalto, 1,5MM, cilindrica, din 340", "PDM082"),
    ("TEADIT | Flat gasket | 10POL, 300#, epdm, 1,6MM, rf", "PDM034"),
    ("Generic | Socket head cap screw | cilindrica, M12, 25MM, a2-70, SS304, natural", "PDM002"),
])
def test_catalogo_em_ingles_mais_casos(pdm, indice, linha, classe):
    assert le_pedido(pdm, indice, "Novo item, linha do catálogo abaixo.", linha)[0].id_pdm == classe
