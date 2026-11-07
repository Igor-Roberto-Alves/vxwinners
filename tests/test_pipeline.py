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


# ------------------------------------------------- extracao em duas passadas

def test_pdm062_extrai_condicional_governado_pelo_tipo(pdm):
    """'IN 25A' e 'CURVA C' estao na linha e tem de ser lidos.

    A extracao avaliava aplica_atributo uma unica vez, com valores=None: os
    condicionais de PDM062 ('somente MINIDISJUNTOR DIN') dependem do TIPO, que
    so existe depois da primeira passada, entao nunca entravam na grade e nunca
    eram extraidos. O texto ia inteiro para a sobra e a classe ficava em 0% de
    SANEADO - a chave de identidade exigia justamente esses atributos.
    """
    from saneamento import ExtratorLexico

    ext = ExtratorLexico(pdm)
    c = ext.extrair("DISJUNTOR COM TIPO MINI DISJUNTOR COM POLOS 3P IN 25A CURVA C",
                    pdm.classes["PDM062"], "DISJUNTOR")
    assert c["TIPO"].valor == "MINIDISJUNTOR DIN"      # habilita os condicionais
    assert c["CORRENTE NOMINAL"].valor == "25A"
    assert c["CURVA"].valor == "C"
    assert "CAPACIDADE INTERRUPCAO" in c, "condicional aplicavel tem de ter caixa"
    assert c["CAPACIDADE INTERRUPCAO"].valor is None   # o texto nao diz: vazia, nao palpite
    # FAIXA AJUSTE e "somente disjuntor MOTOR": nao se aplica a um MINIDISJUNTOR
    assert "FAIXA AJUSTE" not in c


def test_pdm062_sem_tipo_nao_abre_condicional(pdm):
    """Sem TIPO nao ha o que habilitar: a segunda passada nao pode inventar caixa."""
    from saneamento import ExtratorLexico

    c = ExtratorLexico(pdm).extrair("DISJUNTOR 1P 25A D 6KA STECK",
                                    pdm.classes["PDM062"], "DISJUNTOR")
    assert c["TIPO"].valor is None
    for nome in ("CORRENTE NOMINAL", "CURVA", "CAPACIDADE INTERRUPCAO", "FAIXA AJUSTE"):
        assert nome not in c, f"{nome} nao se aplica sem TIPO"


def test_pdm062_faixa_ajuste_so_no_disjuntor_motor(pdm):
    """Cada TIPO abre o SEU condicional, nao todos."""
    from saneamento import ExtratorLexico

    c = ExtratorLexico(pdm).extrair("DISJUNTOR MODELO PROTECAO MOTOR 3P FAIXA AJUSTE 2,5-4A",
                                    pdm.classes["PDM062"], "DISJUNTOR")
    assert c["TIPO"].valor == "MOTOR"
    assert c["FAIXA AJUSTE"].valor == "2,5-4A"
    assert "CURVA" not in c and "CAPACIDADE INTERRUPCAO" not in c


def test_pdm062_fecha_a_chave_ponta_a_ponta(pipe):
    """O caso completo: cinco obrigatorias na linha, chave fechada, SANEADO.

    E o teste que prova que a correcao atravessa as tres camadas (extrator,
    arbitro e montagem): antes, a extracao nao lia os condicionais, o arbitro
    nao criava decisao para eles e chave_identidade - que SEMPRE os exigiu -
    devolvia None, deixando PDM062 em 0% de SANEADO.
    """
    r = pipe.processar({
        "CODIGO_MATERIAL": "13655449",
        "DESCRICAO_LONGA": "DISJUNTOR, TIPO:DIN, POLOS:2P, IN:25A, CURVA:C, ICU:4,5KA",
        "DESCRICAO_CURTA": "", "UNIDADE_MEDIDA": "PC", "NCM": "",
        "GRUPO_MERCADORIA": "ELE01", "FABRICANTE": "", "REFERENCIA_FABRICANTE": "",
    })
    assert r.id_pdm == "PDM062"
    assert r.decisoes["CORRENTE NOMINAL"].valor == "25A"
    assert r.decisoes["CURVA"].valor == "C"
    assert r.decisoes["CAPACIDADE INTERRUPCAO"].valor == "4,5KA"
    assert r.chave_identidade is not None
    assert "CURVA=C" in r.chave_identidade
    assert r.estado == "SANEADO"
    assert r.completude == 1.0


def test_condicional_vazio_derruba_a_completude_do_registro(pipe):
    """Obrigatoria condicional vazia nao pode ser contada como 100%.

    _montar recalculava a completude por classe.obrigatorios, que filtra
    quando=='sempre': o registro anunciava 1,000 de completude e PENDENTE ao
    mesmo tempo, sem nenhuma caixa que explicasse a pendencia.
    """
    r = pipe.processar({
        "CODIGO_MATERIAL": "10272132",
        "DESCRICAO_LONGA": "DISJUNTOR COM TIPO MINI DISJUNTOR COM POLOS 3P IN 25A CURVA C",
        "DESCRICAO_CURTA": "", "UNIDADE_MEDIDA": "PC", "NCM": "",
        "GRUPO_MERCADORIA": "ELE01", "FABRICANTE": "", "REFERENCIA_FABRICANTE": "",
    })
    assert r.pendentes == ["CAPACIDADE INTERRUPCAO"]
    assert r.completude < 1.0
    # Sanear nao e completar: o texto nao informa a capacidade de interrupcao,
    # entao o registro esta SANEADO (tudo o que o texto diz foi lido) mas
    # INCOMPLETO, e sem chave de identidade.
    assert r.chave_identidade is None
    assert r.estado == "SANEADO" and not r.completo


def test_cor_de_cabo_sobrevive_as_passadas(pdm):
    """A COR de cabo (condicional por CONDICAO_ESPECIAL) nao pode regredir.

    Restringir a primeira passada a quando=='sempre' faria COR cair fora da
    grade do cabo MULTIPOLAR - e chave_identidade conta com o valor preenchido
    mesmo quando o atributo nao se aplica, justamente para nao juntar tres
    cabos que diferem so na cor. Por isso a passada seguinte so ACRESCENTA
    caixa: nenhuma sai da grade depois de entrar.
    """
    from saneamento import ExtratorLexico

    ext = ExtratorLexico(pdm)
    um = ext.extrair("CABO ELETRICO FLEXIVEL 2,5MM2 1 450/750V PVC AZUL",
                     pdm.classes["PDM060"], "CABO")
    assert um["NUMERO CONDUTORES"].valor == "1"
    assert um["COR"].valor == "AZUL"

    multi = ext.extrair("CABO MULTIPOLAR BLINDADO 4MM2 4 0,6/1KV XLPE PRETO",
                        pdm.classes["PDM060"], "CABO")
    assert multi["NUMERO CONDUTORES"].valor == "4"
    assert multi["COR"].valor == "PRETO", "valor achado nao pode ser descartado"


def test_irmaos_de_grandeza_incluem_o_condicional(pdm):
    """DIAMETRO REDUZIDO disputa os POL com DIAMETRO NOMINAL, nao copia o dele.

    classe.obrigatorios deixava o condicional fora do conjunto de irmaos, e
    como irmao unico cada um pegava o PRIMEIRO numero do texto: os dois saiam
    com 1.1/4POL numa bucha de 1.1/4 x 1/2.
    """
    from saneamento import ExtratorLexico

    c = ExtratorLexico(pdm).extrair(
        "BUCHA REDUCAO 1.1/4POL 1/2POL 3000# ROSCA NPT ACO CARBONO FORJADO A105",
        pdm.classes["PDM050"], "BUCHA REDUCAO")
    assert c["DIAMETRO NOMINAL"].valor == "1.1/4POL"
    assert c["DIAMETRO REDUZIDO"].valor == "1/2POL"


def test_numero_unico_fica_com_a_caixa_que_sempre_existe(pdm):
    """Um numero e duas caixas: o 'sempre' mantem o valor, o condicional fica vazio.

    DIAMETRO e extraido na primeira passada, quando ESPESSURA ainda nao se
    aplica, e o valor nao e reextraido depois. Sem isso o disco de corte com
    uma unica medida perderia o diametro que ja estava certo - e o risco oposto
    (ESPESSURA receber o diametro) fica coberto porque, na passada em que ela
    entra, os dois disputam a mesma familia de grandeza.
    """
    from saneamento import ExtratorLexico

    c = ExtratorLexico(pdm).extrair("DISCO ABRASIVO CORTE 115MM ACO INOX",
                                    pdm.classes["PDM081"], "DISCO ABRASIVO")
    assert c["DIAMETRO"].valor == "115MM"
    assert c["ESPESSURA"].valor is None

    dois = ExtratorLexico(pdm).extrair("DISCO ABRASIVO CORTE 115MM 1,6MM ACO INOX",
                                       pdm.classes["PDM081"], "DISCO ABRASIVO")
    assert dois["DIAMETRO"].valor == "115MM"
    assert dois["ESPESSURA"].valor == "1,6MM"


def test_arbitro_julga_a_caixa_que_a_segunda_passada_abriu(pdm):
    """O arbitro tem de reconhecer a caixa condicional, senao descarta o candidato.

    aplicaveis era calculado com valores=None: o candidato 'CURVA C' chegava do
    extrator e era jogado fora por nao ter decisao correspondente.
    """
    arb = Arbitro(Validador(pdm))
    classe = pdm.classes["PDM062"]
    regras = {
        "TIPO": Candidato("TIPO", "MINIDISJUNTOR DIN", "sinonimo", 0.94),
        "POLOS": Candidato("POLOS", "3P", "gazetteer", 0.98),
        "CORRENTE NOMINAL": Candidato("CORRENTE NOMINAL", "25A", "gramatica", 0.90),
        "CURVA": Candidato("CURVA", "C", "gazetteer", 0.98),
    }
    r = arb.arbitrar(classe, regras, {}, 0.95, "DISJUNTOR")
    assert r.decisoes["CURVA"].valor == "C"
    assert r.decisoes["CURVA"].estado == "ACEITO"
    # a que se aplica e nao veio e pendencia, e entra no denominador
    assert r.decisoes["CAPACIDADE INTERRUPCAO"].estado == "PENDENTE"
    assert "CAPACIDADE INTERRUPCAO" in r.obrigatorios
    assert r.completude == 0.8
    # FAIXA AJUSTE e so de disjuntor MOTOR: nao existe caixa para ela aqui
    assert "FAIXA AJUSTE" not in r.decisoes


def test_grade_abre_caixa_condicional_e_a_marca_obrigatoria(pdm):
    """A grade nao pode dizer 'tudo_bate' com obrigatoria condicional vazia.

    grade_vazia monta as caixas com aplica_atributo sem valores e marca
    obrigatoria so em quando=='sempre'. O disjuntor 10272132 saia com
    'completude 100%, tudo_bate: True' e duas caixas de fora, no mesmo registro
    que o pipeline marcava PENDENTE.
    """
    from saneamento.encaixotador import Encaixotador

    g = Encaixotador(pdm).encaixotar({
        "CODIGO_MATERIAL": "10272132",
        "DESCRICAO_LONGA": "DISJUNTOR COM TIPO MINI DISJUNTOR COM POLOS 3P IN 25A CURVA C",
        "DESCRICAO_CURTA": "", "GRUPO_MERCADORIA": "ELE01",
        "FABRICANTE": "", "REFERENCIA_FABRICANTE": "",
    })
    assert g.caixas["CURVA"].valor == "C"
    assert g.caixas["CORRENTE NOMINAL"].valor == "25A"
    assert g.caixas["CAPACIDADE INTERRUPCAO"].obrigatoria is True
    assert g.pendentes == ["CAPACIDADE INTERRUPCAO"]
    assert g.tudo_bate is False
    assert g.completude < 1.0
    # a ordem da grade continua sendo a coluna ORDEM do PDM
    assert list(g.caixas) == ["TIPO", "POLOS", "CORRENTE NOMINAL", "CURVA",
                              "CAPACIDADE INTERRUPCAO"]


def test_teto_de_passadas_nao_corta_nenhuma_classe(pdm, monkeypatch):
    """O teto de 3 passadas e limite de seguranca, nao limite de alcance.

    O laco e limitado de proposito: as condicoes do PDM nao sao monotonas
    ('somente X' fica mais aplicavel quando o contexto cresce, 'todas, exceto X'
    fica menos), e um par dessas duas se alternaria para sempre. Mas o teto so
    pode existir se nenhuma classe real precisar de mais que ele - senao estaria
    truncando extracao em silencio, que e o bug que esta correcao veio consertar.
    Elevar o teto a 10 tem de dar exatamente o mesmo resultado.
    """
    from saneamento import ExtratorLexico
    from saneamento import regras as mod

    assert mod.PASSADAS_CONDICIONAL == 3
    texto_rico = "25A 115MM 1,6MM 1/2POL CURVA C 6KA CORTE FLAP 1 PVC AZUL M6 SCH 40"
    for classe in pdm.classes.values():
        subst = classe.substantivos[0] if classe.substantivos else ""
        alvo = f"{subst} {texto_rico}"

        com_teto = set(ExtratorLexico(pdm).extrair(alvo, classe, subst))
        monkeypatch.setattr(mod, "PASSADAS_CONDICIONAL", 10)
        sem_teto = set(ExtratorLexico(pdm).extrair(alvo, classe, subst))
        monkeypatch.setattr(mod, "PASSADAS_CONDICIONAL", 3)

        assert com_teto == sem_teto, f"{classe.id_pdm} nao estabilizou em 3 passadas"


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


def test_confiavel_responde_pelo_valor_canonico(pdm):
    """`ExtratorLexico` pergunta com o VALOR, nao com o termo que casou.

    Sem isso, toda entrada aprendida era reportada como 'a revisar' e a
    confianca do candidato ficava presa em 0,80 mesmo apos confirmacao.
    """
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None, confirmacoes_para_confiar=2)
    a = next(x for x in pdm.classes["PDM032"].atributos if x.nome == "MATERIAL")
    ap.aprender(a, "BORRACHA NITRILICA", "NBR", "llm", "PDM032")
    assert ap.confiavel("MATERIAL", "NBR") is False     # uma confirmacao so
    ap.aprender(a, "BORRACHA NITRILICA", "NBR", "llm", "PDM032")
    assert ap.confiavel("MATERIAL", "NBR") is True
    assert ap.confiavel("MATERIAL", "EPDM") is False    # nunca aprendido


def test_consultar_prefere_o_termo_mais_longo(pdm):
    """'ACO INOX 316' tem de vencer 'INOX' no mesmo texto."""
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "MATERIAL")
    ap.aprender(a, "INOX MARINHO", "ACO INOX 316", "llm", "PDM001")
    ap.aprender(a, "AISI 304", "ACO INOX 304", "llm", "PDM001")
    assert ap.consultar(a, "PARAFUSO INOX MARINHO") == "ACO INOX 316"
    assert ap.consultar(a, "PARAFUSO AISI 304") == "ACO INOX 304"
    # entrada nova nao pode ficar invisivel atras do indice em cache
    ap.aprender(a, "A2 70", "ACO INOX 304", "llm", "PDM001")
    assert ap.consultar(a, "PARAFUSO A2 70") == "ACO INOX 304"


def test_aprendizado_nao_aprende_caixa_numerica(pdm):
    """'110MM' nao significa 'diametro do eixo': a atribuicao e posicional."""
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    a = next(x for x in pdm.classes["PDM032"].atributos if x.nome == "DIAMETRO EIXO")
    assert ap.aprender(a, "110MM", "110MM", "bert", "PDM032") is False


def test_revalidar_limpa_dicionario_antigo(pdm):
    """Termo gravado antes de a trava existir nao pode seguir sendo consultado.

    As travas sao de escrita, mas o arquivo sobrevive ao codigo: sem revalidar,
    'CLASSE RESISTENCIA 12.9 -> 10.9' continuaria respondendo para sempre.
    """
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    cr = next(x for x in pdm.classes["PDM001"].atributos
              if x.nome == "CLASSE RESISTENCIA")
    bit = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "BITOLA")
    assert ap.aprender(cr, "12.9", "10.9", "llm", "PDM001") is True
    assert ap.aprender(bit, "M-12", "M12", "llm", "PDM001") is True
    assert len(ap.entradas) == 2

    fora = ap.revalidar(pdm)
    assert [e.termo for e, _m in fora] == ["12.9"]
    assert "gemeo numerico" in fora[0][1]
    assert len(ap.entradas) == 1
    # BITOLA e grandeza, nao vocabulario: fica
    assert ap.consultar(bit, "PARAFUSO M-12 X 50") == "M12"
    assert ap.consultar(cr, "PARAFUSO 12.9") is None


def test_substantivo_e_nome_de_caixa_nao_viram_termo(pdm):
    """As duas entradas de maior alcance e menor sentido da amostra.

    'PARAFUSO' entrou como MATERIAL 'ACO CARBONO' e como ACABAMENTO 'SEM
    ACABAMENTO', casando em 400 dos 3.000 registros: e o sujeito da classe, nao
    valor de caixa. 'ACABAMENTO' entrou como valor do proprio ACABAMENTO, vindo
    do BERT recortando o rotulo de 'ACABAMENTO: ZINCADO'.
    """
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "ACABAMENTO")
    mat = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "MATERIAL")

    # nome da propria caixa: barrado na escrita
    assert ap.aprender(a, "ACABAMENTO", "SEM ACABAMENTO", "bert", "PDM001") is False

    # substantivo da classe: sem o PDM em maos, so a revalidacao pega
    assert ap.aprender(mat, "PARAFUSO", "ACO CARBONO", "llm", "PDM001") is True
    fora = ap.revalidar(pdm)
    assert [e.termo for e, _m in fora] == ["PARAFUSO"]
    assert "substantivo" in fora[0][1]
    assert ap.entradas == {}

    # com o PDM entregue ao construtor, barra ja na escrita
    com_pdm = Aprendizado(None, pdm=pdm)
    assert com_pdm.aprender(mat, "PARAFUSO", "ACO CARBONO", "llm", "PDM001") is False
    assert com_pdm.entradas == {}
    # e nao estorva termo legitimo da mesma classe
    assert com_pdm.aprender(mat, "AISI 316", "ACO INOX 316", "llm", "PDM001") is True


def test_rotulo_interno_do_pipeline_nao_vira_termo(pdm):
    """'DICIONARIO APRENDIDO' como termo e o dicionario se contaminando.

    `regras.py` grava a string 'dicionario aprendido' no campo evidencia quando
    e o proprio aprendido que resolveu a caixa. Se o LLM depois sobrescreve essa
    caixa sem devolver evidencia, `incorporar_llm` cai no fallback
    `d.evidencia` e o rotulo de procedencia do dicionario volta como CHAVE do
    dicionario. Mesmo caminho para 'coluna FABRICANTE' (pipeline.py) e
    'notacao compacta ...' (regras.py).
    """
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None, pdm=pdm)
    acab = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "ACABAMENTO")
    rosca = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "ROSCA")
    fab = next(x for x in pdm.classes["PDM110"].atributos if x.nome == "FABRICANTE")

    assert ap.aprender(acab, "dicionario aprendido", "OXIDADO PRETO", "llm", "PDM001") is False
    assert ap.aprender(rosca, "notacao compacta M<bitola>X<comprimento>",
                       "METRICA GROSSA", "llm", "PDM001") is False
    assert ap.aprender(fab, "coluna FABRICANTE", "METSO", "llm", "PDM110") is False
    assert ap.entradas == {}


def test_sujeito_abreviado_nao_vira_termo(pdm):
    """'ARR LISA' e o sujeito (arruela lisa), nao um acabamento.

    A entrada aplicaria SEM ACABAMENTO a toda arruela lisa da base, que e
    inferencia sobre o produto e nao leitura do texto. A trava de substantivo
    exato nao pega porque o texto abrevia: 'ARR' != 'ARRUELA'.
    """
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None, pdm=pdm)
    acab = next(x for x in pdm.classes["PDM004"].atributos if x.nome == "ACABAMENTO")
    assert ap.aprender(acab, "ARR LISA", "SEM ACABAMENTO", "llm", "PDM004") is False

    # abreviacao legitima de VALOR, na mesma caixa, continua entrando
    assert ap.aprender(acab, "ZB", "ZINCADO BRANCO", "llm", "PDM004") is True


def test_revalidar_limpa_termo_em_caixa_de_grandeza(pdm):
    """A regra de termo vale fora do portao de vocabulario.

    BITOLA nao e vocabulario puro, entao as travas de enum nao a alcancam - e
    era por isso que BITOLA 'DICIONARIO APRENDIDO' -> '1POL' sobrevivia a
    limpeza, pulada antes de qualquer checagem.
    """
    from saneamento.aprendizado import Aprendizado, Entrada

    # Entrada gravada por uma versao anterior, antes da trava existir: e esse o
    # caso que revalidar() atende, e por isso ela entra pelo dicionario e nao
    # por aprender(), que hoje ja barraria.
    ap = Aprendizado(None)
    e = Entrada(atributo="BITOLA", termo="DICIONARIO APRENDIDO", valor="M12",
                fonte="llm", classes=["PDM001"])
    ap.entradas[e.chave] = e

    fora = ap.revalidar(pdm)
    assert [e.termo for e, _m in fora] == ["DICIONARIO APRENDIDO"]
    assert "rotulo interno" in fora[0][1]
    assert ap.entradas == {}


def test_aprendizado_persiste_em_disco(pdm, tmp_path):
    from saneamento.aprendizado import Aprendizado

    arq = tmp_path / "ap.json"
    ap = Aprendizado(arq)
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "MATERIAL")
    ap.aprender(a, "AISI 316", "ACO INOX 316", "llm", "PDM001")
    ap.salvar()

    outro = Aprendizado(arq)
    assert outro.consultar(a, "PARAFUSO AISI 316") == "ACO INOX 316"


# -------------------------------------------- lacuna de vocabulario do sujeito
# Os 718 registros FORA_DO_PDM (3,0%) nao eram item sem classe: eram o
# substantivo escrito de um jeito que o PDM nao lista. Cada caso abaixo e um
# registro REAL da base, copiado com o codigo de material, que antes do bloco de
# SINONIMO_SUJEITO correspondente ficava sem classe nenhuma.

SUJEITO_RECUPERADO = [
    # (codigo, grupo, unidade, ncm, descricao_longa, classe esperada)
    ("13031016", "VED01", "PC", "40169300",
     "O-RING, SECAO TRANSV:2MM, FKM (VITON), DUREZA:70 SHORE A",
     "PDM031"),                                   # O-RING -> ANEL O-RING
    ("16163552", "ELE01", "PC", "85364900",
     "CONTACTOR 220VCA 1NF",
     "PDM063"),                                   # CONTACTOR -> CONTATOR
    ("14205660", "TUB01", "PC", "7307.23.00",
     "T REDUCAO COM BITOLA DN 65, DIAMETRO REDUZIDO DE 1,25POL, COM SCHEDULE"
     " SCH 10S, ACO INOX A403 WP316, EXTREMIDADE BUTT WELD, NORMA CONSTRUCAO"
     " DE ASME B16.9",
     "PDM050"),                                   # T REDUCAO -> TE REDUCAO
    ("14848482", "TUB01", "PC", "7307.99.00",
     "TAMPAO, BITOLA:1POL, CL:6000#, MATERIAL:A105, EXTREMIDADES:RSC NPT,"
     " NORMA CONSTRUCAO:ASME B16.11",
     "PDM050"),                                   # TAMPAO -> CAP
    ("26122267", "TUB01", "PC", "73072900",
     "COTOV 90 GRAUS DIAMETRO DE DN15 MAT DE A182 F316 COM TIPO CONEXAO"
     " SOLDA ENCAIXE SW ASME B16.11",
     "PDM050"),                                   # COTOV -> COTOVELO 90 GRAUS
    ("14568532", "TUB01", "PC", "7307.91.00",
     "FLG PESCOCO WN 2POL 300# ACO CARBONO FORJADO A105 ASME B16.5",
     "PDM050"),                                   # FLG -> FLANGE
    ("14849568", "TUB01", "PC", "7307.99.00",
     "NIPPLE, EXTREMIDADE:NPT, CLASSE:3000#, ACO CARBONO FORJADO A105,"
     " DIAM:1/2 IN",
     "PDM050"),                                   # NIPPLE -> NIPLE
    ("12206609", "EPI01", "PR", "6403.9990",
     "BOTINA SEGURANCA, TIPO:BOTINA ELASTICO, TAMANHO:34, BIQUEIRA:NAO"
     " METALICA, PU MONODENSIDADE, COR:PRETA, CERT APROVACAO:30135",
     "PDM071"),                                   # BOTINA -> CALCADO SEGURANCA
    ("18045503", "FIX01", "PC", "73181600",
     "PCA MODELO DE SEXTAVADA COM ROSCA ROSCA GROSSA M20 GRAU DE 5 CARBONO"
     " TRATAMENTO DE GF NORMA DIN 934",
     "PDM003"),                                   # PCA -> PORCA
    ("20782603", "ELE01", "M", "85444900",
     "CONDUTOR ELETRICO, TENSAO:0,6/1KV, BITOLA:6 MM2, CONDUTORES:1,"
     " TIPO:FLEXIVEL, ISOLACAO:HEPR, COR:PRETO",
     "PDM060"),                                   # CONDUTOR -> CABO ELETRICO
    ("22806497", "ELE01", "PC", "85361000",
     "FUS;DIAZED;TAM.:D II;CORR NOM:4 A;CLASSE:RAPIDO",
     "PDM064"),                                   # FUS -> FUSIVEL
]


@pytest.mark.parametrize("codigo,grupo,unidade,ncm,descricao,esperado",
                         SUJEITO_RECUPERADO)
def test_sinonimo_de_sujeito_recupera_registro_real(
        pipe, codigo, grupo, unidade, ncm, descricao, esperado):
    r = pipe.processar({
        "CODIGO_MATERIAL": codigo,
        "DESCRICAO_LONGA": descricao,
        "DESCRICAO_CURTA": descricao[:40],
        "UNIDADE_MEDIDA": unidade, "NCM": ncm, "GRUPO_MERCADORIA": grupo,
        "FABRICANTE": "", "REFERENCIA_FABRICANTE": "",
    })
    assert r.estado != "FORA_DO_PDM"
    assert r.id_pdm == esperado


def test_vergalhao_tensora_e_barra_tensora_com_grupo_corrigido(pipe):
    """Chave de duas palavras: VERGALHAO sozinho e BARRA ROSCADA em FIX01.

    O registro esta cadastrado em ROL01 (rolamentos) e e peca de peneira
    vibratoria, ou seja PDM110 (SOB01): corrigir o grupo faz parte da entrega.
    """
    r = pipe.processar({
        "CODIGO_MATERIAL": "20095446",
        "DESCRICAO_LONGA": "VERGALHAO TENSORA, FABRICANTE:FLSMIDTH, MODELO"
                           " EQUIPAMENTO:LUDOWICI 3.6X8.5, APLICACAO:PENEIRA"
                           " VIBRATORIA, P/N:7823559159",
        "DESCRICAO_CURTA": "VERGALHAO TENSORA FLSMIDTH MODELO EQUIPA",
        "UNIDADE_MEDIDA": "PC", "NCM": "84749000", "GRUPO_MERCADORIA": "ROL01",
        "FABRICANTE": "FLSMIDTH", "REFERENCIA_FABRICANTE": "",
    })
    assert r.id_pdm == "PDM110"
    assert r.grupo_corrigido is True


def test_jta_corrige_junta_espiralada_que_caia_em_anel_oring(pipe):
    """JTA -> JUNTA tambem CORRIGE classe errada, nao so recupera sem classe.

    40 juntas espiraladas da base vinham como PDM031 (ANEL O-RING) porque a
    unica palavra do PDM no texto era o ANEL de 'ANEL INTERNO SEM ANEL INTERNO'.
    Com JUNTA no texto, JUNTA+ESPIRALADA pesa mais que ANEL sozinho.
    """
    r = pipe.processar({
        "CODIGO_MATERIAL": "20700664",
        "DESCRICAO_LONGA": "JTA ESPIRALADA, DIAM NOMINAL 14POL, CL 300#,"
                           " MATERIAL FITA ACO INOX 304, ENCHIMENTO TEFLON,"
                           " ANEL INTERNO SEM ANEL INTERNO, CONF ASME B16.20",
        "DESCRICAO_CURTA": "JTA ESPIRALADA DIAM 14POL CL 300# FITA A",
        "UNIDADE_MEDIDA": "CT", "NCM": "8484.10.00", "GRUPO_MERCADORIA": "VED01",
        "FABRICANTE": "", "REFERENCIA_FABRICANTE": "",
    })
    assert r.id_pdm == "PDM033"


def test_sinonimo_de_sujeito_nao_atravessa_grupo_de_mercadoria(pdm):
    """LUVA e o unico risco C do PDM: PDM070 (EPI) e PDM050 (TUB01).

    Nenhuma entrada de SINONIMO_SUJEITO pode criar ou destruir a palavra LUVA,
    senao uma luva de seguranca viraria conexao de tubo (ou o contrario).
    """
    from saneamento.sinonimos import SINONIMO_SUJEITO, expandir_sujeito

    for de, para in SINONIMO_SUJEITO.items():
        assert "LUVA" not in de.split(), f"{de!r} mexe em LUVA"
        assert "LUVA" not in para.split(), f"{de!r} -> {para!r} cria LUVA"

    assert "LUVA" in expandir_sujeito(
        "LUVA SEGURANCA TAMANHO 9 VAQUETA").split()
    assert "LUVA" in expandir_sujeito(
        "LUVA REDUCAO 1POL 3000# A105 NPT ASME B16.11").split()


def test_termo_curto_t_casa_so_token_solto(pdm):
    """'T' e o termo curto do docs/05-riscos-pdm.md: tem de casar so o token.

    A troca e feita com espaco nos dois lados, entao nao pode entrar dentro de
    TE, TUBO, PTFE nem de uma medida. Medido na base inteira: recupera 42
    registros e nao troca a classe de nenhum registro ja classificado.
    """
    from saneamento.sinonimos import expandir_sujeito

    assert expandir_sujeito("T REDUCAO DN50 1POL 6000#").startswith("TE REDUCAO")
    assert expandir_sujeito("T 6POL SCHEDULE DE SCH 40S").startswith("TE 6POL")
    for intocado in ("TUBO ACO 6POL SCH 40",
                     "TE 1POL 3000# A105",
                     "JUNTA PLANA PTFE EXPANDIDO 3MM",
                     "TERMINAL ELETRICO TUBULAR 6MM2"):
        assert expandir_sujeito(intocado) == intocado, intocado
# -------------------------------------------------- saida do LLM (sem chamada)
#
# Nada aqui chama o Bedrock: sao as funcoes puras que tratam o que o modelo
# devolveu. Todos os casos sao resposta REAL do Haiku 4.5 na base, colhida com
# scripts/04_extrair.py, e nao hipotese.

def test_evidencia_com_underscore_casa_com_o_nome_do_atributo(pdm):
    """'MODELO_EQUIPAMENTO' tem de virar 'MODELO EQUIPAMENTO'.

    `evidencias` e o unico campo livre da resposta - nao passa pelo enum do
    schema -, e o modelo troca o espaco por underscore. Sem este casamento o
    dicionario nunca aprendia o par mais valioso do dominio.
    """
    from saneamento.llm import _limpar_evidencias

    classe = pdm.classes["PDM110"]
    texto = "BOMBA CENTRIFUGA AHLSTAR A2280 SULZER ACO"
    limpas = _limpar_evidencias(
        classe, texto,
        {"MODELO EQUIPAMENTO": "AHLSTAR A22-80"},
        {"MODELO_EQUIPAMENTO": "AHLSTAR A2280"},
    )
    assert limpas == {"MODELO EQUIPAMENTO": "AHLSTAR A2280"}


def test_evidencia_de_justificativa_e_descartada(pdm):
    """O modelo usa o campo para explicar o null; isso nao e trecho de texto."""
    from saneamento.llm import _limpar_evidencias

    classe = pdm.classes["PDM001"]
    texto = "PARAFUSO SEXTAVADO M12X50 ACO CARBONO ZINCADO"
    limpas = _limpar_evidencias(
        classe, texto,
        {"ACABAMENTO": None, "MATERIAL": "ACO CARBONO"},
        {"ACABAMENTO": "ZINCADO e ambiguo entre AMARELO e BRANCO",
         "MATERIAL": "ACO CARBONO"},
    )
    assert limpas == {"MATERIAL": "ACO CARBONO"}


def test_evidencia_que_nao_esta_no_texto_e_descartada(pdm):
    """Unica verificacao objetiva possivel: o trecho tem de ser subcadeia do texto."""
    from saneamento.llm import _limpar_evidencias

    classe = pdm.classes["PDM001"]
    texto = "PARAFUSO SEXTAVADO M12X50"
    limpas = _limpar_evidencias(
        classe, texto, {"MATERIAL": "ACO CARBONO"}, {"MATERIAL": "ACO CARBONO"})
    assert limpas == {}, "valor nao escrito no texto nao pode virar termo"


def test_evidencia_igual_a_descricao_inteira_e_descartada(pdm):
    """Termo que e a descricao toda nao generaliza: seria copia do cache por hash."""
    from saneamento.llm import _limpar_evidencias

    classe = pdm.classes["PDM110"]
    texto = "CHAPA DE DESGASTE TC12"
    limpas = _limpar_evidencias(
        classe, texto,
        {"REFERENCIA FABRICANTE": "CHAPA DE DESGASTE TC12"},
        {"REFERENCIA FABRICANTE": "CHAPA DE DESGASTE TC12"},
    )
    assert limpas == {}


def test_trecho_ambiguo_nao_vira_valor_mesmo_sendo_valido(pdm):
    """O erro que o validador NAO pega, e por isso o unico que precisa de codigo.

    'ZINCADO' serve a ZINCADO AMARELO e a ZINCADO BRANCO. O modelo completa para
    BRANCO, que e valor valido do PDM e passa pelo validador intacto. Trocar
    304 por 316 pelo mesmo mecanismo cria item que alguem compra e instala.
    """
    from saneamento.llm import _vetar_ambiguos

    classe = pdm.classes["PDM001"]
    texto = "PARAFUSO SEXTAVADO M12X50 ACO CARBONO ZINCADO"
    valores = {"ACABAMENTO": "ZINCADO BRANCO", "MATERIAL": "ACO CARBONO"}
    evid = {"ACABAMENTO": "ZINCADO", "MATERIAL": "ACO CARBONO"}
    _vetar_ambiguos(classe, texto, valores, evid)
    assert valores["ACABAMENTO"] is None
    assert "ACABAMENTO" not in evid, "evidencia vetada nao pode alimentar o dicionario"
    # MATERIAL fica: 'ACO CARBONO' alcanca um unico valor do enum
    assert valores["MATERIAL"] == "ACO CARBONO"


def test_trecho_ambiguo_so_em_outra_classe_e_aceito(pdm):
    """A mesma abreviacao decide ou nao conforme o enum DAQUELA classe.

    PDM005 tem ZINCADO BRANCO como unico zincado, entao 'ZINC' distingue. Em
    PDM001, que tem AMARELO e BRANCO, o mesmo 'ZINC' nao distingue.
    """
    from saneamento.llm import _vetar_ambiguos

    valores = {"ACABAMENTO": "ZINCADO BRANCO"}
    _vetar_ambiguos(pdm.classes["PDM005"], "ARRUELA PRESSAO ACO MOLA ZINC",
                    valores, {"ACABAMENTO": "ZINC"})
    assert valores["ACABAMENTO"] == "ZINCADO BRANCO"

    valores = {"ACABAMENTO": "ZINCADO BRANCO"}
    _vetar_ambiguos(pdm.classes["PDM001"], "PARAFUSO M12X50 ZINC",
                    valores, {"ACABAMENTO": "ZINC"})
    assert valores["ACABAMENTO"] is None


def test_veto_cede_quando_o_texto_distingue_sozinho(pdm):
    """Recorte preguicoso nao deve custar um acerto.

    Se o modelo recorta so 'ZINCADO' mas o texto escreve 'ZINCADO AMARELO'
    inteiro, o texto distingue e o veto nao se aplica.
    """
    from saneamento.llm import _vetar_ambiguos

    valores = {"ACABAMENTO": "ZINCADO AMARELO"}
    _vetar_ambiguos(pdm.classes["PDM001"], "PARAFUSO M10X40 ZINCADO AMARELO",
                    valores, {"ACABAMENTO": "ZINCADO"})
    assert valores["ACABAMENTO"] == "ZINCADO AMARELO"


def test_notacao_diferente_nao_e_ambiguidade(pdm):
    """'TC12' alcanca um unico valor do enum ('TC-12'), entao nao e vetado."""
    from saneamento.llm import _vetar_ambiguos

    valores = {"MODELO EQUIPAMENTO": "TC-12"}
    _vetar_ambiguos(pdm.classes["PDM110"], "CHAPA DE DESGASTE TC12 METSO",
                    valores, {"MODELO EQUIPAMENTO": "TC12"})
    assert valores["MODELO EQUIPAMENTO"] == "TC-12"


def test_gemeo_numerico_nao_passa(pdm):
    """CLASSE RESISTENCIA '12.9' nao pode virar '10.9'.

    12.9 existe no PDM, mas na lista de OUTRA classe: em PDM001 a lista e
    10.9|5.8|8.8|A2-70|A4-70|SAE GRAU 2|5|8. Sem valor certo disponivel, a
    resposta e null - o modelo escolheu a classe de resistencia vizinha, e o
    validador nao pega porque 10.9 e valor legitimo da lista. Aconteceu em 74
    registros da amostra de 3.000.
    """
    from saneamento.llm import _vetar_ambiguos

    valores = {"CLASSE RESISTENCIA": "10.9"}
    _vetar_ambiguos(pdm.classes["PDM001"],
                    "PARAFUSO SEXTAVADO M10X80 12.9 ACO ESPECIAL",
                    valores, {"CLASSE RESISTENCIA": "12.9"})
    assert valores["CLASSE RESISTENCIA"] is None


def test_gemeo_numerico_nao_vale_para_grandeza(pdm):
    """Em BITOLA a diferenca numerica entre trecho e valor e a regra 2 do PDM.

    'M12X50' origina BITOLA M12 + COMPRIMENTO 50MM: o trecho tem 12 e 50, o
    valor so 12, e isso esta certo. A trava vale onde o PDM declara 'lista de
    valores', nao onde declara formato de grandeza.
    """
    from saneamento.llm import _vetar_ambiguos

    valores = {"BITOLA": "M12", "COMPRIMENTO": "50MM"}
    _vetar_ambiguos(pdm.classes["PDM001"], "PARAFUSO SEXTAVADO M12X50 ZINCADO BRANCO",
                    valores, {"BITOLA": "M12X50", "COMPRIMENTO": "M12X50"})
    assert valores["BITOLA"] == "M12"


def test_ambiguidade_por_palavra_nao_passa(pdm):
    """'ACO FORJADO' nao e subcadeia de nenhum valor, mas cabe em dois deles.

    PDM050 tem ACO CARBONO FORJADO A105 e ACO INOX FORJADO A182 F316: formas de
    produto diferentes. O trecho nao diz qual, entao nao decide.
    """
    from saneamento.llm import _vetar_ambiguos

    valores = {"MATERIAL": "ACO CARBONO FORJADO A105"}
    _vetar_ambiguos(pdm.classes["PDM050"], "LUVA REDUCAO 1POL 3000# ACO FORJADO",
                    valores, {"MATERIAL": "ACO FORJADO"})
    assert valores["MATERIAL"] is None


def test_abreviacao_sem_numero_continua_passando(pdm):
    """A trava numerica nao pode derrubar abreviacao legitima do dominio.

    'ZB' -> ZINCADO BRANCO e '2RS' -> BORRACHA AMBOS LADOS nao compartilham
    numero com o valor canonico, e as duas estao certas.
    """
    from saneamento.llm import _vetar_ambiguos

    valores = {"ACABAMENTO": "ZINCADO BRANCO"}
    _vetar_ambiguos(pdm.classes["PDM005"], "ARRUELA PRESSAO ACO MOLA ZB",
                    valores, {"ACABAMENTO": "ZB"})
    assert valores["ACABAMENTO"] == "ZINCADO BRANCO"

    valores = {"VEDACAO": "BORRACHA AMBOS LADOS"}
    _vetar_ambiguos(pdm.classes["PDM020"], "ROLAMENTO 6308-2RS 40MM 90MM 23MM",
                    valores, {"VEDACAO": "2RS"})
    assert valores["VEDACAO"] == "BORRACHA AMBOS LADOS"


def test_mudar_o_prompt_invalida_o_cache(pdm, tmp_path):
    """Sem a versao do prompt na chave, a execucao seguinte serve em silencio
    resposta produzida sob as regras antigas."""
    import saneamento.llm as mod

    classe = pdm.classes["PDM001"]
    llm = mod.DesempateLlm(cache=tmp_path, ativo=False)
    antes = llm._chave(classe, "PARAFUSO M12X50", ["MATERIAL"])
    original = mod._VERSAO_PROMPT
    try:
        mod._VERSAO_PROMPT = "outraversao"
        depois = llm._chave(classe, "PARAFUSO M12X50", ["MATERIAL"])
    finally:
        mod._VERSAO_PROMPT = original
    assert antes != depois



def test_rotulo_interno_nao_entra_no_dicionario_como_termo(pdm):
    """So o trecho devolvido PELO LLM pode virar termo aprendido.

    O campo `evidencia` carrega duas coisas no projeto: as vezes o trecho
    literal do texto, as vezes uma explicacao legivel para humano
    ('dicionario aprendido', 'notacao compacta M<bitola>X<comprimento>',
    'coluna FABRICANTE'). O ciclo de aprendizado tratava tudo como trecho, e o
    rotulo interno entrava no dicionario COMO TERMO - um deles chegou a 25
    confirmacoes e a marcado confiavel, casando em registros reais.
    """
    from saneamento.aprendizado import Aprendizado

    ap = Aprendizado(None, pdm=pdm)
    arb = Arbitro(Validador(pdm))
    classe = pdm.classes["PDM001"]

    # a caixa chega com uma explicacao legivel no campo evidencia, nao um trecho
    res = arb.arbitrar(classe, {}, {}, 0.95, "PARAFUSO")
    res.decisoes["ACABAMENTO"].evidencia = "dicionario aprendido"

    # o LLM resolve a caixa mas NAO devolve evidencia para ela
    arb.incorporar_llm(classe, res, {"ACABAMENTO": "OXIDADO PRETO"},
                       evidencias={}, aprendizado=ap)

    assert res.decisoes["ACABAMENTO"].valor == "OXIDADO PRETO"
    assert ap.entradas == {}, f"rotulo interno virou termo: {list(ap.entradas)}"

    # com evidencia de verdade do LLM, aprende normalmente
    res2 = arb.arbitrar(classe, {}, {}, 0.95, "PARAFUSO")
    arb.incorporar_llm(classe, res2, {"ACABAMENTO": "OXIDADO PRETO"},
                       evidencias={"ACABAMENTO": "OXID"}, aprendizado=ap)
    assert "ACABAMENTO|OXID" in ap.entradas


# ------------------------------------------------- contribuicao de cada camada

def test_toda_camada_contribui(pdm):
    """Camada que preenche ZERO caixas esta desligada, e o pipeline nao acusa.

    Quatro vezes neste projeto uma camada entrou no codigo e ficou sem efeito,
    com o pipeline rodando e entregando menos, em silencio:

      1. sinonimos.py nao era consultado pelo caminho principal (valia +5,1
         pontos de SANEADO ao ligar)
      2. o dicionario aprendido ficava em 0 termos porque a chave de evidencia
         vinha com underscore ('MODELO_EQUIPAMENTO') e nunca casava
      3. pares() era usado so para gerar o treino do BERT, nunca na extracao
      4. a camada 0 recebia o texto ja normalizado, sem os dois-pontos, e
         pares() nao achava par nenhum - a fonte 'rotulo' ficou em ZERO

    Nenhum dos quatro quebrava teste. Este quebra.
    """
    from collections import Counter

    from saneamento import ler_base

    amostra = ler_base(RAIZ / "dados/01_base_materiais.xlsx")[:400]
    pipe = Pipeline(pdm)
    fontes = Counter()
    for r in amostra:
        for d in pipe.processar(r).decisoes.values():
            if d.valor:
                fontes[d.fonte] += 1

    # camadas deterministicas: tem de aparecer numa amostra de 400 registros
    for camada in ("rotulo", "gazetteer", "sinonimo", "gramatica", "regra_pdm_2"):
        assert fontes[camada] > 0, (
            f"a camada {camada!r} nao preencheu nenhuma caixa em 400 registros: "
            f"provavelmente esta desligada. Fontes vistas: {dict(fontes)}")


def test_rotulo_ganha_da_deducao_da_regra_2(pdm):
    """O cadastro escreveu 'ROSCA:MF': a deducao nao pode dizer METRICA GROSSA.

    A regra 2 do PDM desmembra 'M12X50' em BITOLA + COMPRIMENTO, e assume
    metrica grossa quando o passo nao aparece. E DEDUCAO, nao leitura - e
    perdia para nada. No registro 27422515 o cadastro escreve 'ROSCA:MF,
    BITOLA:M12X1,5' e a deducao sobrescrevia com METRICA GROSSA e M12,
    deduzindo contra o que esta escrito.
    """
    from saneamento import ExtratorLexico

    ext = ExtratorLexico(pdm)
    texto = "PARAFUSO SEXT, ROSCA:MF, BITOLA:M12X1,5, COMPR:120MM, CLASSE:10.9"
    c = ext.extrair(texto, pdm.classes["PDM001"], "PARAFUSO",
                    texto_estruturado=texto)
    assert c["COMPRIMENTO"].valor == "120MM", "o rotulo COMPR:120MM tem de valer"
    assert c["COMPRIMENTO"].fonte == "rotulo"
    assert c["CLASSE RESISTENCIA"].valor == "10.9"


def test_opcional_nao_copia_o_primeiro_numero(pdm):
    """Caixa opcional disputa a familia de grandeza, nao herda o primeiro numero.

    SECAO de PDM031 (opcional) era 'irmao unico' da familia MM porque o filtro
    de irmaos exigia obrigatorio, e irmao unico copia o primeiro numero que
    acha: recebia o mesmo valor de DIAMETRO INTERNO. Com os tres numeros do
    texto e as tres caixas de PDM004 (todas opcionais), a restricao de dominio
    passa a atuar.
    """
    from saneamento import ExtratorLexico

    texto = ("ARRUELA LISA, PARA PARAFUSO:M36, DIAMETRO INTERNO:39MM,"
             " DIAM EXTERNO:110 MM, E:8 MM")
    c = ExtratorLexico(pdm).extrair(texto, pdm.classes["PDM004"], "ARRUELA",
                                    texto_estruturado=texto)
    assert c["DIAMETRO INTERNO"].valor == "39MM"
    assert c["DIAMETRO EXTERNO"].valor == "110MM"
    assert c["ESPESSURA"].valor == "8MM"
    assert c["DIAMETRO INTERNO"].valor != c["DIAMETRO EXTERNO"].valor


# ------------------------------------------- BERT restrito + rotulo telegrafico

class _BertFalso:
    """Devolve sempre as mesmas previsoes, para testar a mascara do pipeline."""

    def __init__(self, previsoes):
        self.previsoes = previsoes
        self.vistos: list[list[str]] = []

    def prever(self, tokens):
        from saneamento.bert import Predicao
        self.vistos.append(tokens)
        return [Predicao(a, v, c, ()) for a, v, c in self.previsoes]


def test_bert_descarta_proposta_fora_da_lista_em_caixa_textual(pdm):
    # 'FABRICANTE' recortado como MATERIAL (caixa TEXTUAL) era a recusa mais
    # comum da base: 3.141 registros, cada um uma caixa INVALIDO sem informacao.
    falso = _BertFalso([("MATERIAL", "FABRICANTE", 0.9),
                        ("REFERENCIA FABRICANTE", "519-8798", 0.9)])
    p = Pipeline(pdm, bert=falso)
    cand = p._bert("EIXO CAMINHAO FAB CATERPILLAR P/N 519-8798", pdm.classes["PDM110"])
    assert "MATERIAL" not in cand
    assert cand["REFERENCIA FABRICANTE"].valor == "519-8798"


def test_bert_com_valor_da_lista_ainda_aponta_conflito(pdm):
    # Valor VALIDO e diferente do da regra continua indo ao arbitro: foi assim
    # que apareceram os 136 BITOLA M10 x M10X1,25 (rosca fina).
    falso = _BertFalso([("BITOLA", "M10X1,25", 0.9)])
    p = Pipeline(pdm, bert=falso)
    cand = p._bert("PARAFUSO SEXTAVADO M10 ROSCA FINA", pdm.classes["PDM001"])
    assert cand["BITOLA"].valor == "M10X1,25"


def test_invalido_em_atributo_opcional_nao_trava_registro(pdm):
    # PDM110 MATERIAL e opcional ('quando informado pelo fabricante'). Um lixo
    # do BERT ali nao pode tirar de SANEADO um registro com a chave fechada.
    falso = _BertFalso([("MATERIAL", "PARA", 0.9)])
    p = Pipeline(pdm, bert=falso)
    r = p.processar({
        "CODIGO_MATERIAL": "T2", "GRUPO_MERCADORIA": "",
        "DESCRICAO_LONGA": "EIXO, APLIC:CAMINHAO FORA DE ESTRADA, MODELO:793F, "
                           "FABRICANTE:CATERPILLAR, PN:519-8798",
    })
    assert r.id_pdm == "PDM110"
    assert "MATERIAL" not in r.pendentes


def test_coluna_erp_vence_bert_no_part_number(pdm):
    falso = _BertFalso([("REFERENCIA FABRICANTE", "18316702", 0.95)])
    r = Pipeline(pdm, bert=falso).processar({
        "CODIGO_MATERIAL": "T3", "GRUPO_MERCADORIA": "",
        "DESCRICAO_LONGA": "CABECOTE PERFURATRIZ FLEXIROC T45 EPIROC 18316702",
        "FABRICANTE": "EPIROC", "REFERENCIA_FABRICANTE": "5215 6049 61",
    })
    assert r.decisoes["REFERENCIA FABRICANTE"].valor == "5215 6049 61"


def test_bert_recebe_texto_sem_expansao(pdm):
    # O treino ve o valor cru; FAB -> FABRICANTE na inferencia criava palavra nova.
    tokens = Pipeline(pdm)._tokens_para_bert("EIXO COM FAB CATERPILLAR P/N 519-8798")
    assert "FAB" in tokens and "FABRICANTE" not in tokens
    assert "P/N" in tokens and "PART" not in tokens


@pytest.mark.parametrize("texto,esperado", [
    ("EIXO CAMINHAO FORA DE ESTRADA FAB CATERPILLAR P/N 519-8798", "519-8798"),
    ("VIGA PENEIRA EQUIP TS 3.6X7.3 METSO P/N N45459632 REV A", "N45459632 REV A"),
    ("MANDIBULA FIXA CJ412 COD 458.6479-93 REV A SANDVIK", "458.6479-93 REV A"),
    ("BUCHA REF FABRICANTE 1096757 HIDR", "1096757"),
    ("ROLAMENTO REFERENCIA DE 22310E/C3", "22310E/C3"),
    ("CABECOTE FLEXIROC T45 EPIROC PN 1728 9860 67", "1728 9860 67"),   # grupos
    ("BUCHA REF 12345 50 MM", "12345"),                                  # 50 MM e medida
])
def test_part_number_depois_de_rotulo_telegrafico(pdm, texto, esperado):
    from saneamento.regras import ExtratorLexico
    c = ExtratorLexico(pdm).extrair(texto, pdm.classes["PDM110"], "EIXO")
    assert c["REFERENCIA FABRICANTE"].valor == esperado
    assert c["REFERENCIA FABRICANTE"].fonte == "rotulo_telegrafico"


@pytest.mark.parametrize("texto", [
    "FLANGE CEGO PN 16 ACO CARBONO",      # pressao nominal, nao part number
    "BUCHA REF 25MM",                     # medida, nao codigo
    "TAMPA REF FABRICANTE A CONFIRMAR",   # rotulo sem codigo
])
def test_rotulo_telegrafico_nao_inventa_codigo(pdm, texto):
    from saneamento.regras import ExtratorLexico
    c = ExtratorLexico(pdm).extrair(texto, pdm.classes["PDM110"], "BUCHA")
    assert c["REFERENCIA FABRICANTE"].fonte != "rotulo_telegrafico" or \
        c["REFERENCIA FABRICANTE"].valor is None


@pytest.mark.parametrize("regra,bert", [
    ("N45459632 REV A", "N45459632-REVA"),     # mesma referencia, outra pontuacao
    ("MM1728484", "MM1728484 APLICACAO"),      # BERT engoliu a palavra seguinte
])
def test_part_number_compativel_e_acordo(pdm, regra, bert):
    arb = Arbitro(Validador(pdm))
    d = arb._decidir(pdm.classes["PDM110"], "REFERENCIA FABRICANTE",
                     Candidato("REFERENCIA FABRICANTE", regra, "rotulo_telegrafico", 0.9, regra),
                     Candidato("REFERENCIA FABRICANTE", bert, "bert", 0.9, bert))
    assert d.estado == "ACEITO" and d.fonte == "acordo"
    assert d.valor == regra                     # vale o valor ancorado no rotulo


def test_part_number_diferente_e_conflito(pdm):
    arb = Arbitro(Validador(pdm))
    d = arb._decidir(pdm.classes["PDM110"], "REFERENCIA FABRICANTE",
                     Candidato("REFERENCIA FABRICANTE", "1R-1808", "rotulo_telegrafico", 0.9, "1R-1808"),
                     Candidato("REFERENCIA FABRICANTE", "P551808", "bert", 0.9, "P551808"))
    assert d.estado == "CONFLITO"


def test_coluna_erp_vence_rotulo_telegrafico(pipe):
    # A coluna REFERENCIA_FABRICANTE e o campo proprio do cadastro: quando
    # existe, o codigo lido do texto nao a substitui.
    r = pipe.processar({
        "CODIGO_MATERIAL": "T1", "GRUPO_MERCADORIA": "",
        "DESCRICAO_LONGA": "CABECOTE PERFURATRIZ FLEXIROC T45 EPIROC COD 18316702",
        "FABRICANTE": "EPIROC", "REFERENCIA_FABRICANTE": "5215 6049 61",
    })
    assert r.id_pdm == "PDM110"
    d = r.decisoes["REFERENCIA FABRICANTE"]
    assert d.valor == "5215 6049 61"
    assert d.fonte == "coluna_erp"


@pytest.mark.parametrize("cru,esperado", [
    ("35,0MM", "35MM"), ("6,40MM", "6,4MM"), ("16,25MM", "16,25MM"), ("1,50MM2", "1,5MM2"),
])
def test_validador_tira_zero_decimal_inutil(pdm, cru, esperado):
    # Mesmo valor tem de gerar a mesma chave: COMPR:35,0MM e M8X35 sao 35MM.
    a = next(x for x in pdm.classes["PDM001"].atributos if x.nome == "COMPRIMENTO")
    if cru.endswith("MM2"):
        a = next(x for c in pdm.classes.values() for x in c.atributos if x.nome == "SECAO CABO")
    assert Validador(pdm).valor(a, cru).valor == esperado


def test_polegada_decimal_nao_vira_so_a_parte_decimal(pipe):
    # '1,5POL' casava a partir do 5 e virava 5POL: valvula de 1.1/2" como de 5".
    r = pipe.processar({"CODIGO_MATERIAL": "T4", "GRUPO_MERCADORIA": "VAL01",
                        "DESCRICAO_LONGA": "VALVULA ESFERA 1,5POL 300# ACO INOX"})
    assert r.decisoes["DIAMETRO NOMINAL"].valor == "1.1/2POL"


def test_ultimo_par_da_longa_nao_vaza_para_a_curta(pipe):
    r = pipe.processar({
        "CODIGO_MATERIAL": "T5", "GRUPO_MERCADORIA": "VAL01",
        "DESCRICAO_LONGA": "VALV GAV, ACIONAMENTO:VOLANTE, 300#, CONEXAO:FLANGEADA RF, "
                           "DIAM NOMINAL:1,5POL",
        "DESCRICAO_CURTA": "VALV GAV ACIONAMENTO VOLANTE 300# ACO IN",
    })
    d = r.decisoes["DIAMETRO NOMINAL"]
    assert d.valor == "1.1/2POL" and d.fonte == "rotulo"


@pytest.mark.parametrize("texto,bitola,comprimento", [
    ('PARAFUSO SEXTAVADO UNC, BITOLA 1/2", COMPR 2 POL, SAE GRAU 8', "1/2POL", "2POL"),
    ('PARAF HEXAGONAL; BITOLA:1 1/4 POL; ROSCA:UNC; COMP:1-1/4"; CL:SAE GRAU 8', "1.1/4POL", "1.1/4POL"),
    ('PARAFUSO SEXTAVADO, ROSCA:UNF, BITOLA:1", COMPR:3-1/2", CL:SAE GRAU 8', "1POL", "3.1/2POL"),
])
def test_parafuso_polegada_bitola_e_comprimento(pipe, texto, bitola, comprimento):
    # As duas medidas em polegada estao na lista de COMPRIMENTO. A que ja e a
    # BITOLA nao serve para o comprimento; duas grafias do mesmo valor nao sao
    # ambiguidade.
    r = pipe.processar({"CODIGO_MATERIAL": "T6", "GRUPO_MERCADORIA": "FIX01",
                        "DESCRICAO_LONGA": texto})
    assert r.decisoes["BITOLA"].valor == bitola
    assert r.decisoes["COMPRIMENTO"].valor == comprimento


@pytest.mark.parametrize("texto,grupo,atributo,esperado", [
    # fracao mista: '1 3/4POL' nao pode oferecer '3/4POL' a BITOLA
    ('PARAFUSO SEXTAVADO, ROSCA:UNC, ROSCA:1/2", COMPRIMENTO:1 3/4POL, GRAU:SAE GRAU 5',
     "FIX01", "BITOLA", "1/2POL"),
    ('PARAF SEXT. UNC 7/8"X2 1/4POL SAE GRAU 8 ACO CARB', "FIX01", "COMPRIMENTO", "2.1/4POL"),
    # 'DN 6"' e 6 polegadas, nao DN 6 (1/8")
    ('VALVULA ESFERA DN 6" 150# INOX 316', "VAL01", "DIAMETRO NOMINAL", "6POL"),
    ("VALVULA ESFERA DN 50 150#", "VAL01", "DIAMETRO NOMINAL", "2POL"),
    # secao de cabo escrita em MM e mm2
    ("CABO ELETRICO, TIPO:FLEXIVEL, SECAO:2,5MM, VIAS:1, 450/750V", "ELE01", "SECAO", "2,5MM2"),
])
def test_medidas_que_chegavam_erradas(pipe, texto, grupo, atributo, esperado):
    r = pipe.processar({"CODIGO_MATERIAL": "T7", "GRUPO_MERCADORIA": grupo,
                        "DESCRICAO_LONGA": texto})
    assert r.decisoes[atributo].valor == esperado


@pytest.mark.parametrize("recorte,esperado", [
    ("PN 12560", "12560"), ("COD FABRICANTE 1498169442", "1498169442"), ("REF 22310E/C3", "22310E/C3"),
])
def test_bert_nao_leva_rotulo_no_part_number(pdm, recorte, esperado):
    p = Pipeline(pdm, bert=_BertFalso([("REFERENCIA FABRICANTE", recorte, 0.9)]))
    cand = p._bert("TAMBOR RETORNO FLEXCO PN 12560", pdm.classes["PDM110"])
    assert cand["REFERENCIA FABRICANTE"].valor == esperado


@pytest.mark.parametrize("recorte", ["PN", "COD", "REF"])
def test_bert_rotulo_sozinho_nao_e_part_number(pdm, recorte):
    p = Pipeline(pdm, bert=_BertFalso([("REFERENCIA FABRICANTE", recorte, 0.9)]))
    assert "REFERENCIA FABRICANTE" not in p._bert("ANEL DESGASTE KSB PN", pdm.classes["PDM110"])


def test_dado_ausente_nao_tira_de_saneado_mas_valor_nao_reconhecido_tira(pipe):
    # Ausente do texto: saneado e incompleto.
    ausente = pipe.processar({"CODIGO_MATERIAL": "T8", "GRUPO_MERCADORIA": "FIX01",
                              "DESCRICAO_LONGA": "PARAFUSO SEXTAVADO M12X50 8.8 DIN 933"})
    assert ausente.estado == "SANEADO" and not ausente.completo
    assert ausente.pendentes                      # a lista do que falta continua la
    # Completo: tudo cheio e a chave fecha.
    cheio = pipe.processar({
        "CODIGO_MATERIAL": "T9", "GRUPO_MERCADORIA": "FIX01",
        "DESCRICAO_LONGA": "PARAFUSO SEXTAVADO; ROSCA: METRICA GROSSA; BITOLA: M12; "
                           "COMPRIMENTO: 75MM; CLASSE RESISTENCIA: 8.8; MATERIAL: ACO CARBONO; "
                           "ACABAMENTO: OXIDADO PRETO; NORMA: DIN 931"})
    assert cheio.estado == "SANEADO" and cheio.completo and cheio.chave_identidade


def test_trecho_fora_da_lista_fica_anotado_sem_travar(pdm):
    # Insumo do scripts/11_canonizar_termos.py: o termo que o BERT recortou e o
    # PDM nao tem ('ZINC') fica na decisao, mas a caixa nao vira INVALIDO.
    p = Pipeline(pdm, bert=_BertFalso([("ACABAMENTO", "ZINC", 0.9)]))
    r = p.processar({"CODIGO_MATERIAL": "T10", "GRUPO_MERCADORIA": "FIX01",
                     "DESCRICAO_LONGA": "PARAFUSO SEXTAVADO M12X50 8.8 ZINC DIN 933"})
    d = r.decisoes["ACABAMENTO"]
    assert d.estado != "INVALIDO"
    assert d.candidato_bert == "ZINC" and "fora da lista do PDM" in d.motivo


def test_desempate_gravado_e_aplicado_so_onde_ainda_ha_duvida(pdm):
    # O LLM resolveu MATERIAL e NORMA numa execucao anterior. NORMA hoje ja sai
    # da regra (DIN 933 escrito): a resposta antiga nao pode sobrescreve-la.
    texto = "PARAFUSO SEXTAVADO M12X50 8.8 DIN 933 ACO INOX 304 OU ACO INOX 316"
    antes = Pipeline(pdm).processar({"CODIGO_MATERIAL": "T11", "GRUPO_MERCADORIA": "FIX01",
                                     "DESCRICAO_LONGA": texto})
    assert antes.decisoes["MATERIAL"].estado == "AMBIGUO"
    p = Pipeline(pdm, desempates={"T11": ({"MATERIAL": "ACO INOX 304", "NORMA": "DIN 931"},
                                          {"MATERIAL": "ACO INOX 304", "NORMA": "DIN 931"})})
    r = p.processar({"CODIGO_MATERIAL": "T11", "GRUPO_MERCADORIA": "FIX01",
                     "DESCRICAO_LONGA": texto})
    assert r.decisoes["MATERIAL"].valor == "ACO INOX 304"
    assert r.decisoes["MATERIAL"].fonte == "llm"
    assert r.decisoes["NORMA"].valor == "DIN 933"           # nao sobrescreveu
    assert p.contador["desempates_aplicados"] == 1


def test_carregar_desempates_le_so_os_aceitos(tmp_path):
    from saneamento.pipeline import carregar_desempates
    arq = tmp_path / "d.jsonl"
    arq.write_text(
        '{"codigo": "1", "id_pdm": "PDM001", "aceitos": [{"atributo": "MATERIAL", '
        '"valor": "ACO CARBONO", "evidencia": "ACO CARB"}], "recusados": []}\n'
        '{"codigo": "2", "id_pdm": "PDM001", "aceitos": [], "recusados": '
        '[{"atributo": "NORMA", "proposto": null, "motivo": "LLM devolveu null"}]}\n',
        encoding="utf-8")
    d = carregar_desempates(arq)
    assert d == {"1": ({"MATERIAL": "ACO CARBONO"}, {"MATERIAL": "ACO CARB"})}
