# -*- coding: utf-8 -*-
"""Mede, contra o gabarito, o efeito das travas do dicionario aprendido.

Uso:
  uv run --no-project --with pandas --with openpyxl python avaliacao/13_efeito_travas.py \
      [--curado artefatos/aprendizado_curado.json] [--saida avaliacao/efeito_travas.md]

Como mede, e o que a medida supoe
---------------------------------
Reexecutar o pipeline inteiro mudaria `artefatos/` (que outra sessao esta
usando) e misturaria o efeito das travas com o de qualquer outra alteracao em
andamento. Em vez disso, isto reprocessa SO a camada que mudou:

  para cada rotulo do gold cuja decisao atual veio da fonte `aprendido`,
  pergunta ao dicionario CURADO, com as travas ligadas, o que ele responderia
  hoje - e recalcula o veredito com a mesma comparacao do avaliador.

Suposicao declarada: quando o dicionario passa a se abster, o atributo fica
PENDENTE (veredito ABSTEVE). E a leitura conservadora - em `_por_gazetteer` o
dicionario e a ultima camada antes do vazio, e as duas anteriores (valor
literal e `sinonimos.py`) ja falharam, senao a decisao nao teria vindo dele.
Na execucao real, BERT, LLM ou o arbitro ainda podem preencher alguns desses
casos, o que tornaria a cobertura um pouco melhor do que a estimada aqui.
"""
import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
sys.path.insert(0, str(REPO / "src"))

from saneamento.aprendizado import Aprendizado, MARCA_INTERPRETACAO  # noqa: E402
from saneamento.pdm import Pdm  # noqa: E402
from saneamento.texto import com_bordas, expandir  # noqa: E402


def carrega_avaliador():
    spec = importlib.util.spec_from_file_location(
        "ev", RAIZ / "evaluate_caracteristicas.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    return ev


def le_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curado", default=str(REPO / "artefatos/aprendizado_curado.json"))
    ap.add_argument("--saida", default=str(RAIZ / "efeito_travas.md"))
    a = ap.parse_args()

    ev = carrega_avaliador()
    pdm = Pdm.carregar(REPO / "artefatos/pdm.json")
    gold = {(r["CODIGO_MATERIAL"], r["campo"]): r
            for r in le_csv(RAIZ / "gold_caracteristicas.csv")}
    cand = {r["CODIGO_MATERIAL"]: r
            for r in le_csv(RAIZ / "candidatos_caracteristicas.csv")}
    san = {}
    with open(REPO / "artefatos/saneado_base.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["CODIGO_MATERIAL"] in cand:
                san[r["CODIGO_MATERIAL"]] = r

    novo = Aprendizado(a.curado, pdm=pdm, congelado=True, travas=True)
    print(f"dicionario curado: {len(novo.entradas)} entradas, "
          f"{sum(1 for e in novo.entradas.values() if not e.revisar)} aplicaveis")

    # --- veredito atual de todos os rotulos, e quais vieram do dicionario ----
    atual, do_dicionario = {}, []
    with open(REPO / "artefatos/decisoes_base.jsonl", encoding="utf-8") as f:
        for linha in f:
            if not linha.strip():
                continue
            r = json.loads(linha)
            cod = str(r.get("codigo", "")).strip()
            if cod not in cand:
                continue
            for d in r.get("decisoes", []):
                k = (cod, d["atributo"].strip())
                if k not in gold:
                    continue
                atual[k] = d
                if d.get("fonte") == "aprendido" and d.get("valor"):
                    do_dicionario.append(k)

    def veredito(campo, status, y_gold, valor):
        v = ev.norm(campo, valor or "")
        alvo = ev.norm(campo, y_gold)
        if status == "DEFINIDO":
            return "ABSTEVE" if v == "" else (
                "ACERTO" if ev.valor_igual(campo, alvo, v) else "ERRO")
        return "ABSTENCAO_CORRETA" if v == "" else "INVENCAO"

    antes = Counter()
    for k, g in gold.items():
        d = atual.get(k) or {}
        antes[veredito(k[1], g["status"], g["y_gold"], d.get("valor"))] += 1

    # --- o que o dicionario curado responderia -------------------------------
    depois = Counter(antes)
    mudancas = []
    for k in do_dicionario:
        cod, campo = k
        g = gold[k]
        id_pdm = (san.get(cod, {}).get("ID_PDM") or "").strip()
        classe = pdm.classes.get(id_pdm)
        atributo = next((x for x in (classe.atributos if classe else [])
                         if x.nome == campo), None)
        if atributo is None:
            continue
        texto = (cand[cod]["DESCRICAO_CURTA"] + " " + cand[cod]["DESCRICAO_LONGA"])
        t = com_bordas(expandir(texto))
        novo.bloqueados.clear()
        resposta = novo.consultar(atributo, t)
        v_antes = atual[k].get("valor")
        if ev.norm(campo, resposta or "") == ev.norm(campo, v_antes or ""):
            continue
        ver_antes = veredito(campo, g["status"], g["y_gold"], v_antes)
        ver_depois = veredito(campo, g["status"], g["y_gold"], resposta)
        depois[ver_antes] -= 1
        depois[ver_depois] += 1
        mudancas.append({
            "codigo": cod, "campo": campo, "status_gold": g["status"],
            "y_gold": ev.norm(campo, g["y_gold"]), "antes": v_antes,
            "depois": resposta or "(PENDENTE)",
            "ver_antes": ver_antes, "ver_depois": ver_depois,
            "motivo": (novo.bloqueados[0]["motivo"] if novo.bloqueados
                       else "entrada descartada na curadoria"),
            "texto": cand[cod]["DESCRICAO_LONGA"],
        })

    def metricas(c):
        definido = c["ACERTO"] + c["ERRO"] + c["ABSTEVE"]
        preench = c["ACERTO"] + c["ERRO"]
        nao_def = c["INVENCAO"] + c["ABSTENCAO_CORRETA"]
        return {
            "precisao": ev.pct_ic(c["ACERTO"], preench),
            "cobertura": ev.pct(preench, definido),
            "invencao": f"{c['INVENCAO']}/{nao_def} ({c['INVENCAO'] / nao_def:.0%})",
            "acertos": c["ACERTO"], "erros": c["ERRO"], "absteve": c["ABSTEVE"],
        }

    ma, md = metricas(antes), metricas(depois)
    melhora = Counter(m["ver_depois"] for m in mudancas
                      if m["ver_antes"] in ("ERRO", "INVENCAO"))
    perda = [m for m in mudancas if m["ver_antes"] == "ACERTO"]

    L = ["# Efeito das travas do dicionario aprendido\n",
         f"Dicionario curado: `{Path(a.curado).name}` · "
         f"{len(novo.entradas)} entradas, "
         f"{sum(1 for e in novo.entradas.values() if not e.revisar)} aplicaveis como regra, "
         f"{sum(1 for e in novo.entradas.values() if MARCA_INTERPRETACAO in e.fonte)} "
         "marcadas como interpretacao.\n",
         f"Rotulos do gold decididos pelo dicionario hoje: **{len(do_dicionario)}**; "
         f"o dicionario curado muda **{len(mudancas)}** deles.\n",
         "## Antes e depois (1 131 rotulos do gold)\n",
         "| metrica | antes | depois |", "|---|---|---|",
         f"| precisao | {ma['precisao']} | {md['precisao']} |",
         f"| cobertura | {ma['cobertura']} | {md['cobertura']} |",
         f"| taxa de invencao | {ma['invencao']} | {md['invencao']} |",
         f"| acertos | {ma['acertos']} | {md['acertos']} |",
         f"| erros | {ma['erros']} | {md['erros']} |",
         f"| absteve (perda de cobertura) | {ma['absteve']} | {md['absteve']} |",
         "",
         f"Erros e invencoes removidos: **{sum(melhora.values())}** "
         f"(viraram {dict(melhora)}). Acertos perdidos: **{len(perda)}**.\n",
         "## Cada rotulo que muda\n",
         "| codigo | atributo | gold | antes | depois | veredito | motivo |",
         "|---|---|---|---|---|---|---|"]
    for m in sorted(mudancas, key=lambda m: (m["ver_antes"], m["campo"], m["codigo"])):
        L.append(f"| {m['codigo']} | {m['campo']} | "
                 f"{m['status_gold']}:{m['y_gold'] or '—'} | `{m['antes']}` | "
                 f"`{m['depois']}` | {m['ver_antes']} → {m['ver_depois']} | "
                 f"{m['motivo']} |")
    L.append("")
    mudou = {(m["codigo"], m["campo"]) for m in mudancas}
    resistentes = []
    for k in do_dicionario:
        if k in mudou:
            continue
        g, d = gold[k], atual[k]
        v = veredito(k[1], g["status"], g["y_gold"], d.get("valor"))
        if v in ("ERRO", "INVENCAO"):
            resistentes.append((k, g, d, v))
    if resistentes:
        L.append("## O que as travas NAO resolvem\n")
        for (cod, campo), g, d, v in resistentes:
            L.append(f"- **{cod} {campo}** ({v}): gold "
                     f"`{g['status']}:{ev.norm(campo, g['y_gold']) or '—'}`, "
                     f"pipeline `{d.get('valor')}`  \n"
                     f"  texto: {cand[cod]['DESCRICAO_LONGA'][:140]}")
        L.append("")
    if perda:
        L.append("## Os acertos perdidos, um por um\n")
        for m in perda:
            L.append(f"- **{m['codigo']} {m['campo']}** = `{m['antes']}` "
                     f"deixa de ser preenchido ({m['motivo']})  \n"
                     f"  texto: {m['texto'][:140]}")
        L.append("")
    Path(a.saida).write_text("\n".join(L) + "\n", encoding="utf-8")
    # mesmo conteudo em forma estruturada, para o gerador da apresentacao nao
    # ter de reparsear o .md
    Path(a.saida).with_suffix(".json").write_text(json.dumps({
        "rotulos_do_dicionario": len(do_dicionario), "mudam": len(mudancas),
        "antes": {k: v for k, v in antes.items()},
        "depois": {k: v for k, v in depois.items()},
        "metricas_antes": ma, "metricas_depois": md,
        "removidos": sum(melhora.values()), "acertos_perdidos": len(perda),
        "resistentes": [{"codigo": k[0], "campo": k[1], "veredito": v}
                        for (k, _g, _d, v) in resistentes],
        "dicionario": {
            "entradas": len(novo.entradas),
            "aplicaveis": sum(1 for e in novo.entradas.values() if not e.revisar),
            "sugestoes": sum(1 for e in novo.entradas.values() if e.revisar),
        },
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"\nrotulos decididos pelo dicionario: {len(do_dicionario)} | mudam: {len(mudancas)}")
    print(f"precisao  {ma['precisao']} -> {md['precisao']}")
    print(f"cobertura {ma['cobertura']} -> {md['cobertura']}")
    print(f"invencao  {ma['invencao']} -> {md['invencao']}")
    print(f"removidos {sum(melhora.values())} erros/invencoes | perdidos {len(perda)} acertos")
    print(f"\n{a.saida} gravado")


if __name__ == "__main__":
    main()
