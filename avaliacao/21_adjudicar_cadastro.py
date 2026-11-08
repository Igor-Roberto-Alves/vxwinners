# -*- coding: utf-8 -*-
"""V2: adjudica as anotacoes A e B de unidade, descricao e sobrevivente e gera os gabaritos.

Entradas (todas em avaliacao/):
  candidatos_cadastro.csv       universo (gerado por 20_candidatos_cadastro.py, so linha crua)
  anotacoes_cadastro_A.jsonl    persona A: analista de cadastro (le o PDM ao pe da letra)
  anotacoes_cadastro_B.jsonl    persona B: suprimentos/almoxarifado (pensa no saldo e no uso)
  ../dados/03_padrao_cadastro_PDM.xlsx  aba ATRIBUTOS (ORDEM) para remontar a descricao

As duas passadas foram feitas em separado, em ordens diferentes de itens
(visor com semente 11 para A e 97 para B), lendo so a linha crua da base e o PDM.
Nenhuma coluna de saida do pipeline foi vista na anotacao.

Campos comparados (divergencia = valor diferente em qualquer um):
  unidade       id_pdm, unidade_esperada, exige_fator
  descricao     id_pdm, descricao (a string inteira, remontada na ORDEM do PDM);
                o kappa e calculado tambem por atributo
  sobrevivente  sobrevivente_esperado, estoque_consolidado_esperado, concorda_com_a_regra

Cada divergencia exige uma decisao escrita em ADJUDICACOES; se faltar alguma,
o script ABORTA listando as pendencias. Ele nunca decide sozinho.

Convencoes do gabarito de descricao:
  - obrigatorio que o texto nao traz, ou traz sem decidir entre dois valores da
    lista: escrito como "<PENDENTE>" (a caixa fica na descricao, vazia);
  - opcional so entra quando o texto o traz (nao se deduz da referencia);
  - condicional (QUANDO_SE_APLICA) so entra quando a condicao vale;
  - um valor de lista so e fechado quando o texto tem uma palavra sobre aquele
    atributo e a lista do PDM so admite um valor compativel com ela
    (ex.: "MAT TERMINAIS: ACO CARBONO" -> ACO CARBONO ZINCADO, unico de carbono);
  - pressao convertida para BAR com uma casa decimal (60 PSI -> 4,1BAR).

Saidas: gold_unidade.csv, gold_descricao.csv, gold_sobrevivente.csv,
        revisao_humana_cadastro.csv (divergencias + embalagem + 10% do resto).
A concordancia (acordo bruto e kappa) sai no terminal e e repetida no
resultado_cadastro.md pelo evaluate_cadastro.py.

Uso: uv run --no-project --with pandas --with openpyxl python avaliacao/21_adjudicar_cadastro.py
"""
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
SEED_REVISAO = 20261107

CAMPOS = {
    "unidade": ["id_pdm", "unidade_esperada", "exige_fator"],
    "descricao": ["id_pdm", "descricao"],
    "sobrevivente": ["sobrevivente_esperado", "estoque_consolidado_esperado",
                     "concorda_com_a_regra"],
}

# (tarefa, item_id) -> decisao final do ADJUDICADOR (campos que substituem os de A),
# com justificativa propria escrita depois de reler a linha crua e o PDM.
J_MASSA = ("decisao do adjudicador: o rotulo de unidade e a unidade-alvo da classe "
           "(regra 11). FILA_FATOR fica reservado a embalagem (CX, JG, RL, BD, GL, CT, BR), "
           "como define o plano V2.1. B tem razao no saldo: {x} nao vira contagem sem o "
           "fator; isso fica em exige_fator=SIM e o avaliador conta a conversao sem fator a parte")
ADJUDICACOES = {
    ("unidade", "U036"): {"unidade_esperada": "PC", "exige_fator": "SIM",
                          "justificativa": J_MASSA.format(x="KG de barra tensora")},
    ("unidade", "U037"): {"unidade_esperada": "PC", "exige_fator": "SIM",
                          "justificativa": J_MASSA.format(x="KG de correia")},
    ("unidade", "U038"): {"unidade_esperada": "PC", "exige_fator": "SIM",
                          "justificativa": J_MASSA.format(x="KG de parafuso")},
    ("unidade", "U039"): {"unidade_esperada": "PC", "exige_fator": "SIM",
                          "justificativa": J_MASSA.format(x="KG de parafuso")},
    ("unidade", "U049"): {"unidade_esperada": "PC", "exige_fator": "SIM",
                          "justificativa": J_MASSA.format(x="KG de mangueira montada")
                          + "; classe PDM011 (terminais e comprimento 1100MM no texto)"},
    ("unidade", "U044"): {"unidade_esperada": "M", "exige_fator": "SIM",
                          "justificativa": J_MASSA.format(x="UN de cabo (lance sem comprimento)")},
    ("unidade", "U050"): {"unidade_esperada": "L", "exige_fator": "SIM",
                          "fator_no_texto": "200 (TAMBOR 200L)",
                          "justificativa": J_MASSA.format(x="UN de oleo (tambor)")
                          + "; aqui o fator esta no texto: 1 UN = 200 L"},
    ("unidade", "U046"): {"unidade_esperada": "PR", "exige_fator": "SIM",
                          "justificativa": "decisao do adjudicador: PR e a unidade da classe; "
                          "UN de luva pode ser o par ou a peca avulsa e a troca pode dobrar ou "
                          "dividir o saldo; conservador: exige conferir o fator (fica com B)"},
    ("unidade", "U047"): {"unidade_esperada": "PR", "exige_fator": "SIM",
                          "justificativa": "decisao do adjudicador: PR e a unidade da classe; "
                          "PC de calcado e ambiguo (pe ou par); conservador, como U046 (fica com B)"},
    ("descricao", "D027"): {"usar": "B", "justificativa":
                            "decisao do adjudicador: o texto diz MAT TERMINAIS: ACO CARBONO e a "
                            "lista de MATERIAL TERMINAIS so tem um valor de carbono (ACO CARBONO "
                            "ZINCADO); o texto decide dentro da lista (fica com B)"},
    ("descricao", "D004"): {"usar": "B", "justificativa":
                            "decisao do adjudicador: MAT: ACO sem INOX e classe SAE GRAU 5 (so "
                            "existe em aco carbono): o texto decide ACO CARBONO (fica com B)"},
    ("descricao", "D020"): {"usar": "B", "justificativa":
                            "decisao do adjudicador: MATERIAL: ACO FORJADO sem INOX; das opcoes "
                            "forjadas da lista (A105 carbono, A182 F316 inox) so A105 e compativel "
                            "(fica com B; mesmo criterio de D004)"},
    ("descricao", "D001"): {"usar": "A", "justificativa":
                            "decisao do adjudicador: o texto nao tem nenhuma palavra sobre o "
                            "material; deduzir ACO CARBONO da classe 8 e inferencia de dominio "
                            "sobre atributo obrigatorio, que o PDM so autoriza para a rosca "
                            "(regra 2). Fica <PENDENTE> (fica com A)"},
    ("descricao", "D036"): {"usar": "A", "justificativa":
                            "decisao do adjudicador: o texto nao traz a aplicacao; PC3000 e o "
                            "modelo. Deduzir ESCAVADEIRA HIDRAULICA do modelo e o mesmo tipo de "
                            "inferencia rejeitado em D001. Fica <PENDENTE> (fica com A)"},
    ("descricao", "D012"): {"usar": "A", "justificativa":
                            "decisao do adjudicador: DIAMETRO INTERNO e opcional e o texto nao o "
                            "traz; a regra 7 permite deduzir da referencia, mas o gabarito usa "
                            "so valores do texto cru. Fica fora (fica com A). Uma descricao com "
                            "40MM tambem obedece ao PDM: o avaliador mostra isso no modulo valores"},
    ("sobrevivente", "S024"): {"concorda_com_a_regra": "NAO",
                               "sobrevivente_suprimentos": "28561418",
                               "justificativa": "decisao do adjudicador: a regra elege 24774110 "
                               "porque o texto cru de 28561418 nao traz o modelo; mas os quatro "
                               "codigos tem a mesma chave, a descricao do sobrevivente sera "
                               "reescrita no padrao e o modelo e recuperavel dos irmaos. "
                               "28561418 tem a movimentacao mais recente (2026-05) e o maior "
                               "saldo (6). Completude do texto antigo nao deveria vencer o uso "
                               "(fica com B)"},
}

# --------------------------------------------------------------------- PDM
at = pd.read_excel(REPO / "dados/03_padrao_cadastro_PDM.xlsx", sheet_name="ATRIBUTOS",
                   dtype=str).fillna("")
ORDEM = defaultdict(dict)
for r in at.itertuples():
    ORDEM[r.ID_PDM][r.ATRIBUTO.strip()] = int(r.ORDEM)


def montar(cid, cabeca, attrs):
    o = ORDEM[cid]
    for n, _ in attrs:
        if n not in o:
            sys.exit(f"atributo {n!r} nao existe em {cid}")
    attrs = sorted(attrs, key=lambda x: o[x[0]])
    return "; ".join([cabeca] + [f"{n}: {v}" for n, v in attrs])


# --------------------------------------------------------------------- carga
cand = pd.read_csv(RAIZ / "candidatos_cadastro.csv", dtype=str, keep_default_na=False)
itens = cand.groupby(["tarefa", "item_id"])


def carrega(nome):
    d = {}
    for i, linha in enumerate((RAIZ / f"anotacoes_cadastro_{nome}.jsonl")
                              .read_text(encoding="utf-8").splitlines(), 1):
        if not linha.strip():
            continue
        r = json.loads(linha)
        k = (r["tarefa"], r["item_id"])
        if k in d:
            sys.exit(f"{nome}:{i}: item duplicado {k}")
        if r["tarefa"] == "descricao":
            remontada = montar(r["id_pdm"], r["cabeca"], r["atributos"])
            if remontada != r["descricao"]:
                sys.exit(f"{nome}:{i}: descricao nao bate com a remontagem na ORDEM do PDM")
        d[k] = r
    return d


A, B = carrega("A"), carrega("B")
univ = set(itens.groups)
for nome, d in (("A", A), ("B", B)):
    if set(d) != univ:
        sys.exit(f"anotador {nome}: faltam {sorted(univ - set(d))[:5]} sobram {sorted(set(d) - univ)[:5]}")


def kappa(pares):
    n = len(pares)
    po = sum(a == b for a, b in pares) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[c] * cb.get(c, 0) for c in ca) / (n * n)
    if pe >= 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


# --------------------------------------------------------------------- concordancia
pares = defaultdict(list)
divergentes = []
for k in sorted(univ):
    tarefa = k[0]
    a, b = A[k], B[k]
    div = False
    for c in CAMPOS[tarefa]:
        pares[(tarefa, c)].append((str(a[c]), str(b[c])))
        div |= str(a[c]) != str(b[c])
    if tarefa == "descricao":
        da, db = dict(map(tuple, a["atributos"])), dict(map(tuple, b["atributos"]))
        for n in sorted(set(da) | set(db)):
            pares[(tarefa, "atributo")].append((da.get(n, "(fora)"), db.get(n, "(fora)")))
    if div:
        divergentes.append(k)

conc = {}
print("=== acordo A x B (rotulo por campo) ===")
for (t, c), ps in sorted(pares.items()):
    ac = sum(x == y for x, y in ps) / len(ps)
    conc[f"{t}.{c}"] = {"n": len(ps), "acordo": round(ac, 4), "kappa": round(kappa(ps), 4)}
    print(f"  {t:<13} {c:<30} n={len(ps):>3}  acordo={ac:.3f}  kappa={kappa(ps):.3f}")
todos = [p for (t, c), ps in pares.items() if c != "atributo" for p in ps]
conc["global"] = {"n": len(todos), "acordo": round(sum(x == y for x, y in todos) / len(todos), 4),
                  "kappa": round(kappa(todos), 4)}
por_item = {t: sum(1 for k in divergentes if k[0] == t) for t in CAMPOS}
conc["itens_divergentes"] = por_item
print(f"  GLOBAL (campos, sem o detalhe por atributo) n={conc['global']['n']} "
      f"acordo={conc['global']['acordo']:.3f} kappa={conc['global']['kappa']:.3f}")
print(f"\nitens divergentes: {len(divergentes)} {por_item}")
for k in divergentes:
    difs = [f"{c}: A={A[k][c]!s:.60} | B={B[k][c]!s:.60}" for c in CAMPOS[k[0]]
            if str(A[k][c]) != str(B[k][c])]
    print(f"  {k}: " + " ; ".join(difs))

pend = [k for k in divergentes if k not in ADJUDICACOES]
if pend:
    sys.exit(f"\n{len(pend)} divergencia(s) sem adjudicacao: {pend}")
sobra = [k for k in ADJUDICACOES if k not in divergentes]
if sobra:
    sys.exit(f"ADJUDICACOES com item sem divergencia: {sobra}")

# --------------------------------------------------------------------- gabaritos
def resumo(t, r):
    if t == "unidade":
        return f"{r['id_pdm']}|{r['unidade_esperada']}|fator={r['exige_fator']}"
    if t == "descricao":
        return r["descricao"]
    return f"{r['sobrevivente_esperado']}|{r['estoque_consolidado_esperado']}|{r['concorda_com_a_regra']}"


gold = {"unidade": [], "descricao": [], "sobrevivente": []}
for k in sorted(univ):
    t, it = k
    linhas = itens.get_group(k)
    a, b = A[k], B[k]
    final = dict(a)
    origem, conf = "acordo", "ALTA"
    if k in ADJUDICACOES:
        dec = ADJUDICACOES[k]
        if dec.get("usar") == "B":
            final = dict(b)
        final.update({c: v for c, v in dec.items() if c != "usar"})
        origem, conf = "adjudicado", "MEDIA"
    base = {"item_id": it, "estrato": linhas["estrato"].iloc[0],
            "subestrato": linhas["subestrato"].iloc[0]}
    tail = {"justificativa": final["justificativa"], "anot_A": resumo(t, a),
            "anot_B": resumo(t, b), "origem_decisao": origem, "confianca": conf}
    if t == "unidade":
        r = linhas.iloc[0]
        gold[t].append({**base, "CODIGO_MATERIAL": r["CODIGO_MATERIAL"],
                        "unidade_original": r["UNIDADE_MEDIDA"], "id_pdm": final["id_pdm"],
                        "unidade_esperada": final["unidade_esperada"],
                        "exige_fator": final["exige_fator"],
                        "fator_no_texto": final.get("fator_no_texto", ""), **tail})
    elif t == "descricao":
        r = linhas.iloc[0]
        gold[t].append({**base, "CODIGO_MATERIAL": r["CODIGO_MATERIAL"], "id_pdm": final["id_pdm"],
                        "cabeca": final["cabeca"],
                        "atributos": json.dumps(final["atributos"], ensure_ascii=False),
                        "descricao_esperada": montar(final["id_pdm"], final["cabeca"],
                                                     final["atributos"]), **tail})
    else:
        cods = list(linhas["CODIGO_MATERIAL"])
        for c in (final["sobrevivente_esperado"],):
            assert c in cods, (it, c)
        gold[t].append({**base, "codigos": "|".join(cods), "n_codigos": len(cods),
                        "sobrevivente_esperado": final["sobrevivente_esperado"],
                        "estoque_consolidado_esperado": final["estoque_consolidado_esperado"],
                        "concorda_com_a_regra": final["concorda_com_a_regra"],
                        "sobrevivente_suprimentos": final["sobrevivente_suprimentos"],
                        "completude_julgada": json.dumps(final["completude_julgada"]), **tail})

for t, arq in (("unidade", "gold_unidade.csv"), ("descricao", "gold_descricao.csv"),
               ("sobrevivente", "gold_sobrevivente.csv")):
    pd.DataFrame(gold[t]).to_csv(RAIZ / arq, index=False, encoding="utf-8")
    print(f"gravado {arq}: {len(gold[t])} itens "
          f"({sum(g['origem_decisao'] == 'adjudicado' for g in gold[t])} adjudicados)")

# --------------------------------------------------------------------- revisao humana
texto = {}
for k in univ:
    g = itens.get_group(k)
    texto[k] = " || ".join(f"{r.CODIGO_MATERIAL} [{r.STATUS} {r.UNIDADE_MEDIDA} est={r.ESTOQUE_ATUAL} "
                           f"mov={r.DATA_ULTIMA_MOVIMENTACAO}] {r.DESCRICAO_LONGA}"
                           if k[0] == "sobrevivente" else
                           f"{r.CODIGO_MATERIAL} [{r.UNIDADE_MEDIDA}] {r.DESCRICAO_LONGA}"
                           for r in g.itertuples())
rev, resto = [], []
for t, linhas in gold.items():
    for g in linhas:
        k = (t, g["item_id"])
        motivo = []
        if g["origem_decisao"] == "adjudicado":
            motivo.append("divergencia adjudicada")
        if t == "unidade" and g["estrato"] == "embalagem":
            motivo.append("embalagem")
        rot = (f"{g['unidade_esperada']} (exige_fator={g['exige_fator']})" if t == "unidade" else
               g["descricao_esperada"] if t == "descricao" else
               f"sobrevivente={g['sobrevivente_esperado']}; estoque={g['estoque_consolidado_esperado']}; "
               f"concorda={g['concorda_com_a_regra']}")
        linha = {"tarefa": t, "item_id": g["item_id"], "estrato": g["estrato"],
                 "texto_cru": texto[k], "rotulo_gold": rot,
                 "justificativa": g["justificativa"], "anot_A": g["anot_A"], "anot_B": g["anot_B"]}
        (rev if motivo else resto).append((linha, "; ".join(motivo)))
rng = random.Random(SEED_REVISAO)
amostra = rng.sample(resto, max(1, round(0.10 * len(resto))))
saida = [{**l, "motivo_inclusao": m} for l, m in rev] + \
        [{**l, "motivo_inclusao": "amostra 10% dos demais"} for l, _ in amostra]
for s in saida:
    s.update({"concordo_discordo": "", "valor_certo": "", "comentario": "", "revisor": ""})
pd.DataFrame(saida).to_csv(RAIZ / "revisao_humana_cadastro.csv", index=False, encoding="utf-8")
print(f"gravado revisao_humana_cadastro.csv: {len(saida)} linhas "
      f"({len(rev)} obrigatorias + {len(amostra)} da amostra de 10% de {len(resto)})")

print("\nconcordancia:", json.dumps(conc["global"]))
