# -*- coding: utf-8 -*-
"""Avalia a leitura dos PEDIDOS pelo pipeline contra o gabarito de pedidos.

Uso:
  backend/.venv/bin/python avaliacao/evaluate_pedidos.py \
      [--artefatos artefatos/] [--saida avaliacao/resultado_pedidos.md]

Le de --artefatos: saneado_pedidos.csv (ESTADO, ID_PDM) e decisoes_pedidos.jsonl
(valor, fonte e estado de CADA atributo - e o que permite dizer qual camada erra).
Le de avaliacao/: gold_pedidos.csv, gold_classe_pedidos.csv, concordancia_pedidos.json.

O que mede
----------
CLASSE     acerto de ID_PDM (ou FORA_DO_PDM), com a matriz de confusao das classes
           irmas que se confundem.
CAIXAS     por atributo, por familia, por estilo de entrada, por armadilha e POR
           FONTE do valor (gazetteer, rotulo, gramatica, dominio, aprendido...):
             precisao  dos valores que o pipeline afirmou, quantos batem
             cobertura dos obrigatorios que o gabarito diz DEFINIDO, quantos o
                       pipeline preencheu
             invencao  o gabarito diz AUSENTE/INDEFINIVEL e o pipeline preencheu
INVENCAO em duas leituras, porque o gabarito carrega as duas:
  estrita     qualquer preenchimento sobre AUSENTE/INDEFINIVEL conta
  permissiva  nao conta quando o valor preenchido e exatamente o `permissivo` do
              gabarito, isto e, a deducao que o texto nao sustenta mas a operacao
              defende (ex.: "do H3SH 9" -> APLICACAO REDUTOR)
  A diferenca entre as duas e quanto do que o pipeline preenche vem de fora do
  texto do pedido.

Comparacao de valores: grandeza numerica com unidade compara numero (35,0MM =
35MM), polegada em fracao vira decimal (1.1/2POL = 1,5), pressao tolera 1%, e
valor de lista compara sem acento e sem caixa.
"""
import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent

IRMAS = [
    ("valvulas", ["PDM040", "PDM041", "PDM042", "PDM043", "PDM044"]),
    ("rolamentos", ["PDM020", "PDM021", "PDM022", "PDM023"]),
    ("parafusos", ["PDM001", "PDM002"]),
    ("arruelas", ["PDM004", "PDM005"]),
    ("mangueiras", ["PDM010", "PDM011", "PDM012", "PDM013", "PDM014"]),
    ("vedacao", ["PDM031", "PDM032", "PDM033", "PDM034"]),
    ("conexoes", ["PDM050", "PDM051"]),
    ("referencia_fabricante", ["PDM100", "PDM110"]),
]


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def norm(s):
    return re.sub(r"\s+", " ", sem_acento(s)).strip().upper()


# ----------------------------------------------------------- comparacao ------
_FRAC = re.compile(r"^(?:(\d+)\.)?(\d+)\s*/\s*(\d+)$")


def _numero(txt):
    """Devolve (valor, unidade) de '35,0MM', '1,5MM2', '1.1/2POL', '0-16BAR'..."""
    t = norm(txt).replace(" ", "")
    m = re.match(r"^0-(\d+(?:,\d+)?)(BAR)$", t)        # faixa de manometro
    if m:
        return float(m.group(1).replace(",", ".")), "FAIXA_BAR"
    m = re.match(r"^((?:\d+\.)?\d+/\d+|\d+(?:,\d+)?)(MM2|MM|POL|BAR|W|A|V|KV|KA|MM%)?$", t)
    if not m:
        return None, None
    bruto, uni = m.group(1), m.group(2) or ""
    f = _FRAC.match(bruto)
    if f:
        val = int(f.group(2)) / int(f.group(3)) + int(f.group(1) or 0)
    else:
        try:
            val = float(bruto.replace(",", "."))
        except ValueError:
            return None, None
    return val, uni


def igual(gold, pred):
    """Compara o valor do gabarito com o do pipeline."""
    g, p = norm(gold), norm(pred)
    if g == p:
        return True
    vg, ug = _numero(g)
    vp, up = _numero(p)
    if vg is None or vp is None or ug != up:
        return False
    tol = 0.01 if ug in ("BAR", "FAIXA_BAR") else 1e-6
    return abs(vg - vp) <= max(tol * max(abs(vg), 1e-9), 1e-9)


# ------------------------------------------------------------- estatistica ---
def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    meio = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centro - meio), min(1.0, centro + meio)


def pct(k, n):
    if n == 0:
        return "—"
    p, lo, hi = wilson(k, n)
    return f"{p:.1%} [{lo:.1%}–{hi:.1%}]"


# ------------------------------------------------------------------ dados ----
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--artefatos", default=str(REPO / "artefatos"))
ap.add_argument("--saida", default=str(RAIZ / "resultado_pedidos.md"))
a = ap.parse_args()
ART = Path(a.artefatos)

gold = pd.read_csv(RAIZ / "gold_pedidos.csv", dtype=str).fillna("")
gold_cls = pd.read_csv(RAIZ / "gold_classe_pedidos.csv", dtype=str).fillna("")
conc = json.loads((RAIZ / "concordancia_pedidos.json").read_text(encoding="utf-8"))

san = pd.read_csv(ART / "saneado_pedidos.csv", dtype=str).fillna("")
pred_classe = {}
for _, r in san.iterrows():
    pred_classe[r["CODIGO_MATERIAL"]] = r["ID_PDM"] or r["ESTADO"]
pred_estado = dict(zip(san["CODIGO_MATERIAL"], san["ESTADO"]))

# decisoes por (pedido, atributo): valor, fonte, estado
pred: dict[tuple[str, str], dict] = {}
with (ART / "decisoes_pedidos.jsonl").open(encoding="utf-8") as fh:
    for ln in fh:
        r = json.loads(ln)
        for d in r["decisoes"]:
            pred[(r["codigo"], norm(d["atributo"]))] = d

# ------------------------------------------------------------------ classe ---
cls_rows, conf = [], Counter()
for _, g in gold_cls.iterrows():
    pid, y = g["ID_PEDIDO"], g["y_gold"]
    yp = pred_classe.get(pid, "SEM_SAIDA")
    if y == "FORA_DO_PDM":
        ok = pred_estado.get(pid) == "FORA_DO_PDM"
    else:
        ok = (yp == y)
    cls_rows.append({"ID_PEDIDO": pid, "gold": y, "pred": yp, "ok": ok,
                     "estrato": g["estrato"], "estilo": g["estilo"]})
    if not ok:
        conf[(y, yp)] += 1
cls = pd.DataFrame(cls_rows)

# ------------------------------------------------------------------ caixas ---
linhas = []
for _, g in gold.iterrows():
    pid, campo = g["ID_PEDIDO"], norm(g["campo"])
    d = pred.get((pid, campo))
    aceito = bool(d and d.get("estado") == "ACEITO" and d.get("valor"))
    valor = (d.get("valor") or "") if d else ""
    fonte = (d.get("fonte") or "-") if d else "sem_decisao"
    st = g["status"]
    # Classe certa? Se o pipeline deu outra classe ao pedido, ele avaliou outro
    # conjunto de atributos e esta caixa nunca foi considerada - perder nao e o
    # mesmo defeito que perder com a classe certa, e as duas coisas nao podem
    # entrar na mesma cobertura.
    classe_ok = pred_classe.get(pid) == g["id_pdm"]
    estado_pred = (d.get("estado") if d else "") or "sem_decisao"
    bate = aceito and st == "DEFINIDO" and igual(g["y_gold"], valor)
    inv_estrita = aceito and st in ("AUSENTE", "INDEFINIVEL")
    inv_permissiva = inv_estrita and not (g["permissivo"]
                                          and igual(g["permissivo"], valor))
    linhas.append({
        "ID_PEDIDO": pid, "campo": g["campo"], "id_pdm": g["id_pdm"],
        "familia": g["familia_prevista"], "estilo": g["estilo"],
        "armadilhas": g["armadilhas"], "status": st, "y_gold": g["y_gold"],
        "permissivo": g["permissivo"], "pred": valor, "fonte": fonte,
        "aceito": aceito, "acerto": bate, "inv_estrita": inv_estrita,
        "inv_permissiva": inv_permissiva,
        "erro_de_valor": aceito and st == "DEFINIDO" and not bate,
        "perdido": (not aceito) and st == "DEFINIDO",
        "classe_ok": classe_ok, "estado_pred": estado_pred,
        "perdido_classe_errada": (not aceito) and st == "DEFINIDO" and not classe_ok,
        "perdido_pendente": ((not aceito) and st == "DEFINIDO" and classe_ok
                             and estado_pred == "PENDENTE"),
        "perdido_ambiguo": ((not aceito) and st == "DEFINIDO" and classe_ok
                            and estado_pred == "AMBIGUO"),
        "evidencia": g["evidencia"], "confianca": g["confianca"],
        "origem_decisao": g["origem_decisao"],
    })
cx = pd.DataFrame(linhas)

definidos = cx[cx["status"] == "DEFINIDO"]
vazios = cx[cx["status"].isin(["AUSENTE", "INDEFINIVEL"])]
afirmados = cx[cx["aceito"]]


def bloco(df, coluna, titulo):
    """Tabela de precisao/cobertura/invencao agrupada por `coluna`."""
    out = [f"\n### {titulo}\n",
           "| " + coluna + " | n gold | afirmados | precisão [IC 95%] | "
           "cobertura | invenção estrita | invenção permissiva |",
           "|---|---:|---:|---|---|---:|---:|"]
    for v, g in sorted(df.groupby(coluna), key=lambda kv: -len(kv[1])):
        gd = g[g["status"] == "DEFINIDO"]
        gv = g[g["status"].isin(["AUSENTE", "INDEFINIVEL"])]
        ga = g[g["aceito"] & (g["status"] == "DEFINIDO")]
        out.append(
            f"| {v or '—'} | {len(g)} | {int(g['aceito'].sum())} | "
            f"{pct(int(ga['acerto'].sum()), len(ga))} | "
            f"{pct(int(gd['aceito'].sum()), len(gd))} | "
            f"{int(gv['inv_estrita'].sum())}/{len(gv)} | "
            f"{int(gv['inv_permissiva'].sum())}/{len(gv)} |")
    return "\n".join(out)


# ------------------------------------------------------------------ relatorio ---
ga = cx[cx["aceito"] & (cx["status"] == "DEFINIDO")]
L = []
L.append("# Resultado: gabarito de PEDIDOS — classe e caixas\n")
L.append(f"Gerado por `avaliacao/evaluate_pedidos.py` em "
         f"{datetime.now():%Y-%m-%d %H:%M}, sobre `{ART}`. "
         f"Gabarito: `gold_pedidos.csv` ({len(gold)} rótulos de caixa) e "
         f"`gold_classe_pedidos.csv` ({len(gold_cls)} de classe), em "
         f"{gold['ID_PEDIDO'].nunique()} pedidos. Sorteio: "
         "`22_candidatos_pedidos.py` (semente 20261108); adjudicação: "
         "`23_adjudicar_pedidos.py`.\n")
L.append("IC = intervalo de confiança de 95% de Wilson.\n")

L.append("## Resumo\n")
L.append(f"- **Classe:** acerto {pct(int(cls['ok'].sum()), len(cls))} em "
         f"{len(cls)} pedidos.")
L.append(f"- **Caixas:** precisão {pct(int(ga['acerto'].sum()), len(ga))} nos "
         f"{len(ga)} valores afirmados sobre caixa que o gabarito define; "
         f"cobertura {pct(int(definidos['aceito'].sum()), len(definidos))}.")
L.append(f"- **Invenção:** estrita {int(vazios['inv_estrita'].sum())} de "
         f"{len(vazios)} caixas vazias ({pct(int(vazios['inv_estrita'].sum()), len(vazios))}); "
         f"permissiva {int(vazios['inv_permissiva'].sum())} de {len(vazios)} "
         f"({pct(int(vazios['inv_permissiva'].sum()), len(vazios))}).")
dcls = definidos[definidos["classe_ok"]]
L.append(f"- **Cobertura com a classe certa:** "
         f"{pct(int(dcls['aceito'].sum()), len(dcls))} — é o número que mede a "
         f"leitura, porque exclui as caixas que se perderam só porque a classe "
         f"errou.")
L.append(f"- **Perdido** (gabarito define, pipeline não preencheu): "
         f"{int(definidos['perdido'].sum())} de {len(definidos)}, sendo "
         f"{int(definidos['perdido_classe_errada'].sum())} por classe errada "
         f"(o atributo nunca foi considerado), "
         f"{int(definidos['perdido_pendente'].sum())} como 'não informado no "
         f"texto' e {int(definidos['perdido_ambiguo'].sum())} como ambíguo.")
L.append(f"- **Concordância A×B:** acordo bruto "
         f"{conc['global']['acordo_bruto']:.1%}, kappa "
         f"{conc['global']['kappa']:.3f}; {conc['global']['divergencias']} "
         f"divergências, todas adjudicadas com motivo escrito.\n")
L.append("> **Ressalva de método, que vale para todos os números acima.** As duas "
         "passadas de anotação (A e B) são do mesmo anotador — um LLM — sob duas "
         "regras de decisão diferentes, e **não** de dois anotadores independentes. "
         "O kappa mede quanto a regra de anotação muda o rótulo, não concordância "
         "entre duas cabeças. Enquanto `revisao_humana_pedidos.csv` não voltar "
         "respondida por uma pessoa do time, este gabarito é **provisório**.\n")

L.append("## 1. Classe\n")
L.append(f"Acerto: **{pct(int(cls['ok'].sum()), len(cls))}** em {len(cls)} pedidos.\n")
L.append("**Por estilo de entrada — é o corte que explica o número inteiro:**\n")
L.append("| estilo de entrada | n | acertos | acerto [IC 95%] |")
L.append("|---|---:|---:|---|")
for v, g in sorted(cls.groupby("estilo"), key=lambda kv: -len(kv[1])):
    L.append(f"| {v} | {len(g)} | {int(g['ok'].sum())} | "
             f"{pct(int(g['ok'].sum()), len(g))} |")
_cat = cls[cls["estilo"] == "catalogo"]
if len(_cat) and _cat["ok"].mean() < 0.9:
    _outros = cls[cls["estilo"] != "catalogo"]
    L.append(f"\nOs três formatos em português somam "
             f"{pct(int(_outros['ok'].sum()), len(_outros))}. O catálogo do "
             f"fornecedor fica em {pct(int(_cat['ok'].sum()), len(_cat))}, e é de "
             f"onde vem **{int((~_cat['ok']).sum())} dos "
             f"{int((~cls['ok']).sum())}** erros de classe. A causa é a língua: "
             "essas linhas vêm em inglês (`Ball valve`, `Hex head bolt`, "
             "`Oil seal`, `Twist drill`), o pipeline não acha o substantivo do PDM "
             "e conclui FORA_DO_PDM. Os poucos acertos do canal confirmam a causa — "
             "são justamente os itens cujo termo inglês coincide com o vocabulário "
             "do PDM (`O-ring`) ou que trazem os atributos em português.\n")
L.append("\n**Por estrato de sorteio:**\n")
L.append("| estrato | n | acertos | acerto [IC 95%] |")
L.append("|---|---:|---:|---|")
for v, g in sorted(cls.groupby("estrato"), key=lambda kv: -len(kv[1])):
    L.append(f"| {v} | {len(g)} | {int(g['ok'].sum())} | "
             f"{pct(int(g['ok'].sum()), len(g))} |")
if conf:
    L.append("\n**Erros de classe** (gabarito → pipeline):\n")
    L.append("| gabarito | pipeline | n | são irmãs? |")
    L.append("|---|---|---:|---|")
    for (y, yp), n in conf.most_common():
        fam = next((nome for nome, cs in IRMAS if y in cs and yp in cs), "")
        L.append(f"| {y} | {yp} | {n} | {('sim: ' + fam) if fam else 'não'} |")
else:
    L.append("\nNenhum erro de classe.\n")

L.append("\n## 2. Caixas, por recorte\n")
L.append(bloco(cx, "campo", "Por atributo"))
L.append(bloco(cx, "familia", "Por família prevista"))
L.append(bloco(cx, "estilo", "Por estilo de entrada (é o recorte que o pedido "
                "tem e a base não)"))
L.append(bloco(cx, "fonte", "Por fonte do valor — qual camada erra"))

arm = []
for _, r in cx.iterrows():
    for x in (r["armadilhas"].split("|") if r["armadilhas"] else []):
        d = dict(r)
        d["arm"] = x
        arm.append(d)
if arm:
    L.append(bloco(pd.DataFrame(arm), "arm", "Por armadilha (um rótulo conta em "
                   "cada armadilha do seu pedido)"))

L.append("\n## 3. Cada erro de valor\n")
err = cx[cx["erro_de_valor"]]
if len(err):
    L.append(f"{len(err)} erro(s).\n")
    L.append("| pedido | classe | campo | gabarito | pipeline | fonte | evidência |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in err.iterrows():
        L.append(f"| {r['ID_PEDIDO']} | {r['id_pdm']} | {r['campo']} | "
                 f"`{r['y_gold']}` | `{r['pred']}` | {r['fonte']} | "
                 f"{r['evidencia'][:40]} |")
else:
    L.append("Nenhum erro de valor.\n")

L.append("\n## 4. Cada invenção\n")
inv = cx[cx["inv_estrita"]]
if len(inv):
    L.append(f"{len(inv)} preenchimento(s) sobre caixa que o gabarito diz vazia. "
             "A coluna `permissivo` diz quando a operação defenderia o valor.\n")
    L.append("| pedido | classe | campo | status gold | pipeline | permissivo | "
             "conta na permissiva? | fonte |")
    L.append("|---|---|---|---|---|---|---|---|")
    for _, r in inv.iterrows():
        L.append(f"| {r['ID_PEDIDO']} | {r['id_pdm']} | {r['campo']} | {r['status']} | "
                 f"`{r['pred']}` | `{r['permissivo'] or '—'}` | "
                 f"{'sim' if r['inv_permissiva'] else 'não'} | {r['fonte']} |")
else:
    L.append("Nenhuma invenção.\n")

L.append("\n## 5. Cada caixa perdida\n")
perd = cx[cx["perdido"]]
if len(perd):
    L.append(f"{len(perd)} caixa(s) que o gabarito define e o pipeline deixou "
             "vazia. Não é invenção — é leitura que faltou. Os três motivos são "
             "defeitos diferentes e pedem conserto diferente.\n")
    pc = perd[~perd["classe_ok"]]
    L.append(f"**(a) {len(pc)} por classe errada.** O pipeline deu outra classe ao "
             "pedido e por isso nunca considerou este atributo. Conserta-se na "
             "classificação, não na extração.\n")
    if len(pc):
        L.append("| pedido | classe gold | classe pipeline | caixas perdidas |")
        L.append("|---|---|---|---:|")
        for pid, g in sorted(pc.groupby("ID_PEDIDO"), key=lambda kv: -len(kv[1])):
            L.append(f"| {pid} | {g['id_pdm'].iloc[0]} | "
                     f"{pred_classe.get(pid, '—')} | {len(g)} |")
    pp = perd[perd["classe_ok"]]
    L.append(f"\n**(b) {len(pp)} com a classe certa** — aqui a leitura é que "
             "falhou. Agrupado por atributo:\n")
    if len(pp):
        L.append("| campo | classe | n | estado do pipeline |")
        L.append("|---|---|---:|---|")
        for (campo, idp, est), g in sorted(
                pp.groupby(["campo", "id_pdm", "estado_pred"]),
                key=lambda kv: -len(kv[1])):
            L.append(f"| {campo} | {idp} | {len(g)} | {est} |")
        L.append("\nLinha a linha:\n")
        L.append("| pedido | classe | campo | gabarito | estado | evidência no texto |")
        L.append("|---|---|---|---|---|---|")
        for _, r in pp.iterrows():
            L.append(f"| {r['ID_PEDIDO']} | {r['id_pdm']} | {r['campo']} | "
                     f"`{r['y_gold']}` | {r['estado_pred']} | "
                     f"{r['evidencia'][:50]} |")
else:
    L.append("Nenhuma caixa perdida.\n")

L.append("\n## 6. Limitações deste gabarito\n")
L.append(f"- **Só {len(vazios)} das {len(cx)} caixas do gabarito "
         f"({len(vazios) / len(cx):.1%}) são AUSENTE ou INDEFINIVEL**, contra os "
         "25% que o `PROMPT_gabarito_caracteristicas.md` pede. Não é falha do "
         "sorteio: os 520 pedidos chegam quase completos contra o PDM, ao "
         "contrário da base (onde 78,5% da referência do fabricante é vazia). "
         "Forçar um estrato de pedido incompleto encheria o denominador de um "
         "caso raro e daria uma taxa de invenção que não vale para a entrada "
         "real. A consequência é que o IC da invenção é largo — leia o intervalo, "
         "não a média.")
L.append("- **A conversão de pressão não é exercida.** Os pedidos com PSI são "
         "todos de mangueira montada (PDM011), classe em que `PRESSAO TRABALHO` "
         "não é obrigatória. Para medir conversão de unidade seria preciso "
         "sortear PDM010, 012, 013 ou 014, que não aparecem nestes 120.")
L.append("- **Três armadilhas da base não existem no pedido** e estão com zero "
         "casos nos 520: `polegada_in`, `abrev_ambigua` e `equivalencia`.")
L.append("- **BERT e LLM desligados** na execução medida: `artefatos/modelo_bert` "
         "está vazio e a camada de LLM custa dinheiro. Estes são números do piso "
         "(regras, gazetteer, gramática e dicionário aprendido).")
L.append(f"- **A anotação é de um LLM, em duas passadas não independentes.** "
         f"`revisao_humana_pedidos.csv` tem as linhas que uma pessoa precisa "
         f"conferir; até lá, provisório.\n")

Path(a.saida).write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"gravado {a.saida}")
print(f"  classe:   {pct(int(cls['ok'].sum()), len(cls))} em {len(cls)} pedidos")
print(f"  caixas:   precisao {pct(int(ga['acerto'].sum()), len(ga))} em {len(ga)} afirmados")
print(f"  cobertura {pct(int(definidos['aceito'].sum()), len(definidos))}")
print(f"  invencao  estrita {int(vazios['inv_estrita'].sum())}/{len(vazios)}, "
      f"permissiva {int(vazios['inv_permissiva'].sum())}/{len(vazios)}")
print(f"  perdidas  {int(definidos['perdido'].sum())}/{len(definidos)}")
print(f"  erros de valor: {len(err)}")
