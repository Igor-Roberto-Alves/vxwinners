"""Carrega o PDM (03_padrao_cadastro_PDM.xlsx) e o compila em estruturas de uso.

O PDM e a especificacao do desafio: 44 classes, 229 atributos, listas de valores
permitidos, unidade padrao e NCM por classe. Tudo e lido da planilha, nunca
digitado no codigo: se a banca mudar o padrao, o pipeline continua valido.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .texto import normalizar, normalizar_valor

# Unidades legadas -> unidade basica do PDM.
# Sinonimo converte direto; EMBALAGEM nao converte: 1 CX = N PC exige fator,
# e converter sem o fator corrompe saldo de estoque e preco medio.
UNIDADE_SINONIMO = {
    "UN": "PC", "PC": "PC", "PCA": "PC", "PÇ": "PC", "PC.": "PC",
    "M": "M", "MT": "M", "MTS": "M", "METRO": "M",
    "PR": "PR", "PAR": "PR",
    "KG": "KG", "KGS": "KG",
    "L": "L", "LT": "L", "LTS": "L", "LITRO": "L",
}
UNIDADE_EMBALAGEM = {"JG": "jogo", "CX": "caixa", "CT": "cartela",
                     "BD": "balde", "RL": "rolo", "BR": "barra", "GL": "galao"}


# Condicoes da coluna QUANDO_SE_APLICA que nao usam termo em caixa alta.
CONDICAO_ESPECIAL = {
    "somente cabos de 1 condutor": ("NUMERO CONDUTORES", {"1"}),
}

_TERMO_CAPS = re.compile(r"\b[A-Z][A-Z0-9/]*(?:\s+[A-Z][A-Z0-9/]*)*\b")


def aplica_atributo(atributo: "Atributo", substantivo: str,
                    valores: dict[str, str | None] | None = None) -> bool:
    """Regra 7: atributo condicional vale so para certos tipos de item.

    As 19 condicoes da planilha estao em linguagem natural ("somente FLANGE",
    "todas, exceto conexoes para solda de topo (BW)"), mas o PDM sempre escreve
    o termo controlado em CAIXA ALTA - e isso da um parser confiavel. Sem isso,
    um CAP sairia com DIAMETRO REDUZIDO, atributo que so existe em TE REDUCAO,
    LUVA REDUCAO e BUCHA REDUCAO.
    """
    quando = (atributo.quando or "sempre").strip()
    baixa = quando.lower()
    if baixa in ("sempre", "") or baixa.startswith("quando informado"):
        return True

    valores = valores or {}
    contexto = normalizar(" ".join([substantivo or ""] + [v for v in valores.values() if v]))

    if quando in CONDICAO_ESPECIAL:
        campo, aceitos = CONDICAO_ESPECIAL[quando]
        v = normalizar(valores.get(campo) or "")
        return v in aceitos if v else True

    termos = [t for t in _TERMO_CAPS.findall(quando) if len(t) > 1]
    if not termos:
        return True

    casou = any(f" {t} " in f" {contexto} " for t in termos)
    negado = "exceto" in baixa
    return (not casou) if negado else casou


@dataclass
class Atributo:
    id_pdm: str
    ordem: int
    nome: str
    obrigatorio: bool
    quando: str
    formato: str
    valores: list[str] = field(default_factory=list)

    @property
    def fechado(self) -> bool:
        """Atributo de vocabulario fechado: resolve por gazetteer, nao por modelo."""
        return bool(self.valores)

    @property
    def chaves(self) -> dict[str, str]:
        """chave de casamento -> valor canonico do PDM.

        'FKM (VITON)' e guardado como o padrao escreve, mas e casado pela chave
        'FKM VITON', porque normalizar() transforma pontuacao em espaco e e isso
        que o texto do cadastro traz.
        """
        return {normalizar(v): v for v in self.valores}

    @property
    def sempre(self) -> bool:
        return normalizar(self.quando) == "SEMPRE"


@dataclass
class Classe:
    id_pdm: str
    substantivos: list[str]
    qualificadores: list[str]
    grupo: str
    unidade: str
    ncm: list[str]
    criterio: str
    atributos: list[Atributo] = field(default_factory=list)

    @property
    def por_referencia(self) -> bool:
        """True quando a identidade e FABRICANTE + PART NUMBER (regra 9)."""
        return "REFERENCIA DO FABRICANTE" in normalizar(self.criterio)

    @property
    def obrigatorios(self) -> list[Atributo]:
        return [a for a in self.atributos if a.obrigatorio and a.sempre]

    def rotulo(self, substantivo: str | None = None) -> str:
        """SUBSTANTIVO QUALIFICADOR para o inicio da descricao padrao (regra 2)."""
        s = substantivo or self.substantivos[0]
        q = self.qualificadores[0] if len(self.qualificadores) == 1 else ""
        return f"{s} {q}".strip()


class Pdm:
    def __init__(self, classes: list[Classe], unidades: list[str],
                 grupos: dict[str, str], ncm_por_classe: dict[str, list[str]]):
        self.classes = {c.id_pdm: c for c in classes}
        self.unidades = unidades
        self.grupos = grupos
        self.ncm_por_classe = ncm_por_classe
        self.por_grupo: dict[str, list[Classe]] = {}
        for c in classes:
            self.por_grupo.setdefault(c.grupo, []).append(c)

    # -------------------------------------------------------------- leitura

    @classmethod
    def de_xlsx(cls, caminho: str | Path) -> "Pdm":
        import openpyxl

        wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)

        def aba(nome: str) -> list[tuple]:
            linhas = list(wb[nome].iter_rows(values_only=True))
            return linhas[1:]

        sobressalentes = [r[0] for r in aba("SUBSTANTIVOS_SOBRESSALENTES") if r[0]]
        conexoes = [r[0] for r in aba("SUBSTANTIVOS_CONEXOES") if r[0]]

        atributos: dict[str, list[Atributo]] = {}
        for r in aba("ATRIBUTOS"):
            if not r[0]:
                continue
            valores = []
            if r[6]:
                valores = [normalizar_valor(v) for v in str(r[6]).split("|")
                           if normalizar_valor(v)]
            atributos.setdefault(r[0], []).append(
                Atributo(
                    id_pdm=r[0],
                    ordem=int(r[1]) if r[1] else 0,
                    nome=normalizar(r[2]),
                    obrigatorio=normalizar(r[3]) == "S",
                    quando=str(r[4] or "sempre"),
                    formato=str(r[5] or ""),
                    valores=valores,
                )
            )

        ncm_por_classe: dict[str, list[str]] = {}
        for r in aba("NCM_REFERENCIA"):
            if not r[0] or not r[1]:
                continue
            achados = re.findall(r"\d{4}\.?\d{2}\.?\d{2}", str(r[1]))
            ncm_por_classe.setdefault(r[0], [])
            for a in achados:
                d = re.sub(r"\D", "", a)
                if len(d) == 8 and d not in ncm_por_classe[r[0]]:
                    ncm_por_classe[r[0]].append(d)

        classes: list[Classe] = []
        for r in aba("CLASSES"):
            if not r[0]:
                continue
            idp = r[0]
            bruto_subst = str(r[1] or "")
            if idp == "PDM110":
                substantivos = [normalizar(s) for s in sobressalentes]
            elif idp == "PDM050":
                substantivos = [normalizar(s) for s in conexoes]
            else:
                substantivos = [normalizar(s) for s in bruto_subst.split("|") if normalizar(s)]
            quals = [
                normalizar(q)
                for q in str(r[2] or "").split("|")
                if normalizar(q) and not str(q).strip().startswith("(")
            ]
            ncm = ncm_por_classe.get(idp) or [
                re.sub(r"\D", "", m) for m in re.findall(r"\d{4}\.\d{2}\.\d{2}", str(r[5] or ""))
            ]
            classes.append(
                Classe(
                    id_pdm=idp,
                    substantivos=substantivos,
                    qualificadores=quals,
                    grupo=str(r[3] or "").strip(),
                    unidade=normalizar(r[4]),
                    ncm=ncm,
                    criterio=str(r[6] or ""),
                    atributos=sorted(atributos.get(idp, []), key=lambda a: a.ordem),
                )
            )

        unidades = [normalizar(r[0]) for r in aba("UNIDADES") if r[0]]
        grupos = {str(r[0]).strip(): str(r[1]) for r in aba("GRUPOS_MERCADORIA") if r[0]}
        wb.close()
        return cls(classes, unidades, grupos, ncm_por_classe)

    # -------------------------------------------------------------- derivados

    @property
    def nomes_atributos(self) -> list[str]:
        """Conjunto global de nomes de atributo, ordenado.

        E o espaco de rotulos do BERT: 'DIAMETRO INTERNO' e um rotulo unico,
        compartilhado entre classes, para somar exemplos de treino. Na inferencia
        o resultado e mascarado pelos atributos validos da classe prevista.
        """
        nomes = {a.nome for c in self.classes.values() for a in c.atributos}
        return sorted(nomes)

    def gazetteer(self) -> dict[str, dict[str, list[str]]]:
        """{id_pdm: {atributo: [valores permitidos]}} para casamento por dicionario."""
        return {
            cid: {a.nome: a.valores for a in c.atributos if a.fechado}
            for cid, c in self.classes.items()
        }

    def estatisticas(self) -> dict:
        attrs = [a for c in self.classes.values() for a in c.atributos]
        obrig = [a for a in attrs if a.obrigatorio]
        return {
            "classes": len(self.classes),
            "atributos": len(attrs),
            "obrigatorios": len(obrig),
            "vocabulario_fechado": sum(1 for a in attrs if a.fechado),
            "nomes_distintos": len(self.nomes_atributos),
            "classes_por_referencia": sum(1 for c in self.classes.values() if c.por_referencia),
            "unidades_validas": self.unidades,
        }

    # -------------------------------------------------------------- io

    def salvar(self, destino: str | Path) -> None:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "classes": [asdict(c) for c in self.classes.values()],
            "unidades": self.unidades,
            "grupos": self.grupos,
            "ncm_por_classe": self.ncm_por_classe,
            "nomes_atributos": self.nomes_atributos,
        }
        destino.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def carregar(cls, origem: str | Path) -> "Pdm":
        d = json.loads(Path(origem).read_text(encoding="utf-8"))
        classes = [
            Classe(
                **{k: v for k, v in c.items() if k != "atributos"},
                atributos=[Atributo(**a) for a in c["atributos"]],
            )
            for c in d["classes"]
        ]
        return cls(classes, d["unidades"], d["grupos"], d["ncm_por_classe"])
