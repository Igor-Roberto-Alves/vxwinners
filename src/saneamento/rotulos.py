"""Distant supervision: rotulos de treino tirados da propria base, sem anotar a mao.

59,9% dos registros (14.112) ja trazem pares explicitos "ATRIBUTO: VALOR" na
descricao longa, somando 59.318 pares, dos quais 76,8% casam com um nome de
atributo do PDM. Sao ~45 mil anotacoes atributo-valor de graca.

O detalhe que faz isso funcionar: o NOME DO ATRIBUTO E REMOVIDO do texto de
treino. Se ele ficasse, o modelo aprenderia apenas "copie o que vem depois dos
dois pontos" - inutil nos 40% de registros telegraficos (RET. 110MM 15MM BASL
NBR), que sao exatamente o alvo. Treinando so com os valores, na ordem em que
aparecem, a entrada passa a ter a mesma distribuicao do texto cru.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from .pdm import Pdm
from .regras import ClassificadorLexico
from .texto import normalizar, normalizar_estrutura

# Rotulos usados na base legada que nao batem com o nome do PDM.
# Medidos em docs/01-dados.md (top rotulos nao reconhecidos).
SINONIMO_ROTULO = {
    "C": "COMPRIMENTO", "COMP": "COMPRIMENTO", "COMPR": "COMPRIMENTO",
    "LARG": "LARGURA", "ESP": "ESPESSURA",
    "DIAM": "DIAMETRO NOMINAL", "DIAM NOMINAL": "DIAMETRO NOMINAL",
    "DIAM INTERNO": "DIAMETRO INTERNO", "DIAM INT": "DIAMETRO INTERNO",
    "DIAM EXTERNO": "DIAMETRO EXTERNO", "DIAM EXT": "DIAMETRO EXTERNO",
    "DIAM EIXO": "DIAMETRO EIXO", "DIAM ALOJAMENTO": "DIAMETRO ALOJAMENTO",
    "MAT": "MATERIAL", "MAT CORPO": "MATERIAL CORPO",
    "APLIC": "APLICACAO", "USO": "APLICACAO", "PARA": "APLICACAO",
    "MOD": "MODELO EQUIPAMENTO", "MODELO": "MODELO EQUIPAMENTO",
    "EQUIP": "MODELO EQUIPAMENTO",
    "FABR": "FABRICANTE", "FAB": "FABRICANTE", "MARCA": "FABRICANTE",
    "REF": "REFERENCIA FABRICANTE", "REF FABRICANTE": "REFERENCIA FABRICANTE",
    "COD FABRICANTE": "REFERENCIA FABRICANTE", "P/N": "REFERENCIA FABRICANTE",
    "PART NUMBER": "REFERENCIA FABRICANTE", "PN": "REFERENCIA FABRICANTE",
    "CL": "CLASSE RESISTENCIA", "CLASSE": "CLASSE RESISTENCIA",
    "NORMA CONSTRUCAO": "NORMA", "PADRAO": "NORMA", "CONF": "NORMA",
    "PRESSAO": "PRESSAO TRABALHO", "TENSAO": "TENSAO ISOLAMENTO",
}

RX_PAR = re.compile(
    r"([A-Z/ ]{1,30}?)\s*:\s*"              # rotulo
    r"(.+?)"                                 # valor, o menor possivel
    r"(?=\s*[;,]|\s+[A-Z][A-Z0-9/ ]{0,28}\s*:|\s*$)"   # ate o delimitador ou o proximo rotulo
)


@dataclass
class Exemplo:
    codigo: str
    id_pdm: str
    tokens: list[str]
    rotulos: list[str]
    texto_original: str


def pares(descricao: str) -> list[tuple[str, str]]:
    """Extrai os pares ATRIBUTO: VALOR da descricao legada, ja com sinonimo resolvido."""
    out = []
    for rotulo, valor in RX_PAR.findall(normalizar_estrutura(descricao)):
        r = normalizar(rotulo).strip(" -")
        v = normalizar(valor).strip(" -")
        if not r or not v:
            continue
        out.append((SINONIMO_ROTULO.get(r, r), v))
    return out


class GeradorRotulos:
    def __init__(self, pdm: Pdm, semente: int = 42):
        self.pdm = pdm
        self.clf = ClassificadorLexico(pdm)
        self.rng = random.Random(semente)

    def exemplo(self, codigo: str, descricao: str, grupo: str,
                dropout: float = 0.0, manter_rotulos: bool = False) -> Exemplo | None:
        """Monta um exemplo BIO a partir de um registro auto-rotulado.

        dropout: probabilidade de descartar um atributo, simulando dado ausente -
        ensina o modelo a deixar slot vazio em vez de forcar preenchimento.
        """
        achados = pares(descricao)
        if not achados:
            return None

        sujeito = self.clf.classificar(descricao, grupo)
        if sujeito.classe is None:
            return None
        classe = sujeito.classe
        validos = {a.nome for a in classe.atributos}

        tokens: list[str] = []
        rotulos: list[str] = []

        # o sujeito abre o texto e nao recebe rotulo de atributo
        for t in f"{sujeito.substantivo} {sujeito.qualificador}".split():
            tokens.append(t)
            rotulos.append("O")

        usados = 0
        for rotulo, valor in achados:
            if rotulo not in validos:
                continue
            if dropout and self.rng.random() < dropout:
                continue
            partes = valor.split()
            if not partes:
                continue
            if manter_rotulos:  # variante de diagnostico: deixa o rotulo no texto (vaza)
                for t in rotulo.split():
                    tokens.append(t)
                    rotulos.append("O")
            for i, t in enumerate(partes):
                tokens.append(t)
                rotulos.append(("B-" if i == 0 else "I-") + rotulo)
            usados += 1

        if usados < 2 or len(tokens) < 3:
            return None
        return Exemplo(codigo, classe.id_pdm, tokens, rotulos, normalizar(descricao))

    def gerar(self, registros: list[dict], dropout: float = 0.15,
              manter_rotulos: bool = False) -> list[Exemplo]:
        out = []
        for r in registros:
            ex = self.exemplo(
                r["CODIGO_MATERIAL"], r["DESCRICAO_LONGA"], r["GRUPO_MERCADORIA"],
                dropout=dropout, manter_rotulos=manter_rotulos,
            )
            if ex:
                out.append(ex)
        return out

    # ------------------------------------------------------------------ io

    @staticmethod
    def salvar(exemplos: list[Exemplo], destino: str | Path) -> None:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("w", encoding="utf-8") as fh:
            for e in exemplos:
                fh.write(json.dumps({
                    "codigo": e.codigo, "id_pdm": e.id_pdm,
                    "tokens": e.tokens, "rotulos": e.rotulos,
                }, ensure_ascii=False) + "\n")

    @staticmethod
    def ler(origem: str | Path) -> list[dict]:
        with Path(origem).open(encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    @staticmethod
    def dividir(exemplos: list[dict], validacao: float = 0.1, semente: int = 42):
        """Separa treino e validacao por CODIGO, nunca por linha, para nao vazar."""
        rng = random.Random(semente)
        codigos = sorted({e["codigo"] for e in exemplos})
        rng.shuffle(codigos)
        corte = int(len(codigos) * (1 - validacao))
        treino_cod = set(codigos[:corte])
        treino = [e for e in exemplos if e["codigo"] in treino_cod]
        val = [e for e in exemplos if e["codigo"] not in treino_cod]
        return treino, val
