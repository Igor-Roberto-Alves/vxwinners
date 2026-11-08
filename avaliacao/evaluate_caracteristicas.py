# -*- coding: utf-8 -*-
"""Avalia o pipeline contra o conjunto-ouro de caracteristicas, classe e juncao.

Uso:
  uv run --no-project --with pandas --with openpyxl python \
      avaliacao/evaluate_caracteristicas.py [--saida avaliacao/resultado_caracteristicas.md]

Entradas (o que o pipeline produziu):
  artefatos/decisoes_base.jsonl   uma linha por item, com uma decisao por atributo
                                  (atributo, valor, fonte, estado, confianca)
  artefatos/saneado_base.csv      ID_PDM (classe escolhida) e CHAVE_IDENTIDADE (juncao)

Gabarito:
  avaliacao/gold_caracteristicas.csv, gold_classe.csv, gold_juncao.csv
  avaliacao/candidatos_caracteristicas.csv  (familia prevista, estilo, armadilhas)
  avaliacao/pares_juncao_candidatos.csv     (fonte do par)

Veredito de cada rotulo de caracteristica:
  ACERTO             gold DEFINIDO e o pipeline preencheu o mesmo valor
  ERRO               gold DEFINIDO e o pipeline preencheu outro valor
  ABSTEVE            gold DEFINIDO e o pipeline deixou vazio (perda de cobertura)
  ABSTENCAO_CORRETA  gold AUSENTE/INDEFINIVEL e o pipeline deixou vazio
  INVENCAO           gold AUSENTE/INDEFINIVEL e o pipeline preencheu

Metricas por atributo, familia de classe, estilo de texto, armadilha e fonte:
  precisao = ACERTO / (ACERTO + ERRO)          IC 95% de Wilson
  cobertura = (ACERTO + ERRO) / rotulos DEFINIDO do gold
  invencao = INVENCAO / rotulos AUSENTE+INDEFINIVEL do gold

Comparacao de valores: grandezas sao comparadas numericamente (35,0MM = 35MM;
1 1/4POL = 1.1/4POL), pressao e convertida para BAR com tolerancia de 1%,
part number compara so [A-Z0-9] e valor de lista compara em maiuscula sem acento.
"""
import argparse
import csv
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent

VAZIOS = {"", "PENDENTE", "<PENDENTE>", "NA", "N/A", "NONE", "NULL", "-", "NAN",
          "AUSENTE", "?"}
CAMPOS_CODIGO = {"REFERENCIA", "REFERENCIA FABRICANTE", "MODELO EQUIPAMENTO"}
TOLERANCIA_PRESSAO = 0.01

FAMILIA_DA_CLASSE = {
    **{f"PDM{n:03d}": "fixadores" for n in (1, 2, 3, 4, 5, 6)},
    **{f"PDM{n:03d}": "mangueiras" for n in (10, 11, 12, 13, 14)},
    **{f"PDM{n:03d}": "rolamentos" for n in (20, 21, 22, 23)},
    **{f"PDM{n:03d}": "vedacao" for n in (31, 32, 33, 34)},
    **{f"PDM{n:03d}": "valvulas" for n in (40, 41, 42, 43, 44)},
    **{f"PDM{n:03d}": "conexoes" for n in (50, 51)},
    **{f"PDM{n:03d}": "eletricos" for n in (60, 61, 62, 63, 64, 65)},
    **{f"PDM{n:03d}": "outras" for n in (30, 66, 67, 70, 71, 72, 80, 81, 82, 90, 100)},
    "PDM110": "sobressalentes",
    "FORA_DO_PDM": "fora_pdm",
}

# classes irmas que se confundem: a matriz de confusao sai por grupo
GRUPOS_IRMAS = {
    "valvulas": ["PDM040", "PDM041", "PDM042", "PDM043", "PDM044"],
    "rolamentos": ["PDM020", "PDM021", "PDM022", "PDM023"],
    "parafusos": ["PDM001", "PDM002"],
    "arruelas": ["PDM004", "PDM005"],
    "mangueiras": ["PDM010", "PDM011", "PDM012", "PDM013", "PDM014"],
    "juntas": ["PDM033", "PDM034"],
    "conexoes_tubo": ["PDM050", "PDM051", "FORA_DO_PDM"],
}


# --------------------------------------------------------------- utilitarios --
def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def norm(campo, v):
    v = re.sub(r"\s+", " ", sem_acento(v or "").upper().strip())
    if v in VAZIOS:
        return ""
    if campo in CAMPOS_CODIGO:
        return re.sub(r"[^A-Z0-9]", "", v)
    return v


FATOR_BAR = {"BAR": 1.0, "PSI": 1 / 14.5038, "KGF/CM2": 0.980665,
             "KGFCM2": 0.980665, "KG/CM2": 0.980665, "MPA": 10.0, "KPA": 0.01}
UNIDADES = ("MM2", "MM", "POL", "BAR", "PSI", "KGF/CM2", "KGFCM2", "KG/CM2",
            "MPA", "KPA", "KA", "KV", "KW", "A", "V", "W", "M")


def parse_grandeza(v):
    """'35,0MM'->(35.0,'MM'); '1 1/4POL'->(1.25,'POL'); '145PSI'->(10.0,'BAR').

    Devolve None quando o valor nao e um numero com unidade (valor de lista,
    codigo, faixa como 13-18A, tensao como 0,6/1KV).
    """
    v = v.replace('"', "POL").replace(" IN", "POL").strip()
    m = re.fullmatch(r"(\d+)[.\s](\d+)\s*/\s*(\d+)\s*POL", v)        # 1.1/4POL
    if m:
        a, b, c = (float(x) for x in m.groups())
        return a + b / c, "POL"
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)\s*POL", v)                  # 3/4POL
    if m:
        a, b = (float(x) for x in m.groups())
        return a / b, "POL"
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(" + "|".join(
        re.escape(u) for u in UNIDADES) + r")", v)
    if m:
        num = float(m.group(1).replace(",", "."))
        unid = m.group(2)
        if unid in FATOR_BAR:
            return num * FATOR_BAR[unid], "BAR"
        return num, unid
    return None


def valor_igual(campo, gold, modelo):
    if gold == modelo:
        return True
    g, m = parse_grandeza(gold), parse_grandeza(modelo)
    if g and m and g[1] == m[1]:
        if g[1] == "BAR":
            return abs(g[0] - m[0]) <= TOLERANCIA_PRESSAO * max(abs(g[0]), abs(m[0]), 1e-9)
        return abs(g[0] - m[0]) < 1e-9
    return False


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centro - meia), min(1.0, centro + meia)


def pct_ic(k, n):
    if n == 0:
        return "—"
    p, lo, hi = wilson(k, n)
    return f"{p:.1%} [{lo:.0%}–{hi:.0%}]"


def pct(k, n):
    return "—" if n == 0 else f"{k / n:.1%}"


def le_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------ entradas --
def carrega_decisoes(codigos):
    """codigo -> {atributo: decisao} e codigo -> id_pdm das decisoes."""
    dec, pdm_dec = {}, {}
    with open(REPO / "artefatos/decisoes_base.jsonl", encoding="utf-8") as f:
        for linha in f:
            if not linha.strip():
                continue
            r = json.loads(linha)
            cod = str(r.get("codigo", "")).strip()
            if cod not in codigos:
                continue
            dec[cod] = {d["atributo"].strip(): d for d in r.get("decisoes", [])}
            pdm_dec[cod] = (r.get("id_pdm") or "").strip()
    return dec, pdm_dec


def carrega_saneado(codigos):
    san = {}
    with open(REPO / "artefatos/saneado_base.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["CODIGO_MATERIAL"].strip() in codigos:
                san[r["CODIGO_MATERIAL"].strip()] = r
    return san


# ------------------------------------------------------------------ metricas --
class Agregado:
    def __init__(self):
        self.c = Counter()
        self.itens = set()

    def soma(self, veredito, codigo):
        self.c[veredito] += 1
        self.itens.add(codigo)

    @property
    def definido(self):
        return self.c["ACERTO"] + self.c["ERRO"] + self.c["ABSTEVE"]

    @property
    def preenchido(self):
        return self.c["ACERTO"] + self.c["ERRO"]

    @property
    def nao_definido(self):
        return self.c["INVENCAO"] + self.c["ABSTENCAO_CORRETA"]

    def linha(self, nome):
        return [nome, str(len(self.itens)), str(self.definido + self.nao_definido),
                pct_ic(self.c["ACERTO"], self.preenchido),
                pct(self.preenchido, self.definido),
                str(self.c["ERRO"]), str(self.c["ABSTEVE"]),
                f"{self.c['INVENCAO']}/{self.nao_definido}"
                + (f" ({self.c['INVENCAO'] / self.nao_definido:.0%})"
                   if self.nao_definido else "")]


CAB = ["recorte", "itens", "rotulos", "precisao (IC 95%)", "cobertura", "erros",
       "absteve", "invencao"]


def tabela_md(cabecalho, linhas):
    out = ["| " + " | ".join(cabecalho) + " |",
           "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(l) + " |" for l in linhas]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(RAIZ / "resultado_caracteristicas.md"))
    args = ap.parse_args()

    gold = le_csv(RAIZ / "gold_caracteristicas.csv")
    gold_classe = le_csv(RAIZ / "gold_classe.csv")
    gold_juncao = le_csv(RAIZ / "gold_juncao.csv")
    cand = {r["CODIGO_MATERIAL"]: r for r in le_csv(RAIZ / "candidatos_caracteristicas.csv")}
    pares = {r["par_id"]: r for r in le_csv(RAIZ / "pares_juncao_candidatos.csv")}
    cego = {r["par_id"]: r for r in le_csv(RAIZ / "pares_juncao_cego.csv")}

    codigos = {r["CODIGO_MATERIAL"] for r in gold_classe}
    cods_pares = {p[c] for p in pares.values() for c in ("codigo_1", "codigo_2")}
    dec, pdm_dec = carrega_decisoes(codigos)
    san = carrega_saneado(codigos | cods_pares)

    classe_gold = {r["CODIGO_MATERIAL"]: r["y_gold"] for r in gold_classe}
    classe_pipe = {c: (san.get(c, {}).get("ID_PDM") or "").strip() or "FORA_DO_PDM"
                   for c in codigos}

    # --- rotulos de caracteristica -----------------------------------------
    regs = []
    for g in gold:
        cod, campo = g["CODIGO_MATERIAL"], g["campo"]
        d = dec.get(cod, {}).get(campo)
        valor = norm(campo, (d or {}).get("valor") or "")
        fonte = ((d or {}).get("fonte") or "").strip() or "(sem decisao)"
        if valor == "":
            fonte = "(vazio) " + fonte if d else "(sem decisao)"
        alvo = norm(campo, g["y_gold"])
        if g["status"] == "DEFINIDO":
            veredito = ("ABSTEVE" if valor == "" else
                        "ACERTO" if valor_igual(campo, alvo, valor) else "ERRO")
        else:
            veredito = "ABSTENCAO_CORRETA" if valor == "" else "INVENCAO"
        c = cand[cod]
        regs.append({"codigo": cod, "campo": campo, "status": g["status"],
                     "y_gold": alvo, "valor": valor, "veredito": veredito,
                     "fonte": fonte, "estado_dec": (d or {}).get("estado", ""),
                     "confianca": (d or {}).get("confianca", ""),
                     "familia": FAMILIA_DA_CLASSE.get(classe_gold[cod], "outras"),
                     "estilo": c["estilo"], "estrato": g["estrato"],
                     "armadilhas": [a for a in c["armadilhas"].split("|") if a],
                     "texto": c["DESCRICAO_LONGA"],
                     "evidencia": g["evidencia"], "justificativa": g["justificativa"],
                     "origem": g["origem_decisao"]})

    def agrega(chave_fn):
        ag = defaultdict(Agregado)
        for r in regs:
            k = chave_fn(r)
            for kk in (k if isinstance(k, list) else [k]):
                ag[kk].soma(r["veredito"], r["codigo"])
        return ag

    geral = Agregado()
    for r in regs:
        geral.soma(r["veredito"], r["codigo"])
    por_atributo = agrega(lambda r: r["campo"])
    por_familia = agrega(lambda r: r["familia"])
    por_estilo = agrega(lambda r: r["estilo"])
    por_armadilha = agrega(lambda r: r["armadilhas"] or ["(sem armadilha)"])
    por_fonte = agrega(lambda r: r["fonte"])
    por_status = Counter(r["veredito"] for r in regs)

    # atributos que o pipeline preencheu fora do universo do gold (classe errada)
    universo = {(r["CODIGO_MATERIAL"], r["campo"]) for r in gold}
    fora_escopo = []
    for cod in codigos:
        for atributo, d in dec.get(cod, {}).items():
            if (cod, atributo) in universo:
                continue
            if norm(atributo, d.get("valor") or ""):
                fora_escopo.append((cod, atributo, norm(atributo, d.get("valor")),
                                    d.get("fonte", ""), classe_gold[cod],
                                    classe_pipe[cod]))

    # --- classe -------------------------------------------------------------
    acertos_classe = sum(1 for c in codigos if classe_pipe[c] == classe_gold[c])
    erros_classe = [(c, classe_gold[c], classe_pipe[c], cand[c]["DESCRICAO_LONGA"],
                     san.get(c, {}).get("ESTADO", ""))
                    for c in sorted(codigos) if classe_pipe[c] != classe_gold[c]]
    confusao = {}
    for grupo, classes in GRUPOS_IRMAS.items():
        cods = [c for c in codigos if classe_gold[c] in classes]
        if not cods:
            continue
        m = Counter((classe_gold[c], classe_pipe[c]) for c in cods)
        linhas_m = sorted({g for g, _ in m})
        colunas_m = sorted({p for _, p in m})
        confusao[grupo] = (linhas_m, colunas_m, m, len(cods))

    # --- juncao -------------------------------------------------------------
    jun = []
    for g in gold_juncao:
        pid = g["CODIGO_MATERIAL"]
        c1, c2 = pares[pid]["codigo_1"], pares[pid]["codigo_2"]
        k1 = (san.get(c1, {}).get("CHAVE_IDENTIDADE") or "").strip()
        k2 = (san.get(c2, {}).get("CHAVE_IDENTIDADE") or "").strip()
        juntou = bool(k1) and k1 == k2
        jun.append({"par": pid, "gold": g["y_gold"], "juntou": juntou,
                    "fonte_par": pares[pid]["fonte_par"],
                    "codigo_1": c1, "codigo_2": c2,
                    "texto_1": cego[pid]["longa_1"], "texto_2": cego[pid]["longa_2"],
                    "chave_1": k1, "chave_2": k2,
                    "justificativa": g["justificativa"]})
    decidiveis = [j for j in jun if j["gold"] != "INDETERMINADO"]
    vp = sum(1 for j in decidiveis if j["juntou"] and j["gold"] == "MESMO_ITEM")
    fp = sum(1 for j in decidiveis if j["juntou"] and j["gold"] == "ITENS_DIFERENTES")
    fn = sum(1 for j in decidiveis if not j["juntou"] and j["gold"] == "MESMO_ITEM")
    vn = sum(1 for j in decidiveis if not j["juntou"] and j["gold"] == "ITENS_DIFERENTES")
    indet_juntou = sum(1 for j in jun if j["gold"] == "INDETERMINADO" and j["juntou"])

    # --- markdown -----------------------------------------------------------
    L = []
    L.append("# Avaliação do pipeline contra o conjunto-ouro de características\n")
    L.append(f"Gabarito: `gold_caracteristicas.csv` ({len(gold)} rótulos de atributo), "
             f"`gold_classe.csv` ({len(gold_classe)} itens), "
             f"`gold_juncao.csv` ({len(gold_juncao)} pares).  ")
    L.append("Pipeline: `artefatos/decisoes_base.jsonl` + `artefatos/saneado_base.csv`.\n")
    L.append("Precisão = acertos / (acertos + erros) com IC 95% de Wilson. "
             "Cobertura = preenchidos / rótulos DEFINIDO do gold. "
             "Invenção = preencheu onde o gold diz AUSENTE ou INDEFINÍVEL.\n")

    L.append("## 1. Resumo\n")
    L.append(tabela_md(CAB, [geral.linha("geral")]))
    L.append("\nVereditos: " + ", ".join(f"{k}={v}" for k, v in sorted(por_status.items())))
    L.append(f"\nAtributos preenchidos fora do universo do gold (classe divergente): "
             f"{len(fora_escopo)}\n")

    for titulo, ag, ordem in (
            ("2. Por atributo", por_atributo, lambda kv: -kv[1].definido - kv[1].nao_definido),
            ("3. Por família de classe", por_familia, lambda kv: kv[0]),
            ("4. Por estilo de texto", por_estilo, lambda kv: kv[0]),
            ("5. Por armadilha", por_armadilha, lambda kv: kv[0]),
            ("6. Por fonte do valor", por_fonte, lambda kv: kv[0])):
        L.append(f"## {titulo}\n")
        L.append(tabela_md(CAB, [a.linha(k) for k, a in sorted(ag.items(), key=ordem)]))
        L.append("")

    L.append("## 7. Classe do item\n")
    L.append(f"Acerto de classe: **{acertos_classe}/{len(codigos)}** "
             f"({pct_ic(acertos_classe, len(codigos))}).\n")
    for grupo, (linhas_m, colunas_m, m, n) in sorted(confusao.items()):
        L.append(f"### Matriz de confusão — {grupo} ({n} itens do gold)\n")
        L.append(tabela_md(["gold \\ pipeline"] + colunas_m,
                           [[g] + [str(m.get((g, p), 0)) for p in colunas_m]
                            for g in linhas_m]))
        L.append("")
    if erros_classe:
        L.append("### Erros de classe\n")
        L.append(tabela_md(["código", "gold", "pipeline", "estado", "texto cru"],
                           [[c, g, p, e, t[:90]] for c, g, p, t, e in erros_classe]))
        L.append("")

    L.append("## 8. Junção de duplicados\n")
    L.append(f"Pares decidíveis: {len(decidiveis)} (MESMO_ITEM={vp + fn}, "
             f"ITENS_DIFERENTES={fp + vn}); INDETERMINADO no gold: "
             f"{len(jun) - len(decidiveis)} (o pipeline juntou {indet_juntou} deles).\n")
    L.append(tabela_md(["métrica", "valor"], [
        ["precisão", pct_ic(vp, vp + fp) + f"  ({vp}/{vp + fp})"],
        ["recall", pct_ic(vp, vp + fn) + f"  ({vp}/{vp + fn})"],
        ["verdadeiros positivos", str(vp)], ["falsos positivos", str(fp)],
        ["falsos negativos", str(fn)], ["verdadeiros negativos", str(vn)]]))
    L.append("")
    L.append("### Por fonte do par\n")
    linhas_fp = []
    for fonte in sorted({j["fonte_par"] for j in jun}):
        sub = [j for j in jun if j["fonte_par"] == fonte]
        subd = [j for j in sub if j["gold"] != "INDETERMINADO"]
        a = sum(1 for j in subd if j["juntou"] == (j["gold"] == "MESMO_ITEM"))
        linhas_fp.append([fonte, str(len(sub)), str(len(subd)), pct_ic(a, len(subd)),
                          str(sum(1 for j in subd if j["juntou"] and j["gold"] == "ITENS_DIFERENTES")),
                          str(sum(1 for j in subd if not j["juntou"] and j["gold"] == "MESMO_ITEM"))])
    L.append(tabela_md(["fonte do par", "pares", "decidíveis", "acerto (IC 95%)",
                        "juntou errado", "deixou passar"], linhas_fp))
    L.append("")
    erros_jun = [j for j in decidiveis if j["juntou"] != (j["gold"] == "MESMO_ITEM")]
    if erros_jun:
        L.append("### Pares errados\n")
        for j in erros_jun:
            L.append(f"- **{j['par']}** ({j['fonte_par']}): gold `{j['gold']}`, "
                     f"pipeline {'juntou' if j['juntou'] else 'separou'}  \n"
                     f"  `{j['codigo_1']}`: {j['texto_1'][:150]}  \n"
                     f"  `{j['codigo_2']}`: {j['texto_2'][:150]}  \n"
                     f"  gold: {j['justificativa']}")
        L.append("")

    L.append("## 9. Cada erro de característica\n")
    erros = [r for r in regs if r["veredito"] == "ERRO"]
    if erros:
        for r in sorted(erros, key=lambda r: (r["campo"], r["codigo"])):
            L.append(f"- **{r['codigo']} {r['campo']}**: gold `{r['y_gold']}`, "
                     f"pipeline `{r['valor']}` (fonte {r['fonte']}, "
                     f"confiança {r['confianca']})  \n"
                     f"  texto: {r['texto'][:150]}  \n"
                     f"  gold: {r['evidencia']} | {r['justificativa']}")
    else:
        L.append("Nenhum erro de valor.")
    L.append("")

    L.append("## 10. Cada invenção\n")
    inv = [r for r in regs if r["veredito"] == "INVENCAO"]
    if inv:
        for r in sorted(inv, key=lambda r: (r["campo"], r["codigo"])):
            L.append(f"- **{r['codigo']} {r['campo']}** (gold {r['status']}): "
                     f"pipeline `{r['valor']}` (fonte {r['fonte']}, "
                     f"confiança {r['confianca']})  \n"
                     f"  texto: {r['texto'][:150]}  \n"
                     f"  gold: {r['justificativa']}")
    else:
        L.append("Nenhuma invenção.")
    L.append("")

    if fora_escopo:
        L.append("## 11. Atributos preenchidos fora do universo do gold\n")
        L.append("Atributo que o pipeline preencheu porque escolheu outra classe; "
                 "não entra na precisão, mas é consequência do erro de classe.\n")
        L.append(tabela_md(["código", "atributo", "valor", "fonte", "classe gold",
                            "classe pipeline"],
                           [[c, a, v, f, cg, cp] for c, a, v, f, cg, cp
                            in sorted(fora_escopo)[:60]]))
        if len(fora_escopo) > 60:
            L.append(f"\n(+{len(fora_escopo) - 60} linhas)")
        L.append("")

    Path(args.saida).write_text("\n".join(L) + "\n", encoding="utf-8")

    # --- console ------------------------------------------------------------
    print("=== caracteristicas ===")
    print("  " + " | ".join(CAB))
    print("  " + " | ".join(geral.linha("geral")))
    print(f"=== classe === acerto {acertos_classe}/{len(codigos)} "
          f"({acertos_classe / len(codigos):.1%})")
    print(f"=== juncao === precisao {pct(vp, vp + fp)} ({vp}/{vp + fp})  "
          f"recall {pct(vp, vp + fn)} ({vp}/{vp + fn})")
    print(f"\n{args.saida} gravado ({len(regs)} rotulos avaliados, "
          f"{len(erros)} erros, {len(inv)} invencoes)")


if __name__ == "__main__":
    main()
