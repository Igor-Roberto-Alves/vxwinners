"""06_llm_naive: comparador ingenuo - joga o registro inteiro numa LLM e pede para completar.

Solucoes 'llm_naive_haiku', 'llm_naive_sonnet' e 'llm_naive_fable' (selecao via
--modelos; default haiku+sonnet). Desenho deliberadamente ingenuo:
1 registro por chamada, SEM lista de valores validos, SEM exemplos, SEM vocabulario -
apenas o registro completo da base (15 colunas, campos mascarados = null) e a instrucao.

Uniao das linhas de teste dos 4 campos; cada linha vira 1 chamada por modelo e os
tokens/chamadas/segundos da chamada sao rateados igualmente entre os campos mascarados
da linha. Checkpoint em cache/ para retomar sem repagar chamadas ja feitas.
"""
import argparse
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato import (CACHE, CAMPOS, DADOS, RAIZ, caminho_split, norm_rotulo,
                      salvar_meta, salvar_pred)
from bedrock_util import FABLE, HAIKU, PRECOS, SONNET, Contador, converse, extrai_json

ARQ_LOG = RAIZ / "06_llm_naive.log"
MAX_TOKENS = 1500
MAX_TOKENS_FABLE = 8000  # raciocinio do Fable 5 sempre ligado e cobrado como saida
PROMPT = ('Complete os campos com valor null deste registro de material industrial. '
          'Responda apenas um JSON {"CAMPO": "valor", ...} com os campos que estavam null.')
SOLUCOES = {"haiku": ("llm_naive_haiku", HAIKU),
            "sonnet": ("llm_naive_sonnet", SONNET),
            "fable": ("llm_naive_fable", FABLE)}
ERROS_AUTH = ("ExpiredToken", "ExpiredTokenException", "UnrecognizedClientException",
              "InvalidClientTokenId")
LIMITE_AUTH_CONSEC = 30

_lock_log = threading.Lock()


def log(msg):
    linha = time.strftime("%H:%M:%S ") + msg
    with _lock_log:
        print(linha, flush=True)
        with ARQ_LOG.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")


def monta_registros():
    """Uniao das linhas de teste dos 4 campos.

    Devolve lista de (codigo, campos_mascarados, registro_json) onde registro_json
    e a linha COMPLETA da base (15 colunas) com cada campo mascarado = None.
    """
    base = pd.read_csv(DADOS / "base.csv", dtype=str).fillna("")
    assert base["CODIGO_MATERIAL"].is_unique, "CODIGO_MATERIAL duplicado na base"
    colunas = list(base.columns)
    bidx = base.set_index("CODIGO_MATERIAL", drop=False)

    uniao = {}  # codigo -> {campo: y_true_normalizado}
    for campo in CAMPOS:
        t = pd.read_csv(caminho_split(campo, "teste"), dtype=str).fillna("")
        assert t["CODIGO_MATERIAL"].is_unique
        for cod, y in zip(t["CODIGO_MATERIAL"], t["y"]):
            uniao.setdefault(cod, {})[campo] = y

    registros = []
    for cod, masc in uniao.items():
        row = bidx.loc[cod]
        reg = {c: row[c] for c in colunas}
        for campo, y in masc.items():
            # confere que a linha da base e mesmo a do split antes de mascarar
            assert norm_rotulo(campo, reg[campo]) == y, f"linha da base nao bate: {cod}/{campo}"
            reg[campo] = None
        # validacao anti-vazamento: nenhum campo mascarado sai com o valor verdadeiro
        for campo in masc:
            assert reg[campo] is None, f"vazamento: {campo} de {cod} nao foi mascarado"
        registros.append((cod, sorted(masc), reg))
    return registros


def processa(model_id, cod, masc, reg, parar):
    """Uma chamada: devolve (cod, masc, preds, tok_in, tok_out, chamou, erro)."""
    if parar.is_set():
        return cod, masc, {}, 0, 0, False, "abortado_auth"
    for campo in masc:  # cinto e suspensorio: nunca enviar valor de campo mascarado
        assert reg[campo] is None
    c = Contador()
    max_tokens = MAX_TOKENS_FABLE if model_id == FABLE else MAX_TOKENS
    try:
        resp = converse(model_id, PROMPT + "\n" + json.dumps(reg, ensure_ascii=False),
                        max_tokens=max_tokens, contador=c)
    except Exception as e:
        r = getattr(e, "response", None)
        cod_err = r.get("Error", {}).get("Code", "") if isinstance(r, dict) else ""
        return cod, masc, {}, c.entrada, c.saida, True, (cod_err or type(e).__name__)
    preds = {}
    try:
        obj = extrai_json(resp)
        assert isinstance(obj, dict)
        preds = {campo: norm_rotulo(campo, obj.get(campo, "")) for campo in masc}
    except Exception:
        preds = {}  # resposta ilegivel = abstencao em todos os campos da linha
    return cod, masc, preds, c.entrada, c.saida, True, ""


def roda_modelo(solucao, model_id, registros, n_threads, gravar_ck=True):
    """Roda todas as linhas num modelo. Devolve (checkpoint, abortou_por_auth)."""
    t0 = time.time()
    arq_ck = CACHE / f"06_llm_naive_{solucao}.json"
    ck = {"preds": {}, "tok": {c: {"entrada": 0.0, "saida": 0.0, "chamadas": 0.0} for c in CAMPOS},
          "entrada": 0, "saida": 0, "chamadas": 0, "erros": {}, "segundos": 0.0}
    if gravar_ck and arq_ck.exists():
        ck = json.loads(arq_ck.read_text())
        log(f"{solucao}: retomando checkpoint com {len(ck['preds'])} linhas prontas")
    pend = [r for r in registros if r[0] not in ck["preds"]]
    erros = Counter(ck["erros"])
    parar = threading.Event()
    auth_consec, feitas = 0, 0
    log(f"{solucao}: {len(pend)} linhas a chamar ({n_threads} threads, modelo {model_id})")

    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        futs = [ex.submit(processa, model_id, cod, masc, reg, parar)
                for cod, masc, reg in pend]
        for fut in as_completed(futs):
            cod, masc, preds, e_tok, s_tok, chamou, erro = fut.result()
            feitas += 1
            ck["preds"][cod] = {campo: preds.get(campo, "") for campo in masc}
            n = len(masc)
            for campo in masc:  # rateio igualitario entre os campos mascarados da linha
                t = ck["tok"][campo]
                t["entrada"] += e_tok / n
                t["saida"] += s_tok / n
                t["chamadas"] += (1.0 / n) if chamou else 0.0
            if chamou:
                ck["entrada"] += e_tok
                ck["saida"] += s_tok
                ck["chamadas"] += 1
            if erro:
                erros[erro] += 1
                if any(a in erro for a in ERROS_AUTH):
                    auth_consec += 1
                    if auth_consec >= LIMITE_AUTH_CONSEC and not parar.is_set():
                        parar.set()
                        log(f"{solucao}: {auth_consec} falhas de credencial consecutivas "
                            f"({erro}) - abortando linhas restantes")
                else:
                    auth_consec = 0
            else:
                auth_consec = 0
            if feitas % 200 == 0 or feitas == len(pend):
                dt = time.time() - t0
                log(f"{solucao}: {feitas}/{len(pend)} linhas em {dt:.0f}s "
                    f"({feitas / max(dt, 1e-9):.2f}/s), tokens {ck['entrada']}in/{ck['saida']}out, "
                    f"erros={sum(erros.values())}")
            if gravar_ck and feitas % 1000 == 0:
                ck["erros"] = dict(erros)
                arq_ck.write_text(json.dumps(ck))

    ck["segundos"] += time.time() - t0
    ck["erros"] = dict(erros)
    if gravar_ck:
        arq_ck.write_text(json.dumps(ck))
    return ck, parar.is_set()


def grava_saidas(solucao, model_id, ck, abortou_auth):
    pe, ps = PRECOS[model_id]
    cham_total = sum(ck["tok"][c]["chamadas"] for c in CAMPOS)
    for campo in CAMPOS:
        teste = pd.read_csv(caminho_split(campo, "teste"), dtype=str).fillna("")
        y_pred = [ck["preds"].get(cod, {}).get(campo, "") for cod in teste["CODIGO_MATERIAL"]]
        df = pd.DataFrame({"CODIGO_MATERIAL": teste["CODIGO_MATERIAL"], "y_true": teste["y"],
                           "y_pred": y_pred, "conf": "", "top3": y_pred})
        salvar_pred(solucao, campo, df)
        t = ck["tok"][campo]
        custo = t["entrada"] / 1e6 * pe + t["saida"] / 1e6 * ps
        abst = sum(1 for v in y_pred if not v)
        obs = ("Comparador ingenuo: 1 chamada por linha da uniao do teste, enviando o registro "
               "completo da base (15 colunas) em JSON com os campos de teste da linha = null; "
               "sem vocabulario de valores validos, sem exemplos, sem few-shot. Linhas presentes "
               "no teste de mais de um campo compartilham a mesma chamada, por isso tokens, "
               "chamadas e segundos da chamada foram rateados igualmente entre os campos "
               "mascarados da linha (valores fracionarios; a soma dos 4 campos = total do modelo). "
               f"Abstencoes: {abst}/{len(teste)} (resposta ilegivel, campo ausente no JSON, "
               "normalizacao vazia ou falha apos retries). "
               f"Erros de API da solucao inteira: {ck['erros'] or 'nenhum'}.")
        if abortou_auth:
            obs += (" ATENCAO: execucao abortada por falhas de credencial consecutivas "
                    "(ExpiredToken/UnrecognizedClient); linhas restantes = abstencao.")
        salvar_meta(solucao, campo,
                    segundos=round(ck["segundos"] * (t["chamadas"] / cham_total), 1) if cham_total else 0.0,
                    chamadas_api=round(t["chamadas"], 2),
                    tokens_entrada=int(round(t["entrada"])),
                    tokens_saida=int(round(t["saida"])),
                    modelo=model_id,
                    custo_estimado_usd=round(custo, 4),
                    observacoes=obs)
        log(f"{solucao}/{campo}: pred+meta gravados | abst={abst}/{len(teste)} "
            f"chamadas_rateadas={t['chamadas']:.2f} custo=${custo:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amostra", type=int, default=0,
                    help="valida com N linhas em foreground, sem gravar nada")
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--modelos", nargs="+", choices=sorted(SOLUCOES),
                    default=["haiku", "sonnet"],
                    help="quais modelos rodar (default: haiku sonnet)")
    args = ap.parse_args()
    solucoes = [SOLUCOES[m] for m in args.modelos]

    registros = monta_registros()
    dist = Counter(len(m) for _, m, _ in registros)
    log(f"uniao do teste: {len(registros)} linhas | campos mascarados por linha: {dict(sorted(dist.items()))}")

    if args.amostra:
        simples = [r for r in registros if len(r[1]) == 1]
        multi = [r for r in registros if len(r[1]) > 1]
        registros = (simples[:max(1, args.amostra - 2)] + multi[:2])[:args.amostra]
        log(f"modo amostra: {len(registros)} linhas, nada sera gravado")
        exemplo = next(r for r in registros if len(r[1]) > 1) if multi else registros[0]
        log("exemplo de payload mascarado (" + ",".join(exemplo[1]) + "): "
            + json.dumps(exemplo[2], ensure_ascii=False))

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(solucoes)) as ex:  # modelos selecionados em paralelo
        futs = {ex.submit(roda_modelo, sol, mid, registros, args.threads,
                          gravar_ck=not args.amostra): (sol, mid) for sol, mid in solucoes}
        for fut in as_completed(futs):
            sol, mid = futs[fut]
            ck, abortou = fut.result()
            pe, ps = PRECOS[mid]
            custo = ck["entrada"] / 1e6 * pe + ck["saida"] / 1e6 * ps
            log(f"{sol}: concluido | chamadas={ck['chamadas']} tokens={ck['entrada']}in/"
                f"{ck['saida']}out custo=${custo:.2f} erros={ck['erros'] or 'nenhum'}"
                + (" ABORTADO_POR_AUTH" if abortou else ""))
            if args.amostra:
                log(f"{sol} amostra preds: {json.dumps(ck['preds'], ensure_ascii=False)}")
            else:
                grava_saidas(sol, mid, ck, abortou)
    log(f"fim: {time.time() - t0:.0f}s no total")


if __name__ == "__main__":
    main()
