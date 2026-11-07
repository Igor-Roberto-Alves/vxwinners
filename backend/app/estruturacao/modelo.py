from __future__ import annotations

from dataclasses import dataclass, field

from ..pdm.modelo import Pdm


@dataclass
class Valor:
    valor: str | None          # canônico; None = não deu para validar
    bruto: str | None
    origem: str                # REGRA_ROTULO, REGRA_TEXTO, REGRA_PDM, COLUNA_ERP, LLM, ...
    trecho: str | None
    confianca: float
    candidatos: tuple[str, ...] = ()


@dataclass
class Extracao:
    id_pdm: str | None = None
    nome: str | None = None
    confianca_classe: float = 0.0
    metodo: str = "REGRA"
    valores: dict[str, Valor] = field(default_factory=dict)
    ambiguas: tuple[tuple[str, str], ...] = ()      # (nome, id_pdm) quando a classe ficou ambígua
    avisos: list[str] = field(default_factory=list)

    def valores_planos(self, minimo: float = 0.0) -> dict[str, str | None]:
        return {k: v.valor for k, v in self.valores.items() if v.valor and v.confianca >= minimo}

    def faltando(self, pdm: Pdm, minimo: float = 0.0) -> list[str]:
        if not self.id_pdm:
            return []
        plano = self.valores_planos(minimo)
        return [a.nome for a in pdm.obrigatorios_aplicaveis(self.id_pdm, self.nome or "", plano) if a.nome not in plano]
