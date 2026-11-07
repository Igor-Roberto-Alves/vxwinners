"""Dicionario de sinonimos de dominio: a camada que o embedding nao substitui.

Medido com o encoder multilingue e5-small sobre o vocabulario real do PDM
(scripts/05_medir_caixas.py --probe):

    NITRILICA  -> ACO CARBONO   (0,837)   deveria ser NBR
    BUNA-N     -> ACO CARBONO   (0,828)   deveria ser NBR
    VITON      -> ACO CARBONO   (0,823)   deveria ser FKM (VITON)
    HDG        -> ORGANOMETALICO(0,814)   deveria ser GALVANIZADO A FOGO
    DIN931     -> DIN 933       (0,865)   deveria ser DIN 931

O modelo nao sabe que NBR e borracha nitrilica; ele casa "coisa que parece
material" com "coisa que parece material". E, no sentido contrario, aproxima o
que precisa ficar separado:

    cos(ACO INOX 304, ACO INOX 316) = 0,963
    cos(ROSCA NPT,    ROSCA BSP)    = 0,965
    cos(DIN 931,      DIN 933)      = 0,959
    cos(150#,         300#)         = 0,944

Cada entrada abaixo e uma linha de dicionario que resolve de forma
deterministica, auditavel e de graca um caso em que o embedding erra ou fica na
duvida. Este arquivo e conhecimento de dominio, nao modelo - e e o que a banca
de suprimentos e manutencao reconhece.
"""

from __future__ import annotations

from .texto import normalizar

# Sinonimo -> valor canonico do PDM, por familia de atributo.
# A chave e casada pelo texto inteiro da caixa, ja normalizado.
SINONIMOS: dict[str, str] = {}


def _registrar(canonico: str, *variantes: str) -> None:
    for v in variantes:
        SINONIMOS[normalizar(v)] = canonico


# --------------------------------------------------------------- acos e ligas
_registrar("ACO INOX 316", "INOX 316", "AISI 316", "SS316", "SS 316", "A4",
           "ACO INOXIDAVEL 316", "316", "INOX316")
_registrar("ACO INOX 304", "INOX 304", "AISI 304", "SS304", "SS 304", "A2",
           "ACO INOXIDAVEL 304", "304", "INOX304")
_registrar("ACO CARBONO", "ACO CARB", "CARBONO", "ACO AO CARBONO", "AC",
           "ACO COMUM", "ACO 1020", "ACO CARBONO COMUM")
_registrar("ACO LIGA", "LIGA", "ACO LIGADO")
_registrar("ACO CARBONO FORJADO A105", "A105", "ASTM A105", "FORJADO A105")
_registrar("ACO CARBONO FUNDIDO A216 WCB", "WCB", "A216 WCB", "A216", "ASTM A216 WCB")
_registrar("ACO INOX FORJADO A182 F316", "A182 F316", "F316", "A182F316", "ASTM A182 F316")
_registrar("ACO INOX FUNDIDO A351 CF8M", "A351 CF8M", "CF8M", "A351", "ASTM A351 CF8M")
_registrar("ACO CROMO-MOLIBDENIO", "CROMO MOLIBDENIO", "CR-MO", "CRMO", "ACO CR MO")
_registrar("ACO CARBONO SAE 1045", "SAE 1045", "1045", "ACO 1045")
_registrar("ACO MANGANES", "MANGANES", "ACO AO MANGANES", "HADFIELD")
_registrar("FERRO FUNDIDO NODULAR", "FOFO NODULAR", "FERRO NODULAR", "NODULAR")
_registrar("FERRO FUNDIDO CINZENTO", "FOFO CINZENTO", "FERRO CINZENTO")

# --------------------------------------------------------------- elastomeros
_registrar("NBR", "NITRILICA", "BORRACHA NITRILICA", "BUNA-N", "BUNA N", "BUNA",
           "NITRILA", "NITRILO", "BORRACHA NBR")
_registrar("FKM (VITON)", "VITON", "FKM", "FLUORELASTOMERO", "BORRACHA VITON")
_registrar("EPDM", "BORRACHA EPDM", "ETILENO PROPILENO")
_registrar("PTFE", "TEFLON", "POLITETRAFLUORETILENO")
_registrar("RPTFE", "PTFE REFORCADO", "TEFLON REFORCADO")
_registrar("SBR", "BORRACHA SBR", "ESTIRENO BUTADIENO")

# --------------------------------------------------------------- acabamentos
_registrar("ZINCADO BRANCO", "ZB", "ZN BRANCO", "ZINCADO BR", "ZINCO BRANCO",
           "ELETROZINCADO BRANCO")
_registrar("ZINCADO AMARELO", "ZA", "ZN AMARELO", "ZINCADO AM", "ZINCO AMARELO",
           "ELETROZINCADO AMARELO")
_registrar("GALVANIZADO A FOGO", "HDG", "GF", "ZINCADO A QUENTE", "GALVANIZADO FOGO",
           "GALV A FOGO", "GALVANIZACAO A QUENTE", "ZINCADO QUENTE")
_registrar("OXIDADO PRETO", "BLACK OXIDE", "OXIDO PRETO", "PRETO OXIDADO", "BRUNIDO")
_registrar("NATURAL", "SEM TRATAMENTO", "BRANCO NATURAL", "NAT")
_registrar("SEM ACABAMENTO", "NENHUM", "SEM REVESTIMENTO")

# --------------------------------------------------------------- roscas e conexoes
_registrar("METRICA GROSSA", "MA", "METRICA", "ROSCA METRICA", "MG", "METRICA NORMAL")
_registrar("METRICA FINA", "MF", "ROSCA METRICA FINA")
_registrar("ROSCA NPT", "NPT", "ROSCADA NPT", "NPT MACHO", "ROSCA NPT MACHO")
_registrar("ROSCA BSP", "BSP", "ROSCADA BSP", "BSPT", "BSPP", "GAS")
_registrar("SOLDA ENCAIXE SW", "SW", "SOCKET WELD", "SOLDA ENCAIXE", "SOLDA SW")
_registrar("SOLDA TOPO BW", "BW", "BUTT WELD", "SOLDA TOPO", "SOLDA DE TOPO")
_registrar("FLANGE RF", "RF", "FLANGEADA RF", "FLANGEADO RF", "RAISED FACE")
_registrar("FLANGE FF", "FF", "FLANGEADA FF", "FLANGEADO FF", "FLAT FACE")

# --------------------------------------------------------------- vedacao de rolamento
_registrar("BORRACHA AMBOS LADOS", "2RS", "2RSH", "2RSR", "DDU", "2HRS", "RS2",
           "VEDACAO BORRACHA", "2RS1")
_registrar("METALICA AMBOS LADOS", "2Z", "ZZ", "2ZR", "VEDACAO METALICA", "Z2")
_registrar("ABERTO", "SEM VEDACAO", "OPEN")

# --------------------------------------------------------------- passagem e sede
_registrar("PLENA", "FULL BORE", "PASSAGEM PLENA", "FULL PORT", "PLENO")
_registrar("REDUZIDA", "REDUCED BORE", "PASSAGEM REDUZIDA", "REDUCED PORT", "REDUZIDO")
_registrar("METAL-METAL", "METAL METAL", "MM", "SEDE METALICA", "METAL/METAL")

# --------------------------------------------------------------- isolacao de cabo
_registrar("PVC", "CLORETO DE POLIVINILA", "ISOLACAO PVC")
_registrar("XLPE", "POLIETILENO RETICULADO", "EPR RETICULADO")
_registrar("HEPR", "BORRACHA ETILENO PROPILENO", "EPR")
_registrar("FLEXIVEL", "CABO FLEXIVEL", "FLEX", "CABINHO")
_registrar("RIGIDO", "CABO RIGIDO")

# --------------------------------------------------------------- tipos de retentor
_registrar("BASL", "BA SL", "BASLX")

# --------------------------------------------------------------- disjuntores
# Medido: o valor literal do PDM aparece em so 147 das 346 descricoes de
# disjuntor da base. O resto escreve 'MINI DISJUNTOR' (com espaco), 'DIN' solto
# ou 'PROTECAO MOTOR'.
_registrar("MINIDISJUNTOR DIN", "MINI DISJUNTOR", "MINIDISJUNTOR", "DIN",
           "DISJUNTOR DIN", "MINI DISJ", "MDW")
_registrar("CAIXA MOLDADA", "CX MOLDADA", "CAIXA MOLD", "MOLDADA", "DWB")
_registrar("MOTOR", "PROTECAO MOTOR", "PROTETOR MOTOR", "GUARDA MOTOR",
           "DISJUNTOR MOTOR", "MPW")

# --------------------------------------------------------------- normas
_registrar("DIN 931", "DIN931", "DIN-931")
_registrar("DIN 933", "DIN933", "DIN-933")
_registrar("DIN 985", "DIN985", "DIN-985")
_registrar("ASME B18.2.1", "ASME B18 2 1", "B18.2.1", "ASMEB18.2.1")
_registrar("ASME B16.11", "B16.11", "ASME B16 11")
_registrar("ASME B16.5", "B16.5", "ASME B16 5")


# Sinonimos de SUBSTANTIVO, aplicados antes da classificacao. Diferente dos
# valores, aqui a expressao tem mais de um token, entao a troca e por frase.
# 'ELEMENTO FILTRANTE OLEO FLEETGUARD LF3970' caia em OLEO LUBRIFICANTE (PDM090)
# porque nenhuma classe de FIL01 casava o substantivo FILTRO literalmente.
SINONIMO_SUJEITO = {
    "ELEMENTO FILTRANTE": "FILTRO",
    "ELEMENTO FILTRO": "FILTRO",
    "CARTUCHO FILTRANTE": "FILTRO",
    "CARTUCHO FILTRO": "FILTRO",
    "REPARO FILTRO": "FILTRO",
    "ANEL ORING": "ANEL O-RING",
    "ANEL O RING": "ANEL O-RING",
    "VEDADOR": "RETENTOR",
    "ROLAMENTO DE ESFERAS": "ROLAMENTO RIGIDO ESFERAS",
    "CORREIA V": "CORREIA TRAPEZOIDAL",
    "CABO DE FORCA": "CABO ELETRICO",
    "CHAVE CONTATORA": "CONTATOR",
}


def expandir_sujeito(texto: str) -> str:
    """Troca expressoes de substantivo por frase, antes de classificar."""
    t = f" {normalizar(texto)} "
    for de, para in SINONIMO_SUJEITO.items():
        t = t.replace(f" {de} ", f" {para} ")
    return t.strip()


def canonizar(atributo, texto: str) -> str | None:
    """Resolve o texto da caixa por dicionario, dentro da lista do atributo.

    Devolve None quando o sinonimo nao existe ou quando o valor canonico que ele
    aponta nao e permitido para este atributo - e o que impede NBR de entrar num
    atributo de aco so porque a palavra apareceu.
    """
    if not texto or not atributo.fechado:
        return None
    chaves = atributo.chaves
    n = normalizar(texto)

    direto = chaves.get(n)
    if direto:
        return direto

    alvo = SINONIMOS.get(n)
    if alvo and normalizar(alvo) in chaves:
        return chaves[normalizar(alvo)]
    return None


def cobertura(pdm) -> dict:
    """Quantos valores permitidos do PDM tem ao menos um sinonimo mapeado."""
    canonicos = set(SINONIMOS.values())
    todos, cobertos = set(), set()
    for c in pdm.classes.values():
        for a in c.atributos:
            for v in a.valores:
                todos.add(v)
                if v in canonicos:
                    cobertos.add(v)
    return {"valores_distintos": len(todos), "com_sinonimo": len(cobertos),
            "entradas": len(SINONIMOS)}
