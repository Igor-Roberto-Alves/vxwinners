# -*- coding: utf-8 -*-
"""Mede, contra o gabarito, o efeito de um piso de probabilidade POR PALAVRA no BERT.

Uso:
  uv run --no-project --with pandas --with openpyxl --with torch --with transformers \
      python avaliacao/19_efeito_piso_bert.py \
      [--pisos 0,0.3,0.4,0.5,0.6] [--saida avaliacao/efeito_piso_bert.md]

O que esta sendo medido
-----------------------
O limiar que existia era `LIMIAR_BERT = 0,60` (arbitro.py), aplicado sobre a
MEDIA das probabilidades do span. Media dilui a palavra fraca: o span
'INOX 316 EXTREMIDADES', com 0,88 / 0,99 / 0,31, da 0,73 e passa o corte - e o
que o barrou foi o enum do PDM, nao o limiar. Em caixa LIVRE (part number,
modelo) nao existe enum para barrar, e o limiar fica sozinho.

O piso novo (`ExtratorBert.prever(piso=...)`) corta ANTES de agrupar: palavra
cujo rotulo mais provavel nao alcanca o piso vira O, o que FECHA o span em vez
de engolir a palavra duvidosa.

Como mede
---------
Reexecuta o pipeline de verdade, sem LLM e com o dicionario CONGELADO, nos 232
codigos do conjunto-ouro de caracteristicas - uma vez por piso - e aplica a
MESMA comparacao do avaliador oficial (importa evaluate_caracteristicas e reusa
`norm`, `valor_igual` e `wilson`, em vez de reimplementar a tolerancia de
grandeza e pressao).

O piso 0,0 e a execucao de referencia: ele reproduz o comportamento atual, e a
tabela mostra a diferenca contra ele. Nada em artefatos/ e tocado.

Limites declarados:
  - o LLM fica de fora (desempates e deteccoes do artefato continuam sendo
    aplicados, porque e assim que a execucao de referencia foi produzida);
  - sao 232 codigos, nao a base inteira: o intervalo de Wilson diz quanto a
    amostra sustenta.
"""
import argparse
import csv
import importlib.util
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
sys.path.insert(0, str(REPO / "src"))

ART = REPO / "artefatos"


def carrega_avaliador():
    """Reusa a comparacao de valores do avaliador oficial, sem copiar nada."""
    spec = importlib.util.spec_from_file_location(
        "aval_caract", RAIZ / "evaluate_caracteristicas.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["aval_caract"] = m
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pisos", default="0,0.3,0.4,0.5,0.6",
                    help="pisos a comparar; 0 e a execucao de referencia")
    ap.add_argument("--saida", default=str(RAIZ / "efeito_piso_bert.md"))
    ap.add_argument("--gold", default=str(RAIZ / "gold_caracteristicas.csv"))
    ap.add_argument("--amostra", type=int, default=2000,
                    help="registros aleatorios da base para medir o alcance do piso "
                         "fora do gabarito (0 desliga)")
    a = ap.parse_args()

    aval = carrega_avaliador()
    from saneamento import Arbitro, ExtratorBert, Pdm, Pipeline, Validador
    from saneamento.aprendizado import Aprendizado
    from saneamento.dados import ler_base
    from saneamento.pipeline import carregar_desempates, carregar_deteccoes

    with open(a.gold, newline="", encoding="utf-8") as f:
        gold = list(csv.DictReader(f))
    codigos = {g["CODIGO_MATERIAL"] for g in gold}

    pdm = Pdm.carregar(ART / "pdm.json")
    registros = [r for r in ler_base(REPO / "dados/01_base_materiais.xlsx")
                 if str(r.get("CODIGO_MATERIAL", "")).strip() in codigos]
    desempates = carregar_desempates(ART / "desempate_llm.jsonl")
    deteccoes = carregar_deteccoes(ART / "deteccao_ausentes.jsonl")

    print(f"gold: {len(gold)} rotulos em {len(codigos)} codigos "
          f"({len(registros)} achados na base)")
    print(f"desempates do LLM: {len(desempates)} · deteccoes: {len(deteccoes)}")

    pisos = [float(x) for x in a.pisos.split(",")]
    bert = ExtratorBert(pdm.nomes_atributos).carregar(ART / "modelo_bert")
    linhas, por_piso, guarda_decisoes = [], {}, {}

    for piso in pisos:
        bert.piso_palavra = piso
        # congelado=True: medir nao pode alterar artefatos/aprendizado.json
        aprendizado = Aprendizado(ART / "aprendizado.json", pdm=pdm, congelado=True)
        pipe = Pipeline(pdm, bert=bert, llm=None,
                        arbitro=Arbitro(Validador(pdm)), aprendizado=aprendizado,
                        desempates=desempates, deteccoes=deteccoes)
        t0 = time.time()
        decisoes = {}
        for r in registros:
            res = pipe.processar(r)
            # res.decisoes e dict[nome] -> Decisao (dataclass)
            decisoes[str(r["CODIGO_MATERIAL"]).strip()] = {
                nome: {"valor": d.valor, "fonte": d.fonte, "estado": d.estado,
                       "motivo": d.motivo or ""}
                for nome, d in res.decisoes.items()}
        dt = time.time() - t0

        c = Counter()
        fontes_erro = Counter()
        # recorte dos campos sem enum (part number, modelo): ali o validador nao
        # tem lista para recusar nada, e o corte de probabilidade e a unica trava
        c_codigo = Counter()
        for g in gold:
            cod, campo = g["CODIGO_MATERIAL"], g["campo"]
            d = decisoes.get(cod, {}).get(campo)
            valor = aval.norm(campo, (d or {}).get("valor") or "")
            alvo = aval.norm(campo, g["y_gold"])
            if g["status"] == "DEFINIDO":
                v = ("ABSTEVE" if valor == "" else
                     "ACERTO" if aval.valor_igual(campo, alvo, valor) else "ERRO")
            else:
                v = "ABSTENCAO_CORRETA" if valor == "" else "INVENCAO"
            c[v] += 1
            if campo in aval.CAMPOS_CODIGO:
                c_codigo[v] += 1
            if v in ("ERRO", "INVENCAO"):
                fontes_erro[(d or {}).get("fonte", "-")] += 1

        # ruido que o BERT manda para o canonizador: trecho recortado que o enum
        # recusou. Nao e erro medido contra o gold, e trabalho que o LLM paga.
        # O estado nao serve de filtro (a proposta fora da lista e descartada
        # antes do arbitro, em pipeline._do_bert): o que sobra e o motivo.
        invalidos = sum(1 for dec in decisoes.values() for d in dec.values()
                        if "recusado pelo validador" in d["motivo"]
                        or "BERT recortou" in d["motivo"])
        guarda_decisoes[piso] = decisoes

        definidos = c["ACERTO"] + c["ERRO"] + c["ABSTEVE"]
        afirmados = c["ACERTO"] + c["ERRO"]
        ausentes = c["ABSTENCAO_CORRETA"] + c["INVENCAO"]
        prec, lo, hi = aval.wilson(c["ACERTO"], afirmados)
        cob = afirmados / definidos if definidos else 0.0
        inv = c["INVENCAO"] / ausentes if ausentes else 0.0
        afirm_cod = c_codigo["ACERTO"] + c_codigo["ERRO"]
        prec_cod = c_codigo["ACERTO"] / afirm_cod if afirm_cod else 0.0
        por_piso[piso] = dict(c=c, prec=prec, lo=lo, hi=hi, cob=cob, inv=inv,
                              fontes_erro=fontes_erro, segundos=dt,
                              c_codigo=c_codigo, prec_cod=prec_cod,
                              invalidos=invalidos)
        linhas.append((piso, c, prec, lo, hi, cob, inv, dt))
        print(f"  piso {piso:.2f}: precisao {prec:6.1%} [{lo:.0%}-{hi:.0%}] "
              f"cobertura {cob:6.1%} invencao {inv:6.1%} "
              f"(acerto {c['ACERTO']}, erro {c['ERRO']}, absteve {c['ABSTEVE']}, "
              f"invencao {c['INVENCAO']}) · campos de codigo: precisao "
              f"{prec_cod:5.1%} ({afirm_cod} afirmados) · trechos recusados pelo "
              f"enum: {invalidos} · {dt:.0f}s")

    base = por_piso[pisos[0]]
    md = ["# Efeito do piso de probabilidade por palavra no BERT", "",
          f"Gabarito: `{Path(a.gold).name}` — {len(gold)} rótulos em {len(codigos)} códigos.",
          "Pipeline reexecutado por piso, sem LLM, dicionário congelado; desempates e",
          "detecções do artefato aplicados, como na execução de referência.", "",
          "| piso | precisão | IC 95% | cobertura | invenção | acerto | erro | absteve | invenção |",
          "|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for piso, c, prec, lo, hi, cob, inv, _ in linhas:
        md.append(f"| {piso:.2f} | {prec:.1%} | {lo:.0%}–{hi:.0%} | {cob:.1%} | {inv:.1%} | "
                  f"{c['ACERTO']} | {c['ERRO']} | {c['ABSTEVE']} | {c['INVENCAO']} |")
    md += ["", "## Diferença contra o piso 0,00 (comportamento atual)", "",
           "| piso | Δ precisão | Δ cobertura | Δ erros | Δ abstenções | Δ invenções |",
           "|---:|---:|---:|---:|---:|---:|"]
    for piso in pisos[1:]:
        p = por_piso[piso]
        md.append(f"| {piso:.2f} | {p['prec'] - base['prec']:+.1%} | "
                  f"{p['cob'] - base['cob']:+.1%} | "
                  f"{p['c']['ERRO'] - base['c']['ERRO']:+d} | "
                  f"{p['c']['ABSTEVE'] - base['c']['ABSTEVE']:+d} | "
                  f"{p['c']['INVENCAO'] - base['c']['INVENCAO']:+d} |")
    md += ["", "## Campos sem enum (part number, modelo) e ruído para o canonizador", "",
           "Nos campos de código o validador não tem lista para recusar nada: o corte de",
           "probabilidade é a única trava. A última coluna conta o trecho que o BERT recortou",
           "e o enum recusou — não é erro contra o gabarito, é trabalho que o LLM paga depois.", "",
           "| piso | precisão nos campos de código | afirmados | trechos recusados pelo enum |",
           "|---:|---:|---:|---:|"]
    for piso in pisos:
        p = por_piso[piso]
        afirm = p["c_codigo"]["ACERTO"] + p["c_codigo"]["ERRO"]
        md.append(f"| {piso:.2f} | {p['prec_cod']:.1%} | {afirm} | {p['invalidos']} |")
    # --- alcance: quantas decisoes o piso muda fora do gold -------------------
    # O gold tem 232 codigos e mede qualidade. Esta parte mede ALCANCE: numa
    # amostra maior da base, quantas decisoes trocam de valor por causa do piso.
    # Sem isso a leitura "nao mudou nada" fica sem tamanho: pode ser que o piso
    # seja inofensivo, ou que ele quase nunca dispare.
    md += ["", "## Alcance fora do gabarito", ""]
    if a.amostra > 0 and len(pisos) > 1:
        import random
        rng = random.Random(42)
        todos = ler_base(REPO / "dados/01_base_materiais.xlsx")
        amostra = rng.sample(todos, min(a.amostra, len(todos)))
        print(f"\nalcance numa amostra de {len(amostra)} registros da base:")
        md += [f"Amostra aleatória de {len(amostra)} registros (semente 42), fora do gabarito.",
               "",
               "`trocou` é o efeito que não era esperado: quando o piso derruba o recorte do",
               "BERT, a caixa não fica vazia — outra camada (regra léxica, ordem do PDM,",
               "dicionário) assume e pode gravar um valor DIFERENTE. O piso muda quem decide,",
               "não só quanto se afirma.", "",
               "| piso | decisões que mudaram | registros afetados | sumiram | trocaram | (destas, encurtaram) | surgiram |",
               "|---:|---:|---:|---:|---:|---:|---:|"]
        blocos = []
        ref = None
        for piso in pisos:
            bert.piso_palavra = piso
            pipe = Pipeline(pdm, bert=bert, llm=None, arbitro=Arbitro(Validador(pdm)),
                            aprendizado=Aprendizado(ART / "aprendizado.json", pdm=pdm,
                                                    congelado=True),
                            desempates=desempates, deteccoes=deteccoes)
            atual = {}
            for r in amostra:
                res = pipe.processar(r)
                atual[str(r["CODIGO_MATERIAL"]).strip()] = {
                    n: (d.valor or "") for n, d in res.decisoes.items()}
            if ref is None:
                ref = atual
                md.append(f"| {piso:.2f} | — (referência) | — | — | — | — | — |")
                continue
            mudou = sumiu = trocou = encurtou = surgiu = 0
            afetados = set()
            exemplos = {"sumiu": [], "trocou": []}
            for cod, caixas in atual.items():
                for nome, v in caixas.items():
                    antes = ref.get(cod, {}).get(nome, "")
                    if v == antes:
                        continue
                    mudou += 1
                    afetados.add(cod)
                    if antes and not v:
                        sumiu += 1
                        if len(exemplos["sumiu"]) < 5:
                            exemplos["sumiu"].append((cod, nome, antes, v))
                    elif antes and v:
                        trocou += 1
                        if len(v) < len(antes):
                            encurtou += 1
                        if len(exemplos["trocou"]) < 5:
                            exemplos["trocou"].append((cod, nome, antes, v))
                    else:
                        surgiu += 1
            print(f"  piso {piso:.2f}: {mudou} decisões mudaram em {len(afetados)} registros "
                  f"({sumiu} sumiram, {trocou} trocaram de valor, {surgiu} surgiram)")
            md.append(f"| {piso:.2f} | {mudou} | {len(afetados)} | {sumiu} | {trocou} | "
                      f"{encurtou} | {surgiu} |")
            bloco = [f"", f"Exemplos com piso {piso:.2f}:", ""]
            for tipo, titulo in (("sumiu", "a caixa ficou vazia"),
                                 ("trocou", "outra camada assumiu e gravou outro valor")):
                for c, n, antes, depois in exemplos[tipo]:
                    bloco.append(f"- {titulo} · `{c}` · {n}: "
                                 f"`{antes or '(vazio)'}` → `{depois or '(vazio)'}`")
            blocos.append(bloco)
        for b in blocos:          # exemplos depois da tabela, nao no meio dela
            md += b
    md += ["", "## De onde vêm os erros e as invenções que sobram", ""]
    for piso in pisos:
        fe = por_piso[piso]["fontes_erro"]
        md.append(f"- piso {piso:.2f}: " + (", ".join(
            f"`{k}` {v}" for k, v in fe.most_common(6)) or "nenhum"))
    Path(a.saida).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\n{a.saida}")


if __name__ == "__main__":
    main()
