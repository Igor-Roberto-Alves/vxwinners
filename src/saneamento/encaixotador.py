"""Encaixotador: transforma a linha crua na grade de caixas, em cascata.

Ordem das camadas por caixa, do barato e certo para o caro e incerto. A ordem
foi definida por medicao, nao por gosto (ver sinonimos.py para os numeros):

  1. CASAMENTO LITERAL     valor permitido aparece no texto           -> EXATA
  2. DICIONARIO            sinonimo curado de dominio                 -> EXATA
  3. BERT                  recorta QUAL trecho pertence a cada caixa
  4. GRAMATICA             grandeza com formato fixo (MM, POL, BAR)
  5. EMBEDDING             casa o trecho recortado com o vocabulario   -> ALTA ou BANDA_LLM
  6. LLM                   so nas caixas da banda do meio

O embedding entra em quinto porque ele nao recorta nada: ele precisa receber um
trecho ja atribuido a uma caixa. Quem recorta e o BERT (ou o fatiamento por
delimitador). Primeiro se decide DE QUEM e o texto, depois O QUE o texto quer
dizer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .caixas import (
    ALTA, BAIXA, BANDA_LLM, EXATA, LIVRE, NUMERICA, TEXTUAL, VAZIA,
    Caixa, Grade, classificar_banda, fatiar, grade_vazia,
)
from .pdm import Classe, Pdm
from .regras import ClassificadorLexico, ExtratorLexico
from .sinonimos import canonizar as canonizar_dicionario
from .texto import expandir, juntar, normalizar
from .validador import Validador


@dataclass
class Contadores:
    linhas: int = 0
    sem_classe: int = 0
    tudo_bate: int = 0
    com_banda_llm: int = 0
    caixas: int = 0
    por_fonte: dict = None
    por_banda: dict = None

    def __post_init__(self):
        self.por_fonte = {}
        self.por_banda = {}

    def conta(self, caixa: Caixa) -> None:
        self.caixas += 1
        if caixa.cheia:
            self.por_fonte[caixa.fonte] = self.por_fonte.get(caixa.fonte, 0) + 1
        self.por_banda[caixa.banda] = self.por_banda.get(caixa.banda, 0) + 1


class Encaixotador:
    def __init__(self, pdm: Pdm, bert=None, canonizador=None,
                 limiar_alta: float = 0.92, limiar_banda: float = 0.75,
                 margem_minima: float = 0.04, limiar_bert: float = 0.60):
        self.pdm = pdm
        self.clf = ClassificadorLexico(pdm)
        self.regras = ExtratorLexico(pdm)
        self.validador = Validador(pdm)
        self.bert = bert
        self.canon = canonizador
        self.limiar_alta = limiar_alta
        self.limiar_banda = limiar_banda
        self.margem_minima = margem_minima
        self.limiar_bert = limiar_bert
        self.contadores = Contadores()

    # ------------------------------------------------------------- texto

    @staticmethod
    def texto_da_linha(registro: dict) -> str:
        return juntar(*(
            str(registro.get(c, "") or "")
            for c in ("DESCRICAO_LONGA", "DESCRICAO_CURTA", "FABRICANTE",
                      "REFERENCIA_FABRICANTE")
        ))

    # ------------------------------------------------------------- recorte

    def _recortes_bert(self, texto: str, classe: Classe) -> dict[str, tuple[str, float]]:
        """BERT diz qual trecho do texto pertence a qual caixa."""
        if self.bert is None:
            return {}
        tokens = expandir(texto).split()
        if not tokens:
            return {}
        validos = {a.nome for a in classe.atributos}
        out: dict[str, tuple[str, float]] = {}
        for p in self.bert.prever(tokens):
            if p.atributo not in validos:
                continue
            atual = out.get(p.atributo)
            if atual is None or p.confianca > atual[1]:
                out[p.atributo] = (p.valor, p.confianca)
        return out

    # ------------------------------------------------------------- canonizar

    def _canonizar(self, atributo, trecho: str, conf_recorte: float) -> dict:
        """Trecho recortado -> valor permitido do PDM, com banda de confianca."""
        # 2. dicionario de dominio, antes do vetor
        por_dicionario = canonizar_dicionario(atributo, trecho)
        if por_dicionario:
            exato = normalizar(trecho) in atributo.chaves
            return {"valor": por_dicionario,
                    "fonte": "literal" if exato else "dicionario",
                    "confianca": 0.99 if exato else 0.96,
                    "similaridade": 1.0, "margem": 1.0, "banda": EXATA,
                    "motivo": "" if exato else f"sinonimo de dominio: {trecho}"}

        # 5. embedding: so agora, e sempre com margem e trava de gemeo numerico
        if self.canon is None:
            return {}
        acerto = self.canon.casar(atributo, trecho)
        if acerto.valor is None:
            return {}
        banda = classificar_banda(
            acerto.similaridade, acerto.margem, acerto.exato,
            acerto.valor, acerto.segundo,
            self.limiar_alta, self.limiar_banda, self.margem_minima,
        )
        return {
            "valor": acerto.valor if banda in (EXATA, ALTA, BANDA_LLM) else None,
            "fonte": "embedding", "confianca": min(acerto.similaridade, conf_recorte or 1.0),
            "similaridade": acerto.similaridade, "margem": acerto.margem,
            "banda": banda,
            "alternativas": tuple(x for x in (acerto.valor, acerto.segundo) if x),
            "motivo": (f"vetor: {trecho!r} ~ {acerto.valor!r} "
                       f"(sim {acerto.similaridade:.3f}, margem {acerto.margem:.3f}"
                       + (f", gemeo numerico de {acerto.segundo!r}"
                          if banda == BANDA_LLM and acerto.segundo else "") + ")"),
        }

    # ------------------------------------------------------------- grade

    def encaixotar(self, registro: dict) -> Grade:
        self.contadores.linhas += 1
        codigo = str(registro.get("CODIGO_MATERIAL", ""))
        grupo = str(registro.get("GRUPO_MERCADORIA", "") or "").strip()
        texto = self.texto_da_linha(registro)

        sujeito = self.clf.classificar(texto, grupo)
        if sujeito.classe is None:
            self.contadores.sem_classe += 1
            return Grade(codigo=codigo, texto=texto)

        classe = sujeito.classe
        g = grade_vazia(classe, codigo, sujeito.substantivo, sujeito.qualificador, texto)
        g.confianca_sujeito = sujeito.confianca
        g.grupo_corrigido = sujeito.grupo_corrigido

        cand_regras = self.regras.extrair(texto, classe, sujeito.substantivo)
        recortes = self._recortes_bert(texto, classe)
        usados: list[str] = []

        for nome, caixa in g.caixas.items():
            atributo = next(a for a in classe.atributos if a.nome == nome)
            regra = cand_regras.get(nome)
            recorte = recortes.get(nome)

            # ---- 1. casamento literal pelo gazetteer (inclui a regra 2 do PDM)
            if regra is not None and regra.valor and not regra.ambiguo:
                caixa.bruto = regra.evidencia or regra.valor
                caixa.valor = regra.valor
                caixa.fonte = regra.fonte
                caixa.confianca = regra.confianca
                caixa.banda = EXATA
                caixa.similaridade = 1.0
                usados.append(caixa.bruto)
                self.contadores.conta(caixa)
                continue

            # ---- caixa NUMERICA: gramatica ou nada. Vetor nunca entra aqui.
            if caixa.tipo == NUMERICA:
                if regra is not None and regra.ambiguo:
                    caixa.alternativas = regra.alternativas
                    caixa.bruto = regra.evidencia
                    # valor presente mas sem folga: entra na banda do LLM para
                    # confirmacao, nunca e aceito direto nem descartado em silencio
                    caixa.valor = regra.valor
                    caixa.fonte = regra.fonte if regra.valor else ""
                    caixa.confianca = regra.confianca
                    caixa.banda = BANDA_LLM
                    caixa.motivo = (f"gramatica achou {len(regra.alternativas) or 'varios'} "
                                    f"valores candidatos: {list(regra.alternativas)[:4]}")
                elif recorte:
                    # BERT recortou o trecho; a gramatica apenas o formata
                    trecho, conf = recorte
                    v = self.validador.valor(atributo, trecho)
                    if v.ok:
                        caixa.bruto, caixa.valor = trecho, v.valor
                        caixa.fonte, caixa.confianca = "bert", conf
                        caixa.banda = ALTA if conf >= self.limiar_bert else BANDA_LLM
                        usados.append(trecho)
                    else:
                        caixa.bruto = trecho
                        caixa.banda = BANDA_LLM
                        caixa.motivo = f"BERT recortou {trecho!r}: {v.motivo}"
                self.contadores.conta(caixa)
                continue

            # ---- caixa LIVRE: part number e modelo. Igualdade de string, sem vetor.
            if caixa.tipo == LIVRE:
                if recorte:
                    trecho, conf = recorte
                    caixa.bruto = trecho
                    caixa.valor = self.validador.texto_padrao(trecho)
                    caixa.fonte = "bert"
                    caixa.confianca = conf
                    caixa.banda = ALTA if conf >= self.limiar_bert else BANDA_LLM
                    usados.append(trecho)
                self.contadores.conta(caixa)
                continue

            # ---- caixa TEXTUAL: dicionario, depois embedding
            trechos: list[tuple[str, float]] = []
            if recorte:
                trechos.append(recorte)
            if regra is not None and regra.ambiguo and regra.alternativas:
                # o gazetteer casou mais de um valor: cada um e um trecho candidato
                trechos += [(x, 0.5) for x in regra.alternativas]
            for fatia in fatiar(texto):
                if fatia not in usados and len(fatia) <= 40:
                    trechos.append((fatia, 0.3))

            melhor = {}
            for trecho, conf in trechos:
                r = self._canonizar(atributo, trecho, conf)
                if not r:
                    continue
                if not melhor or r["similaridade"] > melhor["similaridade"]:
                    melhor = {**r, "bruto": trecho}
                if r["banda"] == EXATA:
                    break

            if melhor:
                caixa.bruto = melhor.pop("bruto")
                for k, v in melhor.items():
                    setattr(caixa, k, v)
                if caixa.valor:
                    usados.append(caixa.bruto)
            elif regra is not None and regra.ambiguo:
                caixa.alternativas = regra.alternativas
                caixa.banda = BANDA_LLM
                caixa.motivo = f"dicionario ambiguo entre {list(regra.alternativas)}"
            self.contadores.conta(caixa)

        g.sobra = self._sobra(g, classe, texto)

        if g.tudo_bate:
            self.contadores.tudo_bate += 1
        elif g.para_llm:
            self.contadores.com_banda_llm += 1
        return g

    # ------------------------------------------------------------- sobra

    @staticmethod
    def _sobra(g: Grade, classe: Classe, texto: str) -> str:
        """Texto que nao foi atribuido a caixa nenhuma.

        Diagnostico de recorte: sobra grande significa que ha informacao na linha
        que o encaixotamento nao soube onde por. O desconto e feito sobre o texto
        JA EXPANDIDO, porque e nele que o casamento aconteceu ('ACO CARB' virou
        'ACO CARBONO' antes de bater no gazetteer). Descontam-se tambem os nomes
        de atributo e o sujeito: eles sao estrutura da descricao, nao conteudo
        orfao.
        """
        restante = f" {expandir(texto)} "
        descartar: list[str] = []
        for c in g.caixas.values():
            descartar += [c.valor or "", c.bruto or ""]
            descartar.append(c.atributo)                 # rotulo no texto e estrutura
        descartar += [g.substantivo, g.qualificador]
        descartar += [a.nome for a in classe.atributos]

        for d in sorted((x for x in descartar if x), key=len, reverse=True):
            restante = restante.replace(f" {normalizar(d)} ", "  ")
        return " ".join(restante.split())
