"""Visão em memória do PDM ativo. É pequeno (44 classes, 229 atributos) e imutável."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..normalizacao.texto import normaliza
from . import condicoes


@dataclass(frozen=True)
class Atributo:
    ordem: int
    nome: str
    obrigatorio: bool
    quando: str
    formato: str
    valores: tuple[str, ...]
    tipo: str

    @property
    def opcional_por_fabricante(self) -> bool:
        return self.quando.lower().startswith("quando informado")


@dataclass(frozen=True)
class Classe:
    id_pdm: str
    substantivo: str
    qualificador: str
    grupo: str
    unidade: str
    ncm: str
    criterio: str
    guarda_chuva: bool
    atributos: tuple[Atributo, ...]
    nomes: tuple[str, ...]

    @property
    def por_referencia(self) -> bool:
        return self.criterio == "REFERENCIA"

    def atributo(self, nome: str) -> Atributo | None:
        return next((a for a in self.atributos if a.nome == nome), None)


@dataclass
class Pdm:
    versao_id: int | None
    classes: dict[str, Classe]
    grupos: dict[str, str]
    unidades: dict[str, str]
    ncm_regras: dict[str, list[dict]]
    regras_gerais: list[str]
    _nome_para_classe: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def de_dict(cls, d: dict, versao_id: int | None = None) -> "Pdm":
        classes = {}
        for idp, c in d["classes"].items():
            classes[idp] = Classe(
                id_pdm=idp, substantivo=c["substantivo"], qualificador=c["qualificador"],
                grupo=c["grupo"], unidade=c["unidade"], ncm=c["ncm"], criterio=c["criterio"],
                guarda_chuva=c["guarda_chuva"],
                atributos=tuple(Atributo(a["ordem"], a["nome"], a["obrigatorio"], a["quando"],
                                         a["formato"], tuple(a["valores"]), a["tipo"])
                                for a in c["atributos"]),
                nomes=tuple(c["nomes"]),
            )
        p = cls(versao_id, classes, d["grupos"], d["unidades"], d["ncm_regras"], d["regras_gerais"])
        for idp, c in classes.items():
            for n in c.nomes:
                p._nome_para_classe[normaliza(n)] = idp
        return p

    def classe_do_nome(self, nome: str) -> Classe | None:
        idp = self._nome_para_classe.get(normaliza(nome))
        return self.classes.get(idp) if idp else None

    def todos_os_nomes(self) -> list[tuple[str, str]]:
        return [(n, idp) for idp, c in self.classes.items() for n in c.nomes]

    def classes_do_grupo(self, grupo: str) -> list[Classe]:
        return [c for c in self.classes.values() if c.grupo == grupo]

    # -- atributos que valem para um item concreto
    def aplicaveis(self, id_pdm: str, nome: str, valores: dict[str, str | None]) -> list[tuple[Atributo, bool | None]]:
        """Cada atributo da classe com seu estado de aplicação (True/False/None=depende)."""
        c = self.classes[id_pdm]
        return [(a, condicoes.aplica(id_pdm, a.nome, a.quando, nome, valores)) for a in c.atributos]

    def obrigatorios_aplicaveis(self, id_pdm: str, nome: str, valores: dict[str, str | None]) -> list[Atributo]:
        return [a for a, ap in self.aplicaveis(id_pdm, nome, valores) if a.obrigatorio and ap is True]

    def avisos(self) -> list[str]:
        return [f"condicao sem predicado: {i} {a}: {q}" for i, a, q in
                condicoes.lacunas({k: {"atributos": [{"nome": a.nome, "quando": a.quando} for a in c.atributos]}
                                   for k, c in self.classes.items()})]
