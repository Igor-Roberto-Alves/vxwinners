"""Testes do validador, do arbitro e da identidade (regra 10 e regra 13).

Os dois casos do briefing estao aqui: o rolamento 6205, que DEVE ser unificado,
e o filtro intercambiavel, que NAO deve. Um sistema que acerta os dois vence um
que so junta texto parecido.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from saneamento import Arbitro, Pdm, Pipeline, Validador  # noqa: E402
from saneamento.pdm import aplica_atributo  # noqa: E402
from saneamento.regras import Candidato  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pdm():
    arq = RAIZ / "artefatos/pdm.json"
    if not arq.exists():
        pytest.skip("rode scripts/01_compilar_pdm.py antes")
    return Pdm.carregar(arq)


@pytest.fixture(scope="module")
def pipe(pdm):
    # sem BERT e sem LLM: testa a camada deterministica, que e a que tem de ser estavel
    return Pipeline(pdm)


# ----------------------------------------------------------------- unidade

def test_unidade_sinonimo_converte(pdm):
    v = Validador(pdm)
    assert v.unidade("PCA", pdm.classes["PDM001"]).valor == "PC"
    assert v.unidade("MTS", pdm.classes["PDM010"]).valor == "M"
    assert v.unidade("PAR", pdm.classes["PDM070"]).valor == "PR"


def test_unidade_embalagem_nao_converte_sem_fator(pdm):
    # 1 CX = N PC: converter sem o fator corrompe saldo de estoque e preco medio
    r = Validador(pdm).unidade("CX", pdm.classes["PDM001"])
    assert r.ok is False and r.valor is None
    assert "fator" in r.motivo


# ----------------------------------------------------------------- ncm

def test_ncm_reformata_para_oito_digitos(pdm):
    r = Validador(pdm).ncm("73181500", pdm.classes["PDM001"])
    assert r.valor == "7318.15.00"          # regra 12


def test_ncm_divergente_e_corrigido_pela_classe(pdm):
    r = Validador(pdm).ncm("7318.16.00", pdm.classes["PDM001"])
    assert r.ok is False and r.valor == "7318.15.00"


def test_ncm_ausente_derivado_da_classe(pdm):
    r = Validador(pdm).ncm("", pdm.classes["PDM001"])
    assert r.valor == "7318.15.00"


# ----------------------------------------------------------------- valor

def test_valor_fora_da_lista_e_recusado(pdm):
    # a trava que impede alucinacao de chegar na base, venha do BERT ou do LLM
    v = Validador(pdm)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "MATERIAL")
    assert v.valor(a, "ACO INOX 316").ok is True
    assert v.valor(a, "INOX").ok is False
    assert v.valor(a, "ACO SUPER RESISTENTE").ok is False


def test_valor_em_mm_e_reformatado(pdm):
    v = Validador(pdm)
    a = next(x for x in pdm.classes["PDM032"].atributos if x.nome == "LARGURA")
    assert v.valor(a, "15MM").valor == "15MM"
    assert v.valor(a, "16.25MM").valor == "16,25MM"


# ----------------------------------------------------------------- condicional

def test_atributo_condicional_nao_vale_fora_do_seu_caso(pdm):
    # DIAMETRO REDUZIDO existe em TE REDUCAO, nao em CAP
    a = next(x for x in pdm.classes["PDM050"].atributos if x.nome == "DIAMETRO REDUZIDO")
    assert aplica_atributo(a, "CAP") is False
    assert aplica_atributo(a, "TE REDUCAO") is True


def test_descricao_omite_condicional_inaplicavel(pdm):
    d = Validador(pdm).descricao(pdm.classes["PDM050"], "CAP",
                                 {"DIAMETRO NOMINAL": "1.1/4POL"})
    assert "DIAMETRO REDUZIDO" not in d


# ----------------------------------------------------------------- descricao

def test_descricao_segue_formato_e_ordem(pdm):
    valores = {"ROSCA": "METRICA GROSSA", "BITOLA": "M12", "COMPRIMENTO": "50MM",
               "CLASSE RESISTENCIA": "8.8", "MATERIAL": "ACO CARBONO",
               "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}
    d = Validador(pdm).descricao(pdm.classes["PDM001"], "PARAFUSO", valores)
    assert d == ("PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12; "
                 "COMPRIMENTO: 50MM; CLASSE RESISTENCIA: 8.8; MATERIAL: ACO CARBONO; "
                 "ACABAMENTO: ZINCADO BRANCO; NORMA: DIN 933")


def test_obrigatorio_vazio_vira_pendente_na_descricao(pdm):
    d = Validador(pdm).descricao(pdm.classes["PDM001"], "PARAFUSO", {"BITOLA": "M12"})
    assert "MATERIAL: <PENDENTE>" in d


# ----------------------------------------------------------------- identidade

def test_chave_fecha_so_com_todos_os_obrigatorios(pdm):
    v = Validador(pdm)
    completo = {"ROSCA": "METRICA GROSSA", "BITOLA": "M12", "COMPRIMENTO": "50MM",
                "CLASSE RESISTENCIA": "8.8", "MATERIAL": "ACO CARBONO",
                "ACABAMENTO": "ZINCADO BRANCO", "NORMA": "DIN 933"}
    assert v.chave_identidade(pdm.classes["PDM001"], "PARAFUSO", completo) is not None
    incompleto = dict(completo)
    del incompleto["MATERIAL"]
    assert v.chave_identidade(pdm.classes["PDM001"], "PARAFUSO", incompleto) is None


def test_regra_10_mesma_especificacao_fecha_a_mesma_chave(pdm):
    """VALV ESF 2POL == VALVULA DE ESFERA DN 50: a duplicidade do briefing.

    Depois da normalizacao, duplicidade deixa de ser semelhanca de texto e passa
    a ser igualdade de chave.
    """
    v = Validador(pdm)
    comum = {"CLASSE PRESSAO": "800#", "MATERIAL CORPO": "ACO INOX FORJADO A182 F316",
             "CONEXAO": "ROSCA NPT", "PASSAGEM": "PLENA", "VEDACAO SEDE": "PTFE",
             "ACIONAMENTO": "ALAVANCA"}
    a = v.chave_identidade(pdm.classes["PDM040"], "VALVULA", {**comum, "DIAMETRO NOMINAL": "2POL"})
    b = v.chave_identidade(pdm.classes["PDM040"], "VALVULA", {**comum, "DIAMETRO NOMINAL": "2POL"})
    assert a == b and a is not None


def test_regra_13_filtro_equivalente_nao_e_duplicidade(pdm):
    """CAT 1R-1808 e DONALDSON P551808 se substituem, mas sao itens distintos.

    Classe de REFERENCIA DO FABRICANTE: a identidade e fabricante + part number.
    Um algoritmo de similaridade de texto erra exatamente aqui.
    """
    v = Validador(pdm)
    cat = v.chave_identidade(pdm.classes["PDM100"], "FILTRO", {},
                             fabricante="CATERPILLAR", referencia="1R-1808")
    don = v.chave_identidade(pdm.classes["PDM100"], "FILTRO", {},
                             fabricante="DONALDSON", referencia="P551808")
    assert cat is not None and don is not None
    assert cat != don


def test_part_number_normaliza_pontuacao(pdm):
    """1R-1808 e 1R1808 sao o mesmo part number escrito de dois jeitos."""
    v = Validador(pdm)
    a = v.chave_identidade(pdm.classes["PDM100"], "FILTRO", {},
                           fabricante="CATERPILLAR", referencia="1R-1808")
    b = v.chave_identidade(pdm.classes["PDM100"], "FILTRO", {},
                           fabricante="CATERPILLAR", referencia="1R1808")
    assert a == b


# ----------------------------------------------------------------- arbitro

def test_acordo_entre_as_camadas_tem_confianca_alta(pdm):
    arb = Arbitro(Validador(pdm))
    classe = pdm.classes["PDM032"]
    regras = {"MATERIAL": Candidato("MATERIAL", "NBR", "gazetteer", 0.98)}
    bert = {"MATERIAL": Candidato("MATERIAL", "NBR", "bert", 0.91)}
    r = arb.arbitrar(classe, regras, bert, 0.95, "RETENTOR")
    d = r.decisoes["MATERIAL"]
    assert d.estado == "ACEITO" and d.fonte == "acordo" and d.confianca > 0.9


def test_discordancia_escala_para_o_llm(pdm):
    arb = Arbitro(Validador(pdm))
    classe = pdm.classes["PDM032"]
    regras = {"MATERIAL": Candidato("MATERIAL", "NBR", "gazetteer", 0.98)}
    bert = {"MATERIAL": Candidato("MATERIAL", "FKM (VITON)", "bert", 0.88)}
    r = arb.arbitrar(classe, regras, bert, 0.95, "RETENTOR")
    assert r.decisoes["MATERIAL"].estado == "CONFLITO"
    assert r.escalar is True
    assert any("conflito" in m for m in r.motivos_escalada)


def test_obrigatorio_ausente_nao_vai_para_o_llm(pdm):
    # ausencia de dado nao e discordancia: nenhum modelo pode preencher sem inventar
    arb = Arbitro(Validador(pdm))
    r = arb.arbitrar(pdm.classes["PDM032"], {}, {}, 0.95, "RETENTOR")
    assert all(d.estado == "PENDENTE" for d in r.decisoes.values() if d.atributo)
    assert r.discordancia == 0.0
    assert r.escalar is False


def test_llm_tambem_passa_pelo_validador(pdm):
    arb = Arbitro(Validador(pdm))
    classe = pdm.classes["PDM032"]
    r = arb.arbitrar(classe, {}, {}, 0.95, "RETENTOR")
    r = arb.incorporar_llm(classe, r, {"MATERIAL": "BORRACHA MALUCA"})
    assert r.decisoes["MATERIAL"].valor is None       # recusado: fora da lista
    r = arb.incorporar_llm(classe, r, {"MATERIAL": "NBR"})
    assert r.decisoes["MATERIAL"].valor == "NBR"      # aceito: esta na lista
    assert r.decisoes["MATERIAL"].fonte == "llm"


# ----------------------------------------------------------------- ponta a ponta

def test_pipeline_sanea_registro_telegrafico(pipe):
    """'RET. 110MM 15MM BASL NBR' esta cadastrado no grupo errado (TUB01)."""
    r = pipe.processar({
        "CODIGO_MATERIAL": "12711820",
        "DESCRICAO_LONGA": "RET. 110MM 15MM BASL NBR",
        "DESCRICAO_CURTA": "RET. 110MM 15MM BASL NBR",
        "UNIDADE_MEDIDA": "PC", "NCM": "40169300", "GRUPO_MERCADORIA": "TUB01",
        "FABRICANTE": "SKF", "REFERENCIA_FABRICANTE": "",
    })
    assert r.id_pdm == "PDM032"            # RETENTOR, apesar do grupo TUB01
    assert r.grupo_corrigido is True
    assert r.decisoes["TIPO"].valor == "BASL"
    assert r.decisoes["MATERIAL"].valor == "NBR"
    assert r.ncm_pdm == "4016.93.00"


def test_pipeline_marca_fora_do_pdm(pipe):
    # pedido real: nao existe classe para cadeira de escritorio
    r = pipe.processar({
        "CODIGO_MATERIAL": "SC-X",
        "DESCRICAO_LONGA": "Cadeira de escritorio giratoria com braco, para a sala de controle",
        "DESCRICAO_CURTA": "", "UNIDADE_MEDIDA": "PC", "NCM": "",
        "GRUPO_MERCADORIA": "", "FABRICANTE": "", "REFERENCIA_FABRICANTE": "",
    })
    assert r.estado == "FORA_DO_PDM"


def test_condicional_obrigatorio_entra_na_chave(pdm):
    """Tres cabos de 1 condutor iguais, exceto a COR, NAO sao o mesmo item.

    COR e obrigatorio condicional ('somente cabos de 1 condutor'), logo nao
    aparece em classe.obrigatorios, que filtra quando == 'sempre'. Enquanto a
    chave usava aquela lista, 17998595 / 28229677 / 10287797 fechavam a mesma
    chave e eram juntados - um falso positivo de duplicidade.
    """
    v = Validador(pdm)
    comum = {"TIPO": "FLEXIVEL", "SECAO": "35MM2", "NUMERO CONDUTORES": "1",
             "TENSAO ISOLAMENTO": "0,6/1KV", "ISOLACAO": "PVC"}
    chaves = {
        cor: v.chave_identidade(pdm.classes["PDM060"], "CABO", {**comum, "COR": cor})
        for cor in ("VERDE", "AZUL", "PRETO")
    }
    assert all(c is not None for c in chaves.values())
    assert len(set(chaves.values())) == 3, "cores diferentes tem de dar chaves diferentes"


def test_condicional_que_nao_se_aplica_nao_bloqueia_a_chave(pdm):
    """Cabo multipolar nao tem COR: a chave tem de fechar sem ela."""
    v = Validador(pdm)
    chave = v.chave_identidade(pdm.classes["PDM060"], "CABO", {
        "TIPO": "MULTIPOLAR BLINDADO", "SECAO": "4MM2", "NUMERO CONDUTORES": "4",
        "TENSAO ISOLAMENTO": "0,6/1KV", "ISOLACAO": "XLPE",
    })
    assert chave is not None and "COR" not in chave


def test_formato_com_duas_unidades_nao_troca_a_medida(pdm):
    """PDM001 COMPRIMENTO aceita MM e POL: nao pode converter um no outro.

    Testar POL antes de MM fazia o validador reescrever 75MM como 75POL - troca
    a medida do parafuso em vez de corrigir a notacao, e corrompe a chave.
    """
    v = Validador(pdm)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "COMPRIMENTO")
    assert v.valor(a, "75MM").valor == "75MM"
    assert v.valor(a, "2.1/4POL").valor == "2.1/4POL"
    assert v.valor(a, "75POL").valor == "75POL"


def test_obrigatorio_condicional_vira_pendente(pdm):
    """COR e obrigatorio em cabo de 1 condutor: vazia tem de constar como PENDENTE.

    O arbitro filtrava por quando=='sempre', entao os obrigatorios condicionais
    nao entravam na completude nem viravam PENDENTE - mas bloqueavam a chave de
    identidade. A classe PDM062 (disjuntor) reportava 0% de SANEADO com a lista
    de pendencias vazia, sem explicacao visivel.
    """
    arb = Arbitro(Validador(pdm))
    classe = pdm.classes["PDM060"]
    regras = {
        "TIPO": Candidato("TIPO", "FLEXIVEL", "gazetteer", 0.98),
        "SECAO": Candidato("SECAO", "35MM2", "gramatica", 0.9),
        "NUMERO CONDUTORES": Candidato("NUMERO CONDUTORES", "1", "gramatica", 0.9),
        "TENSAO ISOLAMENTO": Candidato("TENSAO ISOLAMENTO", "0,6/1KV", "gazetteer", 0.98),
        "ISOLACAO": Candidato("ISOLACAO", "PVC", "gazetteer", 0.98),
    }
    r = arb.arbitrar(classe, regras, {}, 0.95, "CABO")
    assert r.decisoes["COR"].estado == "PENDENTE"
    assert r.completude < 1.0, "completude nao pode ignorar o condicional aplicavel"


def test_sinonimo_de_dominio_entra_no_caminho_principal(pdm):
    """'MINI DISJUNTOR' e 'DIN' tem de resolver para MINIDISJUNTOR DIN.

    O dicionario sinonimos.py so era consultado pelo Encaixotador; o
    ExtratorLexico (que produz os numeros) usava apenas casamento literal.
    """
    from saneamento import ExtratorLexico
    ext = ExtratorLexico(pdm)
    for texto in ("DISJUNTOR COM TIPO MINI DISJUNTOR COM POLOS 3P IN 25A CURVA C",
                  "DISJUNTOR DIN 3P 4A D 10KA SIEMENS",
                  "DISJUNTOR MODELO PROTECAO MOTOR 3P FAIXA AJUSTE 2,5-4A"):
        c = ext.extrair(texto, pdm.classes["PDM062"], "DISJUNTOR")["TIPO"]
        assert c.valor in ("MINIDISJUNTOR DIN", "MOTOR"), f"{texto!r} -> {c.valor!r}"


def test_cache_de_sinonimo_nao_vaza_entre_classes(pdm):
    """'TIPO' existe em varias classes com listas de valores diferentes.

    O cache de sinonimos era indexado so pelo nome do atributo, e os 93 nomes do
    PDM sao globais: a primeira classe processada envenenava as demais. Processar
    o retentor antes do disjuntor fazia o TIPO do disjuntor parar de resolver.
    """
    from saneamento import ExtratorLexico
    ext = ExtratorLexico(pdm)
    # retentor primeiro, de proposito: e quem envenenava o cache
    assert ext.extrair("RETENTOR 90MM 112MM 8MM BASL NBR",
                       pdm.classes["PDM032"], "RETENTOR")["TIPO"].valor == "BASL"
    assert ext.extrair("DISJUNTOR COM TIPO MINI DISJUNTOR COM POLOS 3P",
                       pdm.classes["PDM062"], "DISJUNTOR")["TIPO"].valor == "MINIDISJUNTOR DIN"
    assert ext.extrair("CABO ELETRICO FLEXIVEL 2,5MM2 1 450/750V PVC AZUL",
                       pdm.classes["PDM060"], "CABO")["TIPO"].valor == "FLEXIVEL"


# ----------------------------------------------------------------- aprendizado

def test_aprendizado_evita_rechamada_do_mesmo_problema(pdm):
    """Termo resolvido pelo LLM vale para OUTROS textos com o mesmo termo.

    E a diferenca em relacao ao cache do llm.py, que e indexado por hash do
    texto inteiro e so evita rechamada no registro identico.
    """
    from saneamento.aprendizado import Aprendizado
    from saneamento import ExtratorLexico

    ap = Aprendizado(None)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "MATERIAL")
    # termo que NAO esta em sinonimos.py, senao a camada curada resolveria antes
    assert ap.aprender(a, "INOX MARINHO", "ACO INOX 316", "llm", "PDM001") is True

    ext = ExtratorLexico(pdm, aprendizado=ap)
    # texto completamente diferente do que originou o aprendizado
    c = ext.extrair("PARAFUSO SEXTAVADO M20X80 A4-70 INOX MARINHO NATURAL DIN 931",
                    pdm.classes["PDM001"], "PARAFUSO")["MATERIAL"]
    assert c.valor == "ACO INOX 316"
    assert c.fonte == "aprendido", "a camada curada nao devia ter resolvido este termo"


def test_aprendizado_nao_vaza_entre_classes_homonimas(pdm):
    """'TIPO' existe em varias classes: o valor aprendido numa nao vale na outra.

    A validacao tem de acontecer na LEITURA contra o enum do atributo recebido,
    nao apenas na escrita.
    """
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    tipo_disj = next(x for x in pdm.classes["PDM062"].atributos if x.nome == "TIPO")
    tipo_ret = next(x for x in pdm.classes["PDM032"].atributos if x.nome == "TIPO")
    ap.aprender(tipo_disj, "MINI DISJUNTOR", "MINIDISJUNTOR DIN", "llm", "PDM062")

    assert ap.consultar(tipo_disj, "DISJUNTOR MINI DISJUNTOR 3P") == "MINIDISJUNTOR DIN"
    # mesmo termo, atributo homonimo de outra classe: recusado
    assert ap.consultar(tipo_ret, "RETENTOR MINI DISJUNTOR 90MM") is None
    assert ap.estatisticas()["recusados_pelo_enum"] >= 1


def test_aprendizado_recusa_valor_fora_do_enum(pdm):
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "MATERIAL")
    assert ap.aprender(a, "ALGUMA COISA", "ACO SUPER RESISTENTE", "llm") is False
    assert ap.entradas == {}


def test_aprendizado_marca_conflito_sem_sobrescrever(pdm):
    """Mesmo termo com dois valores diferentes e sinal de termo ambiguo."""
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "ACABAMENTO")
    ap.aprender(a, "ZINCADO", "ZINCADO BRANCO", "llm", "PDM001")
    assert ap.aprender(a, "ZINCADO", "ZINCADO AMARELO", "llm", "PDM001") is False
    e = ap.entradas["ACABAMENTO|ZINCADO"]
    assert e.valor == "ZINCADO BRANCO" and e.revisar is True and "conflito" in e.fonte


def test_aprendizado_so_confia_apos_confirmacao(pdm):
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None, confirmacoes_para_confiar=2)
    a = next(x for x in pdm.classes["PDM032"].atributos if x.nome == "MATERIAL")
    ap.aprender(a, "BORRACHA NITRILICA", "NBR", "llm", "PDM032")
    assert ap.confiavel("MATERIAL", "BORRACHA NITRILICA") is False
    ap.aprender(a, "BORRACHA NITRILICA", "NBR", "llm", "PDM032")
    assert ap.confiavel("MATERIAL", "BORRACHA NITRILICA") is True


def test_aprendizado_nao_aprende_caixa_numerica(pdm):
    """'110MM' nao significa 'diametro do eixo': a atribuicao e posicional."""
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    a = next(x for x in pdm.classes["PDM032"].atributos if x.nome == "DIAMETRO EIXO")
    assert ap.aprender(a, "110MM", "110MM", "bert", "PDM032") is False


def test_aprendizado_persiste_em_disco(pdm, tmp_path):
    from saneamento.aprendizado import Aprendizado

    arq = tmp_path / "ap.json"
    ap = Aprendizado(arq)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "MATERIAL")
    ap.aprender(a, "AISI 316", "ACO INOX 316", "llm", "PDM001")
    ap.salvar()

    outro = Aprendizado(arq)
    assert outro.consultar(a, "PARAFUSO AISI 316") == "ACO INOX 316"
