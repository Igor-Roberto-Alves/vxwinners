"""Extração por regras: lê da descrição o que ela realmente diz, sem adivinhar.

1. Descrições no estilo `SUBSTANTIVO; ATRIBUTO: VALOR; ...` (e variantes com `-` ou `,`).
2. Valores da lista do PDM presentes no texto (gazetteer), com fronteira de palavra.
3. Notação composta `M12X50` e referência do rolamento (série + vedação + folga).
4. Colunas FABRICANTE e REFERENCIA_FABRICANTE do ERP nas classes de referência.
O que as regras não alcançam fica vazio para o LLM ou para a pessoa.
"""
from __future__ import annotations

import re

from ..classes.resolver import IndiceClasses, prepara
from ..identidade.referencias import deduz_vedacao_folga, fabricante_canonico, fabricante_no_texto
from ..normalizacao import grandezas
from ..normalizacao.texto import normaliza
from ..normalizacao.vocabulario import acha_no_texto
from ..pdm.modelo import Classe, Pdm
from .canonicalizar import canonicaliza_atributo
from .modelo import Extracao, Valor

_SEPARADOR = re.compile(r"\s*(?:;|\s-\s|,\s+(?=[A-Za-z0-9 /\.]{1,30}:))\s*")

# rótulo abreviado → atributo (aplicado se a classe tem o atributo)
ALIAS_ROTULO = {
    "APLIC": "APLICACAO", "MAT": "MATERIAL", "MARCA": "FABRICANTE", "FABR": "FABRICANTE", "FAB": "FABRICANTE",
    "P/N": "REFERENCIA FABRICANTE", "PN": "REFERENCIA FABRICANTE", "PART NUMBER": "REFERENCIA FABRICANTE",
    "PARTNUMBER": "REFERENCIA FABRICANTE", "REF": "REFERENCIA", "REFERENCIA": "REFERENCIA",
    "MOD": "MODELO EQUIPAMENTO", "MODELO": "MODELO EQUIPAMENTO", "EQUIP": "MODELO EQUIPAMENTO",
    "EQUIPAMENTO": "MODELO EQUIPAMENTO", "COMP": "COMPRIMENTO", "RATING": "CLASSE PRESSAO",
    "RESISTENCIA": "CLASSE RESISTENCIA", "CORPO": "MATERIAL CORPO", "ENCAIXE": "CONEXAO",
    "NORMA CONSTRUCAO": "NORMA", "EMB": "EMBALAGEM", "PRESSAO": "PRESSAO TRABALHO", "ISO VG": "VISCOSIDADE",
    "TERM A": "TERMINAL A", "TERM B": "TERMINAL B", "LARG": "LARGURA", "ESP": "ESPESSURA",
    "PROTECAO": "VEDACAO", "ACION": "ACIONAMENTO", "VEDACAO": "VEDACAO",
}


def _atributo_do_rotulo(classe: Classe, rotulo: str) -> str | None:
    r = normaliza(rotulo)
    nomes = [a.nome for a in classe.atributos]
    if r in nomes:
        return r
    alvo = ALIAS_ROTULO.get(r)
    if alvo == "REFERENCIA":
        alvo = "REFERENCIA" if "REFERENCIA" in nomes else "REFERENCIA FABRICANTE"
    if alvo in nomes:
        return alvo
    # prefixo único: DIAM INT → DIAMETRO INTERNO
    rt = r.replace(".", "").split()
    achados = []
    for n in nomes:
        nt = n.split()
        if len(rt) <= len(nt) and all(nt[i].startswith(rt[i]) for i in range(len(rt))):
            achados.append(n)
    return achados[0] if len(achados) == 1 else None


_SERIE_ROLAMENTO = re.compile(r"(?<![A-Z0-9])(\d{4,5})(?![0-9])")


def classe_rolamento_por_serie(pdm: Pdm, texto: str) -> tuple[str, str] | None:
    """A série identifica o tipo: 6xxx = rígido de esferas, 3xxxx = rolos cônicos, 22xxx/23xxx = autocompensador."""
    for m in _SERIE_ROLAMENTO.finditer(normaliza(texto)):
        s = m.group(1)
        idp = None
        if len(s) == 4 and s[0] == "6":
            idp = "PDM020"
        elif len(s) == 5 and s[:2] in ("30", "31", "32", "33"):
            idp = "PDM022"
        elif len(s) == 5 and s[:2] in ("22", "23", "21"):
            idp = "PDM021"
        if idp:
            return idp, pdm.classes[idp].nomes[0]
    return None


def _decide(pdm: Pdm, cands):
    """(id_pdm, nome, ambiguas). Empate entre nomes da mesma classe de referência deixa o nome em aberto;
    empate entre classes deixa a classe em aberto. Nunca escolhe por ordem alfabética."""
    if not cands:
        return None, None, ()
    top = cands[0]
    empatados = [c for c in cands if top.pontos - c.pontos < 0.05]
    if len(empatados) == 1 and not top.ambiguo:
        return top.id_pdm, top.nome, ()
    ids = {c.id_pdm for c in empatados}
    ambiguas = tuple((c.nome, c.id_pdm) for c in empatados)
    if len(ids) == 1 and pdm.classes[top.id_pdm].por_referencia:
        return top.id_pdm, None, ambiguas
    return None, None, ambiguas


def _partes(texto: str) -> list[str]:
    return [p for p in _SEPARADOR.split(texto) if p]


def extrai_por_regras(pdm: Pdm, indice: IndiceClasses, r: dict) -> Extracao:
    """`r`: dict com descricao_longa, descricao_curta, grupo, fabricante, referencia_fabricante."""
    texto = (r.get("descricao_longa") or r.get("descricao_curta") or "").strip()
    ex = Extracao()
    if not texto:
        return ex
    partes = _partes(texto)
    cabeca = partes[0] if partes and ":" not in partes[0] else ""
    grupo = r.get("grupo")

    # ---- classe
    cands = indice.detectar_no_texto(cabeca, grupo=grupo) if cabeca else []
    origem_classe = "cabecalho"
    if not cands:
        cands = indice.detectar_no_texto(texto, grupo=grupo)
        origem_classe = "texto"
    id_pdm, nome, ambiguas = _decide(pdm, cands)
    if not id_pdm and (grupo == "ROL01" or "ROLAMENTO" in prepara(texto)):
        por_serie = classe_rolamento_por_serie(pdm, texto)
        if por_serie:
            id_pdm, nome, ambiguas = por_serie[0], por_serie[1], ()
            origem_classe = "serie"
    if not id_pdm:
        ex.ambiguas = ambiguas
        return ex
    classe = pdm.classes[id_pdm]
    ex.id_pdm, ex.nome, ex.metodo = id_pdm, nome, "REGRA"
    ex.ambiguas = ambiguas
    ex.confianca_classe = {"cabecalho": 0.9, "texto": 0.8, "serie": 0.85}[origem_classe]
    if nome is None:
        ex.avisos.append("nome do material em aberto (empate entre " + ", ".join(n for n, _ in ambiguas) + ")")
    if grupo and classe.grupo != grupo:
        ex.confianca_classe -= 0.15
        ex.avisos.append(f"grupo do ERP ({grupo}) difere do grupo da classe ({classe.grupo})")

    def poe(atr: str, v: Valor) -> None:
        atual = ex.valores.get(atr)
        if atual is None or (not atual.valor and v.valor) or (v.valor and v.confianca > atual.confianca and atual.origem != "REGRA_ROTULO"):
            ex.valores[atr] = v

    # ---- 1. rótulos ATRIBUTO: VALOR
    nao_rotulados: list[str] = []
    for p in partes[1:] if cabeca else partes:
        if ":" not in p:
            nao_rotulados.append(p)
            continue
        rot, _, val = p.partition(":")
        atr = _atributo_do_rotulo(classe, rot)
        val = val.strip()
        if not atr or not val:
            continue
        a = classe.atributo(atr)
        c = canonicaliza_atributo(a, val, classe.id_pdm)
        ex.valores[atr] = Valor(c.valor, val, "REGRA_ROTULO", p, c.confianca, c.candidatos)

    # ---- 2. notação composta M12X50 (parafusos, porcas, barras)
    if classe.atributo("BITOLA"):
        for atr, n in grandezas.rosca_composta(texto).items():
            a = classe.atributo(atr)
            if a and (atr not in ex.valores or not ex.valores[atr].valor):
                c = canonicaliza_atributo(a, n.valor)
                if c.valor:
                    poe(atr, Valor(c.valor, n.valor, "REGRA_TEXTO", n.motivo, min(n.confianca, c.confianca)))

    # ---- 3. gazetteer sobre o texto inteiro, para atributos de lista ainda vazios
    for a in classe.atributos:
        atual = ex.valores.get(a.nome)
        if (atual and atual.valor) or a.tipo != "LISTA":
            continue
        if a.nome in ("FABRICANTE",) and not classe.por_referencia:
            continue
        m = acha_no_texto(a.valores, texto)
        if m.valor:
            poe(a.nome, Valor(m.valor, m.valor, "REGRA_TEXTO", m.valor, m.confianca))
        elif m.candidatos and not atual:
            ex.valores[a.nome] = Valor(None, None, "REGRA_TEXTO", None, 0.0, m.candidatos)

    # ---- 4. colunas do ERP nas classes de referência (regra 9)
    if classe.por_referencia:
        fab_col, ref_col = r.get("fabricante"), r.get("referencia_fabricante")
        a_fab = classe.atributo("FABRICANTE")
        if a_fab and not fab_col and not (ex.valores.get("FABRICANTE") and ex.valores["FABRICANTE"].valor):
            achado = fabricante_no_texto(texto, a_fab.valores)
            if achado:
                ex.valores["FABRICANTE"] = Valor(achado, achado, "REGRA_TEXTO", achado, 0.9)
        if fab_col and a_fab and not (ex.valores.get("FABRICANTE") and ex.valores["FABRICANTE"].valor):
            c = canonicaliza_atributo(a_fab, fabricante_canonico(fab_col, a_fab.valores))
            if c.valor:
                ex.valores["FABRICANTE"] = Valor(c.valor, fab_col, "COLUNA_ERP", fab_col, 0.95)
        if ref_col and classe.atributo("REFERENCIA FABRICANTE") and not (
                ex.valores.get("REFERENCIA FABRICANTE") and ex.valores["REFERENCIA FABRICANTE"].valor):
            ex.valores["REFERENCIA FABRICANTE"] = Valor(ref_col.strip(), ref_col, "COLUNA_ERP", ref_col, 0.95)

    # ---- 5. rolamento: vedação e folga saem do sufixo da referência
    if classe.id_pdm == "PDM020":
        ref = ex.valores.get("REFERENCIA")
        if not (ref and ref.valor):
            ref_txt = r.get("referencia_fabricante") or texto
            from ..identidade.referencias import referencia_rolamento
            norm = referencia_rolamento(ref_txt)
            if norm and re.match(r"^\d{4,5}", norm):
                ex.valores["REFERENCIA"] = Valor(norm, ref_txt, "REGRA_TEXTO", ref_txt, 0.9)
                ref = ex.valores["REFERENCIA"]
        if ref and ref.valor:
            for atr, v in deduz_vedacao_folga(ref.bruto or ref.valor).items():
                if not (ex.valores.get(atr) and ex.valores[atr].valor):
                    ex.valores[atr] = Valor(v, ref.bruto, "REGRA_PDM", ref.bruto, 0.92)
    return ex
