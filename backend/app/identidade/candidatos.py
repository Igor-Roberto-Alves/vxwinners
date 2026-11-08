"""Verificação de duplicidade: quais itens já existentes se parecem com o que está sendo cadastrado.

Níveis (docs/06-plano-modo-cadastro.md, seção 8):
  IGUAL        mesma chave de identidade, completa nos dois lados (regra 10)
  PROVAVEL     nenhum atributo diverge e o candidato só não tem alguns obrigatórios
  DIVERGENTE   mesma família, mas um atributo de identidade difere (mostra qual)
  PARECIDO     só semelhança de texto: informa, nunca decide
  EQUIVALENTE  intercambiável registrado (regra 13): informa, nunca une códigos

O painel nunca afirma que um item "não existe": devolve também a cobertura, isto é, quantos
registros da classe puderam ser comparados por atributos.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy import Connection, text

from ..normalizacao.texto import tokens
from ..pdm.modelo import Pdm
from .chave import _valor_identidade, chave_identidade
from .referencias import fabricante_canonico, referencia_generica

ORDEM = {"IGUAL": 0, "PROVAVEL": 1, "EQUIVALENTE": 2, "DIVERGENTE": 3, "PARECIDO": 4}
ESTADOS_EM_ANDAMENTO = ("APROVADO", "EM_REVISAO", "AGUARDANDO_REATIVACAO", "CADASTRADO")


@dataclass
class Candidato:
    codigo: str
    nivel: str
    pontos: float
    origem: str = "base"                 # base | cadastro
    status: str | None = None
    centro: str | None = None
    estoque: float | None = None
    descricao: str | None = None
    comparacao: list[dict] = field(default_factory=list)
    motivo: str = ""
    permite_uso_direto: bool = False     # só código ATIVO pode ser usado direto


@dataclass
class Resultado:
    candidatos: list[Candidato]
    comparaveis: int                     # registros da classe com chave completa
    total_classe: int                    # registros da classe na base


def acrescenta_vizinhos(conn: Connection, res: Resultado, vizinhos: list[dict], *, minimo: float = 0.6, limite: int = 8) -> Resultado:
    """Vizinhos de texto na base inteira (serviço de sugestão), inclusive itens sem classe. Só informam:
    texto parecido nunca prova duplicidade (nos 15 produtos reais, comparar texto achou 0 dos duplicados)."""
    ja = {c.codigo for c in res.candidatos}
    novos = [v for v in vizinhos if v.get("codigo") not in ja and float(v.get("similaridade") or 0) >= minimo]
    if not novos:
        return res
    rows = conn.execute(text("select codigo, status, centro, estoque, descricao_longa from material where codigo = any(:c)"),
                        {"c": [v["codigo"] for v in novos]}).mappings().all()
    info = {r["codigo"]: r for r in rows}
    for v in novos:
        i = info.get(v["codigo"])
        if not i:
            continue
        sim = float(v["similaridade"])
        res.candidatos.append(Candidato(v["codigo"], "PARECIDO", round(min(sim, 0.7), 3), status=i["status"], centro=i["centro"],
                                        estoque=float(i["estoque"] or 0), descricao=i["descricao_longa"],
                                        motivo=f"texto {round(sim * 100)}% parecido; confira os atributos", permite_uso_direto=i["status"] == "ATIVO"))
    res.candidatos = sorted(res.candidatos, key=lambda c: (ORDEM[c.nivel], -c.pontos, c.codigo))[:limite]
    return res


def _peso(pdm: Pdm, id_pdm: str, atr: str) -> int:
    """Quanto coincidir neste atributo prova semelhança: lista curta (2-3 valores) pouco, texto/medida muito."""
    a = pdm.classes[id_pdm].atributo(atr)
    if a is None or a.tipo == "LIVRE":
        return 3
    if a.tipo == "LISTA":
        return 1 if len(a.valores) <= 6 else 2
    return 3


def _serie(id_pdm: str, valor: str | None) -> str | None:
    """Rolamentos: a série (6205) é a evidência forte dentro da referência (6205-2RS/C3)."""
    if id_pdm not in ("PDM020", "PDM021", "PDM022") or not valor:
        return None
    m = re.match(r"^(\d{4,5})", _valor_identidade(id_pdm, "REFERENCIA", valor))
    return m.group(1) if m else None


def _compara(pdm: Pdm, id_pdm: str, rascunho: dict, candidato: dict, obrigatorios: list[str]) -> list[dict]:
    out = []
    for atr in obrigatorios:
        r, c = rascunho.get(atr), candidato.get(atr)
        rn = _valor_identidade(id_pdm, atr, r) if r else None
        cn = _valor_identidade(id_pdm, atr, c) if c else None
        if rn and cn:
            estado = "igual" if rn == cn else "diverge"
        elif rn and not cn:
            estado = "ausente"        # o candidato não tem este atributo registrado
        else:
            estado = "sem_valor"      # o rascunho ainda não preencheu
        out.append({"atributo": atr, "rascunho": r, "candidato": c, "estado": estado, "peso": _peso(pdm, id_pdm, atr)})
        if atr == "REFERENCIA" and _serie(id_pdm, r) and _serie(id_pdm, c):
            out.append({"atributo": "REFERENCIA (serie)", "rascunho": _serie(id_pdm, r), "candidato": _serie(id_pdm, c),
                        "estado": "igual" if _serie(id_pdm, r) == _serie(id_pdm, c) else "diverge", "peso": 3})
    return out


def _forca(comp: list[dict]) -> float:
    """Parcela do peso comparável que coincide (0 a 1)."""
    util = [x for x in comp if x["estado"] in ("igual", "diverge", "ausente")]
    total = sum(x["peso"] for x in util)
    return sum(x["peso"] for x in util if x["estado"] == "igual") / total if total else 0.0


def busca(conn: Connection, pdm: Pdm, id_pdm: str, nome: str | None, valores: dict[str, str | None], *,
          limite: int = 8, texto: str | None = None, ignorar_cadastro: str | None = None) -> Resultado:
    classe = pdm.classes[id_pdm]
    plano = {k: v for k, v in valores.items() if v}
    ch = chave_identidade(pdm, id_pdm, nome or "", plano)
    total = conn.execute(text("select count(*) from material_identidade where id_pdm = :i"), {"i": id_pdm}).scalar() or 0
    comparaveis = conn.execute(text("select count(*) from material_identidade where id_pdm = :i and completa"),
                               {"i": id_pdm}).scalar() or 0
    cands: dict[str, Candidato] = {}

    def anexa(codigos: list[str]) -> dict[str, dict]:
        if not codigos:
            return {}
        rows = conn.execute(text("""select codigo, status, centro, estoque, descricao_longa from material
                                    where codigo = any(:c)"""), {"c": codigos}).all()
        return {r[0]: dict(r._mapping) for r in rows}

    if classe.por_referencia:
        _candidatos_referencia(conn, pdm, classe, plano, ch, cands)
    else:
        _candidatos_especificacao(conn, pdm, classe, nome, plano, ch, cands)

    # PARECIDO: sobreposição de texto dentro da classe (só informa). Os rótulos do próprio PDM
    # (ROLAMENTO, REFERENCIA, VEDACAO...) aparecem em toda descrição gerada e não provam semelhança:
    # ficam de fora, e é preciso dividir um token distintivo (número de modelo, medida composta).
    rotulos = {t for n in classe.nomes for t in tokens(n)} | {t for a in classe.atributos for t in tokens(a.nome)}
    tk = sorted(set(tokens(texto or "")) - rotulos) if texto else []
    distintivos = {t for t in tk if any(ch.isdigit() for ch in t) and len(t) >= 4}
    if tk:
        rows = conn.execute(text("""select codigo, tokens from material_identidade
            where id_pdm = :i and tokens && :t limit 400"""), {"i": id_pdm, "t": tk}).all()
        base = set(tk)
        for cod, tks in rows:
            if cod in cands:
                continue
            outro = set(tks) - rotulos
            if distintivos and not (distintivos & outro):
                continue
            j = len(base & outro) / len(base | outro)
            if j >= (0.5 if distintivos else 0.6):
                cands[cod] = Candidato(cod, "PARECIDO", round(min(j, 0.7), 3), motivo="texto semelhante; confira os atributos")

    info = anexa([c.codigo for c in cands.values() if c.origem == "base"])
    for c in cands.values():
        i = info.get(c.codigo)
        if i:
            c.status, c.centro, c.estoque, c.descricao = i["status"], i["centro"], float(i["estoque"] or 0), i["descricao_longa"]
            c.permite_uso_direto = i["status"] == "ATIVO"
    cands.pop(f"cadastro:{ignorar_cadastro}", None)  # um cadastro em revisão não é duplicata de si mesmo
    ordenados = sorted(cands.values(), key=lambda c: (ORDEM[c.nivel], -c.pontos, c.codigo))[:limite]
    return Resultado(ordenados, comparaveis, total)


def _squeeze(v: str | None) -> str:
    return re.sub(r"[^A-Z0-9,./#]", "", (v or "").upper())


def _classifica(cod, comp, ch, cands) -> None:
    diverge = [x["atributo"] for x in comp if x["estado"] == "diverge" and not x["atributo"].endswith("(serie)") and not x.get("opcional")]
    diverge_serie = any(x["estado"] == "diverge" and x["atributo"].endswith("(serie)") for x in comp)
    diverge_opcional = any(x["estado"] == "diverge" and x.get("opcional") for x in comp)
    base = [x for x in comp if not x.get("opcional")]
    ausentes = [x["atributo"] for x in base if x["estado"] == "ausente"]
    iguais = [x for x in base if x["estado"] == "igual"]
    preenchidos = [x for x in base if x["estado"] != "sem_valor"]
    if not iguais or diverge_serie:
        return
    forca = _forca(base)
    if not diverge and ausentes and forca >= 0.4:
        if diverge_opcional:   # medida opcional diferente (ex.: diâmetro externo 150 x 52 mm) desmente o "provável"
            return
        cands[cod] = Candidato(cod, "PROVAVEL", round(0.6 + 0.3 * forca, 3), comparacao=comp,
                               motivo="não diverge em nada, mas faltam atributos no cadastro existente: " + ", ".join(ausentes))
    elif (diverge or diverge_opcional) and forca >= 0.5:
        quais = diverge + [x["atributo"] for x in comp if x["estado"] == "diverge" and x.get("opcional")]
        cands[cod] = Candidato(cod, "DIVERGENTE", round(min(0.85, 0.4 + 0.45 * forca), 3), comparacao=comp,
                               motivo="atributo de identidade diverge: " + ", ".join(quais))
    elif not diverge and not ausentes and not diverge_opcional and len(iguais) == len(preenchidos) and not ch.completa:
        cands[cod] = Candidato(cod, "PROVAVEL", round(0.5 + 0.3 * forca, 3), comparacao=comp,
                               motivo="igual no que já foi preenchido; faltam atributos no rascunho")


def _candidatos_especificacao(conn, pdm, classe, nome, plano, ch, cands) -> None:
    ob = [a.nome for a in pdm.obrigatorios_aplicaveis(classe.id_pdm, nome or "", plano)]
    # medidas e demais atributos OPCIONAIS já preenchidos no rascunho: provam semelhança ou diferença
    opc = [a.nome for a, ap in pdm.aplicaveis(classe.id_pdm, nome or "", plano) if ap is True and not a.obrigatorio and plano.get(a.nome)]
    rows = conn.execute(text("""select codigo, chave, completa, valores from material_identidade
        where id_pdm = :i and nome = :n"""), {"i": classe.id_pdm, "n": nome}).all()
    pendentes: dict[str, list[dict]] = {}
    for cod, chave, completa, valores in rows:
        valores = valores if isinstance(valores, dict) else json.loads(valores)
        comp = _compara(pdm, classe.id_pdm, plano, valores, ob)
        for x in _compara(pdm, classe.id_pdm, plano, valores, opc):
            if x["estado"] in ("igual", "diverge"):
                x["opcional"] = True
                comp.append(x)
        if ch.completa and completa and chave == ch.texto:
            cands[cod] = Candidato(cod, "IGUAL", 1.0, comparacao=comp, motivo="todos os atributos obrigatórios coincidem")
        elif any(x["estado"] == "ausente" and not x.get("opcional") for x in comp):
            pendentes[cod] = comp     # pode ter o valor no texto, fora da lista do PDM: confere abaixo
        else:
            _classifica(cod, comp, ch, cands)
    if pendentes:
        # atributo "ausente" que o cadastro existente tem escrito fora do PDM (guardado como valor bruto):
        # se é diferente do rascunho, é divergência, não ausência
        brutos = conn.execute(text("""select codigo, atributo, valor_bruto from material_atributo
            where codigo = any(:c) and valor is null and valor_bruto is not null"""), {"c": list(pendentes)}).all()
        por_cod: dict[str, dict[str, str]] = {}
        for cod, atr, bruto in brutos:
            por_cod.setdefault(cod, {})[atr] = bruto
        for cod, comp in pendentes.items():
            for x in comp:
                bruto = por_cod.get(cod, {}).get(x["atributo"])
                if x["estado"] == "ausente" and bruto:
                    x["candidato"] = f"{bruto} (fora do PDM)"
                    x["estado"] = "igual" if _squeeze(bruto) == _squeeze(x["rascunho"]) else "diverge"
            _classifica(cod, comp, ch, cands)
    # cadastros novos já aprovados com a mesma chave (ainda sem código no ERP)
    if ch.completa:
        for cid, estado, codigo_erp in conn.execute(text(
                "select id::text, estado, codigo_erp from cadastro where chave = :c and estado = any(:e)"),
                {"c": ch.texto, "e": list(ESTADOS_EM_ANDAMENTO)}):
            cands[f"cadastro:{cid}"] = Candidato(codigo_erp or f"cadastro:{cid}", "IGUAL", 1.0, origem="cadastro",
                                                 status=estado, motivo="já existe um cadastro novo aprovado com esta chave")


def _candidatos_referencia(conn, pdm, classe, plano, ch, cands) -> None:
    a_fab = classe.atributo("FABRICANTE")
    fab = fabricante_canonico(plano.get("FABRICANTE"), a_fab.valores if a_fab else ())
    ref = referencia_generica(plano.get("REFERENCIA FABRICANTE"))
    if not ref:
        return
    rows = conn.execute(text("""select codigo, chave, completa, valores from material_identidade where id_pdm = :i
        and (valores->>'REFERENCIA FABRICANTE') is not null"""), {"i": classe.id_pdm}).all()
    for cod, chave, completa, valores in rows:
        valores = valores if isinstance(valores, dict) else json.loads(valores)
        rc = referencia_generica(valores.get("REFERENCIA FABRICANTE"))
        fc = fabricante_canonico(valores.get("FABRICANTE"), a_fab.valores if a_fab else ())
        comp = [{"atributo": "FABRICANTE", "rascunho": fab, "candidato": fc, "estado": "igual" if fab and fab == fc else ("diverge" if fab and fc else "ausente")},
                {"atributo": "REFERENCIA FABRICANTE", "rascunho": plano.get("REFERENCIA FABRICANTE"),
                 "candidato": valores.get("REFERENCIA FABRICANTE"), "estado": "igual" if ref == rc else "diverge"}]
        if rc != ref:
            continue
        if fab and fc and fab == fc:
            cands[cod] = Candidato(cod, "IGUAL", 1.0, comparacao=comp, motivo="mesmo fabricante e mesma referência")
        elif fab and fc and fab != fc:
            cands[cod] = Candidato(cod, "PARECIDO", 0.5, comparacao=comp,
                                   motivo="mesma referência, fabricante diferente: pode ser outro produto")
        else:
            cands[cod] = Candidato(cod, "PROVAVEL", 0.7, comparacao=comp, motivo="mesma referência; fabricante não registrado no existente")
    # equivalência registrada (regra 13): só informa
    if fab:
        eq = conn.execute(text("""select b_fabricante, b_referencia, fonte from equivalencia where a_fabricante = :f and a_referencia = :r
            union select a_fabricante, a_referencia, fonte from equivalencia where b_fabricante = :f and b_referencia = :r"""),
                          {"f": fab, "r": ref}).all()
        for f2, r2, fonte in eq:
            for cod, in conn.execute(text("""select codigo from material_identidade where id_pdm = :i
                and chave = :k"""), {"i": classe.id_pdm, "k": f"{classe.id_pdm}|{f2}|{referencia_generica(r2)}"}):
                cands.setdefault(cod, Candidato(cod, "EQUIVALENTE", 0.6, motivo=f"intercambiável ({f2} {r2}); item distinto, não une códigos. Fonte: {fonte}"))
    if ch.completa:
        for cid, estado, codigo_erp in conn.execute(text(
                "select id::text, estado, codigo_erp from cadastro where chave = :c and estado = any(:e)"),
                {"c": ch.texto, "e": list(ESTADOS_EM_ANDAMENTO)}):
            cands[f"cadastro:{cid}"] = Candidato(codigo_erp or f"cadastro:{cid}", "IGUAL", 1.0, origem="cadastro",
                                                 status=estado, motivo="já existe um cadastro novo aprovado com esta chave")
