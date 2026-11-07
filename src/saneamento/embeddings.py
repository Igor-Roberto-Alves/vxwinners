"""Embedding de caixas textuais: canonizar valor e comparar registro a registro.

Dois usos, nesta ordem:

  1. CANONIZAR  caixa TEXTUAL -> valor permitido do PDM mais proximo.
                'INOX 316' -> ACO INOX 316;  'nitrilica' -> NBR
  2. COMPARAR   caixa LIVRE de um registro x caixa LIVRE de outro, para decidir
                duplicidade quando a chave de identidade nao fecha.

Em ambos o que decide nao e so a similaridade: e a MARGEM sobre o segundo
colocado. ACO INOX 304 e ACO INOX 316 sao quase o mesmo vetor, e confundir os
dois cria um item errado na base. Com margem baixa, a caixa vai para o LLM.

Caixas NUMERICA e LIVRE nao passam por aqui na etapa 1: numero e part number se
resolvem por gramatica e por igualdade de string, nunca por proximidade vetorial.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .texto import normalizar

# e5-small multilingue: 384 dimensoes, roda em CPU, bom em portugues tecnico.
# O prefixo 'query: ' / 'passage: ' e exigido pela familia e5.
MODELO_PADRAO = "intfloat/multilingual-e5-small"
PREFIXO_CONSULTA = "query: "
PREFIXO_ALVO = "passage: "


@dataclass
class Acerto:
    valor: str | None
    similaridade: float = 0.0
    margem: float = 0.0
    segundo: str | None = None
    exato: bool = False


class Codificador:
    """Encoder com cache em memoria e em disco. Sem sentence-transformers."""

    def __init__(self, modelo: str = MODELO_PADRAO, lote: int = 64,
                 cache: str | Path | None = None):
        self.nome = modelo
        self.lote = lote
        self.cache = Path(cache) if cache else None
        self._tok = None
        self._modelo = None
        self._memo: dict[str, list[float]] = {}
        self.erro = ""
        if self.cache and self.cache.exists():
            try:
                self._memo = json.loads(self.cache.read_text(encoding="utf-8"))
            except Exception:
                self._memo = {}

    # ------------------------------------------------------------- carga

    def _montar(self):
        if self._modelo is not None:
            return True
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            self._torch = torch
            self._tok = AutoTokenizer.from_pretrained(self.nome)
            self._modelo = AutoModel.from_pretrained(self.nome)
            self._modelo.eval()
            return True
        except Exception as e:
            self.erro = f"{type(e).__name__}: {e}"
            return False

    # ------------------------------------------------------------- encode

    def codificar(self, textos: list[str], prefixo: str = PREFIXO_CONSULTA):
        """Devolve lista de vetores normalizados (norma 1), usando cache."""
        chaves = [prefixo + normalizar(t) for t in textos]
        faltando = [k for k in dict.fromkeys(chaves) if k not in self._memo]

        if faltando:
            if not self._montar():
                raise RuntimeError(f"encoder indisponivel: {self.erro}")
            torch = self._torch
            with torch.no_grad():
                for i in range(0, len(faltando), self.lote):
                    bloco = faltando[i:i + self.lote]
                    enc = self._tok(bloco, padding=True, truncation=True,
                                    max_length=64, return_tensors="pt")
                    saida = self._modelo(**enc).last_hidden_state
                    mascara = enc["attention_mask"].unsqueeze(-1).float()
                    # media ponderada pela mascara (mean pooling da familia e5)
                    vet = (saida * mascara).sum(1) / mascara.sum(1).clamp(min=1e-9)
                    vet = torch.nn.functional.normalize(vet, p=2, dim=1)
                    for k, v in zip(bloco, vet.tolist()):
                        self._memo[k] = v
        return [self._memo[k] for k in chaves]

    def um(self, texto: str, prefixo: str = PREFIXO_CONSULTA) -> list[float]:
        return self.codificar([texto], prefixo)[0]

    def salvar_cache(self) -> None:
        if self.cache:
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            self.cache.write_text(json.dumps(self._memo), encoding="utf-8")


def cosseno(a: list[float], b: list[float]) -> float:
    """Vetores ja vem normalizados: o produto interno e o cosseno."""
    return sum(x * y for x, y in zip(a, b))


class CanonizadorSemantico:
    """Etapa 1: caixa TEXTUAL -> valor permitido do PDM."""

    def __init__(self, codificador: Codificador):
        self.cod = codificador
        self._vocab: dict[str, tuple[list[str], list[list[float]]]] = {}

    def preparar(self, atributos) -> None:
        """Pre-calcula o vetor de cada valor permitido, uma vez por atributo."""
        for a in atributos:
            if not a.fechado or a.nome in self._vocab:
                continue
            valores = list(a.valores)
            self._vocab[a.nome] = (valores, self.cod.codificar(valores, PREFIXO_ALVO))

    def casar(self, atributo, texto: str) -> Acerto:
        """Casa o texto da caixa contra a lista de valores, com margem."""
        if not texto or not atributo.fechado:
            return Acerto(None)

        # casamento literal primeiro: embedding nao melhora o que ja e exato
        canonico = atributo.chaves.get(normalizar(texto))
        if canonico:
            return Acerto(canonico, 1.0, 1.0, None, exato=True)

        if atributo.nome not in self._vocab:
            self.preparar([atributo])
        valores, vetores = self._vocab[atributo.nome]
        if not valores:
            return Acerto(None)

        v = self.cod.um(texto)
        sims = sorted(((cosseno(v, u), nome) for nome, u in zip(valores, vetores)),
                      reverse=True)
        s1, melhor = sims[0]
        s2, segundo = sims[1] if len(sims) > 1 else (0.0, None)
        return Acerto(melhor, s1, s1 - s2, segundo)


class ComparadorDeCaixas:
    """Etapa 2: caixa LIVRE de um registro x caixa LIVRE de outro.

    Usado so quando a chave de identidade nao fecha por igualdade. Devolve a
    similaridade media das caixas comparaveis e quantas bateram exatamente.
    """

    def __init__(self, codificador: Codificador):
        self.cod = codificador

    def comparar(self, a: dict[str, str | None], b: dict[str, str | None],
                 so_atributos: list[str] | None = None) -> dict:
        nomes = [n for n in (so_atributos or set(a) | set(b))
                 if a.get(n) and b.get(n)]
        if not nomes:
            return {"similaridade": 0.0, "exatas": 0, "comparadas": 0, "por_caixa": {}}

        textos = [a[n] for n in nomes] + [b[n] for n in nomes]
        vet = self.cod.codificar(textos)
        meio = len(nomes)
        por_caixa, exatas = {}, 0
        for i, n in enumerate(nomes):
            if normalizar(a[n]) == normalizar(b[n]):
                s, exatas = 1.0, exatas + 1
            else:
                s = cosseno(vet[i], vet[meio + i])
            por_caixa[n] = round(s, 3)
        return {
            "similaridade": sum(por_caixa.values()) / len(por_caixa),
            "exatas": exatas,
            "comparadas": len(nomes),
            "por_caixa": por_caixa,
        }
