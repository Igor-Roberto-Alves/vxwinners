# -*- coding: utf-8 -*-
"""Avalia saidas do pipeline contra o conjunto-ouro (avaliacao/gold.csv).

Regras de pontuacao por rotulo-ouro:
  status DEFINIDO    acerto se y_pred == y_gold; abstencao conta como 'absteve'
  status AUSENTE     comportamento correto = abster; prever algo = INVENCAO (o erro capital)
  status INDEFINIVEL fora da acuracia (reportado a parte)

Metricas por (campo, estrato) e por campo: precisao nos definidos (com IC 95% de
Wilson), cobertura, taxa de invencao nos ausentes (com IC), n.

Uso:
  python3 10_avaliar.py --preds caminho.csv        # csv generico: CODIGO_MATERIAL,campo,y_pred
  python3 10_avaliar.py --auto                     # procura preenchimento/{pred,saida} (branch main)
"""
import argparse
import math
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c))


def norm(campo, v):
    v = sem_acento(str(v or "")).upper().strip()
    if v in ("PENDENTE", "NAN", "NONE", "NULL", "N/A", "NA", "-"):
        return ""
    if campo == "NCM":
        d = re.sub(r"\D", "", v)
        return d if len(d) == 8 else ""
    if campo == "REFERENCIA_FABRICANTE":
        return re.sub(r"[^A-Z0-9]", "", v)
    return re.sub(r"\s+", " ", v)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, max(0.0, centro - meia), min(1.0, centro + meia))


def carrega_preds(args):
    """Devolve dict nome_sistema -> DataFrame(CODIGO_MATERIAL, campo, y_pred)."""
    sistemas = {}
    if args.preds:
        df = pd.read_csv(args.preds, dtype=str, keep_default_na=False)
        sistemas[Path(args.preds).stem] = df
    if args.auto:
        pdir = REPO / "preenchimento/pred"
        for arq in sorted(pdir.glob("*.csv")) if pdir.exists() else []:
            sol, campo = arq.stem.split("__", 1)
            df = pd.read_csv(arq, dtype=str, keep_default_na=False)
            df["campo"] = campo
            sistemas.setdefault(sol, []).append(df[["CODIGO_MATERIAL", "campo", "y_pred"]])
        sdir = REPO / "preenchimento/saida"
        fills = []
        for arq in sorted(sdir.glob("preenchido_*.csv")) if sdir.exists() else []:
            campo = arq.stem.replace("preenchido_", "")
            df = pd.read_csv(arq, dtype=str, keep_default_na=False)
            df["campo"] = campo
            fills.append(df[["CODIGO_MATERIAL", "campo", "y_pred"]])
        if fills:
            sistemas["PREENCHEDOR_FINAL"] = fills
        sistemas = {k: (pd.concat(v, ignore_index=True) if isinstance(v, list) else v)
                    for k, v in sistemas.items()}
    return sistemas


def avalia(gold, preds, nome):
    g = gold.copy()
    p = preds.copy()
    p["chave"] = p["CODIGO_MATERIAL"].astype(str) + "|" + p["campo"]
    g["chave"] = g["CODIGO_MATERIAL"].astype(str) + "|" + g["campo"]
    p = p.drop_duplicates("chave").set_index("chave")
    g["y_pred_raw"] = g["chave"].map(p["y_pred"])
    g = g[g["y_pred_raw"].notna()].copy()  # so onde o sistema opinou sobre o item
    if g.empty:
        return None
    g["p"] = [norm(c, v) for c, v in zip(g["campo"], g["y_pred_raw"])]
    g["gnorm"] = [norm(c, v) for c, v in zip(g["campo"], g["y_gold"])]

    linhas = []
    for (campo, estrato), sub in g.groupby(["campo", "estrato"]):
        defin = sub[sub["status"] == "DEFINIDO"]
        aus = sub[sub["status"] == "AUSENTE"]
        resp = defin[defin["p"] != ""]
        ac = int((resp["p"] == resp["gnorm"]).sum())
        inv = int((aus["p"] != "").sum())
        prec, plo, phi = wilson(ac, len(resp))
        tinv, ilo, ihi = wilson(inv, len(aus))
        linhas.append({
            "sistema": nome, "campo": campo, "estrato": estrato,
            "n_definidos": len(defin), "cobertura": round(len(resp) / len(defin), 3) if len(defin) else "",
            "precisao": round(prec, 3) if len(resp) else "",
            "ic95": f"[{plo:.2f};{phi:.2f}]" if len(resp) else "",
            "n_ausentes": len(aus),
            "taxa_invencao": round(tinv, 3) if len(aus) else "",
            "ic95_inv": f"[{ilo:.2f};{ihi:.2f}]" if len(aus) else "",
            "indefiniveis_excluidos": int((sub["status"] == "INDEFINIVEL").sum()),
        })
    return pd.DataFrame(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--gold", default=str(RAIZ / "gold.csv"))
    args = ap.parse_args()
    gold = pd.read_csv(args.gold, dtype=str, keep_default_na=False)
    sistemas = carrega_preds(args)
    if not sistemas:
        sys.exit("nenhuma predicao encontrada (use --preds ou --auto na branch com preenchimento/)")
    tudo = []
    for nome, preds in sistemas.items():
        r = avalia(gold, preds, nome)
        if r is not None:
            tudo.append(r)
    res = pd.concat(tudo, ignore_index=True)
    res.to_csv(RAIZ / "resultado_avaliacao.csv", index=False)
    pd.set_option("display.width", 250)
    for nome in res["sistema"].unique():
        print(f"\n===== {nome} =====")
        print(res[res["sistema"] == nome].drop(columns="sistema").to_string(index=False))
    print(f"\nresultado_avaliacao.csv gravado ({len(res)} linhas)")


if __name__ == "__main__":
    main()
