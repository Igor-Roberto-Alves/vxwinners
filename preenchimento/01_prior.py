"""Solucao 'prior': linha de base de frequencia (custo zero, sem API).

- GRUPO_MERCADORIA: moda do treino; top3 = 3 classes mais frequentes;
  conf = frequencia relativa do top1.
- NCM e FABRICANTE: moda condicional por GRUPO_MERCADORIA no treino
  (fallback: moda global quando o grupo nao tem exemplos no treino);
  top3 = 3 valores mais frequentes do grupo; conf = freq. relativa do top1 no grupo.
- REFERENCIA_FABRICANTE: abstencao total (y_pred vazio).

Usa exclusivamente o split de treino de cada campo para qualquer ajuste.
O y do teste e copiado apenas para a coluna y_true.
"""
import time

import pandas as pd

from contrato import caminho_split, norm_rotulo, norm_texto, salvar_meta, salvar_pred

SOLUCAO = "prior"


def ler_split(campo: str, parte: str) -> pd.DataFrame:
    df = pd.read_csv(caminho_split(campo, parte), dtype=str, keep_default_na=False)
    print(f"[{campo}] {parte}: {len(df)} linhas")
    return df


def contagens(serie: pd.Series) -> pd.Series:
    """Contagem de valores nao vazios, mais frequentes primeiro (desempate estavel)."""
    s = serie[serie != ""]
    return s.value_counts()


def top3_de(cnt: pd.Series, campo: str) -> str:
    itens = [norm_rotulo(campo, v) for v in cnt.index[:3]]
    return "|".join(i for i in itens if i)


def roda_grupo_mercadoria() -> None:
    campo = "GRUPO_MERCADORIA"
    t0 = time.time()
    treino = ler_split(campo, "treino")
    teste = ler_split(campo, "teste")

    cnt = contagens(treino["y"])
    moda = norm_rotulo(campo, cnt.index[0])
    conf = round(float(cnt.iloc[0]) / float(cnt.sum()), 6)
    top3 = top3_de(cnt, campo)
    print(f"[{campo}] moda global = {moda} (conf {conf}), top3 = {top3}")

    pred = pd.DataFrame(
        {
            "CODIGO_MATERIAL": teste["CODIGO_MATERIAL"],
            "y_true": teste["y"],
            "y_pred": moda,
            "conf": conf,
            "top3": top3,
        }
    )
    salvar_pred(SOLUCAO, campo, pred)
    salvar_meta(
        SOLUCAO,
        campo,
        segundos=round(time.time() - t0, 3),
        chamadas_api=0,
        tokens_entrada=0,
        tokens_saida=0,
        modelo="",
        custo_estimado_usd=0.0,
        observacoes="Moda global do treino aplicada a todas as linhas; top3 = 3 classes mais frequentes do treino.",
    )
    print(f"[{campo}] pred+meta gravados ({len(pred)} linhas)\n")


def roda_condicional(campo: str) -> None:
    """NCM / FABRICANTE: moda condicional por GRUPO_MERCADORIA do treino."""
    t0 = time.time()
    treino = ler_split(campo, "treino")
    teste = ler_split(campo, "teste")

    treino = treino.assign(_g=treino["GRUPO_MERCADORIA"].map(norm_texto))
    cnt_global = contagens(treino["y"])
    moda_g = norm_rotulo(campo, cnt_global.index[0])
    conf_g = round(float(cnt_global.iloc[0]) / float(cnt_global.sum()), 6)
    top3_g = top3_de(cnt_global, campo)
    print(f"[{campo}] moda global = {moda_g} (conf {conf_g}), top3 = {top3_g}")

    por_grupo = {}
    for g, sub in treino.groupby("_g"):
        cnt = contagens(sub["y"])
        if len(cnt) == 0:
            continue
        por_grupo[g] = (
            norm_rotulo(campo, cnt.index[0]),
            round(float(cnt.iloc[0]) / float(cnt.sum()), 6),
            top3_de(cnt, campo),
        )
    print(f"[{campo}] grupos com moda condicional no treino: {len(por_grupo)}")

    linhas = []
    fallback = 0
    for _, row in teste.iterrows():
        g = norm_texto(row["GRUPO_MERCADORIA"])
        if g in por_grupo:
            y_pred, conf, top3 = por_grupo[g]
        else:
            y_pred, conf, top3 = moda_g, conf_g, top3_g
            fallback += 1
        linhas.append((row["CODIGO_MATERIAL"], row["y"], y_pred, conf, top3))

    pred = pd.DataFrame(linhas, columns=["CODIGO_MATERIAL", "y_true", "y_pred", "conf", "top3"])
    salvar_pred(SOLUCAO, campo, pred)
    salvar_meta(
        SOLUCAO,
        campo,
        segundos=round(time.time() - t0, 3),
        chamadas_api=0,
        tokens_entrada=0,
        tokens_saida=0,
        modelo="",
        custo_estimado_usd=0.0,
        observacoes=(
            "Moda condicional por GRUPO_MERCADORIA no treino; "
            f"fallback para moda global em {fallback} de {len(pred)} linhas de teste "
            "(grupo sem exemplos no treino)."
        ),
    )
    print(f"[{campo}] pred+meta gravados ({len(pred)} linhas, {fallback} fallbacks)\n")


def roda_referencia() -> None:
    campo = "REFERENCIA_FABRICANTE"
    t0 = time.time()
    teste = ler_split(campo, "teste")

    pred = pd.DataFrame(
        {
            "CODIGO_MATERIAL": teste["CODIGO_MATERIAL"],
            "y_true": teste["y"],
            "y_pred": "",
            "conf": 0.0,
            "top3": "",
        }
    )
    salvar_pred(SOLUCAO, campo, pred)
    salvar_meta(
        SOLUCAO,
        campo,
        segundos=round(time.time() - t0, 3),
        chamadas_api=0,
        tokens_entrada=0,
        tokens_saida=0,
        modelo="",
        custo_estimado_usd=0.0,
        observacoes=(
            "Abstencao total: prior de frequencia nao se aplica a REFERENCIA_FABRICANTE, "
            "texto livre quase-unico por item (~4450 valores distintos no treino)."
        ),
    )
    print(f"[{campo}] abstencao total gravada ({len(pred)} linhas)\n")


def main() -> None:
    roda_grupo_mercadoria()
    roda_condicional("NCM")
    roda_condicional("FABRICANTE")
    roda_referencia()
    print("prior: concluido para os 4 campos.")


if __name__ == "__main__":
    main()
