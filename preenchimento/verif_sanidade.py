"""Verificacao de sanidade do benchmark de preenchimento (auditoria, somente leitura).

Checa, sem alterar nenhum arquivo existente:
1. Splits por campo: treino e teste sem CODIGO_MATERIAL duplicado e com
   intersecao treino x teste vazia.
2. Cada pred/{solucao}__{campo}.csv:
   - ids contidos nos ids do teste do campo (nenhum id fora do teste);
   - cobertura >= 95% dos ids do teste;
   - sem ids duplicados;
   - y_true identico ao y do split de teste em TODAS as linhas;
   - conf numerica e dentro de [0,1] quando preenchida (vazia = sem conf).
3. pred/ sem arquivos de solucoes inesperadas (contaminariam o benchmark).

Grava o relatorio em metricas/verificacao_sanidade.json e sai com codigo 1
se houver qualquer violacao.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
SPLITS = RAIZ / "dados" / "splits"
PRED = RAIZ / "pred"
ARQ_SAIDA = RAIZ / "metricas" / "verificacao_sanidade.json"

CAMPOS = ["GRUPO_MERCADORIA", "NCM", "FABRICANTE", "REFERENCIA_FABRICANTE"]
SOLUCOES = ["prior", "regras", "tfidf_lr", "knn_cohere",
            "llm_fewshot_haiku", "llm_fewshot_sonnet",
            "llm_naive_haiku", "llm_naive_sonnet"]
COBERTURA_MINIMA = 0.95
MAX_EXEMPLOS = 5  # quantos ids de exemplo listar por violacao


def ler_csv(caminho: Path) -> pd.DataFrame:
    """Le tudo como string, preservando vazios ('' nunca vira NaN)."""
    return pd.read_csv(caminho, dtype=str, keep_default_na=False)


def main() -> int:
    problemas = []
    rel = {
        "executado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cobertura_minima": COBERTURA_MINIMA,
        "campos": {},
        "preds": {},
    }

    # ------------------------- 1. splits -------------------------
    ids_teste = {}   # campo -> set de CODIGO_MATERIAL do teste
    y_teste = {}     # campo -> dict CODIGO_MATERIAL -> y
    for campo in CAMPOS:
        tr = ler_csv(SPLITS / f"{campo}__treino.csv")
        te = ler_csv(SPLITS / f"{campo}__teste.csv")
        dup_tr = sorted(tr.loc[tr["CODIGO_MATERIAL"].duplicated(), "CODIGO_MATERIAL"].unique())
        dup_te = sorted(te.loc[te["CODIGO_MATERIAL"].duplicated(), "CODIGO_MATERIAL"].unique())
        inter = sorted(set(tr["CODIGO_MATERIAL"]) & set(te["CODIGO_MATERIAL"]))
        info = {
            "n_treino": len(tr),
            "n_teste": len(te),
            "ids_duplicados_treino": len(dup_tr),
            "ids_duplicados_teste": len(dup_te),
            "intersecao_treino_teste": len(inter),
            "ok": not (dup_tr or dup_te or inter),
        }
        if dup_tr:
            problemas.append(f"split {campo}__treino: {len(dup_tr)} CODIGO_MATERIAL "
                             f"duplicados (ex.: {dup_tr[:MAX_EXEMPLOS]})")
        if dup_te:
            problemas.append(f"split {campo}__teste: {len(dup_te)} CODIGO_MATERIAL "
                             f"duplicados (ex.: {dup_te[:MAX_EXEMPLOS]})")
        if inter:
            problemas.append(f"split {campo}: treino e teste compartilham {len(inter)} "
                             f"CODIGO_MATERIAL (ex.: {inter[:MAX_EXEMPLOS]})")
        rel["campos"][campo] = info
        ids_teste[campo] = set(te["CODIGO_MATERIAL"])
        y_teste[campo] = dict(zip(te["CODIGO_MATERIAL"], te["y"]))

    # ------------------------- 2. predicoes -------------------------
    for solucao in SOLUCOES:
        for campo in CAMPOS:
            nome = f"{solucao}__{campo}"
            arq = PRED / f"{nome}.csv"
            if not arq.exists():
                problemas.append(f"pred/{nome}.csv: arquivo ausente")
                rel["preds"][nome] = {"ok": False, "erro": "arquivo ausente"}
                continue
            df = ler_csv(arq)
            faltam_cols = [c for c in ("CODIGO_MATERIAL", "y_true", "y_pred", "conf", "top3")
                           if c not in df.columns]
            if faltam_cols:
                problemas.append(f"pred/{nome}.csv: colunas ausentes {faltam_cols}")
                rel["preds"][nome] = {"ok": False, "erro": f"colunas ausentes {faltam_cols}"}
                continue

            ids = df["CODIGO_MATERIAL"]
            dup = sorted(ids[ids.duplicated()].unique())
            fora = sorted(set(ids) - ids_teste[campo])
            cobertos = set(ids) & ids_teste[campo]
            cobertura = len(cobertos) / len(ids_teste[campo]) if ids_teste[campo] else 0.0

            # y_true == y do split em TODAS as linhas cujo id existe no teste
            esperado = ids.map(y_teste[campo])
            no_teste = esperado.notna()
            diverge = df.loc[no_teste & (df["y_true"] != esperado.where(no_teste, ""))]
            ids_diverg = sorted(diverge["CODIGO_MATERIAL"].unique())

            # conf em [0,1] quando preenchida
            conf = df["conf"].str.strip()
            preenchida = conf != ""
            conf_num = pd.to_numeric(conf[preenchida], errors="coerce")
            nao_numerica = sorted(ids[preenchida][conf_num.isna()].unique())
            fora_01 = sorted(ids[preenchida][(conf_num < 0) | (conf_num > 1)].unique())

            info = {
                "n_linhas": len(df),
                "n_teste": len(ids_teste[campo]),
                "ids_fora_do_teste": len(fora),
                "ids_duplicados": len(dup),
                "cobertura": round(cobertura, 4),
                "linhas_y_true_divergente": int(len(diverge)),
                "conf_preenchidas": int(preenchida.sum()),
                "conf_nao_numerica": len(nao_numerica),
                "conf_fora_de_0_1": len(fora_01),
            }
            info["ok"] = (not fora and not dup and cobertura >= COBERTURA_MINIMA
                          and len(diverge) == 0 and not nao_numerica and not fora_01)
            rel["preds"][nome] = info

            if fora:
                problemas.append(f"pred/{nome}.csv: {len(fora)} ids fora do teste "
                                 f"(ex.: {fora[:MAX_EXEMPLOS]})")
            if dup:
                problemas.append(f"pred/{nome}.csv: {len(dup)} ids duplicados "
                                 f"(ex.: {dup[:MAX_EXEMPLOS]})")
            if cobertura < COBERTURA_MINIMA:
                problemas.append(f"pred/{nome}.csv: cobertura {cobertura:.4f} < "
                                 f"{COBERTURA_MINIMA} do teste")
            if ids_diverg:
                problemas.append(f"pred/{nome}.csv: y_true difere do y do split em "
                                 f"{len(diverge)} linhas (ex.: {ids_diverg[:MAX_EXEMPLOS]})")
            if nao_numerica:
                problemas.append(f"pred/{nome}.csv: conf preenchida nao numerica em "
                                 f"{len(nao_numerica)} ids (ex.: {nao_numerica[:MAX_EXEMPLOS]})")
            if fora_01:
                problemas.append(f"pred/{nome}.csv: conf fora de [0,1] em "
                                 f"{len(fora_01)} ids (ex.: {fora_01[:MAX_EXEMPLOS]})")

    # ------------------------- 3. arquivos inesperados -------------------------
    esperados = {f"{s}__{c}" for s in SOLUCOES for c in CAMPOS}
    extras = sorted(p.name for p in PRED.glob("*.csv") if p.stem not in esperados)
    rel["pred_inesperados"] = extras
    for nome in extras:
        problemas.append(f"pred/{nome}: arquivo de solucao inesperada "
                         "(entraria no benchmark sem fazer parte das 8 solucoes)")

    rel["problemas"] = problemas
    rel["aprovado"] = not problemas

    ARQ_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ARQ_SAIDA.write_text(json.dumps(rel, ensure_ascii=False, indent=1))
    print(f"relatorio gravado em {ARQ_SAIDA}")
    print(f"splits ok: {sum(1 for v in rel['campos'].values() if v['ok'])}/{len(rel['campos'])} | "
          f"preds ok: {sum(1 for v in rel['preds'].values() if v.get('ok'))}/{len(rel['preds'])}")
    if problemas:
        print(f"REPROVADO: {len(problemas)} problema(s)")
        for p in problemas:
            print(" -", p)
        return 1
    print("APROVADO: nenhuma violacao encontrada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
