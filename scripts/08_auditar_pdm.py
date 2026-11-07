"""Audita o PDM e lista TODAS as confusoes estruturais possiveis, antes de rodar.

O caso PDM010 / PDM011 (mangueira hidraulica x mangueira hidraulica montada) foi
descoberto por acidente, olhando um numero esquisito. Este script enumera todos
os casos da mesma familia direto da planilha, para nenhum outro ser descoberto
por acidente.

Sete tipos de risco, cada um com a forma de resolver:

  A  mesmo substantivo, qualificador SUPERCONJUNTO     -> caixas exclusivas
  B  mesmo substantivo, qualificadores DISJUNTOS       -> palavra do qualificador
  C  substantivo COMPARTILHADO entre grupos diferentes -> grupo de mercadoria
  D  nome de atributo igual com ENUM DIFERENTE         -> validar na leitura
  E  classes com os MESMOS atributos obrigatorios      -> indistinguivel por caixa
  F  valor de enum que e SUBCADEIA de outro            -> casamento mais longo
  G  valores GEMEOS NUMERICOS no mesmo enum            -> embedding proibido

Uso: python 08_auditar_pdm.py [--tipo A] [--md docs/05-riscos-pdm.md]
"""

import argparse
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm  # noqa: E402
from saneamento.caixas import gemeos_numericos  # noqa: E402
from saneamento.texto import normalizar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--tipo", default="", help="mostra so um tipo (A..G)")
p.add_argument("--md", default=None, help="grava o relatorio em markdown")
a = p.parse_args()

pdm = Pdm.carregar(Path(a.artefatos) / "pdm.json")
linhas: list[str] = []


def diz(txt=""):
    print(txt)
    linhas.append(txt)


def secao(tipo, titulo, explica, resolve):
    diz()
    diz("=" * 96)
    diz(f"RISCO {tipo} - {titulo}")
    diz("=" * 96)
    diz(explica)
    diz(f"COMO RESOLVER: {resolve}")
    diz()


def quer(tipo):
    return not a.tipo or a.tipo.upper() == tipo


classes = sorted(pdm.classes.values(), key=lambda c: c.id_pdm)
achados: dict[str, int] = defaultdict(int)

# ---------------------------------------------------------------- A e B

if quer("A") or quer("B"):
    por_substantivo: dict[str, list] = defaultdict(list)
    for c in classes:
        for s in c.substantivos:
            por_substantivo[s].append(c)

    super_conj, disjuntos = [], []
    for subst, lista in sorted(por_substantivo.items()):
        if len(lista) < 2:
            continue
        for c1, c2 in combinations(lista, 2):
            q1 = {frozenset(q.split()) for q in c1.qualificadores} or {frozenset()}
            q2 = {frozenset(q.split()) for q in c2.qualificadores} or {frozenset()}
            relacao = None
            for a1 in q1:
                for a2 in q2:
                    if a1 and a2 and a1 < a2:
                        relacao = (c1, c2)
                    elif a1 and a2 and a2 < a1:
                        relacao = (c2, c1)
            if relacao:
                geral, especifica = relacao
                nomes_g = {x.nome for x in geral.atributos}
                excl = [x.nome for x in especifica.atributos
                        if x.obrigatorio and x.nome not in nomes_g]
                super_conj.append((subst, geral, especifica, excl))
            else:
                disjuntos.append((subst, c1, c2))

if quer("A"):
    secao("A", "MESMO SUBSTANTIVO, QUALIFICADOR SUPERCONJUNTO",
          "Uma classe e a outra MAIS alguma coisa. Se o texto nao traz a palavra\n"
          "extra, o casamento lexico cai sempre na classe geral.",
          "regras.ClassificadorLexico._preferir_irmao_especifico: troca para a\n"
          "               especifica quando o texto evidencia as caixas exclusivas dela.")
    for subst, geral, esp, excl in super_conj:
        achados["A"] += 1
        diz(f"  {geral.id_pdm} {geral.rotulo():<34} <- geral")
        diz(f"  {esp.id_pdm} {esp.rotulo():<34} <- especifica")
        diz(f"     substantivo comum .......... {subst}")
        diz(f"     unidade ................... {geral.unidade} vs {esp.unidade}"
            + ("   (a unidade do cadastro ja e uma pista)" if geral.unidade != esp.unidade else ""))
        diz(f"     caixas exclusivas da especifica ({len(excl)}): {excl}")
        diz()
    if not super_conj:
        diz("  nenhum caso.")

if quer("B"):
    secao("B", "MESMO SUBSTANTIVO, QUALIFICADORES DISJUNTOS",
          "Irmas que se distinguem por uma palavra. Se a palavra faltar no texto,\n"
          "nao ha como escolher entre elas pelo nome.",
          "a palavra do qualificador tem de estar no texto; sem ela o registro\n"
          "               fica com empate e vai para a banda do LLM com as candidatas do grupo.")
    por_par: dict[str, list] = defaultdict(list)
    for subst, c1, c2 in disjuntos:
        por_par[subst].append((c1, c2))
    for subst, pares in sorted(por_par.items()):
        achados["B"] += len(pares)
        envolvidas = sorted({c.id_pdm + " " + (c.qualificadores[0] if c.qualificadores else "-")
                             for p in pares for c in p})
        diz(f"  {subst:<24} {len(pares)} par(es): {', '.join(envolvidas)}")

# ---------------------------------------------------------------- C

if quer("C"):
    secao("C", "SUBSTANTIVO COMPARTILHADO ENTRE GRUPOS DIFERENTES",
          "O mesmo substantivo designa objetos SEM NENHUMA relacao. Se o\n"
          "GRUPO_MERCADORIA do cadastro estiver errado, o item vira outra coisa.",
          "manter o filtro por grupo e nunca abandonar grupo de classe unica;\n"
          "               quando a busca ampla troca de grupo, marcar grupo_corrigido.")
    por_subst: dict[str, set] = defaultdict(set)
    for c in classes:
        for s in c.substantivos:
            por_subst[s].add((c.grupo, c.id_pdm, c.rotulo()))
    for s, conj in sorted(por_subst.items()):
        grupos = {g for g, _, _ in conj}
        if len(grupos) > 1:
            achados["C"] += 1
            diz(f"  {s!r}")
            for g, cid, rot in sorted(conj):
                diz(f"      {g}  {cid}  {rot}   ({pdm.grupos.get(g, '')})")
            diz()
    if not achados["C"]:
        diz("  nenhum caso.")

# ---------------------------------------------------------------- D

if quer("D"):
    secao("D", "NOME DE ATRIBUTO IGUAL COM ENUM DIFERENTE",
          "Os 93 nomes de atributo do PDM sao GLOBAIS. O mesmo nome tem listas de\n"
          "valores diferentes em classes diferentes.",
          "qualquer cache ou dicionario indexado por nome de atributo precisa\n"
          "               validar o valor contra o enum DA CLASSE na leitura.")
    por_nome: dict[str, dict] = defaultdict(dict)
    for c in classes:
        for at in c.atributos:
            if at.valores:
                por_nome[at.nome][c.id_pdm] = tuple(at.valores)
    for nome, porc in sorted(por_nome.items(), key=lambda x: -len(set(x[1].values()))):
        distintos = set(porc.values())
        if len(distintos) < 2:
            continue
        achados["D"] += 1
        diz(f"  {nome}  ({len(porc)} classes, {len(distintos)} listas diferentes)")
        for cid, vals in sorted(porc.items())[:4]:
            diz(f"      {cid}: {list(vals)[:5]}{'...' if len(vals) > 5 else ''}")
        if len(porc) > 4:
            diz(f"      ... e mais {len(porc) - 4} classes")
        diz()

# ---------------------------------------------------------------- E

if quer("E"):
    secao("E", "CLASSES COM OS MESMOS ATRIBUTOS OBRIGATORIOS",
          "Duas classes cujas caixas obrigatorias coincidem nao podem ser\n"
          "distinguidas por evidencia de caixa - so pelo nome.",
          "se o nome nao resolver, nao ha sinal estrutural: precisa de LLM ou\n"
          "               de decisao humana.")
    assinatura: dict[tuple, list] = defaultdict(list)
    for c in classes:
        chave = tuple(sorted(x.nome for x in c.atributos if x.obrigatorio))
        if chave:
            assinatura[chave].append(c)
    for chave, lista in assinatura.items():
        if len(lista) > 1:
            achados["E"] += 1
            diz(f"  caixas: {list(chave)}")
            for c in lista:
                diz(f"      {c.id_pdm}  {c.rotulo():<34} grupo {c.grupo}  unidade {c.unidade}")
            diz()
    if not achados["E"]:
        diz("  nenhum caso.")

# ---------------------------------------------------------------- F e G

if quer("F") or quer("G"):
    subcadeia, gemeos = [], []
    for c in classes:
        for at in c.atributos:
            for v1, v2 in combinations(at.valores, 2):
                n1, n2 = normalizar(v1), normalizar(v2)
                if f" {n1} " in f" {n2} " or f" {n2} " in f" {n1} ":
                    subcadeia.append((c.id_pdm, at.nome, v1, v2))
                elif gemeos_numericos(v1, v2):
                    gemeos.append((c.id_pdm, at.nome, v1, v2))

if quer("F"):
    secao("F", "VALOR DE ENUM QUE E SUBCADEIA DE OUTRO",
          "Procurar 'INOX 316' no texto casa tambem dentro de 'ACO INOX 316'.\n"
          "Sem casamento mais longo, o gazetteer escolhe o errado ou acusa ambiguidade.",
          "regras._por_gazetteer ordena por tamanho e descarta o que e subcadeia\n"
          "               de um casamento maior.")
    for cid, attr, v1, v2 in subcadeia[:14]:
        achados["F"] += 1
        diz(f"  {cid} {attr:<22} {v1!r} dentro de {v2!r}")
    if len(subcadeia) > 14:
        diz(f"  ... e mais {len(subcadeia) - 14} pares")
    achados["F"] = len(subcadeia)
    if not subcadeia:
        diz("  nenhum caso.")

if quer("G"):
    secao("G", "VALORES GEMEOS NUMERICOS NO MESMO ENUM",
          "Valores que diferem SO por numero. Medido: cos(ACO INOX 304, ACO INOX 316)\n"
          "= 0,963 - o embedding nao os separa, e confundi-los cria item errado.",
          "caixas.classificar_banda tem trava: se 1o e 2o colocados sao gemeos\n"
          "               numericos, o embedding nunca decide, vai para o LLM.")
    por_attr: dict[tuple, list] = defaultdict(list)
    for cid, attr, v1, v2 in gemeos:
        por_attr[(cid, attr)].append((v1, v2))
    for (cid, attr), pares in sorted(por_attr.items())[:16]:
        diz(f"  {cid} {attr:<22} {len(pares)} par(es), ex.: {pares[0][0]!r} x {pares[0][1]!r}")
    achados["G"] = len(gemeos)
    if len(por_attr) > 16:
        diz(f"  ... e mais {len(por_attr) - 16} atributos")

# ---------------------------------------------------------------- resumo

diz()
diz("=" * 96)
diz("RESUMO")
diz("=" * 96)
rotulos = {
    "A": "mesmo substantivo, qualificador superconjunto",
    "B": "mesmo substantivo, qualificadores disjuntos",
    "C": "substantivo compartilhado entre grupos",
    "D": "nome de atributo com enum diferente por classe",
    "E": "classes com os mesmos atributos obrigatorios",
    "F": "valor de enum subcadeia de outro",
    "G": "valores gemeos numericos no mesmo enum",
}
for t, r in rotulos.items():
    if quer(t):
        diz(f"  {t}  {achados[t]:>5}  {r}")

if a.md:
    destino = Path(a.md)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        "# Riscos estruturais do PDM\n\n"
        "Gerado por `scripts/08_auditar_pdm.py` a partir de\n"
        "`dados/03_padrao_cadastro_PDM.xlsx`. Nao editar a mao.\n\n```\n"
        + "\n".join(linhas) + "\n```\n",
        encoding="utf-8")
    print(f"\nGravado: {destino}")
