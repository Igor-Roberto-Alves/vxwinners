#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avalia tabelas preenchidas por um modelo contra o conjunto-ouro do time.

Uso:
    python evaluate.py --paths caminho1.csv [caminho2.csv ...]
                       [--gold avaliacao/gold.csv] [--saida avaliacao_resultados.md]

Entrada esperada em cada --paths: a base de materiais COMPLETA preenchida pelo
modelo (CSV com CODIGO_MATERIAL e os campos GRUPO_MERCADORIA, NCM, FABRICANTE,
REFERENCIA_FABRICANTE — nomes de coluna são casados sem diferenciar maiúsculas).

Pontuação por rótulo-ouro:
    status DEFINIDO     acerto se valor == y_gold; vazio/PENDENTE conta como abstenção
    status AUSENTE      correto = deixar vazio; preencher qualquer coisa = INVENÇÃO
    status INDEFINIVEL  fora da conta (reportado à parte)

Saída: um .md com o resumo por campo (precisão com IC 95% de Wilson, cobertura,
taxa de invenção), o recorte por estrato e a lista anotada de cada erro/invenção.
"""
import argparse
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

CAMPOS = ["GRUPO_MERCADORIA", "NCM", "FABRICANTE", "REFERENCIA_FABRICANTE"]
VAZIOS = {"", "PENDENTE", "NA", "N/A", "NONE", "NULL", "-", "NAN", "AUSENTE", "?"}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def norm(campo, v):
    v = sem_acento(str(v or "")).upper().strip()
    if v in VAZIOS:
        return ""
    if campo == "NCM":
        d = re.sub(r"\D", "", v)
        return d if len(d) == 8 else ""
    if campo == "REFERENCIA_FABRICANTE":
        return re.sub(r"[^A-Z0-9]", "", v)
    return re.sub(r"\s+", " ", v)


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


def carrega_tabela(caminho):
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    mapa = {c.strip().upper(): c for c in df.columns}
    if "CODIGO_MATERIAL" not in mapa:
        raise SystemExit(f"{caminho}: coluna CODIGO_MATERIAL não encontrada "
                         f"(colunas: {list(df.columns)[:8]}...)")
    df["_cod"] = df[mapa["CODIGO_MATERIAL"]].astype(str).str.strip()
    dup = df["_cod"].duplicated().sum()
    df = df.drop_duplicates("_cod").set_index("_cod")
    cols = {c: mapa.get(c) for c in CAMPOS}
    return df, cols, dup


def avalia(gold, df, cols):
    """Devolve (linhas de rótulo com veredito, campos ausentes na tabela)."""
    sem_coluna = [c for c, col in cols.items() if col is None]
    regs = []
    for _, g in gold.iterrows():
        campo = g["campo"]
        if cols.get(campo) is None:
            continue
        cod = str(g["CODIGO_MATERIAL"]).strip()
        if cod not in df.index:
            veredito, valor = "ITEM_AUSENTE_NA_TABELA", ""
        else:
            valor = norm(campo, df.at[cod, cols[campo]])
            if g["status"] == "DEFINIDO":
                alvo = norm(campo, g["y_gold"])
                veredito = ("ACERTO" if valor == alvo else
                            "ABSTEVE" if valor == "" else "ERRO")
            elif g["status"] == "AUSENTE":
                veredito = "ABSTENCAO_CORRETA" if valor == "" else "INVENCAO"
            else:
                veredito = "INDEFINIVEL"
        regs.append({"CODIGO_MATERIAL": cod, "campo": campo,
                     "estrato": g["estrato"], "status": g["status"],
                     "y_gold": norm(campo, g["y_gold"]) if g["status"] == "DEFINIDO" else "",
                     "valor_modelo": valor, "veredito": veredito,
                     "evidencia": str(g.get("evidencia", ""))[:140],
                     "justificativa": str(g.get("justificativa", ""))[:110]})
    return pd.DataFrame(regs), sem_coluna


def tabela_md(df, colunas, titulos):
    linhas = ["| " + " | ".join(titulos) + " |",
              "|" + "|".join(["---"] * len(titulos)) + "|"]
    for _, r in df.iterrows():
        linhas.append("| " + " | ".join(str(r[c]) for c in colunas) + " |")
    return "\n".join(linhas)


def secao_arquivo(nome, res, sem_coluna, n_dup):
    md = [f"## {nome}\n"]
    if sem_coluna:
        md.append(f"> ⚠️ Campos sem coluna na tabela (não avaliados): {', '.join(sem_coluna)}\n")
    if n_dup:
        md.append(f"> ⚠️ {n_dup} CODIGO_MATERIAL duplicados na tabela (mantida a 1ª ocorrência)\n")
    falt = int((res["veredito"] == "ITEM_AUSENTE_NA_TABELA").sum())
    if falt:
        md.append(f"> ⚠️ {falt} itens do ouro não existem na tabela enviada\n")

    # resumo por campo
    lin = []
    for campo, sub in res.groupby("campo"):
        d = sub[sub["status"] == "DEFINIDO"]
        a = sub[sub["status"] == "AUSENTE"]
        ac = int((d["veredito"] == "ACERTO").sum())
        er = int((d["veredito"] == "ERRO").sum())
        ab = int((d["veredito"] == "ABSTEVE").sum())
        inv = int((a["veredito"] == "INVENCAO").sum())
        lin.append({"campo": campo, "rotulos": len(d), "acertos": ac, "erros": er,
                    "absteve": ab,
                    "precisao (IC95)": pct_ic(ac, ac + er),
                    "cobertura": f"{(ac+er)/len(d):.0%}" if len(d) else "—",
                    "ausentes": len(a), "invencoes": inv,
                    "taxa de invencao (IC95)": pct_ic(inv, len(a))})
    md.append("### Resumo por campo\n")
    md.append(tabela_md(pd.DataFrame(lin),
                        ["campo", "rotulos", "acertos", "erros", "absteve",
                         "precisao (IC95)", "cobertura", "ausentes", "invencoes",
                         "taxa de invencao (IC95)"],
                        ["Campo", "Rótulos (definidos)", "Acertos", "Erros", "Absteve",
                         "Precisão (IC 95%)", "Cobertura", "Ausentes no ouro",
                         "Invenções", "Taxa de invenção (IC 95%)"]))

    # por campo x estrato
    lin = []
    for (campo, estrato), sub in res.groupby(["campo", "estrato"]):
        d = sub[sub["status"] == "DEFINIDO"]
        a = sub[sub["status"] == "AUSENTE"]
        ac = int((d["veredito"] == "ACERTO").sum())
        er = int((d["veredito"] == "ERRO").sum())
        inv = int((a["veredito"] == "INVENCAO").sum())
        lin.append({"campo": campo, "estrato": estrato, "definidos": len(d),
                    "precisao": pct_ic(ac, ac + er),
                    "ausentes": len(a),
                    "invencao": pct_ic(inv, len(a)) if len(a) else "—"})
    md.append("\n### Por campo × estrato\n")
    md.append(tabela_md(pd.DataFrame(lin),
                        ["campo", "estrato", "definidos", "precisao", "ausentes", "invencao"],
                        ["Campo", "Estrato", "Definidos", "Precisão (IC 95%)",
                         "Ausentes", "Taxa de invenção"]))

    # anotações das linhas erradas
    erros = res[res["veredito"] == "ERRO"]
    md.append(f"\n### Linhas que erraram ({len(erros)})\n")
    if erros.empty:
        md.append("Nenhum erro nos rótulos definidos. \n")
    else:
        md.append(tabela_md(erros,
                            ["CODIGO_MATERIAL", "campo", "estrato", "y_gold",
                             "valor_modelo", "evidencia", "justificativa"],
                            ["Código", "Campo", "Estrato", "Esperado (ouro)",
                             "Veio do modelo", "Evidência do ouro", "Nota do anotador"]))

    inv = res[res["veredito"] == "INVENCAO"]
    md.append(f"\n### Invenções — preencheu onde o ouro diz AUSENTE ({len(inv)})\n")
    if inv.empty:
        md.append("Nenhuma invenção: o modelo se absteve corretamente nos ausentes. \n")
    else:
        md.append("O valor pode até ser plausível, mas a informação não existe no "
                  "registro — nenhum sistema (nem humano) pode verificá-la. "
                  "Preencher aqui é risco de dado inventado na base.\n")
        md.append(tabela_md(inv,
                            ["CODIGO_MATERIAL", "campo", "estrato", "valor_modelo",
                             "justificativa"],
                            ["Código", "Campo", "Estrato", "Veio do modelo",
                             "Por que é AUSENTE (anotador)"]))

    abst = res[res["veredito"] == "ABSTEVE"]
    if len(abst):
        md.append(f"\n### Abstenções em rótulos definidos ({len(abst)}) — "
                  "o ouro tem valor, o modelo deixou vazio\n")
        md.append(tabela_md(abst,
                            ["CODIGO_MATERIAL", "campo", "estrato", "y_gold", "evidencia"],
                            ["Código", "Campo", "Estrato", "Esperado (ouro)", "Evidência"]))
    return "\n".join(md)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paths", nargs="+", required=True,
                    help="CSV(s) da base preenchida pelo modelo")
    ap.add_argument("--gold", default=str(Path(__file__).parent / "avaliacao/gold.csv"))
    ap.add_argument("--saida", default="avaliacao_resultados.md")
    args = ap.parse_args()

    gold = pd.read_csv(args.gold, dtype=str, keep_default_na=False)
    md = [f"# Avaliação contra o conjunto-ouro",
          f"\nGerado em {datetime.now():%d/%m/%Y %H:%M} · ouro: `{args.gold}` "
          f"({len(gold)} rótulos, {gold['CODIGO_MATERIAL'].nunique()} itens, "
          f"estratos: {', '.join(sorted(gold['estrato'].unique()))})\n",
          "Regras: DEFINIDO exige o valor exato (normalizado); AUSENTE exige "
          "abstenção — preencher conta como **invenção**; INDEFINIVEL fica fora "
          "da conta. Intervalos de confiança de Wilson a 95%.\n"]

    for caminho in args.paths:
        df, cols, dup = carrega_tabela(caminho)
        res, sem_coluna = avalia(gold, df, cols)
        md.append(secao_arquivo(Path(caminho).name, res, sem_coluna, dup))
        d = res[res["status"] == "DEFINIDO"]
        ac = int((d["veredito"] == "ACERTO").sum())
        er = int((d["veredito"] == "ERRO").sum())
        a = res[res["status"] == "AUSENTE"]
        inv = int((a["veredito"] == "INVENCAO").sum())
        print(f"{Path(caminho).name}: precisão {pct_ic(ac, ac + er)} "
              f"({ac}/{ac+er} respondidos) · invenção {pct_ic(inv, len(a))} "
              f"({inv}/{len(a)} ausentes)")

    Path(args.saida).write_text("\n\n".join(md), encoding="utf-8")
    print(f"relatório: {args.saida}")


if __name__ == "__main__":
    main()
