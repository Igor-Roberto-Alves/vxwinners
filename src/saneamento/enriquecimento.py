"""Camada de ENRIQUECIMENTO: completa a caixa que o cadastro nunca teve.

O pipeline de extracao (regras -> BERT -> arbitro -> LLM) so sabe recortar o que
esta escrito. Medido na base: em 8.815 caixas obrigatorias vazias NENHUMA camada
viu nada no texto. Ali extracao nao e a ferramenta certa - preencher com modelo
seria inventar, e invencao plausivel e o unico erro que nao podemos cometer.

Este modulo faz a outra coisa: busca a informacao FORA do cadastro e grava de
onde ela veio. A diferenca com as outras camadas e de natureza, nao de grau:

    extracao                        enriquecimento
    --------                        --------------
    a resposta esta no texto        a resposta esta numa fonte externa
    evidencia = trecho do texto     evidencia = fonte + url + data + confianca
    fonte: gazetteer/bert/llm       fonte: siscomex/iso15/din/catalogo
    pode preencher qualquer caixa   SO preenche caixa vazia

Tres invariantes, e nenhuma e negociavel:

1. **Procedencia obrigatoria.** Toda sugestao carrega `fonte`,
   `url_ou_referencia`, `data_consulta` e `confianca`. `Sugestao` recusa ser
   construida sem isso (ValueError), para o dado sem rastro nao conseguir
   existir nem por acidente. Toda sugestao sai marcada `tipo=ENRIQUECIDO`, para
   a trilha de auditoria separar o que foi lido do cadastro do que foi buscado
   fora dele.

2. **Passa pelo validador.** `Validador.valor` julga a sugestao igual a qualquer
   outra: valor fora do enum do PDM e recusado, venha de onde vier. Tabela
   tecnica tambem erra, e o enum e o portao.

3. **Nunca sobrescreve extracao.** Enriquecimento le os valores ja preenchidos e
   so propoe para caixa VAZIA. O que o cadastro disse vence o que a tabela diz,
   sempre - porque o item fisico e o que o cadastro descreve.

Uma quarta regra, esta de projeto: **so evidencia positiva**. Rolamento sem
sufixo de vedacao nao vira ABERTO; parafuso cuja faixa de comprimento admite
DIN 931 e DIN 933 nao escolhe uma. Pela norma, ausencia de sufixo TEM
significado (folga Normal, furo cilindrico), mas numa base onde 79% das
descricoes nao seguem o padrao a ausencia significa, quase sempre, que alguem
nao digitou. Inferir a partir do silencio seria invencao com cara de regra.

Ordem das fontes, da mais firme para a mais fraca:

  (a) tabela oficial de NCM (Portal Unico Siscomex, modulo Classif)
      Determinstica e autoritativa. Regra 12 do PDM exige NCM "existente e
      vigente", e hoje o pipeline so confere FORMATO e aderencia a classe.
      Baixada uma vez para dados/referencia/ncm_siscomex.json.

  (b) tabelas tecnicas derivadas (ISO 15, ISO 261, ISO 4014/4017/4032,
      ISO 4184, sistemas de designacao dos fabricantes)
      Determinsticas, curadas aqui no codigo, versionadas no git. Uma tabela
      local curada vale mais que um scraping que quebra.

  (c) catalogo de fabricante
      Tentado e NAO funcionou deste ambiente: as paginas de produto da SKF e da
      Schaeffler respondem HTTP 200 com um shell de JavaScript, sem nenhuma
      dimensao no HTML (precisariam de navegador). Ver `CATALOGO_TENTADO`. O
      caminho (b) cobre o mesmo dado com fonte normativa, que e melhor.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .pdm import Classe, Pdm
from .texto import fmt_mm, normalizar, parse_numero
from .validador import Validador

# Marca que separa o dado buscado fora do dado recortado do texto. Vai em cada
# sugestao e em cada linha da saida.
TIPO_ENRIQUECIDO = "ENRIQUECIDO"

# ------------------------------------------------------------------ fonte (a)

URL_NCM_SISCOMEX = (
    "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json"
)
ARQUIVO_NCM = "ncm_siscomex.json"
PASTA_REFERENCIA = "dados/referencia"


# ------------------------------------------------------------------ fonte (c)
# Registro honesto do que foi tentado em catalogo de fabricante e do que deu.
# Fica no codigo de proposito: "nao funcionou" tambem e resultado, e sem isso a
# proxima pessoa repete a tentativa.
CATALOGO_TENTADO = [
    {
        "fabricante": "SKF",
        "url": "https://www.skf.com/group/products/rolling-bearings/ball-bearings/"
               "deep-groove-ball-bearings/productid-6205-2RSH%2FC3",
        "robots_txt": "permite (so /files/*.pdf, /*.jsp e /*/search-results sao Disallow)",
        "resultado": "HTTP 200, 24 KB de shell Angular; nenhuma dimensao no HTML",
    },
    {
        "fabricante": "Schaeffler (FAG/INA) medias",
        "url": "https://medias.schaeffler.com/api/products/search?q=6205-C-2HRS-C3",
        "robots_txt": "301 em medias.schaeffler.com/robots.txt",
        "resultado": "HTTP 200 text/html com CSRF token; API exige sessao",
    },
]


# ------------------------------------------------------------------ procedencia


@dataclass
class Procedencia:
    """De onde o dado veio. Sem os quatro campos, o dado nao entra."""

    fonte: str                 # identificador curto e estavel da fonte
    url_ou_referencia: str     # URL publica ou citacao normativa
    data_consulta: str         # ISO-8601; quando a fonte foi lida
    confianca: float           # 0..1

    @property
    def completa(self) -> bool:
        return bool(
            str(self.fonte).strip()
            and str(self.url_ou_referencia).strip()
            and str(self.data_consulta).strip()
            and isinstance(self.confianca, (int, float))
            and 0.0 < float(self.confianca) <= 1.0
        )

    def como_texto(self) -> str:
        return (f"{self.fonte} | {self.url_ou_referencia} | {self.data_consulta} "
                f"| conf={self.confianca:.2f}")


def _hoje() -> str:
    return date.today().isoformat()


def _norma(fonte: str, referencia: str, confianca: float) -> Procedencia:
    """Procedencia de tabela normativa curada: a data e a data da consulta."""
    return Procedencia(fonte=fonte, url_ou_referencia=referencia,
                       data_consulta=_hoje(), confianca=confianca)


@dataclass
class Sugestao:
    """Valor proposto para UMA caixa vazia, com o rastro de onde saiu."""

    atributo: str
    valor: str
    procedencia: Procedencia
    derivado_de: str = ""      # a entrada do cadastro usada como chave
    metodo: str = ""           # qual tabela ou formula respondeu
    tipo: str = TIPO_ENRIQUECIDO
    revisar: bool = False      # True quando a fonte nao fecha sozinha
    motivo: str = ""

    def __post_init__(self) -> None:
        # Invariante 1, no construtor: dado sem procedencia nao consegue existir.
        if not isinstance(self.procedencia, Procedencia) or not self.procedencia.completa:
            raise ValueError(
                f"sugestao para {self.atributo!r} sem procedencia completa "
                f"(fonte, url_ou_referencia, data_consulta, confianca)")
        if not str(self.valor).strip():
            raise ValueError(f"sugestao para {self.atributo!r} sem valor")

    def como_dict(self) -> dict:
        return {
            "ATRIBUTO": self.atributo,
            "VALOR": self.valor,
            "TIPO": self.tipo,
            "FONTE": self.procedencia.fonte,
            "URL_OU_REFERENCIA": self.procedencia.url_ou_referencia,
            "DATA_CONSULTA": self.procedencia.data_consulta,
            "CONFIANCA": round(float(self.procedencia.confianca), 3),
            "DERIVADO_DE": self.derivado_de,
            "METODO": self.metodo,
            "REVISAR": int(self.revisar),
            "MOTIVO": self.motivo,
        }


@dataclass
class Enriquecimento:
    """O que esta camada tem a dizer sobre um registro."""

    codigo: str
    id_pdm: str = ""
    sugestoes: list[Sugestao] = field(default_factory=list)
    ncm: Sugestao | None = None
    ncm_veredito: str = ""         # VIGENTE | NAO_VIGENTE | AUSENTE | SEM_TABELA
    ncm_motivo: str = ""
    ficha: dict[str, str] = field(default_factory=dict)   # dado sem caixa no PDM
    recusadas: list[str] = field(default_factory=list)

    @property
    def atributos(self) -> list[str]:
        return [s.atributo for s in self.sugestoes]


# =================================================================== fonte (a)


def _data_br(s: str) -> date | None:
    try:
        return datetime.strptime(str(s).strip(), "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def digitos_ncm(bruto: object) -> str:
    return re.sub(r"\D", "", str(bruto or ""))


def formata_ncm(digitos: str) -> str:
    """8 digitos -> 0000.00.00 (regra 12)."""
    d = digitos_ncm(digitos)
    return f"{d[:4]}.{d[4:6]}.{d[6:]}" if len(d) == 8 else str(digitos or "")


class TabelaNcm:
    """Tabela oficial da NCM: existencia e vigencia, nao so formato.

    O `Validador.ncm` do pipeline confere duas coisas: 8 digitos no formato
    0000.00.00 e aderencia ao NCM da classe. Nao confere a terceira, que a regra
    12 do PDM pede com estas palavras - "existente e vigente na tabela oficial".
    Falta real medida na base: 15 registros em 7306.30.00 e 5 em 8539.50.00, dois
    codigos que a revisao da NCM de 2022/2026 desdobrou e que hoje nao existem.
    Os dois passam pelo formato e pela classe, e passariam para producao.

    O download publico traz apenas a nomenclatura em vigor (todo Data_Fim e
    31/12/9999), entao, na pratica, "nao esta na tabela" significa inexistente ou
    revogado - e nos dois casos o codigo nao pode ser gravado.
    """

    def __init__(self, codigos: dict[str, dict], meta: dict):
        self.codigos = codigos
        self.meta = meta

    # ------------------------------------------------------------- construcao

    @classmethod
    def baixar(cls, destino: str | Path | None = None,
               url: str = URL_NCM_SISCOMEX, timeout: int = 180) -> "TabelaNcm":
        """Le o JSON publico do modulo Classif e guarda a versao compacta.

        Baixa UMA vez: o arquivo em dados/referencia/ e a fonte do pipeline, e o
        download so e refeito quando alguem pedir. Guardamos o Ato e a vigencia
        que o proprio portal declara, porque e isso que torna o dado citavel.
        """
        req = urllib.request.Request(url, headers={
            "User-Agent": "saneamento-materiais/1.0 (hackathon VX, desafio 01)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            bruto = json.loads(r.read().decode("utf-8"))

        codigos: dict[str, dict] = {}
        for n in bruto.get("Nomenclaturas", []):
            d = digitos_ncm(n.get("Codigo"))
            if len(d) != 8:
                continue              # capitulo/posicao/subposicao: nao e NCM
            codigos[d] = {
                "descricao": str(n.get("Descricao", "")).strip(),
                "inicio": n.get("Data_Inicio", ""),
                "fim": n.get("Data_Fim", ""),
            }
        meta = {
            "fonte": "siscomex_classif",
            "url": url,
            "data_download": _hoje(),
            "vigencia_declarada": bruto.get("Data_Ultima_Atualizacao_NCM", ""),
            "ato": bruto.get("Ato", ""),
            "codigos_8_digitos": len(codigos),
        }
        tabela = cls(codigos, meta)
        if destino:
            tabela.salvar(destino)
        return tabela

    def salvar(self, destino: str | Path) -> None:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps({"meta": self.meta, "codigos": self.codigos},
                       ensure_ascii=False, indent=1),
            encoding="utf-8")

    @classmethod
    def carregar(cls, origem: str | Path) -> "TabelaNcm":
        d = json.loads(Path(origem).read_text(encoding="utf-8"))
        return cls(d["codigos"], d["meta"])

    @classmethod
    def local(cls, pasta: str | Path = PASTA_REFERENCIA,
              baixar_se_faltar: bool = False) -> "TabelaNcm | None":
        """Tabela de dados/referencia/. None quando nao existe e nao se pode baixar.

        None e resposta legitima: ambiente sem rede e sem arquivo fica SEM a
        validacao de existencia, e o relatorio diz isso - nao finge que validou.
        """
        caminho = Path(pasta) / ARQUIVO_NCM
        if caminho.exists():
            return cls.carregar(caminho)
        if not baixar_se_faltar:
            return None
        try:
            return cls.baixar(caminho)
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return None

    # ------------------------------------------------------------- consulta

    def existe(self, bruto: object) -> bool:
        return digitos_ncm(bruto) in self.codigos

    def vigente(self, bruto: object, em: date | None = None) -> bool:
        reg = self.codigos.get(digitos_ncm(bruto))
        if reg is None:
            return False
        quando = em or date.today()
        ini, fim = _data_br(reg.get("inicio")), _data_br(reg.get("fim"))
        if ini and quando < ini:
            return False
        if fim and quando > fim:
            return False
        return True

    def descricao(self, bruto: object) -> str:
        reg = self.codigos.get(digitos_ncm(bruto))
        return reg["descricao"] if reg else ""

    def sucessor(self, bruto: object) -> tuple[str, str] | None:
        """Candidato a substituir um codigo que nao esta mais na tabela.

        Devolve (digitos, motivo) ou None. NUNCA e aplicado sozinho: sai marcado
        `revisar=True`, porque escolher a NCM de um item e ato de classificacao
        fiscal, nao de software. O que a tabela permite afirmar e so isto: dentro
        da mesma subposicao de 6 digitos sobrou um unico codigo, ou sobrou um
        residual "Outros".
        """
        d = digitos_ncm(bruto)
        if len(d) != 8 or d in self.codigos:
            return None
        irmaos = sorted(c for c in self.codigos if c[:6] == d[:6])
        if not irmaos:
            return None
        if len(irmaos) == 1:
            return irmaos[0], f"unico codigo vigente na subposicao {formata_ncm(d)[:7]}"
        residuais = [c for c in irmaos
                     if normalizar(self.codigos[c]["descricao"]) in ("OUTROS", "OUTRAS")]
        if len(residuais) == 1:
            return residuais[0], (f"residual 'Outros' da subposicao {formata_ncm(d)[:7]}; "
                                  f"{len(irmaos)} codigos possiveis")
        return None

    def procedencia(self, confianca: float = 0.99) -> Procedencia:
        return Procedencia(
            fonte=self.meta.get("fonte", "siscomex_classif"),
            url_ou_referencia=(f"{self.meta.get('url', URL_NCM_SISCOMEX)} "
                               f"({self.meta.get('ato', '')}; "
                               f"{self.meta.get('vigencia_declarada', '')})").strip(),
            data_consulta=self.meta.get("data_download") or _hoje(),
            confianca=confianca,
        )


# =================================================================== fonte (b)
# Tabelas tecnicas curadas. Cada bloco cita a norma de onde saiu, porque e essa
# citacao que vai para a coluna URL_OU_REFERENCIA da saida.

REF_ISO15 = ("ISO 15:2017 - Rolling bearings, radial bearings, boundary dimensions; "
             "series de dimensoes 10/02/03/04 (esferas), 22/23 (rolos esfericos), "
             "02/03/22/32 (rolos conicos)")
REF_ISO5753 = "ISO 5753-1 / sistemas de designacao SKF, FAG, NSK, NTN, KOYO, NACHI, TIMKEN"
REF_ISO261 = "ISO 261 / ISO 965-1 - rosca metrica ISO de uso geral, passo grosso"
REF_ISO4014 = "ISO 4014 / DIN 931 - parafuso sextavado com rosca parcial"
REF_ISO4017 = "ISO 4017 / DIN 933 - parafuso sextavado com rosca total"
REF_ISO4032 = "ISO 4032 / DIN 934 - porca sextavada; DIN 985 / ISO 10511 - porca autotravante"
REF_ASME = "ASME B18.2.1 - square and hex bolts and screws, inch series"
REF_ISO4184 = "ISO 4184 / RMA IP-20 - correias trapezoidais, comprimentos primitivos"
REF_PREFIXO_FILTRO = ("sistemas de codificacao publicados pelos fabricantes de filtro "
                      "(Fleetguard LF/FF/FS/AF/HF/WF, Donaldson P/DB, Baldwin B/BF/BT/PA/RS, "
                      "Fram PH/CA/G, Mann W/WK/C/HU, Tecfil PSL/PEL/ARL/ARS, Caterpillar 1R)")

# --------------------------------------------------------------- rolamentos

# Codigo de furo -> diametro interno em mm. Esta parte E formula fechada
# (ISO 15 / ISO 15241): abaixo de 04 a tabela e excecao, de 04 a 96 e d = 5*codigo.
FURO_EXCECAO = {0: 10, 1: 12, 2: 15, 3: 17}


def diametro_interno_por_codigo(codigo: int) -> float | None:
    """Codigo de furo da designacao ISO -> diametro interno em mm.

    6205 -> codigo 05 -> 25 mm.  6310 -> codigo 10 -> 50 mm.
    Codigos 00..03 sao excecao tabelada (10, 12, 15, 17 mm); de 04 a 96 vale
    d = 5 * codigo. Fora disso a designacao usa a forma 62/22 (furo explicito),
    tratada em `analisar_rolamento`.
    """
    if codigo in FURO_EXCECAO:
        return float(FURO_EXCECAO[codigo])
    if 4 <= codigo <= 96:
        return float(codigo * 5)
    return None


# ISO 15: (serie de dimensoes) -> {diametro interno: (diametro externo, largura)}.
# O furo sai de formula; D e B nao tem forma fechada - sao a tabela de limites da
# norma, e por isso ficam aqui, curados e versionados. Faixa coberta: todo furo
# que aparece na base (d = 10..100 mm).
ISO15_ESFERAS = {
    # serie 10 - designacao 60xx
    "10": {10: (26, 8), 12: (28, 8), 15: (32, 9), 17: (35, 10), 20: (42, 12),
           25: (47, 12), 30: (55, 13), 35: (62, 14), 40: (68, 15), 45: (75, 16),
           50: (80, 16), 55: (90, 18), 60: (95, 18), 65: (100, 18), 70: (110, 20),
           75: (115, 20), 80: (125, 22), 85: (130, 22), 90: (140, 24), 95: (145, 24),
           100: (150, 24)},
    # serie 02 - designacao 62xx
    "02": {10: (30, 9), 12: (32, 10), 15: (35, 11), 17: (40, 12), 20: (47, 14),
           25: (52, 15), 30: (62, 16), 35: (72, 17), 40: (80, 18), 45: (85, 19),
           50: (90, 20), 55: (100, 21), 60: (110, 22), 65: (120, 23), 70: (125, 24),
           75: (130, 25), 80: (140, 26), 85: (150, 28), 90: (160, 30), 95: (170, 32),
           100: (180, 34)},
    # serie 03 - designacao 63xx
    "03": {10: (35, 11), 12: (37, 12), 15: (42, 13), 17: (47, 14), 20: (52, 15),
           25: (62, 17), 30: (72, 19), 35: (80, 21), 40: (90, 23), 45: (100, 25),
           50: (110, 27), 55: (120, 29), 60: (130, 31), 65: (140, 33), 70: (150, 35),
           75: (160, 37), 80: (170, 39), 85: (180, 41), 90: (190, 43), 95: (200, 45),
           100: (215, 47)},
    # serie 04 - designacao 64xx
    "04": {17: (62, 17), 20: (72, 19), 25: (80, 21), 30: (90, 23), 35: (100, 25),
           40: (110, 27), 45: (120, 29), 50: (130, 31), 55: (140, 33), 60: (150, 35),
           65: (160, 37), 70: (180, 42), 75: (190, 45), 80: (200, 48), 85: (210, 52),
           90: (225, 54)},
}

# ISO 15: rolamento autocompensador de rolos (PDM021), designacao 222xx / 223xx
ISO15_ROLOS_ESFERICOS = {
    "22": {25: (52, 18), 30: (62, 20), 35: (72, 23), 40: (80, 23), 45: (85, 23),
           50: (90, 23), 55: (100, 25), 60: (110, 28), 65: (120, 31), 70: (125, 31),
           75: (130, 31), 80: (140, 33), 85: (150, 36), 90: (160, 40), 95: (170, 43),
           100: (180, 46)},
    "23": {40: (90, 33), 45: (100, 36), 50: (110, 40), 55: (120, 43), 60: (130, 46),
           65: (140, 48), 70: (150, 51), 75: (160, 55), 80: (170, 58), 85: (180, 60),
           90: (190, 64), 95: (200, 67), 100: (215, 73)},
}

# ISO 355 / ISO 15: rolamento de rolos conicos (PDM022), designacao 302xx/303xx/322xx.
# A LARGURA aqui e a largura total T (nao a largura B do anel interno): e a medida
# que o catalogo publica e a que a aplicacao usa. T tem decimal - note que o PDM
# escreve '16,25MM' como EXEMPLO do formato de DIAMETRO INTERNO, e 16,25 e
# exatamente o T do 30205.
ISO15_ROLOS_CONICOS = {
    "302": {17: (40, 13.25), 20: (47, 15.25), 25: (52, 16.25), 30: (62, 17.25),
            35: (72, 18.25), 40: (80, 19.75), 45: (85, 20.75), 50: (90, 21.75),
            55: (100, 22.75), 60: (110, 23.75)},
    "303": {25: (62, 18.25), 30: (72, 20.75), 35: (80, 22.75), 40: (90, 25.25),
            45: (100, 27.25), 50: (110, 29.25)},
    "322": {25: (52, 19.25), 30: (62, 21.25), 35: (72, 24.25), 40: (80, 24.75),
            45: (85, 24.75), 50: (90, 24.75), 55: (100, 26.75), 60: (110, 29.75)},
    "323": {25: (62, 25.25), 30: (72, 28.75), 35: (80, 32.75), 40: (90, 35.25),
            45: (100, 38.25), 50: (110, 42.25)},
}

# Sufixo de vedacao -> valor do enum VEDACAO de PDM020. Cada fabricante escreve o
# mesmo rolamento de um jeito: 6205-2RSH e SKF, 6205-C-2HRS e FAG, 6205DDU e NSK,
# 6205LLU e NTN, 6205ZZ e NTN/KOYO. Sem esta tabela o sufixo e ruido; com ela, o
# sufixo responde a caixa. A informacao NAO esta no cadastro: esta no sistema de
# designacao do fabricante, que e a fonte externa.
# Casamento do mais longo primeiro: '2RSH' antes de 'RSH', '2RS' antes de 'RS'.
SUFIXO_VEDACAO = {
    "2RSH": "BORRACHA AMBOS LADOS",   # SKF, vedacao de contato dois lados
    "2RSL": "BORRACHA AMBOS LADOS",   # SKF, baixo atrito
    "2RS1": "BORRACHA AMBOS LADOS",   # SKF
    "2RSR": "BORRACHA AMBOS LADOS",   # FAG
    "2HRS": "BORRACHA AMBOS LADOS",   # FAG
    "2NSE": "BORRACHA AMBOS LADOS",   # NACHI
    "2NSL": "BORRACHA AMBOS LADOS",   # NACHI
    "2RS": "BORRACHA AMBOS LADOS",    # generico de mercado
    "2RU": "BORRACHA AMBOS LADOS",    # KOYO, nao-contato
    "DDU": "BORRACHA AMBOS LADOS",    # NSK, vedacao de contato dois lados
    "LLU": "BORRACHA AMBOS LADOS",    # NTN, contato dois lados
    "LLB": "BORRACHA AMBOS LADOS",    # NTN, nao-contato
    "VV": "BORRACHA AMBOS LADOS",     # NSK, nao-contato
    "EE": "BORRACHA AMBOS LADOS",     # TIMKEN
    "2ZR": "METALICA AMBOS LADOS",    # FAG
    "ZZE": "METALICA AMBOS LADOS",    # NACHI
    "2ZN": "METALICA AMBOS LADOS",
    "2Z": "METALICA AMBOS LADOS",     # SKF
    "ZZ": "METALICA AMBOS LADOS",     # NSK, NTN, KOYO, generico
}

# Sufixo de folga -> enum FOLGA. 'NORMAL' NAO e derivado da ausencia de sufixo:
# pela ISO 5753 a ausencia significa folga Normal, mas nesta base a ausencia
# significa, quase sempre, que ninguem digitou o sufixo (ver docstring).
SUFIXO_FOLGA = {"C3": "C3"}

# Sufixo de furo do autocompensador (PDM021). Mesmo criterio: so K positivo.
SUFIXO_FURO = {"K30": "CONICO", "K": "CONICO"}

# --------------------------------------------------------------- fixadores

# ISO 261: passo grosso da rosca metrica, em mm.
PASSO_METRICO_GROSSO = {
    3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75, 14: 2.0,
    16: 2.0, 18: 2.5, 20: 2.5, 22: 2.5, 24: 3.0, 27: 3.0, 30: 3.5, 33: 3.5,
    36: 4.0, 39: 4.0, 42: 4.5, 45: 4.5, 48: 5.0, 52: 5.0, 56: 5.5, 60: 5.5,
    64: 6.0,
}

# ISO 4014 / ISO 4017 (DIN 931 / DIN 933 apos a revisao de 1987): cabeca
# sextavada -> (s = entre faces / boca da chave, k = altura da cabeca), em mm.
CABECA_SEXTAVADA = {
    3: (5.5, 2.0), 4: (7.0, 2.8), 5: (8.0, 3.5), 6: (10.0, 4.0), 8: (13.0, 5.3),
    10: (16.0, 6.4), 12: (18.0, 7.5), 14: (21.0, 8.8), 16: (24.0, 10.0),
    18: (27.0, 11.5), 20: (30.0, 12.5), 22: (34.0, 14.0), 24: (36.0, 15.0),
    27: (41.0, 17.0), 30: (46.0, 18.7), 33: (50.0, 21.0), 36: (55.0, 22.5),
    39: (60.0, 25.0), 42: (65.0, 26.0), 45: (70.0, 28.0), 48: (75.0, 30.0),
}

# ISO 4032 / DIN 934 porca sextavada e DIN 985 / ISO 10511 porca autotravante:
# (s = entre faces, m = altura DIN 934, m = altura total DIN 985), em mm.
PORCA_SEXTAVADA = {
    3: (5.5, 2.4, 4.0), 4: (7.0, 3.2, 5.0), 5: (8.0, 4.7, 5.0), 6: (10.0, 5.2, 6.0),
    8: (13.0, 6.8, 8.0), 10: (16.0, 8.4, 10.0), 12: (18.0, 10.8, 12.0),
    14: (21.0, 12.8, 14.0), 16: (24.0, 14.8, 16.0), 18: (27.0, 15.8, 18.0),
    20: (30.0, 18.0, 20.0), 22: (34.0, 19.4, 22.0), 24: (36.0, 21.5, 24.0),
    27: (41.0, 23.8, 27.0), 30: (46.0, 25.6, 30.0), 36: (55.0, 31.0, 36.0),
}

# Tipo de porca -> norma que DEFINE aquele tipo. Nao e correlacao: a norma e a
# definicao do formato, entao o mapa e exato nos dois sentidos.
NORMA_POR_TIPO_PORCA = {
    "SEXTAVADA": "DIN 934",
    "AUTOTRAVANTE": "DIN 985",
    "SEXTAVADA FLANGEADA": "DIN 6923",
    "CASTELO": "DIN 935",
}
TIPO_PORCA_POR_NORMA = {v: k for k, v in NORMA_POR_TIPO_PORCA.items()}

# --------------------------------------------------------------- brocas

# DIN 338 (serie curta), DIN 340 (serie longa) e DIN 345 (haste cone Morse).
# O que a norma define sozinha: 338 e 340 sao de haste CILINDRICA e 345 e de
# haste CONE MORSE. Logo haste -> norma so decide no sentido CONE MORSE (338 e
# 340 empatam na cilindrica), e norma -> haste decide nos tres.
HASTE_POR_NORMA_BROCA = {
    "DIN 338": "CILINDRICA",
    "DIN 340": "CILINDRICA",
    "DIN 345": "CONE MORSE",
}
NORMA_BROCA_POR_HASTE = {"CONE MORSE": "DIN 345"}
REF_DIN_BROCA = ("DIN 338 / DIN 340 - broca helicoidal de haste cilindrica, series "
                 "curta e longa; DIN 345 - broca helicoidal de haste cone Morse")

# --------------------------------------------------------------- correias

# ISO 4184: acrescimo, em mm, do comprimento interno (perfis classicos) ou
# primitivo (perfis estreitos SP) para a CIRCUNFERENCIA EXTERNA - que e a medida
# que a NCM de PDM030 usa para escolher entre 4010.32/4010.34/4010.39.
ACRESCIMO_EXTERNO_CORREIA = {
    "A": 33.0, "A DENTADA": 33.0, "B": 46.0, "B DENTADA": 46.0,
    "C": 74.0, "D": 84.0, "5V": 25.0, "8V": 38.0,
    "SPZ": 13.0, "SPA": 18.0, "SPB": 22.0, "SPC": 30.0,
}

# Faixas da aba NCM_REFERENCIA do PDM para PDM030 (correia trapezoidal nao
# estriada), em cm de circunferencia externa.
FAIXAS_NCM_CORREIA = [
    (60.0, 180.0, "40103200"),
    (180.0, 240.0, "40103400"),
]
NCM_CORREIA_FORA_DE_FAIXA = "40103900"      # <= 60 cm ou > 240 cm

MM_POR_POLEGADA = 25.4

# --------------------------------------------------------------- filtros

# Prefixo do part number -> (fabricante do enum do PDM, tipo do filtro).
# O cadastro tem o part number mas nao tem o fabricante em 71 registros de
# PDM100 - e justamente a caixa obrigatoria que fecha a identidade da classe
# (regra 10: FABRICANTE + PART NUMBER). O prefixo e publicado pelo fabricante.
# Ordem de avaliacao: mais especifico primeiro; empate entre fabricantes
# diferentes NAO preenche.
PREFIXO_FILTRO: list[tuple[str, str, str]] = [
    # Fleetguard
    (r"^LF\s?\d{3,5}[A-Z]?$", "FLEETGUARD", "OLEO LUBRIFICANTE"),
    (r"^FF\s?\d{3,5}[A-Z]?$", "FLEETGUARD", "COMBUSTIVEL"),
    (r"^FS\s?\d{3,5}[A-Z]?$", "FLEETGUARD", "COMBUSTIVEL"),
    (r"^AF\s?\d{3,5}[A-Z]?$", "FLEETGUARD", "AR"),
    (r"^HF\s?\d{3,5}[A-Z]?$", "FLEETGUARD", "HIDRAULICO"),
    (r"^WF\s?\d{3,5}[A-Z]?$", "FLEETGUARD", "AGUA"),
    (r"^AS\s?\d{3,5}[A-Z]?$", "FLEETGUARD", "SEPARADOR AR/OLEO"),
    # Donaldson
    (r"^DBL\s?\d{3,5}$", "DONALDSON", "OLEO LUBRIFICANTE"),
    (r"^DBF\s?\d{3,5}$", "DONALDSON", "COMBUSTIVEL"),
    (r"^DBA\s?\d{3,5}$", "DONALDSON", "AR"),
    (r"^DBB\s?\d{3,5}$", "DONALDSON", "OLEO LUBRIFICANTE"),
    (r"^P\s?\d{6}$", "DONALDSON", ""),
    (r"^P\s?\d{3,4}$", "DONALDSON", ""),
    # Baldwin
    (r"^BF\s?\d{3,5}[A-Z]?$", "BALDWIN", "COMBUSTIVEL"),
    (r"^BT\s?\d{3,5}[A-Z\-]*$", "BALDWIN", "HIDRAULICO"),
    (r"^PA\s?\d{3,5}[A-Z]?$", "BALDWIN", "AR"),
    (r"^RS\s?\d{3,5}[A-Z]?$", "BALDWIN", "AR"),
    (r"^BW\s?\d{3,5}[A-Z]?$", "BALDWIN", "AGUA"),
    (r"^B\s?\d{3,5}[A-Z]?$", "BALDWIN", "OLEO LUBRIFICANTE"),
    # Fram
    (r"^PH\s?\d{3,5}[A-Z]?(?:-\d+)?$", "FRAM", "OLEO LUBRIFICANTE"),
    (r"^CA\s?\d{3,5}[A-Z]?$", "FRAM", "AR"),
    (r"^G\s?\d{3,5}[A-Z]?$", "FRAM", "COMBUSTIVEL"),
    # Mann (o formato com barra e a marca registrada da casa: 'W 950/4')
    (r"^W\s?\d{2,4}/\d{1,2}$", "MANN", "OLEO LUBRIFICANTE"),
    (r"^WK\s?\d{2,4}(?:/\d{1,2})?$", "MANN", "COMBUSTIVEL"),
    (r"^HU\s?\d{2,4}\s?[A-Z]?$", "MANN", "OLEO LUBRIFICANTE"),
    (r"^C\s?\d{3,5}(?:/\d{1,2})?$", "MANN", "AR"),
    # Tecfil
    (r"^PSL\s?\d{3,4}$", "TECFIL", "OLEO LUBRIFICANTE"),
    (r"^PEL\s?\d{3,4}$", "TECFIL", "OLEO LUBRIFICANTE"),
    (r"^ARL\s?\d{3,5}$", "TECFIL", "AR"),
    (r"^ARS\s?\d{3,5}$", "TECFIL", "AR"),
    # Caterpillar
    (r"^1R\s?-?\s?\d{4}$", "CATERPILLAR", "OLEO LUBRIFICANTE"),
    (r"^1G\s?-?\s?\d{4}$", "CATERPILLAR", "COMBUSTIVEL"),
    # Hydac
    (r"^\d{4}\s?[DR]\s?\d{3}\s?[A-Z]{2,4}.*$", "HYDAC", "HIDRAULICO"),
]

# Tipo do filtro -> NCM, conforme a aba NCM_REFERENCIA do PDM para PDM100.
NCM_POR_TIPO_FILTRO = {
    "OLEO LUBRIFICANTE": "84212300",
    "COMBUSTIVEL": "84212300",
    "AR": "84213100",
    "HIDRAULICO": "84212990",
    "SEPARADOR AR/OLEO": "84213990",
}

# Palavra na descricao -> tipo do filtro, para quando o prefixo nao diz o tipo
# (caso do P-series da Donaldson, que cobre todas as familias).
PALAVRA_TIPO_FILTRO = [
    ("SEPARADOR", "SEPARADOR AR/OLEO"),
    ("HIDRAULICO", "HIDRAULICO"),
    ("COMBUSTIVEL", "COMBUSTIVEL"),
    ("DIESEL", "COMBUSTIVEL"),
    ("LUBRIFICANTE", "OLEO LUBRIFICANTE"),
    ("LUBR", "OLEO LUBRIFICANTE"),
    ("OLEO", "OLEO LUBRIFICANTE"),
    ("AR", "AR"),
]


# =========================================================== derivacoes puras
# Funcoes sem estado, sem PDM e sem validador: entram texto/numero, sai dado de
# tabela. Sao o nucleo testavel da camada.


_RX_ROLAMENTO_FURO_EXPLICITO = re.compile(r"\b6([0-4])/(\d{2})\b")
_RX_ESFERAS = re.compile(r"(?<![0-9])6([0-4])(\d{2})(?![0-9])")
_RX_ROLOS_ESFERICOS = re.compile(r"(?<![0-9])22([23])(\d{2})(?![0-9])")
_RX_ROLOS_CONICOS = re.compile(r"(?<![0-9])(302|303|322|323)(\d{2})(?![0-9])")


def analisar_rolamento(designacao: str) -> dict | None:
    """Designacao ISO de rolamento -> dimensoes, vedacao, folga e furo.

    Duas partes, de naturezas diferentes:

      - o DIAMETRO INTERNO sai de formula (codigo de furo x 5, com as quatro
        excecoes 00..03). Isso cobre qualquer codigo, inclusive os que nao
        estiverem na tabela.
      - DIAMETRO EXTERNO e LARGURA saem da tabela de limites da ISO 15. Nao ha
        forma fechada para eles: a norma fixa cada par (D, B) por serie de
        dimensoes, seguindo numeros preferenciais. Fingir uma formula aqui daria
        medida errada, que e pior que caixa vazia.

    6205-2RSH/C3 -> d 25, D 52, B 15, vedacao de borracha, folga C3
    6310-2Z/C3   -> d 50, D 110, B 27, vedacao metalica, folga C3
    22212EK/C3   -> d 60, D 110, B 28, furo conico
    30205        -> d 25, D 52, T 16,25

    None quando a designacao nao casa com nenhuma familia conhecida.
    """
    t = normalizar(designacao).replace(" ", "")
    if not t:
        return None

    familia: str | None = None
    serie: str | None = None
    d: float | None = None

    # Ordem importa: as familias de rolo (22xxx, 302xx) tem 5 digitos e
    # conteriam um casamento falso de 4 digitos se as esferas viessem primeiro.
    m = _RX_ROLAMENTO_FURO_EXPLICITO.search(t)
    if m:                                   # forma 62/22: o furo vem escrito
        familia = "esferas"
        serie = "10" if m.group(1) == "0" else "0" + m.group(1)
        d = float(m.group(2))
    if d is None:
        m = _RX_ROLOS_ESFERICOS.search(t)
        if m:
            familia = "rolos_esfericos"
            serie = {"2": "22", "3": "23"}[m.group(1)]
            d = diametro_interno_por_codigo(int(m.group(2)))
    if d is None:
        m = _RX_ROLOS_CONICOS.search(t)
        if m:
            familia, serie = "rolos_conicos", m.group(1)
            d = diametro_interno_por_codigo(int(m.group(2)))
    if d is None:
        m = _RX_ESFERAS.search(t)
        if m:
            familia = "esferas"
            serie = "10" if m.group(1) == "0" else "0" + m.group(1)
            d = diametro_interno_por_codigo(int(m.group(2)))

    if d is None or familia is None or serie is None:
        return None

    tabela = {"esferas": ISO15_ESFERAS,
              "rolos_esfericos": ISO15_ROLOS_ESFERICOS,
              "rolos_conicos": ISO15_ROLOS_CONICOS}[familia]
    par = tabela.get(serie, {}).get(int(d)) if float(d).is_integer() else None

    out: dict = {"familia": familia, "serie": serie, "DIAMETRO INTERNO": d}
    if par:
        out["DIAMETRO EXTERNO"] = float(par[0])
        out["LARGURA"] = float(par[1])

    # sufixos: casamento do mais longo primeiro, para 2RSH nao casar em RS
    for suf in sorted(SUFIXO_VEDACAO, key=len, reverse=True):
        if suf in t:
            out["VEDACAO"] = SUFIXO_VEDACAO[suf]
            out["sufixo_vedacao"] = suf
            break
    for suf in sorted(SUFIXO_FOLGA, key=len, reverse=True):
        if suf in t:
            out["FOLGA"] = SUFIXO_FOLGA[suf]
            out["sufixo_folga"] = suf
            break
    if familia == "rolos_esfericos":
        for suf in sorted(SUFIXO_FURO, key=len, reverse=True):
            if re.search(rf"{suf}(?![A-Z])", t):
                out["FURO"] = SUFIXO_FURO[suf]
                out["sufixo_furo"] = suf
                break
    return out


# Serie de dimensoes -> prefixo da designacao ISO, por familia. E o caminho de
# volta da tabela: dadas as medidas, qual designacao as produz.
PREFIXO_SERIE = {
    "esferas": {"10": "60", "02": "62", "03": "63", "04": "64"},
    "rolos_esfericos": {"22": "222", "23": "223"},
    "rolos_conicos": {"302": "302", "303": "303", "322": "322", "323": "323"},
}

FAMILIA_POR_CLASSE = {"PDM020": "esferas", "PDM021": "rolos_esfericos",
                      "PDM022": "rolos_conicos"}


def codigo_furo_por_diametro(d: float) -> str | None:
    """Inverso de `diametro_interno_por_codigo`: 25 -> '05', 50 -> '10'."""
    for cod, dd in FURO_EXCECAO.items():
        if abs(dd - d) < 1e-9:
            return f"{cod:02d}"
    if d >= 20 and abs(d / 5 - round(d / 5)) < 1e-9 and 4 <= round(d / 5) <= 96:
        return f"{round(d / 5):02d}"
    return None


def designacao_por_dimensoes(familia: str, interno: float | None,
                             externo: float | None,
                             largura: float | None = None) -> tuple[str, str] | None:
    """Caminho de volta da ISO 15: medidas -> designacao. -> (designacao, serie).

    Preenche a caixa REFERENCIA, que e OBRIGATORIA em PDM020/021/022 e por isso
    tranca a chave de identidade do item. 104 rolamentos da base tem medidas no
    texto e nenhuma referencia.

    Bastam DUAS das tres medidas: na tabela da norma, dentro de uma familia,
    qualquer par entre (d, D, B) identifica uma linha unica - e a familia ja vem
    decidida pela classe do PDM (PDM020 esferas, PDM021 rolos esfericos, PDM022
    rolos conicos). Com uma medida so, varias series casam, e ai devolve None.

    Devolve None quando mais de uma linha casa. A designacao sai SEM o sufixo de
    vedacao e folga - a norma nao deduz sufixo de medida -, e por isso o chamador
    marca a sugestao para revisao.
    """
    tabela = {"esferas": ISO15_ESFERAS, "rolos_esfericos": ISO15_ROLOS_ESFERICOS,
              "rolos_conicos": ISO15_ROLOS_CONICOS}.get(familia)
    if tabela is None:
        return None
    dadas = [m for m in (interno, externo, largura) if m is not None]
    if len(dadas) < 2:
        return None                      # uma medida so nao distingue a serie

    def casa(valor: float | None, esperado: float) -> bool:
        return valor is None or abs(float(valor) - esperado) <= 0.51

    achados: list[tuple[str, int]] = []
    for serie, linhas in tabela.items():
        for d, (de, b) in linhas.items():
            if casa(interno, d) and casa(externo, de) and casa(largura, b):
                achados.append((serie, d))
    if len(achados) != 1:
        return None
    serie, d = achados[0]
    cod = codigo_furo_por_diametro(d)
    prefixo = PREFIXO_SERIE.get(familia, {}).get(serie)
    if not cod or not prefixo:
        return None
    return f"{prefixo}{cod}", serie


_RX_BITOLA_METRICA = re.compile(r"^M(\d{1,2})(?:X(\d{1,2}(?:[.,]\d+)?))?$")


def analisar_bitola(bitola: str) -> dict | None:
    """BITOLA do PDM -> diametro nominal, passo e dimensoes da cabeca.

    'M12'     -> d 12, passo 1,75 (grosso, ISO 261), chave 18, altura 7,5
    'M12X1,5' -> d 12, passo 1,5 -> rosca metrica FINA
    """
    t = normalizar(bitola).replace(" ", "")
    m = _RX_BITOLA_METRICA.match(t)
    if not m:
        return None
    d = int(m.group(1))
    grosso = PASSO_METRICO_GROSSO.get(d)
    passo = parse_numero(m.group(2)) if m.group(2) else grosso
    if passo is None:
        return None
    out = {"diametro": float(d), "passo": float(passo), "passo_grosso": grosso,
           "rosca": "METRICA GROSSA" if grosso is not None and abs(passo - grosso) < 1e-9
                    else "METRICA FINA"}
    cab = CABECA_SEXTAVADA.get(d)
    if cab:
        out["chave_cabeca"] = cab[0]
        out["altura_cabeca"] = cab[1]
    por = PORCA_SEXTAVADA.get(d)
    if por:
        out["chave_porca"] = por[0]
        out["altura_porca_din934"] = por[1]
        out["altura_porca_din985"] = por[2]
    return out


def comprimento_rosca_din931(diametro: float, comprimento: float) -> float:
    """Comprimento de rosca b do DIN 931 / ISO 4014, em mm.

    b = 2d + 6 ate L 125; 2d + 12 de 125 a 200; 2d + 25 acima de 200.
    """
    if comprimento <= 125:
        return 2 * diametro + 6
    if comprimento <= 200:
        return 2 * diametro + 12
    return 2 * diametro + 25


def norma_parafuso_sextavado(rosca: str, bitola: str, comprimento: str) -> tuple[str, str] | None:
    """-> (valor do enum NORMA, motivo) ou None quando a norma nao se decide.

    Duas afirmacoes que as normas sustentam sozinhas, e nada alem delas:

      1. DIN 931 e DIN 933 sao normas de rosca METRICA. Parafuso de rosca UNC ou
         UNF nao pode ser nenhuma das duas: a norma dele e a ASME B18.2.1.
      2. DIN 931 e o parafuso de rosca PARCIAL, e precisa de haste lisa. Se o
         comprimento do parafuso nao chega ao comprimento de rosca b = 2d + 6,
         nao sobra haste: o item so pode ser DIN 933 (rosca total).

    Acima de 2d + 6 as duas normas existem e o catalogo vende as duas. Ali esta
    funcao devolve None de proposito - e caixa que fica vazia, nao caixa que a
    gente chuta.
    """
    r = normalizar(rosca)
    if r in ("UNC", "UNF"):
        return "ASME B18.2.1", f"rosca {r} em polegada: DIN 931/933 sao de rosca metrica"

    b = analisar_bitola(bitola)
    L = parse_numero(re.sub(r"[A-Z]+$", "", normalizar(comprimento)))
    if b is None or L is None:
        return None
    d = b["diametro"]
    # Sanidade: parafuso mais curto que o proprio diametro e erro de cadastro
    # (medido na base: BITOLA M20 com COMPRIMENTO 1,5MM, que e o passo no campo
    # errado). Derivar norma a partir de lixo propaga o lixo.
    if L < d or L < 4:
        return None
    rosca_total = comprimento_rosca_din931(d, L)
    if L <= rosca_total:
        return "DIN 933", (f"L={L:g}MM nao excede o comprimento de rosca do DIN 931 "
                           f"(b=2d+6={rosca_total:g}MM): sem haste lisa, so rosca total")
    return None


def norma_porca(tipo: str) -> tuple[str, str] | None:
    """TIPO da porca -> norma que define aquele tipo. Mapa exato, nao estatistico."""
    t = normalizar(tipo)
    n = NORMA_POR_TIPO_PORCA.get(t)
    if not n:
        return None
    return n, f"{n} e a norma que define a porca {t}"


_RX_CORREIA_CLASSICA = re.compile(r"^(5V|8V|SPZ|SPA|SPB|SPC|[ABCD])\s?-?\s?(\d{2,4})$")


def circunferencia_correia(perfil: str, referencia: str) -> tuple[float, str] | None:
    """-> (circunferencia externa em mm, metodo) ou None.

    Tres notacoes convivem na base e no mercado:

      '2347MM'   comprimento ja em mm (como o extrator recorta hoje)
      'B54'      perfil classico + comprimento INTERNO em polegada
      'SPB 2000' perfil estreito + comprimento PRIMITIVO em mm
      '5V1150'   perfil estreito americano + comprimento efetivo em decimos de polegada

    O acrescimo por perfil (ISO 4184) leva do comprimento interno/primitivo para
    a circunferencia EXTERNA, que e a medida de que a NCM de PDM030 depende.
    """
    p = normalizar(perfil)
    acrescimo = ACRESCIMO_EXTERNO_CORREIA.get(p, 0.0)
    t = normalizar(referencia).replace(" ", "")
    if not t:
        return None

    if t.endswith("MM"):
        v = parse_numero(t[:-2])
        return (v, "comprimento em mm informado na referencia") if v else None

    m = _RX_CORREIA_CLASSICA.match(normalizar(referencia).strip())
    if not m:
        m = _RX_CORREIA_CLASSICA.match(t)
    if m:
        pr, num = m.group(1), float(m.group(2))
        inc = ACRESCIMO_EXTERNO_CORREIA.get(pr, acrescimo)
        if pr in ("5V", "8V"):
            return num / 10.0 * MM_POR_POLEGADA, f"{pr}: comprimento efetivo em decimos de polegada"
        if pr.startswith("SP"):
            return num + inc, f"{pr}: comprimento primitivo em mm + {inc:g}MM (ISO 4184)"
        return num * MM_POR_POLEGADA + inc, \
            f"{pr}{num:g}: comprimento interno em polegada + {inc:g}MM (ISO 4184)"

    v = parse_numero(t)
    if v and v > 200:                       # numero solto grande: mm
        return v + acrescimo, "numero solto tratado como comprimento em mm"
    return None


def ncm_correia(circunferencia_mm: float) -> tuple[str, str]:
    """Circunferencia externa -> NCM de PDM030 (aba NCM_REFERENCIA do PDM)."""
    cm = circunferencia_mm / 10.0
    for ini, fim, ncm in FAIXAS_NCM_CORREIA:
        if ini < cm <= fim:
            return ncm, f"circunferencia externa {cm:.1f}cm na faixa >{ini:g} a {fim:g}cm"
    return NCM_CORREIA_FORA_DE_FAIXA, \
        f"circunferencia externa {cm:.1f}cm fora das faixas de 60 a 240cm"


def fabricante_por_part_number(referencia: str) -> tuple[str, str, str] | None:
    """Part number de filtro -> (fabricante, tipo do filtro, prefixo que casou).

    None quando nenhum padrao casa OU quando dois fabricantes diferentes casam -
    prefixo ambiguo nao preenche caixa. 'LF9009' -> FLEETGUARD; 'DBL7300' ->
    DONALDSON; '1R-1808' -> CATERPILLAR; 'W 056/70' -> MANN.
    """
    t = normalizar(referencia).strip()
    if not t:
        return None
    # a referencia na base vem com lixo colado ('LF7631 LUBRIFICANTE'): usa so o
    # primeiro token, salvo nas notacoes que levam espaco de verdade ('W 056/70')
    candidatos: list[tuple[str, str, str]] = []
    formas = [t, t.split()[0]]
    if len(t.split()) >= 2:
        formas.append(" ".join(t.split()[:2]))
    for rx, fab, tipo in PREFIXO_FILTRO:
        for forma in formas:
            m = re.match(rx, forma)
            if m:
                candidatos.append((fab, tipo, m.group(0)))
                break
    if not candidatos:
        return None
    fabricantes = {c[0] for c in candidatos}
    if len(fabricantes) > 1:
        return None                          # prefixo ambiguo: nao preenche
    com_tipo = [c for c in candidatos if c[1]]
    return com_tipo[0] if com_tipo else candidatos[0]


def tipo_filtro_por_texto(texto: str) -> str:
    """Palavra da descricao -> tipo do filtro, para o prefixo que nao diz o tipo."""
    t = f" {normalizar(texto)} "
    for palavra, tipo in PALAVRA_TIPO_FILTRO:
        if f" {palavra} " in t:
            return tipo
    return ""


# ================================================================ enriquecedor


class Enriquecedor:
    """Camada de enriquecimento: le as caixas cheias, propoe para as vazias.

    Nao conhece o pipeline e nao e chamado por ele: roda depois, sobre o
    resultado saneado, e grava um artefato proprio. A integracao no
    `pipeline.py` fica para quando as outras camadas estiverem estaveis.
    """

    def __init__(self, pdm: Pdm, validador: Validador | None = None,
                 tabela_ncm: TabelaNcm | None = None):
        self.pdm = pdm
        self.validador = validador or Validador(pdm)
        self.ncm_oficial = tabela_ncm
        self.contador: dict[str, int] = {
            "registros": 0, "sugestoes": 0, "recusadas_pelo_validador": 0,
            "recusadas_sem_procedencia": 0, "caixas_ocupadas_preservadas": 0,
            "ncm_vigente": 0, "ncm_nao_vigente": 0, "ncm_preenchido": 0,
            "ncm_sem_tabela": 0, "ncm_ausente": 0,
        }
        self.por_fonte: dict[str, int] = {}
        self.por_atributo: dict[str, int] = {}
        self.trilha: list[Enriquecimento] = []

    # ------------------------------------------------------------- portao

    def _propor(self, destino: list[Sugestao], classe: Classe,
                valores: dict[str, str | None], atributo: str, valor: object,
                proc: Procedencia, derivado_de: str, metodo: str,
                revisar: bool = False, motivo: str = "") -> bool:
        """Portao unico por onde toda sugestao passa. Aqui vivem as 3 invariantes."""
        a = next((x for x in classe.atributos if x.nome == atributo), None)
        if a is None:
            return False                     # atributo nao existe nesta classe

        # invariante 3: enriquecimento nunca sobrescreve extracao
        if valores.get(atributo):
            self.contador["caixas_ocupadas_preservadas"] += 1
            return False

        # invariante 2: o enum/formato do PDM julga igual, venha de onde vier
        v = self.validador.valor(a, str(valor))
        if not v.ok or not v.valor:
            self.contador["recusadas_pelo_validador"] += 1
            return False

        # invariante 1: sem procedencia completa, Sugestao nem se constroi
        try:
            s = Sugestao(atributo=atributo, valor=v.valor, procedencia=proc,
                         derivado_de=derivado_de, metodo=metodo,
                         revisar=revisar, motivo=motivo or v.motivo)
        except ValueError:
            self.contador["recusadas_sem_procedencia"] += 1
            return False

        destino.append(s)
        self.contador["sugestoes"] += 1
        self.por_fonte[proc.fonte] = self.por_fonte.get(proc.fonte, 0) + 1
        self.por_atributo[atributo] = self.por_atributo.get(atributo, 0) + 1
        return True

    # ------------------------------------------------------------- registro

    def enriquecer(self, codigo: str, id_pdm: str, valores: dict[str, str | None],
                   texto: str = "", ncm_atual: object = "") -> Enriquecimento:
        """Propoe valores para as caixas vazias de UM registro ja saneado.

        `valores` e a grade como o pipeline a deixou: atributo -> valor ou None.
        `texto` e a descricao original, usada SO como lugar onde achar a chave de
        consulta (uma designacao, um part number) quando a caixa correspondente
        tambem ficou vazia. O valor devolvido continua vindo da tabela externa.
        """
        self.contador["registros"] += 1
        classe = self.pdm.classes.get(id_pdm)
        out = Enriquecimento(codigo=str(codigo), id_pdm=id_pdm)
        if classe is None:
            return out

        sug: list[Sugestao] = []
        self._rolamento(sug, classe, valores, texto, out.ficha)
        self._fixador(sug, classe, valores, out.ficha)
        self._ferramenta(sug, classe, valores, out.ficha)
        self._correia(sug, classe, valores, out.ficha)
        self._filtro(sug, classe, valores, texto, out.ficha)
        out.sugestoes = sug

        self._ncm(out, classe, valores, texto, ncm_atual)
        self.trilha.append(out)
        return out

    # --------------------------------------------------------- derivadores

    @staticmethod
    def _mm(valor: object) -> float | None:
        return parse_numero(re.sub(r"[A-Z]+$", "", normalizar(valor or "")))

    def _rolamento(self, sug, classe, valores, texto, ficha) -> None:
        if classe.id_pdm not in FAMILIA_POR_CLASSE:
            return
        self._rolamento_por_medidas(sug, classe, valores, ficha)
        chave = valores.get("REFERENCIA") or ""
        origem = "caixa REFERENCIA"
        if not chave:
            # a caixa REFERENCIA tambem ficou vazia: procura a designacao no
            # texto. O que sai continua vindo da ISO 15, nao do texto.
            chave, origem = texto, "designacao achada na descricao original"
        dados = analisar_rolamento(chave)
        if not dados:
            return
        ficha["ROLAMENTO_SERIE"] = f"{dados['familia']} serie {dados['serie']}"

        proc_dim = _norma("iso15_rolamento", REF_ISO15, 0.97)
        for nome in ("DIAMETRO INTERNO", "DIAMETRO EXTERNO", "LARGURA"):
            if nome in dados:
                metodo = ("formula do codigo de furo (d = 5 x codigo)"
                          if nome == "DIAMETRO INTERNO"
                          else f"tabela ISO 15, serie {dados['serie']}")
                self._propor(sug, classe, valores, nome, fmt_mm(dados[nome]),
                             proc_dim, f"{origem}: {normalizar(chave)[:40]}", metodo)

        proc_suf = _norma("designacao_fabricante", REF_ISO5753, 0.93)
        for nome, chave_suf in (("VEDACAO", "sufixo_vedacao"),
                                ("FOLGA", "sufixo_folga"),
                                ("FURO", "sufixo_furo")):
            if nome in dados:
                self._propor(sug, classe, valores, nome, dados[nome], proc_suf,
                             f"{origem}: sufixo {dados[chave_suf]}",
                             f"tabela de sufixos de designacao ({dados[chave_suf]})")

    def _rolamento_por_medidas(self, sug, classe, valores, ficha) -> None:
        """Caminho de volta: as medidas estao no cadastro, a referencia nao."""
        if valores.get("REFERENCIA"):
            return
        r = designacao_por_dimensoes(
            FAMILIA_POR_CLASSE[classe.id_pdm],
            self._mm(valores.get("DIAMETRO INTERNO")),
            self._mm(valores.get("DIAMETRO EXTERNO")),
            self._mm(valores.get("LARGURA")),
        )
        if not r:
            return
        designacao, serie = r
        ficha["ROLAMENTO_SERIE_DEDUZIDA"] = f"{serie} -> {designacao}"
        self._propor(
            sug, classe, valores, "REFERENCIA", designacao,
            _norma("iso15_rolamento", REF_ISO15, 0.80),
            "caixas DIAMETRO INTERNO + DIAMETRO EXTERNO + LARGURA",
            f"busca inversa na tabela ISO 15 (serie {serie})", revisar=True,
            motivo=("serie unica na norma para estas medidas; FALTA o sufixo de "
                    "vedacao e folga, que a norma nao deduz das medidas"))

    def _ferramenta(self, sug, classe, valores, ficha) -> None:
        """PDM082: a norma da broca e a haste se determinam uma a outra."""
        if classe.id_pdm != "PDM082":
            return
        proc = _norma("din_broca", REF_DIN_BROCA, 0.93)
        haste, norma = normalizar(valores.get("HASTE") or ""), \
            normalizar(valores.get("NORMA") or "")
        if norma in HASTE_POR_NORMA_BROCA:
            self._propor(sug, classe, valores, "HASTE", HASTE_POR_NORMA_BROCA[norma],
                         proc, f"caixa NORMA: {norma}",
                         "tabela norma de broca -> tipo de haste",
                         motivo=f"{norma} e norma de broca de haste "
                                f"{HASTE_POR_NORMA_BROCA[norma]}")
        if haste in NORMA_BROCA_POR_HASTE:
            self._propor(sug, classe, valores, "NORMA", NORMA_BROCA_POR_HASTE[haste],
                         proc, f"caixa HASTE: {haste}",
                         "tabela tipo de haste -> norma de broca",
                         motivo="DIN 345 e a unica das tres que usa cone Morse")

    def _fixador(self, sug, classe, valores, ficha) -> None:
        bitola = valores.get("BITOLA") or ""
        b = analisar_bitola(bitola)
        if b:
            ficha["PASSO_ROSCA_MM"] = f"{b['passo']:g}"
            if "chave_cabeca" in b:
                ficha["CABECA_CHAVE_MM"] = f"{b['chave_cabeca']:g}"
                ficha["CABECA_ALTURA_MM"] = f"{b['altura_cabeca']:g}"
            if "chave_porca" in b:
                ficha["PORCA_CHAVE_MM"] = f"{b['chave_porca']:g}"
                ficha["PORCA_ALTURA_DIN934_MM"] = f"{b['altura_porca_din934']:g}"
                ficha["PORCA_ALTURA_DIN985_MM"] = f"{b['altura_porca_din985']:g}"
            # o passo responde ROSCA: a tabela ISO 261 diz qual passo e o grosso
            self._propor(sug, classe, valores, "ROSCA", b["rosca"],
                         _norma("iso261_passo", REF_ISO261, 0.96),
                         f"caixa BITOLA: {normalizar(bitola)}",
                         f"passo {b['passo']:g}MM contra o passo grosso ISO 261")

        if classe.id_pdm in ("PDM001", "PDM002"):
            r = norma_parafuso_sextavado(valores.get("ROSCA") or "", bitola,
                                         valores.get("COMPRIMENTO") or "")
            if r:
                norma, motivo = r
                ref = REF_ASME if norma.startswith("ASME") else f"{REF_ISO4014}; {REF_ISO4017}"
                self._propor(sug, classe, valores, "NORMA", norma,
                             _norma("din_iso_parafuso", ref, 0.90),
                             "caixas ROSCA + BITOLA + COMPRIMENTO",
                             "restricao geometrica do DIN 931 (b = 2d + 6)",
                             motivo=motivo)

        if classe.id_pdm == "PDM003":
            proc = _norma("din_iso_porca", REF_ISO4032, 0.95)
            r = norma_porca(valores.get("TIPO") or "")
            if r:
                norma, motivo = r
                self._propor(sug, classe, valores, "NORMA", norma, proc,
                             f"caixa TIPO: {normalizar(valores.get('TIPO') or '')}",
                             "tabela tipo de porca -> norma", motivo=motivo)
            # o mapa e bijetivo: a norma tambem responde o tipo
            norma_cad = normalizar(valores.get("NORMA") or "")
            if norma_cad in TIPO_PORCA_POR_NORMA:
                tipo = TIPO_PORCA_POR_NORMA[norma_cad]
                self._propor(sug, classe, valores, "TIPO", tipo, proc,
                             f"caixa NORMA: {norma_cad}",
                             "tabela norma -> tipo de porca",
                             motivo=f"{norma_cad} define a porca {tipo}")

    def _correia(self, sug, classe, valores, ficha) -> None:
        if classe.id_pdm != "PDM030":
            return
        r = circunferencia_correia(valores.get("PERFIL") or "",
                                   valores.get("REFERENCIA") or "")
        if not r:
            return
        circ, metodo = r
        ficha["CIRCUNFERENCIA_EXTERNA_MM"] = f"{circ:g}"
        self._propor(sug, classe, valores, "COMPRIMENTO EXTERNO", fmt_mm(circ),
                     _norma("iso4184_correia", REF_ISO4184, 0.90),
                     "caixas PERFIL + REFERENCIA", metodo)

    def _filtro(self, sug, classe, valores, texto, ficha) -> None:
        if classe.id_pdm != "PDM100":
            return
        ref = valores.get("REFERENCIA FABRICANTE") or ""
        r = fabricante_por_part_number(ref)
        if not r:
            return
        fab, tipo, prefixo = r
        tipo = tipo or tipo_filtro_por_texto(texto)
        if tipo:
            ficha["TIPO_FILTRO"] = tipo
        self._propor(sug, classe, valores, "FABRICANTE", fab,
                     _norma("prefixo_part_number_filtro", REF_PREFIXO_FILTRO, 0.88),
                     f"caixa REFERENCIA FABRICANTE: {normalizar(ref)[:30]}",
                     f"prefixo {prefixo} do sistema de codificacao do fabricante")

    # --------------------------------------------------------------- ncm

    def _ncm(self, out: Enriquecimento, classe: Classe, valores, texto,
             ncm_atual: object = "") -> None:
        """Fonte (a): existencia e vigencia na tabela oficial, e so depois valor.

        Tres situacoes, tres respostas:
          codigo presente e vigente        -> VIGENTE, nada a fazer
          codigo presente e NAO vigente    -> NAO_VIGENTE + candidato a sucessor,
                                              sempre marcado para revisao
          codigo ausente e classe com NCM  -> AUSENTE + valor derivado da regra
                                              condicional do PDM, conferido na
                                              tabela oficial antes de sair
        """
        if self.ncm_oficial is None:
            out.ncm_veredito = "SEM_TABELA"
            out.ncm_motivo = ("tabela oficial da NCM nao esta em dados/referencia/: "
                              "existencia e vigencia NAO foram verificadas")
            self.contador["ncm_sem_tabela"] += 1
            return

        tabela = self.ncm_oficial
        atual = digitos_ncm(ncm_atual)

        if len(atual) == 8:
            if tabela.vigente(atual):
                out.ncm_veredito = "VIGENTE"
                out.ncm_motivo = tabela.descricao(atual)[:120]
                self.contador["ncm_vigente"] += 1
                return
            out.ncm_veredito = "NAO_VIGENTE"
            self.contador["ncm_nao_vigente"] += 1
            suc = tabela.sucessor(atual)
            if suc:
                codigo, motivo = suc
                out.ncm_motivo = (f"{formata_ncm(atual)} nao esta na tabela oficial; "
                                  f"candidato {formata_ncm(codigo)}: {motivo}")
                out.ncm = Sugestao(
                    atributo="NCM", valor=formata_ncm(codigo),
                    procedencia=tabela.procedencia(0.55),
                    derivado_de=f"NCM do cadastro {formata_ncm(atual)} (inexistente)",
                    metodo="unico irmao vigente ou residual 'Outros' da subposicao",
                    revisar=True, motivo=motivo)
            else:
                out.ncm_motivo = (f"{formata_ncm(atual)} nao esta na tabela oficial e a "
                                  f"subposicao nao tem sucessor unico: classificacao "
                                  f"fiscal manual")
            return

        # NCM ausente: a classe pode ter NCM unico (o pipeline ja resolve) ou
        # condicional (o pipeline deixa vazio, e e aqui que se resolve)
        out.ncm_veredito = "AUSENTE"
        self.contador["ncm_ausente"] += 1
        candidato = motivo = ""
        if classe.id_pdm == "PDM030":
            r = circunferencia_correia(valores.get("PERFIL") or "",
                                       valores.get("REFERENCIA") or "")
            if r:
                candidato, motivo = ncm_correia(r[0])
        elif classe.id_pdm == "PDM100":
            tipo = out.ficha.get("TIPO_FILTRO") or tipo_filtro_por_texto(texto)
            candidato = NCM_POR_TIPO_FILTRO.get(tipo, "")
            motivo = f"filtro de {tipo}" if candidato else ""
        elif len(classe.ncm) == 1:
            candidato, motivo = classe.ncm[0], f"NCM unico da classe {classe.id_pdm}"

        if not candidato:
            out.ncm_motivo = (f"classe {classe.id_pdm} tem NCM condicional e o atributo "
                              f"que decide a regra esta vazio")
            return
        if not tabela.vigente(candidato):
            out.ncm_motivo = (f"candidato {formata_ncm(candidato)} derivado da regra do PDM "
                              f"NAO esta vigente na tabela oficial: regra do PDM desatualizada")
            return
        if classe.ncm and candidato not in classe.ncm:
            out.ncm_motivo = f"candidato {formata_ncm(candidato)} fora da lista da classe"
            return
        out.ncm = Sugestao(
            atributo="NCM", valor=formata_ncm(candidato),
            procedencia=tabela.procedencia(0.92),
            derivado_de=f"regra condicional do PDM para {classe.id_pdm}",
            metodo="regra NCM_REFERENCIA do PDM, conferida na tabela oficial",
            motivo=f"{motivo}; vigente: {tabela.descricao(candidato)[:80]}")
        out.ncm_motivo = out.ncm.motivo
        self.contador["ncm_preenchido"] += 1

    # --------------------------------------------------------------- io

    def salvar(self, destino: str | Path) -> int:
        """Grava a trilha de auditoria em JSON: uma linha por sugestao."""
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "versao": 1,
            "gerado_em": _hoje(),
            "fontes": {
                "ncm_oficial": self.ncm_oficial.meta if self.ncm_oficial else None,
                "tabelas_tecnicas": [REF_ISO15, REF_ISO5753, REF_ISO261, REF_ISO4014,
                                     REF_ISO4017, REF_ISO4032, REF_ASME, REF_ISO4184,
                                     REF_DIN_BROCA, REF_PREFIXO_FILTRO],
                "catalogo_fabricante": CATALOGO_TENTADO,
            },
            "estatisticas": self.estatisticas(),
            "enriquecimentos": [
                {
                    "codigo": e.codigo, "id_pdm": e.id_pdm,
                    "ncm_veredito": e.ncm_veredito, "ncm_motivo": e.ncm_motivo,
                    "ncm": e.ncm.como_dict() if e.ncm else None,
                    "ficha": e.ficha,
                    "sugestoes": [s.como_dict() for s in e.sugestoes],
                }
                for e in self.trilha if e.sugestoes or e.ncm
            ],
        }
        destino.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        return len(payload["enriquecimentos"])

    def estatisticas(self) -> dict:
        return {
            **self.contador,
            "por_fonte": dict(sorted(self.por_fonte.items(), key=lambda x: -x[1])),
            "por_atributo": dict(sorted(self.por_atributo.items(), key=lambda x: -x[1])),
            "tem_tabela_ncm": self.ncm_oficial is not None,
        }


__all__ = [
    "ACRESCIMO_EXTERNO_CORREIA", "ARQUIVO_NCM", "CABECA_SEXTAVADA",
    "CATALOGO_TENTADO", "Enriquecedor", "Enriquecimento", "FAMILIA_POR_CLASSE",
    "HASTE_POR_NORMA_BROCA", "ISO15_ESFERAS", "ISO15_ROLOS_CONICOS",
    "ISO15_ROLOS_ESFERICOS", "NCM_POR_TIPO_FILTRO", "NORMA_BROCA_POR_HASTE",
    "NORMA_POR_TIPO_PORCA", "PASSO_METRICO_GROSSO", "PORCA_SEXTAVADA",
    "PREFIXO_FILTRO", "Procedencia", "SUFIXO_FOLGA", "SUFIXO_FURO",
    "SUFIXO_VEDACAO", "Sugestao", "TIPO_ENRIQUECIDO", "TIPO_PORCA_POR_NORMA",
    "TabelaNcm", "URL_NCM_SISCOMEX", "analisar_bitola", "analisar_rolamento",
    "circunferencia_correia", "codigo_furo_por_diametro",
    "comprimento_rosca_din931", "designacao_por_dimensoes", "diametro_interno_por_codigo",
    "digitos_ncm", "fabricante_por_part_number", "formata_ncm", "ncm_correia",
    "norma_parafuso_sextavado", "norma_porca", "tipo_filtro_por_texto",
]
