"""Invariantes do PDM: o portao final por onde todo valor passa.

Este modulo e a resposta a "regras lexicas das quais nao podemos fugir". Ele nao
extrai nada: ele recusa o que nao obedece ao padrao, venha de onde vier. Valor
proposto pelo gazetteer, pelo BERT ou pelo LLM e tratado igual - se nao esta na
lista de valores permitidos, nao entra. E o que impede alucinacao de chegar na
base, e e o que torna o resultado defensavel diante da banca.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .pdm import (UNIDADE_EMBALAGEM, UNIDADE_SINONIMO, Atributo, Classe, Pdm,
                   aplica_atributo)
from .texto import (fmt_bar, fmt_inteiro, fmt_metro, fmt_mm, fmt_mm2, fmt_pol,
                    fmt_simples, normalizar, parse_numero, referencia_canonica, sem_acento)

_ZERO_INUTIL = re.compile(r"^(\d+),(\d*?)0+(MM2|MM|BAR|A|W|M)$")


def _sem_zero_inutil(v: str) -> str:
    """'35,0MM' -> '35MM'; '6,40MM' -> '6,4MM'. Mesmo valor, mesma chave.

    A chave de identidade compara texto. Sem isso, 'COMPR:35,0MM' e 'M8X35' nao
    juntavam: um dava 35,0MM, o outro 35MM. Antes da correcao da virgula
    decimal em rotulos.pares() isso passava por acidente, porque o valor era
    cortado na virgula.
    """
    m = _ZERO_INUTIL.match(v)
    if not m:
        return v
    inteiro, decimal, unidade = m.groups()
    return f"{int(inteiro)}{',' + decimal if decimal else ''}{unidade}"


RX_MM = re.compile(r"^\d+(?:,\d+)?MM$")
RX_MM2 = re.compile(r"^\d+(?:,\d+)?MM2$")
RX_POL = re.compile(r"^(?:\d+\.)?(?:\d+/\d+|\d+)POL$")
RX_BAR = re.compile(r"^\d+(?:,\d+)?BAR$")
RX_NCM = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
RX_BITOLA = re.compile(r"^M\d{1,2}(?:X\d+(?:,\d+)?)?$")
RX_A = re.compile(r"^\d+(?:,\d+)?A$")
RX_W = re.compile(r"^\d+(?:,\d+)?W$")
RX_METRO = re.compile(r"^\d+(?:,\d+)?M$")
RX_INT = re.compile(r"^\d+$")
RX_FAIXA = re.compile(r"^0-\d+(?:,\d+)?(?:BAR|MM|A)$")

LIMITE_DESCRICAO_CURTA = 40


@dataclass
class Veredito:
    ok: bool
    valor: str | None = None
    motivo: str = ""


class Validador:
    def __init__(self, pdm: Pdm):
        self.pdm = pdm

    # ------------------------------------------------------------- texto

    @staticmethod
    def texto_padrao(s: str) -> str:
        """Regra 3: maiusculas, sem acento, sem cedilha, espaco colapsado."""
        return re.sub(r"\s+", " ", sem_acento(str(s)).upper()).strip()

    # ------------------------------------------------------------- valor

    def valor(self, atributo: Atributo, valor: str | None) -> Veredito:
        """Aceita, corrige ou recusa um valor de atributo."""
        if valor is None or not str(valor).strip():
            return Veredito(False, None, "vazio")

        v = self.texto_padrao(valor)

        # regra 4: atributo de lista usa exatamente um dos valores permitidos.
        # Casa pela chave normalizada e devolve o valor como o PDM o escreve.
        if atributo.fechado:
            canonico = atributo.chaves.get(normalizar(v))
            if canonico:
                return Veredito(True, canonico)
            # Lista de medidas em polegada (BITOLA de parafuso UNC): o PDM
            # escreve 1.1/4POL e o cadastro escreve '1 1/4 POL', '1-1/4"'.
            # Reformata pela regra 5 antes de desistir da lista.
            if "POL" in v:
                pol = fmt_pol(v.replace("POL", "").strip())
                canonico = atributo.chaves.get(normalizar(pol)) if pol else None
                if canonico:
                    return Veredito(True, canonico, "reformatado para POL")
            return Veredito(False, None, f"fora da lista de valores permitidos de {atributo.nome}")

        f = normalizar(atributo.formato)

        if "M + DIAMETRO" in f:          # BITOLA: designacao de rosca, nao medida
            return (Veredito(True, v) if RX_BITOLA.match(v)
                    else Veredito(False, None, "bitola fora do formato M<numero>"))

        # Regra 5 e 6: formato de grandeza. Um mesmo FORMATO pode citar DUAS
        # unidades - PDM001 COMPRIMENTO e "rosca metrica: numero + MM (50MM);
        # rosca em polegada: fracao + POL". Testar todas as citadas e aceitar a
        # primeira que casar, na mesma ordem de preferencia de regras._familias.
        # Testar POL antes de MM convertia 75MM em 75POL e corrompia a chave.
        candidatos: list[tuple[str, re.Pattern]] = []
        if "MM2" in f:
            candidatos.append(("MM2", RX_MM2))
        else:
            if "MM" in f:
                candidatos.append(("MM", RX_MM))
            if "POL" in f or "POLEGADA" in f:
                candidatos.append(("POL", RX_POL))
            if "BAR" in f:
                candidatos.append(("BAR", RX_BAR))
            # Familias que faltavam. Sem elas, 'numero + W' caia em "formato
            # livre": o BERT recortava '9', a regra dava '9W', e o arbitro
            # registrava CONFLITO entre dois valores identicos.
            if "+ A" in f or f.endswith(" A"):
                candidatos.append(("A", RX_A))
            if "+ W" in f:
                candidatos.append(("W", RX_W))
            if "+ M" in f or f.endswith(" M"):
                candidatos.append(("M", RX_METRO))
            if f == "INTEIRO":
                candidatos.append(("INT", RX_INT))

        if not candidatos:
            # formato livre (part number, referencia de rolamento, modelo)
            return Veredito(True, v)

        for _, rx in candidatos:
            if rx.match(v):
                return Veredito(True, _sem_zero_inutil(v))
        if RX_FAIXA.match(v):
            return Veredito(True, v)       # FAIXA de medicao: 0-16BAR, 0-250BAR

        # nenhuma casou: tenta reformatar na unidade de maior preferencia - ou na
        # que o proprio valor traz, quando o atributo aceita as duas. COMPRIMENTO
        # de PDM001 e 'MM (rosca metrica) ou POL (rosca em polegada)', e
        # reformatar '1-1/4POL' para MM recusava o comprimento de todo parafuso
        # UNC com 'valor em POL, mas o atributo exige MM'.
        unidades = [u for u, _ in candidatos]
        alvo = "POL" if ("POL" in v and "POL" in unidades) else unidades[0]
        return self._corrigir(v, alvo)

    @staticmethod
    def _corrigir(v: str, familia: str) -> Veredito:
        """Ultima tentativa de trazer para o formato antes de recusar.

        So reformata quando a unidade escrita no valor nao contradiz a familia
        esperada: '75POL' nunca deve ser reescrito como '75MM' nem o contrario,
        porque isso troca a medida do item em vez de corrigir a notacao.
        """
        sufixo = re.search(r"[A-Z]+$", v)
        # Secao de cabo escrita 'SECAO:2,5MM': num atributo de MM2 isso e mm2,
        # a unidade so veio abreviada. Recusar deixava o cabo pendente.
        if familia == "MM2" and sufixo and sufixo.group(0) == "MM":
            sufixo = None
        if sufixo and sufixo.group(0) not in (familia, ""):
            return Veredito(False, None,
                            f"valor em {sufixo.group(0)}, mas o atributo exige {familia}")
        n = parse_numero(re.sub(r"[A-Z]+$", "", v))
        if n is None:
            return Veredito(False, None, f"nao reconhecido como grandeza em {familia}")
        corrigido = {"MM": fmt_mm(n), "MM2": fmt_mm2(n), "POL": fmt_pol(n),
                     "BAR": fmt_bar(n, "BAR"), "A": fmt_simples(n, "A"),
                     "W": fmt_simples(n, "W"), "M": fmt_metro(n),
                     "INT": fmt_inteiro(n)}.get(familia)
        if corrigido:
            return Veredito(True, corrigido, f"reformatado para {familia}")
        return Veredito(False, None, f"fora do formato {familia}")

    # ------------------------------------------------------------- unidade

    def unidade(self, bruta: str, classe: Classe) -> Veredito:
        """Regra 11: unidade conforme UNIDADE_PADRAO da classe.

        Sinonimo converte. Embalagem (JG, CX, CT, BD, RL, BR, GL) nao converte:
        1 CX = N PC exige fator, e converter sem o fator corrompe saldo de
        estoque e preco medio. Vai para fila de decisao.
        """
        u = normalizar(bruta).replace(".", "")
        if u == classe.unidade:
            return Veredito(True, classe.unidade)
        if u in UNIDADE_EMBALAGEM:
            return Veredito(
                False, None,
                f"{u} e {UNIDADE_EMBALAGEM[u]}, nao unidade basica: precisa do fator de conversao",
            )
        canonica = UNIDADE_SINONIMO.get(u)
        if canonica is None:
            return Veredito(False, None, f"unidade {u} desconhecida")
        if canonica != classe.unidade:
            return Veredito(
                False, classe.unidade,
                f"classe {classe.id_pdm} exige {classe.unidade}, cadastro tem {u}",
            )
        return Veredito(True, canonica, f"{u} normalizado para {canonica}")

    # ------------------------------------------------------------- ncm

    def ncm(self, bruto: str, classe: Classe) -> Veredito:
        """Regra 12: 8 digitos no formato 0000.00.00, aderente a classe."""
        digitos = re.sub(r"\D", "", str(bruto or ""))
        if len(digitos) != 8:
            esperado = classe.ncm[0] if len(classe.ncm) == 1 else None
            if esperado:
                fmt = f"{esperado[:4]}.{esperado[4:6]}.{esperado[6:]}"
                return Veredito(True, fmt, "ausente, derivado da classe")
            return Veredito(False, None, "ausente e a classe tem NCM condicional")

        fmt = f"{digitos[:4]}.{digitos[4:6]}.{digitos[6:]}"
        if classe.ncm and digitos not in classe.ncm:
            if len(classe.ncm) == 1:
                e = classe.ncm[0]
                return Veredito(
                    False, f"{e[:4]}.{e[4:6]}.{e[6:]}",
                    f"divergente: classe {classe.id_pdm} exige {e[:4]}.{e[4:6]}.{e[6:]}",
                )
            return Veredito(False, fmt, f"fora da lista condicional da classe {classe.id_pdm}")
        return Veredito(True, fmt, "" if RX_NCM.match(str(bruto).strip()) else "reformatado")

    # ------------------------------------------------------------- descricao

    def descricao(self, classe: Classe, substantivo: str, valores: dict[str, str | None],
                  fabricante: str = "", referencia: str = "") -> str:
        """Regra 2: SUBSTANTIVO QUALIFICADOR; ATRIBUTO: VALOR; ... na ordem do PDM.

        Regra 8: em classe de especificacao tecnica, fabricante e referencia ficam
        fora da descricao. Regra 9: em classe de referencia do fabricante, entram.
        """
        partes = [classe.rotulo(substantivo)]
        for a in sorted(classe.atributos, key=lambda x: x.ordem):
            if not aplica_atributo(a, substantivo, valores):
                continue                       # regra 7: condicional que nao vale aqui
            v = valores.get(a.nome)
            if v:
                partes.append(f"{a.nome}: {v}")
            elif a.obrigatorio and a.sempre:
                partes.append(f"{a.nome}: <PENDENTE>")
        if classe.por_referencia:
            for nome, v in (("FABRICANTE", fabricante), ("REFERENCIA FABRICANTE", referencia)):
                if v and not any(p.startswith(f"{nome}:") for p in partes):
                    partes.append(f"{nome}: {self.texto_padrao(v)}")
        return "; ".join(partes)

    def descricao_curta(self, longa: str) -> str:
        """Regra do ERP: 40 caracteres. Corta em limite de palavra."""
        if len(longa) <= LIMITE_DESCRICAO_CURTA:
            return longa
        corte = longa[:LIMITE_DESCRICAO_CURTA]
        return corte[: corte.rfind(" ")] if " " in corte[20:] else corte

    # ------------------------------------------------------------- identidade

    def chave_identidade(self, classe: Classe, substantivo: str, valores: dict[str, str | None],
                         fabricante: str = "", referencia: str = "") -> str | None:
        """Regra 10: identidade do item. None quando faltar obrigatorio.

        Classe de especificacao tecnica: classe + substantivo + qualificador +
        todos os obrigatorios. Classe de referencia: classe + fabricante + part
        number (regra 13: equivalencia entre fabricantes NAO fecha a mesma chave).
        """
        if classe.por_referencia:
            f, r = normalizar(fabricante), referencia_canonica(referencia)
            if not f or not r:
                return None
            # Regra 10: nas classes de referencia a identidade e fabricante + part number. Incluir o
            # substantivo separava o mesmo part number quando o nome era lido errado (ADAPTADOR x EXPULSOR).
            return f"{classe.id_pdm}|{f}|{r}"

        # Percorre TODO atributo obrigatorio, inclusive o condicional. Usar
        # classe.obrigatorios aqui era um bug: ele filtra quando == 'sempre', e
        # por isso os 19 atributos obrigatorios condicionais do PDM ficavam fora
        # da chave. Consequencia real: tres cabos de 1 condutor, identicos exceto
        # pela COR (VERDE, AZUL, PRETO), fechavam a mesma chave e eram juntados.
        campos = [classe.id_pdm, normalizar(substantivo)]
        for a in sorted((x for x in classe.atributos if x.obrigatorio), key=lambda x: x.ordem):
            v = valores.get(a.nome)
            if aplica_atributo(a, substantivo, valores):
                if not v:
                    return None                  # obrigatorio que se aplica e nao veio
                campos.append(f"{a.nome}={normalizar(v)}")
            elif v:
                # nao se aplica, mas veio preenchido: entra na chave de qualquer
                # forma. Omitir seria juntar itens que diferem nesse atributo.
                campos.append(f"{a.nome}={normalizar(v)}")
        return "|".join(campos)
