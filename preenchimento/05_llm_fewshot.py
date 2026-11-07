"""05_llm_fewshot.py - solucoes 'llm_fewshot_haiku', 'llm_fewshot_sonnet' e 'llm_fewshot_fable'.

LLM engenheirada: vocabulario candidato + exemplos few-shot (3 vizinhos TF-IDF
do TREINO) + saida JSON estruturada, em lotes de 20 itens de teste por chamada.

Uso:
  python 05_llm_fewshot.py --validar                 # 1 lote em foreground (nao grava pred)
  python 05_llm_fewshot.py --tudo                    # execucao completa (default: haiku sonnet)
  python 05_llm_fewshot.py --tudo --modelos fable    # execucao completa so do fable
"""
import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

import bedrock_util as B
import contrato as C

LOTE = 20
N_EXEMPLOS = 3
MAX_TOKENS = 3000
# Fable 5 raciocina sempre (o pensamento conta como tokens de saida) -> teto maior.
MAX_TOKENS_FABLE = 16000
THREADS = 8
THREADS_FABLE = 6  # educado com a concorrencia: ha outro processo usando Bedrock
MAX_CHARS_EXEMPLO = 240
SOLUCOES = {"haiku": ("llm_fewshot_haiku", B.HAIKU),
            "sonnet": ("llm_fewshot_sonnet", B.SONNET),
            "fable": ("llm_fewshot_fable", B.FABLE)}

LOG_PATH = C.RAIZ / "05_llm_fewshot.log"
_log_lock = threading.Lock()


def log(msg):
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    with _log_lock:
        print(linha, flush=True)
        try:
            with open(LOG_PATH, "a") as f:
                f.write(linha + "\n")
        except OSError:
            pass


# Regra 8: se TODAS as chamadas passarem a falhar com erro de credencial, parar.
ERROS_AUTH = ("ExpiredToken", "ExpiredTokenException", "UnrecognizedClient",
              "UnrecognizedClientException", "InvalidSignatureException")
_auth_lock = threading.Lock()
_auth_seguidas = 0
ABORTAR = threading.Event()


def registra_erro(e):
    global _auth_seguidas
    cod = ""
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        cod = resp.get("Error", {}).get("Code", "")
    nome = type(e).__name__
    with _auth_lock:
        if any(a in (cod, nome) for a in ERROS_AUTH):
            _auth_seguidas += 1
            if _auth_seguidas >= 5:
                ABORTAR.set()
        else:
            _auth_seguidas = 0
    return cod or nome


def registra_sucesso():
    global _auth_seguidas
    with _auth_lock:
        _auth_seguidas = 0


DEFINICAO = {
    "GRUPO_MERCADORIA": ("GRUPO_MERCADORIA e o codigo do grupo de mercadoria (familia) "
                         "que classifica o material."),
    "NCM": ("NCM e o codigo fiscal de 8 digitos (Nomenclatura Comum do Mercosul) do material. "
            "Responda cada NCM como string JSON de exatamente 8 digitos, sem pontos."),
    "FABRICANTE": ("FABRICANTE e o nome padronizado do fabricante do material; com frequencia "
                   "o nome aparece literalmente na descricao."),
    "REFERENCIA_FABRICANTE": ("REFERENCIA_FABRICANTE e o part number (codigo de catalogo) "
                              "do fabricante do material."),
}

FORMATO_TOP3 = (
    "Responda SOMENTE com um array JSON valido, sem comentarios nem texto fora do JSON, "
    "com exatamente um objeto por item, na ordem dos ids, no formato:\n"
    '[{"id": 1, "top3": [{"v": "MAIS_PROVAVEL", "p": 0.9}, {"v": "SEGUNDO", "p": 0.07}, '
    '{"v": "TERCEIRO", "p": 0.02}]}]\n'
    '"p" e a probabilidade (0.0 a 1.0) de cada candidato; ate 3 candidatos, melhor primeiro.'
)
FORMATO_REF = (
    "Responda SOMENTE com um array JSON valido, sem comentarios nem texto fora do JSON, "
    "com exatamente um objeto por item, na ordem dos ids, no formato:\n"
    '[{"id": 1, "v": "PARTNUMBER"}, {"id": 2, "v": null}]\n'
    "Use null quando o texto nao contiver part number do fabricante."
)


def monta_sistema(campo, prep):
    partes = [f"Voce completa o campo {campo} de registros de materiais industriais "
              "de mineracao.", DEFINICAO[campo]]
    if campo == "GRUPO_MERCADORIA":
        vocab = "\n".join(f"{c} = {d}" for c, d in prep["grupos"])
        partes.append("Escolha exatamente um codigo do vocabulario abaixo "
                      "(responda o codigo, ex.: FIX01):\n" + vocab)
        partes.append("Cada item traz EXEMPLOS: materiais parecidos ja classificados "
                      "(texto -> rotulo).")
        partes.append(FORMATO_TOP3)
    elif campo == "FABRICANTE":
        partes.append(f"Escolha exatamente um nome da lista de fabricantes conhecidos "
                      f"({len(prep['vocab'])} nomes):\n" + ", ".join(prep["vocab"]))
        partes.append("Cada item traz EXEMPLOS: materiais parecidos ja classificados "
                      "(texto -> rotulo).")
        partes.append(FORMATO_TOP3)
    elif campo == "NCM":
        partes.append("Cada item traz CANDIDATOS: os NCMs mais frequentes de materiais do "
                      "mesmo grupo de mercadoria. Prefira um dos CANDIDATOS; so use outro "
                      "NCM de 8 digitos se houver forte evidencia no texto.")
        partes.append("Cada item traz EXEMPLOS: materiais parecidos ja classificados "
                      "(texto -> NCM).")
        partes.append(FORMATO_TOP3)
    else:  # REFERENCIA_FABRICANTE
        partes.append("Extraia o part number do fabricante presente no texto; null quando "
                      "nao houver. Nao confunda com dimensoes, normas (DIN/ISO/ABNT/SAE/ANSI), "
                      "bitolas, tensoes ou o codigo interno do material. Copie o part number "
                      "exatamente como esta no texto.")
        partes.append("Cada item traz EXEMPLOS: materiais parecidos com a referencia correta "
                      "ja extraida (texto -> referencia normalizada sem separadores).")
        partes.append(FORMATO_REF)
    return "\n\n".join(partes)


def preparar_campo(campo):
    """Carrega splits, ajusta TF-IDF + vizinhos no TREINO (1x por campo) e vocabularios."""
    t0 = time.time()
    tr = pd.read_csv(C.caminho_split(campo, "treino"), dtype=str).fillna("")
    te = pd.read_csv(C.caminho_split(campo, "teste"), dtype=str).fillna("")
    incluir_grupo = campo != "GRUPO_MERCADORIA"
    tx_tr = [C.texto_entrada(r, incluir_grupo) for r in tr.to_dict("records")]
    tx_te = [C.texto_entrada(r, incluir_grupo) for r in te.to_dict("records")]
    vec = TfidfVectorizer(sublinear_tf=True)
    Xtr = vec.fit_transform(tx_tr)
    nn = NearestNeighbors(n_neighbors=N_EXEMPLOS, metric="cosine", algorithm="brute")
    nn.fit(Xtr)
    _, idx = nn.kneighbors(vec.transform(tx_te))
    ys = tr["y"].tolist()
    prep = {"teste": te,
            "exemplos": [[(tx_tr[j], ys[j]) for j in fila] for fila in idx]}
    if campo == "GRUPO_MERCADORIA":
        g = pd.read_csv(C.DADOS / "pdm_grupos.csv", dtype=str).fillna("")
        prep["grupos"] = list(zip(g["GRUPO_MERCADORIA"], g["DESCRICAO"]))
    if campo == "FABRICANTE":
        prep["vocab"] = sorted(tr["y"].unique())
    if campo == "NCM":
        topo = (tr.groupby("GRUPO_MERCADORIA")["y"]
                .apply(lambda s: s.value_counts().head(10).index.tolist()).to_dict())
        glob = tr["y"].value_counts().head(10).index.tolist()
        prep["cand"] = [topo.get(str(r.get("GRUPO_MERCADORIA", "")), glob) or glob
                        for r in te.to_dict("records")]
    prep["seg_prep"] = round(time.time() - t0, 1)
    prep["sistema"] = monta_sistema(campo, prep)
    return prep


def bloco_item(campo, it):
    row = it["row"]
    linhas = [f"ITEM {it['id']}"]
    for col in ("DESCRICAO_CURTA", "DESCRICAO_LONGA", "CENTRO", "UNIDADE_MEDIDA"):
        v = str(row.get(col, "") or "")
        if v:
            linhas.append(f"{col}: {v}")
    if campo != "GRUPO_MERCADORIA":
        g = str(row.get("GRUPO_MERCADORIA", "") or "")
        if g:
            linhas.append(f"GRUPO_MERCADORIA: {g}")
    if campo == "NCM" and it.get("candidatos"):
        linhas.append("CANDIDATOS: " + ", ".join(it["candidatos"]))
    linhas.append("EXEMPLOS:")
    for t, y in it["exemplos"]:
        linhas.append(f"- {t[:MAX_CHARS_EXEMPLO]} -> {y}")
    return "\n".join(linhas)


def monta_usuario(campo, itens):
    cab = (f"Complete o campo {campo} dos {len(itens)} itens abaixo. "
           f"Responda somente o array JSON com {len(itens)} objetos.")
    return cab + "\n\n" + "\n\n".join(bloco_item(campo, it) for it in itens)


def monta_lotes(campo, prep):
    rows = prep["teste"].to_dict("records")
    lotes = []
    for ini in range(0, len(rows), LOTE):
        itens = [{"id": k + 1, "row": rows[i], "exemplos": prep["exemplos"][i],
                  "candidatos": prep["cand"][i] if campo == "NCM" else None}
                 for k, i in enumerate(range(ini, min(ini + LOTE, len(rows))))]
        lotes.append((ini // LOTE, itens))
    return lotes


def interpreta(campo, bruto, n_itens):
    """Texto do modelo -> dict id -> (y_pred, conf, top3), ja normalizados."""
    dados = B.extrai_json(bruto)
    if isinstance(dados, dict):
        dados = [dados]
    if not isinstance(dados, list):
        raise ValueError("JSON nao e array")
    out = {}
    for obj in dados:
        if not isinstance(obj, dict):
            continue
        try:
            i = int(obj.get("id"))
        except (TypeError, ValueError):
            continue
        if not (1 <= i <= n_itens) or i in out:
            continue
        if campo == "REFERENCIA_FABRICANTE":
            v = obj.get("v")
            yp = C.norm_rotulo(campo, v) if v is not None else ""
            # formato de extracao nao pede probabilidade -> conf vazia
            out[i] = (yp, "", yp)
        else:
            top = obj.get("top3")
            if isinstance(top, dict):
                top = [top]
            cand = []
            if isinstance(top, list):
                for c in top:
                    v, p = (c.get("v"), c.get("p")) if isinstance(c, dict) else (c, None)
                    nv = C.norm_rotulo(campo, v)
                    if nv and all(nv != x for x, _ in cand):
                        try:
                            p = min(1.0, max(0.0, float(p)))
                        except (TypeError, ValueError):
                            p = ""
                        cand.append((nv, p))
            if cand:
                out[i] = (cand[0][0], cand[0][1], "|".join(x for x, _ in cand[:3]))
            else:
                out[i] = ("", "", "")
    return out


def processa_lote(model_id, campo, sistema, num, itens, contador):
    if ABORTAR.is_set():
        return num, {}, "abortado"
    usuario = monta_usuario(campo, itens)
    max_toks = MAX_TOKENS_FABLE if model_id == B.FABLE else MAX_TOKENS
    erro = ""
    for _ in range(2):  # 2a tentativa apenas para resposta ilegivel (parse)
        try:
            bruto = B.converse(model_id, usuario, sistema=sistema,
                               max_tokens=max_toks, contador=contador)
            registra_sucesso()
        except Exception as e:  # falha persistente apos retries internos
            return num, {}, "api:" + registra_erro(e)
        try:
            return num, interpreta(campo, bruto, len(itens)), ""
        except ValueError as e:
            erro = f"parse:{str(e)[:80]}"
    return num, {}, erro


def roda_campo(solucao, model_id, campo, prep, gravar=True, so_um_lote=False):
    lotes = monta_lotes(campo, prep)
    if so_um_lote:
        lotes = lotes[:1]
    contador = B.Contador()
    t0 = time.time()
    resultados, erros = {}, []
    n_threads = THREADS_FABLE if model_id == B.FABLE else THREADS
    with ThreadPoolExecutor(max_workers=n_threads) as pool:
        futs = {pool.submit(processa_lote, model_id, campo, prep["sistema"],
                            n, its, contador): n for n, its in lotes}
        feitos = 0
        for fut in as_completed(futs):
            num, res, erro = fut.result()
            resultados[num] = res
            feitos += 1
            if erro:
                erros.append(f"lote {num}: {erro}")
            if feitos % 10 == 0 or feitos == len(lotes):
                log(f"{solucao} {campo}: {feitos}/{len(lotes)} lotes "
                    f"(tok {contador.entrada}/{contador.saida})")
    te = prep["teste"]
    linhas, sem_resposta = [], 0
    for n, its in lotes:
        res = resultados.get(n, {})
        for it in its:
            row = te.iloc[n * LOTE + it["id"] - 1]
            yp, conf, top3 = res.get(it["id"], ("", "", ""))
            if it["id"] not in res:
                sem_resposta += 1
            linhas.append({"CODIGO_MATERIAL": row["CODIGO_MATERIAL"],
                           "y_true": C.norm_rotulo(campo, row["y"]),
                           "y_pred": yp, "conf": conf, "top3": top3})
    df = pd.DataFrame(linhas)
    segundos = round(time.time() - t0, 1)
    abst = int((df["y_pred"] == "").sum())
    if gravar and not (ABORTAR.is_set() and contador.chamadas == 0):
        C.salvar_pred(solucao, campo, df)
        obs = (f"lotes de {LOTE} itens ({len(lotes)} lotes); few-shot {N_EXEMPLOS} vizinhos "
               f"TF-IDF do treino; abstencoes={abst} (itens sem resposta/ilegiveis do "
               f"modelo={sem_resposta}); prep tfidf {prep['seg_prep']}s compartilhada "
               f"entre os modelos da execucao")
        if campo == "FABRICANTE":
            obs += f"; vocabulario com {len(prep['vocab'])} fabricantes do treino"
        if campo == "NCM":
            obs += "; candidatos = ate 10 NCMs mais frequentes do grupo no treino"
        if campo == "REFERENCIA_FABRICANTE":
            obs += "; conf vazia (formato de extracao nao pede probabilidade)"
        if erros:
            obs += "; falhas: " + "; ".join(erros[:8])
            if len(erros) > 8:
                obs += f" (+{len(erros) - 8} lotes)"
        if ABORTAR.is_set():
            obs += "; ABORTADO: credenciais AWS invalidas/expiradas no meio da execucao"
        C.salvar_meta(solucao, campo, segundos=segundos, chamadas_api=contador.chamadas,
                      tokens_entrada=contador.entrada, tokens_saida=contador.saida,
                      modelo=model_id,
                      custo_estimado_usd=round(contador.custo(model_id), 4),
                      observacoes=obs)
    log(f"{solucao} {campo}: fim em {segundos}s, chamadas={contador.chamadas}, "
        f"tok={contador.entrada}/{contador.saida}, "
        f"custo=${contador.custo(model_id):.3f}, abstencoes={abst}")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validar", action="store_true", help="1 lote por campo, sem gravar")
    ap.add_argument("--tudo", action="store_true",
                    help="execucao completa dos modelos selecionados")
    ap.add_argument("--modelos", nargs="+", choices=list(SOLUCOES),
                    default=["haiku", "sonnet"],
                    help="modelos a rodar (default: haiku sonnet)")
    args = ap.parse_args()
    solucoes = [SOLUCOES[m] for m in args.modelos]

    log("preparando campos (tfidf + vizinhos do treino)...")
    preps = {c: preparar_campo(c) for c in C.CAMPOS}
    for c in C.CAMPOS:
        log(f"prep {c}: {preps[c]['seg_prep']}s, teste={len(preps[c]['teste'])}, "
            f"sistema={len(preps[c]['sistema'])} chars")

    if args.validar:
        # 1o modelo selecionado: 1 lote por campo; demais: 1 lote de GRUPO_MERCADORIA.
        for k, apelido in enumerate(args.modelos):
            _, mid = SOLUCOES[apelido]
            for campo in (C.CAMPOS if k == 0 else ["GRUPO_MERCADORIA"]):
                df = roda_campo(f"valida_{apelido}", mid, campo, preps[campo],
                                gravar=False, so_um_lote=True)
                log(f"VALIDACAO {apelido} {campo}: {int((df['y_pred'] != '').sum())}/{len(df)} "
                    f"itens com predicao")
        return

    if args.tudo:
        def um_modelo(solucao, mid):
            for campo in C.CAMPOS:
                if ABORTAR.is_set():
                    log(f"{solucao} {campo}: pulado (abortado por credenciais)")
                    continue
                roda_campo(solucao, mid, campo, preps[campo])
        with ThreadPoolExecutor(max_workers=len(solucoes)) as pool:
            for fut in [pool.submit(um_modelo, s, m) for s, m in solucoes]:
                fut.result()
        log("FIM" + (" (ABORTADO por credenciais AWS)" if ABORTAR.is_set() else " ok"))


if __name__ == "__main__":
    main()
