#!/usr/bin/env python3
"""Verificacao independente das metricas do benchmark de preenchimento.

Recalcula do zero, para cada pred/*.csv, as metricas contra o gabarito dos
splits de teste (match por CODIGO_MATERIAL) e compara com benchmark.csv.
As normalizacoes sao reimplementadas aqui de proposito (NAO importa contrato.py).

Nao altera nenhum arquivo existente; grava apenas metricas/verificacao_metricas.json
e imprime no stdout o veredito final em JSON.
"""

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score

BASE = Path(__file__).resolve().parent
SPLITS = BASE / "dados" / "splits"
PRED = BASE / "pred"
METRICAS = BASE / "metricas"
BENCHMARK = BASE / "benchmark.csv"

N_TESTE_ESPERADO_TAREFA = {
    "GRUPO_MERCADORIA": 2000,
    "NCM": 2000,
    "FABRICANTE": 2000,
    "REFERENCIA_FABRICANTE": 1500,
}
CAMPOS_COM_F1 = {"GRUPO_MERCADORIA", "NCM", "FABRICANTE"}
TOL = 0.002  # tolerancia de comparacao com benchmark.csv


# ---------------------------------------------------------------- normalizacao
def _sem_acento(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def norm_texto(s: str) -> str:
    """Campos texto (GRUPO_MERCADORIA, FABRICANTE): maiusculas sem acento,
    espacos colapsados."""
    s = _sem_acento(str(s)).upper()
    return re.sub(r"\s+", " ", s).strip()


def norm_ncm(s: str) -> str:
    """NCM: so digitos; valido somente com exatamente 8 digitos (senao vazio)."""
    d = re.sub(r"\D", "", str(s))
    return d if len(d) == 8 else ""


def norm_ref(s: str) -> str:
    """REFERENCIA_FABRICANTE: maiusculas, so [A-Z0-9]."""
    s = _sem_acento(str(s)).upper()
    return re.sub(r"[^A-Z0-9]", "", s)


def norm(campo: str, s) -> str:
    if s is None:
        return ""
    if campo == "NCM":
        return norm_ncm(s)
    if campo == "REFERENCIA_FABRICANTE":
        return norm_ref(s)
    return norm_texto(s)


# ------------------------------------------------------------------- utilidades
def ler_csv(path: Path) -> pd.DataFrame:
    # dtype=str preserva zeros a esquerda; keep_default_na=False preserva "" e
    # evita que literais como "NA"/"NAN" virem NaN.
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def r6(x):
    return None if x is None else round(float(x), 6)


# ------------------------------------------------------------------------ main
def main() -> None:
    anomalias: list[dict] = []
    resultado: dict = {}

    # ---- gabaritos a partir dos splits de teste
    gabaritos: dict[str, dict[str, str]] = {}
    n_teste: dict[str, int] = {}
    for campo, n_esp in N_TESTE_ESPERADO_TAREFA.items():
        path = SPLITS / f"{campo}__teste.csv"
        df = ler_csv(path)
        n_teste[campo] = len(df)
        if len(df) != n_esp:
            anomalias.append({
                "tipo": "split_tamanho_inesperado", "campo": campo,
                "linhas_split": len(df), "esperado_tarefa": n_esp,
            })
        if "CODIGO_MATERIAL" not in df.columns or "y" not in df.columns:
            anomalias.append({"tipo": "split_sem_colunas", "campo": campo,
                              "colunas": list(df.columns)})
            continue
        cods = df["CODIGO_MATERIAL"].str.strip()
        dup = int(cods.duplicated().sum())
        if dup:
            anomalias.append({"tipo": "split_codigos_duplicados", "campo": campo,
                              "n_duplicados": dup})
        gab = {}
        y_vazio = 0
        y_nao_normalizado = 0
        for cod, y in zip(cods, df["y"]):
            if cod in gab:
                continue  # mantem primeira ocorrencia
            yn = norm(campo, y)
            if yn == "":
                y_vazio += 1
            if yn != str(y):
                y_nao_normalizado += 1
            gab[cod] = yn
        if y_vazio:
            anomalias.append({"tipo": "split_gabarito_vazio_apos_normalizacao",
                              "campo": campo, "n": y_vazio})
        if y_nao_normalizado:
            anomalias.append({
                "tipo": "split_y_difere_da_normalizacao_reimplementada",
                "campo": campo, "n": y_nao_normalizado,
            })
        gabaritos[campo] = gab

    # ---- verifica cada pred/*.csv
    arquivos = sorted(PRED.glob("*.csv"))
    if len(arquivos) != 32:
        anomalias.append({"tipo": "numero_de_arquivos_pred_inesperado",
                          "encontrados": len(arquivos), "esperado": 32})

    for path in arquivos:
        nome = path.name
        stem = path.stem
        if "__" not in stem:
            anomalias.append({"tipo": "nome_arquivo_invalido", "arquivo": nome})
            continue
        solucao, campo = stem.rsplit("__", 1)
        if campo not in gabaritos:
            anomalias.append({"tipo": "campo_desconhecido", "arquivo": nome,
                              "campo": campo})
            continue
        gab = gabaritos[campo]
        n_total = n_teste[campo]

        df = ler_csv(path)
        n_pred = len(df)
        esperadas = {"CODIGO_MATERIAL", "y_true", "y_pred", "conf", "top3"}
        if not esperadas.issubset(df.columns):
            anomalias.append({"tipo": "pred_sem_colunas_esperadas", "arquivo": nome,
                              "colunas": list(df.columns)})
            continue

        cods = df["CODIGO_MATERIAL"].str.strip()
        n_dup = int(cods.duplicated().sum())
        pred_map: dict[str, dict] = {}
        n_fora_do_split = 0
        diverg_y_true_raw = 0
        diverg_y_true_norm = 0
        top3_mais_de_3 = 0
        for cod, y_true, y_pred, top3 in zip(
            cods, df["y_true"], df["y_pred"], df["top3"]
        ):
            if cod not in gab:
                n_fora_do_split += 1
                continue
            if cod in pred_map:
                continue  # duplicado: mantem primeira ocorrencia
            # divergencias y_true(pred) vs y(split) -- gabarito NUNCA vem do pred
            if str(y_true) != gab[cod]:
                diverg_y_true_raw += 1
                if norm(campo, y_true) != gab[cod]:
                    diverg_y_true_norm += 1
            itens = [t for t in str(top3).split("|")]
            if len([t for t in itens if t.strip() != ""]) > 3:
                top3_mais_de_3 += 1
            top3_norm = {norm(campo, t) for t in itens[:3]}
            top3_norm.discard("")
            pred_map[cod] = {
                "y_pred_raw": str(y_pred),
                "y_pred": norm(campo, y_pred),
                "top3": top3_norm,
            }

        n_faltantes = n_total - len(pred_map)

        cobertos = 0            # y_pred valido/nao vazio apos normalizacao
        cobertos_raw = 0        # y_pred bruto nao vazio (definicao alternativa)
        top1_hits = 0
        top3_hits = 0
        f1_gold: list[str] = []
        f1_pred: list[str] = []
        for cod, gold in gab.items():
            p = pred_map.get(cod)
            if p is None:
                continue  # abstencao total: nao coberto, erro no top1/top3
            if p["y_pred_raw"].strip() != "":
                cobertos_raw += 1
            if p["y_pred"] != "":
                cobertos += 1
                f1_gold.append(gold)
                f1_pred.append(p["y_pred"])
                if gold != "" and p["y_pred"] == gold:
                    top1_hits += 1
            if gold != "" and gold in p["top3"]:
                top3_hits += 1

        cobertura = cobertos / n_total if n_total else 0.0
        cobertura_raw = cobertos_raw / n_total if n_total else 0.0
        top1 = top1_hits / n_total if n_total else 0.0
        top1_cobertos = top1_hits / cobertos if cobertos else 0.0
        top3 = top3_hits / n_total if n_total else 0.0
        f1_macro = None
        f1_macro_labels_gab = None
        if campo in CAMPOS_COM_F1 and f1_gold:
            # principal: default sklearn (labels = uniao gold U pred; classes
            # "inventadas" pela predicao entram na media com f1=0)
            f1_macro = float(
                f1_score(f1_gold, f1_pred, average="macro", zero_division=0)
            )
            # variante de reconciliacao: labels restritas as classes do
            # gabarito presentes nas linhas cobertas
            f1_macro_labels_gab = float(
                f1_score(f1_gold, f1_pred, average="macro",
                         labels=sorted(set(f1_gold)), zero_division=0)
            )

        # sentinela "NA" e afins: string literal no CSV que o pandas (leitura
        # padrao, sem keep_default_na=False) converte em NaN -> abstencao
        sentinelas = {"NA", "N/A", "NAN", "NULL", "NONE"}
        n_sentinela = int(
            df["y_pred"].str.strip().str.upper().isin(sentinelas).sum()
        )

        resultado[nome] = {
            "solucao": solucao,
            "campo": campo,
            "n_teste_esperado": n_total,
            "n_pred": n_pred,
            "n_cobertos": cobertos,
            "cobertura": r6(cobertura),
            "cobertura_y_pred_bruto_nao_vazio": r6(cobertura_raw),
            "top1": r6(top1),
            "top1_cobertos": r6(top1_cobertos),
            "top3": r6(top3),
            "f1_macro": r6(f1_macro) if f1_macro is not None else None,
            "f1_macro_labels_gabarito": (
                r6(f1_macro_labels_gab) if f1_macro_labels_gab is not None else None
            ),
            "y_pred_sentinela_na": n_sentinela,
            "divergencias_y_true_vs_split_norm": diverg_y_true_norm,
            "divergencias_y_true_vs_split_raw": diverg_y_true_raw,
            "codigos_pred_fora_do_split": n_fora_do_split,
            "codigos_do_split_sem_pred": n_faltantes,
            "codigos_duplicados_no_pred": n_dup,
        }

        if n_pred != n_total:
            anomalias.append({"tipo": "n_pred_diferente_do_teste", "arquivo": nome,
                              "n_pred": n_pred, "n_teste_esperado": n_total})
        if n_fora_do_split:
            anomalias.append({"tipo": "codigos_pred_fora_do_split", "arquivo": nome,
                              "n": n_fora_do_split})
        if n_faltantes:
            anomalias.append({"tipo": "codigos_do_split_sem_pred", "arquivo": nome,
                              "n": n_faltantes})
        if n_dup:
            anomalias.append({"tipo": "codigos_duplicados_no_pred", "arquivo": nome,
                              "n": n_dup})
        if diverg_y_true_norm:
            anomalias.append({"tipo": "y_true_do_pred_diverge_do_split",
                              "arquivo": nome, "n": diverg_y_true_norm})
        if top3_mais_de_3:
            anomalias.append({"tipo": "top3_com_mais_de_3_itens", "arquivo": nome,
                              "n": top3_mais_de_3})
        if n_sentinela:
            anomalias.append({
                "tipo": "y_pred_sentinela_na", "arquivo": nome, "n": n_sentinela,
                "detalhe": ("y_pred com string literal 'NA'/'N/A' etc.; leitura "
                            "pandas padrao converte em NaN (abstencao), leitura "
                            "literal conta como predicao coberta"),
            })

    # ---- comparacao com benchmark.csv
    divergencias_benchmark: list[dict] = []
    if not BENCHMARK.exists():
        anomalias.append({"tipo": "benchmark_csv_ausente", "arquivo": "benchmark.csv"})
    else:
        bench = pd.read_csv(BENCHMARK)
        bench_map = {
            (str(r["solucao"]), str(r["campo"])): r for _, r in bench.iterrows()
        }
        vistos = set()
        for nome, m in resultado.items():
            chave = (m["solucao"], m["campo"])
            row = bench_map.get(chave)
            if row is None:
                anomalias.append({"tipo": "sem_linha_no_benchmark", "arquivo": nome})
                continue
            vistos.add(chave)
            for metrica in ("cobertura", "top1", "top3"):
                v_ver = m[metrica]
                v_ben = float(row[metrica])
                if abs(v_ver - v_ben) > TOL + 1e-9:
                    divergencias_benchmark.append({
                        "arquivo": nome, "metrica": metrica,
                        "verificado": v_ver, "benchmark": round(v_ben, 6),
                        "diff": round(abs(v_ver - v_ben), 6),
                    })
            # conferencias extras (informativas, mesmo limiar)
            v_ben = row["top1_cobertos"]
            if pd.notna(v_ben) and abs(m["top1_cobertos"] - float(v_ben)) > TOL + 1e-9:
                anomalias.append({
                    "tipo": "divergencia_benchmark_extra", "arquivo": nome,
                    "metrica": "top1_cobertos", "verificado": m["top1_cobertos"],
                    "benchmark": round(float(v_ben), 6),
                })
            v_ben = row["f1_macro"]
            if m["f1_macro"] is not None and pd.notna(v_ben):
                v_ben = float(v_ben)
                if abs(m["f1_macro"] - v_ben) > TOL + 1e-9:
                    if abs(m["f1_macro_labels_gabarito"] - v_ben) <= TOL + 1e-9:
                        anomalias.append({
                            "tipo": "f1_macro_definicao_divergente_reconciliada",
                            "arquivo": nome,
                            "verificado_uniao_labels": m["f1_macro"],
                            "verificado_labels_gabarito":
                                m["f1_macro_labels_gabarito"],
                            "benchmark": round(v_ben, 6),
                            "detalhe": ("benchmark usa labels so do gabarito dos "
                                        "cobertos; verificador usa uniao "
                                        "gold U pred (classes inventadas pesam 0)"),
                        })
                    else:
                        anomalias.append({
                            "tipo": "divergencia_benchmark_extra", "arquivo": nome,
                            "metrica": "f1_macro", "verificado": m["f1_macro"],
                            "benchmark": round(v_ben, 6),
                        })
            if int(row["n_teste"]) != m["n_teste_esperado"]:
                anomalias.append({
                    "tipo": "n_teste_benchmark_diferente", "arquivo": nome,
                    "benchmark": int(row["n_teste"]),
                    "verificado": m["n_teste_esperado"],
                })
            if int(row["n_pred"]) != m["n_pred"]:
                anomalias.append({
                    "tipo": "n_pred_benchmark_diferente", "arquivo": nome,
                    "benchmark": int(row["n_pred"]), "verificado": m["n_pred"],
                })
        for chave in bench_map:
            if chave not in vistos:
                anomalias.append({"tipo": "linha_benchmark_sem_pred",
                                  "solucao": chave[0], "campo": chave[1]})

    # divergencias vs benchmark tambem sao anomalias
    for d in divergencias_benchmark:
        anomalias.append({"tipo": "divergencia_benchmark", **d})

    saida = dict(resultado)
    saida["_anomalias"] = anomalias
    out_path = METRICAS / "verificacao_metricas.json"
    out_path.write_text(
        json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    anomalias_sem_diverg = [a for a in anomalias
                            if a["tipo"] != "divergencia_benchmark"]
    aprovado = not divergencias_benchmark and not any(
        a["tipo"] in {
            "n_pred_diferente_do_teste", "codigos_pred_fora_do_split",
            "codigos_do_split_sem_pred", "codigos_duplicados_no_pred",
            "y_true_do_pred_diverge_do_split", "split_tamanho_inesperado",
            "split_codigos_duplicados", "split_gabarito_vazio_apos_normalizacao",
            "split_y_difere_da_normalizacao_reimplementada",
            "numero_de_arquivos_pred_inesperado", "sem_linha_no_benchmark",
            "linha_benchmark_sem_pred", "n_teste_benchmark_diferente",
            "n_pred_benchmark_diferente", "divergencia_benchmark_extra",
            "benchmark_csv_ausente", "pred_sem_colunas_esperadas",
            "split_sem_colunas", "campo_desconhecido", "nome_arquivo_invalido",
            "top3_com_mais_de_3_itens",
        } for a in anomalias_sem_diverg
    )

    veredito = {
        "aprovado": aprovado,
        "arquivos_verificados": len(resultado),
        "divergencias_benchmark": divergencias_benchmark,
        "anomalias": anomalias_sem_diverg,
        "saida": str(out_path),
    }
    print(json.dumps(veredito, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
