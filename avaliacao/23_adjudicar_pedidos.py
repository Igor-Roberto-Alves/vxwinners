# -*- coding: utf-8 -*-
"""Adjudica as passadas A e B do gabarito de pedidos e gera os gabaritos.

Entradas (todas em avaliacao/):
  candidatos_pedidos.csv       universo (120 pedidos, so linha crua)
  anotacoes_pedidos_A.jsonl    persona A: analista de cadastro (PDM ao pe da letra)
  anotacoes_pedidos_B.jsonl    persona B: suprimentos/almoxarifado (precisa comprar)

Cada divergencia exige uma decisao escrita em ADJUDICACOES. Faltando uma, o
script ABORTA listando as pendencias: ele nunca decide sozinho.

As duas leituras do gabarito (y_gold e permissivo)
--------------------------------------------------
Cinco divergencias sao a mesma pergunta: o pedido diz "eixo saida FLENDER
T6593-468134 do H3SH 9" e nao diz que H3SH 9 e um REDUTOR. A sabe que o texto
nao traz; B sabe que a frota so tem redutor com esse modelo.

Confirmado na planilha: o PDM lista APLICACAO e MODELO EQUIPAMENTO como listas
INDEPENDENTES, e nenhuma aba liga modelo a tipo de equipamento (a unica tabela
proxima, NCM_REFERENCIA, da o NCM por tipo, nao o tipo por modelo). Logo, do
pedido + PDM, APLICACAO esta AUSENTE: a deducao de B usa conhecimento que nao
esta em nenhuma das duas fontes.

Mas seria burro jogar essa informacao fora, porque na operacao B e quem esta
certo, e o dicionario aprendido do pipeline pode legitimamente fornecer o
mapeamento. Entao o gabarito carrega as DUAS leituras:

  y_gold / status   leitura ESTRITA: o que o texto do pedido sustenta
  permissivo        o valor que a deducao de B defende, quando existe

e o avaliador reporta a invencao nas duas: na estrita, preencher conta como
invencao; na permissiva, preencher conta como invencao SO SE o valor diferir do
permissivo. A diferenca entre as duas taxas e exatamente "quanto do que o
pipeline preenche vem de fora do texto".

Saidas: gold_pedidos.csv, gold_classe_pedidos.csv, concordancia_pedidos.json,
        revisao_humana_pedidos.csv

Uso: backend/.venv/bin/python avaliacao/23_adjudicar_pedidos.py
"""
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
SEED_REVISAO = 20261108
FRACAO_REVISAO = 0.10

# (ID_PEDIDO, campo) -> decisao final do ADJUDICADOR.
#   y_gold/status: a leitura estrita que vale como gabarito
#   permissivo:    valor que a leitura operacional defende (vazio quando nao ha)
#   motivo:        por escrito, sempre
ADJUDICACOES = {
    ("SC-202600453", "ACABAMENTO"): dict(
        y_gold="", status="INDEFINIVEL", permissivo="",
        confianca="ALTA", vence="A",
        motivo="'zinc plated' nao escolhe entre ZINCADO BRANCO e ZINCADO AMARELO, "
               "que sao dois valores da lista. Fechar no mais vendido e exatamente "
               "a invencao que este gabarito existe para pegar: nao ha permissivo."),

    # --- modelo do equipamento dado, tipo nao dito (5 casos, mesma pergunta) ---
    ("SC-202600120", "APLICACAO"): dict(
        y_gold="", status="AUSENTE", permissivo="REDUTOR",
        confianca="MEDIA", vence="A",
        motivo="o PDM nao liga modelo a tipo de equipamento em nenhuma aba, "
               "entao do texto + PDM a aplicacao esta ausente; H3SH 9 ser redutor "
               "Flender e conhecimento de frota, e fica como permissivo."),
    ("SC-202600335", "APLICACAO"): dict(
        y_gold="", status="AUSENTE", permissivo="BOMBA POLPA",
        confianca="MEDIA", vence="A",
        motivo="mesma razao: WARMAN 8/6 AH e bomba de polpa pelo catalogo Weir, "
               "nao pelo texto do pedido nem pelo PDM."),
    ("SC-202600023", "APLICACAO"): dict(
        y_gold="", status="AUSENTE", permissivo="ESCAVADEIRA HIDRAULICA",
        confianca="MEDIA", vence="A",
        motivo="mesma razao: '6030' e escavadeira Caterpillar pelo catalogo."),
    ("SC-202600348", "APLICACAO"): dict(
        y_gold="", status="AUSENTE", permissivo="CORREIA TRANSPORTADORA",
        confianca="MEDIA", vence="A",
        motivo="mesma razao: TC-04 e correia pela nomenclatura da planta. Este e o "
               "caso mais defensavel de B, porque TC-xx aparece na lista de modelos "
               "do PDM junto de outras correias - mas a lista nao declara o tipo."),
    ("SC-202600243", "APLICACAO"): dict(
        y_gold="", status="AUSENTE", permissivo="BOMBA CENTRIFUGA",
        confianca="MEDIA", vence="A",
        motivo="mesma razao: AHLSTAR e a linha de bomba centrifuga da Sulzer."),

    # --- valor de linha que o texto nao escreve ---
    ("SC-202600403", "TIPO"): dict(
        y_gold="", status="AUSENTE", permissivo="SEXTAVADA",
        confianca="MEDIA", vence="A",
        motivo="'porca' sozinha nao diz o tipo; que a sextavada seja o padrao de "
               "linha e pratica de compra, nao conteudo do pedido."),
    ("SC-202600252", "TIPO CABECA"): dict(
        y_gold="", status="AUSENTE", permissivo="CILINDRICA",
        confianca="MEDIA", vence="A",
        motivo="DIN 912 (cabeca cilindrica) e o default de catalogo do sextavado "
               "interno, mas o pedido nao cita norma nem cabeca."),
    ("SC-202600158", "LENTE"): dict(
        y_gold="", status="AUSENTE", permissivo="INCOLOR",
        confianca="BAIXA", vence="A",
        motivo="'AMPLA VISAO' e modelo comercial. O incolor e o mais provavel, mas "
               "oculos de ampla visao existem com lente cinza; confianca BAIXA e "
               "linha marcada para a conferencia humana."),

    # --- classe ---
    ("SC-202600087", "_CLASSE"): dict(
        y_gold="PDM050", status="DEFINIDO", permissivo="",
        confianca="MEDIA", vence="A",
        motivo="'pipe fitting ... socket weld, 6000#, A105' e inequivocamente uma "
               "conexao de tubulacao, e PDM050 e justamente a classe cujo "
               "substantivo vem de outra aba. O que falta e o SUBSTANTIVO, nao a "
               "classe - e substantivo nao e campo deste gabarito. B esta certo que "
               "nao da para cotar, mas isso e pendencia de cadastro, nao classe "
               "indefinivel."),

    # --- termo fora do vocabulario do PDM ---
    ("SC-202600141", "TERMINAL A"): dict(
        y_gold="FEMEA RETA JIC", status="DEFINIDO", permissivo="",
        confianca="MEDIA", vence="A",
        motivo="'swivel' qualifica a porca giratoria, nao a geometria; a lista do "
               "PDM so separa RETA de CURVA, e sem angulo declarado e reta. "
               "Linha marcada para a conferencia humana."),
}


def le_jsonl(nome: str) -> dict:
    fora = {}
    with (RAIZ / nome).open(encoding="utf-8") as fh:
        for ln in fh:
            r = json.loads(ln)
            fora[(r["ID_PEDIDO"], r["campo"])] = r
    return fora


def rotulo(r: dict | None) -> str:
    if r is None:
        return "SEM_ROTULO"
    return f"{r['status']}:{r['y_gold']}"


def kappa(pares: list[tuple[str, str]]) -> tuple[float, float]:
    """Acordo bruto e kappa de Cohen de uma lista de (rotulo_A, rotulo_B)."""
    n = len(pares)
    if n == 0:
        return float("nan"), float("nan")
    po = sum(1 for a, b in pares if a == b) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    k = 1.0 if pe == 1 else (po - pe) / (1 - pe)
    return po, k


def main() -> None:
    cand = pd.read_csv(RAIZ / "candidatos_pedidos.csv", dtype=str).fillna("")
    estrato = dict(zip(cand["ID_PEDIDO"], cand["estrato"]))
    familia = dict(zip(cand["ID_PEDIDO"], cand["familia_prevista"]))
    estilo = dict(zip(cand["ID_PEDIDO"], cand["estilo"]))
    armadilhas = dict(zip(cand["ID_PEDIDO"], cand["armadilhas"]))

    A = le_jsonl("anotacoes_pedidos_A.jsonl")
    B = le_jsonl("anotacoes_pedidos_B.jsonl")
    chaves = sorted(set(A) | set(B))

    divergentes = [k for k in chaves if rotulo(A.get(k)) != rotulo(B.get(k))]

    # Divergencia por CONSEQUENCIA da classe, nao por julgamento proprio: quando a
    # adjudicacao do _CLASSE escolhe a classe de uma das passadas, as caixas que so
    # aquela passada anotou vem com ela. Em SC-202600087, B marcou a classe
    # INDEFINIVEL e por isso nao anotou caixa nenhuma; adjudicado PDM050 (de A), as
    # 4 caixas de A seguem. Exigir uma "decisao do adjudicador" para cada uma seria
    # inventar julgamento onde houve um so.
    classe_final = {}
    for pid in {k[0] for k in chaves}:
        adj_cls = ADJUDICACOES.get((pid, "_CLASSE"))
        r = A.get((pid, "_CLASSE")) or B.get((pid, "_CLASSE"))
        classe_final[pid] = adj_cls["y_gold"] if adj_cls else (r["y_gold"] if r else "")

    consequencia = {}
    for k in list(divergentes):
        pid, campo = k
        if campo == "_CLASSE":
            continue
        ra, rb = A.get(k), B.get(k)
        if (ra is None) == (rb is None):      # os dois anotaram: divergencia real
            continue
        presente = ra or rb
        if presente["id_pdm"] == classe_final[pid]:
            consequencia[k] = presente
            divergentes.remove(k)

    faltam = [k for k in divergentes if k not in ADJUDICACOES]
    if faltam:
        print(f"ERRO: {len(faltam)} divergencia(s) sem decisao do adjudicador:",
              file=sys.stderr)
        for pid, campo in faltam:
            print(f"  {pid} / {campo}: A={rotulo(A.get((pid, campo)))} "
                  f"B={rotulo(B.get((pid, campo)))}", file=sys.stderr)
        sys.exit(1)
    sobrando = [k for k in ADJUDICACOES if k not in divergentes]
    if sobrando:
        print(f"ERRO: ADJUDICACOES traz {len(sobrando)} caso(s) que nao divergiram: "
              f"{sobrando}", file=sys.stderr)
        sys.exit(1)

    # ---------------------------------------------------------- concordancia ---
    # As caixas que mudaram por CONSEQUENCIA da classe ficam fora do kappa: elas
    # nao sao julgamentos separados, e contar as 4 caixas de SC-202600087 como 4
    # discordancias multiplicaria por quatro uma unica decisao (a da classe), que
    # ja entra no kappa de _CLASSE.
    por_campo: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for k in chaves:
        if k in consequencia:
            continue
        por_campo[k[1]].append((rotulo(A.get(k)), rotulo(B.get(k))))
    conc = {"passadas": {"A": "analista de cadastro (PDM ao pe da letra)",
                         "B": "suprimentos/almoxarifado (precisa comprar)"},
            "aviso_independencia":
                "A e B sao duas passadas do MESMO anotador (um LLM) sob regras de "
                "decisao diferentes, NAO dois anotadores independentes. O kappa mede "
                "quanto a regra muda o rotulo, nao concordancia entre duas cabecas. "
                "A salvaguarda e revisao_humana_pedidos.csv.",
            "nota_consequencia":
                f"{len(consequencia)} rotulo(s) ficaram fora do kappa: sao caixas que "
                "uma passada nao anotou por ter dado outra classe ao item. Contar cada "
                "uma como discordancia multiplicaria uma unica decisao (a da classe).",
            "por_campo": {}, "global": {}}
    for campo, pares in sorted(por_campo.items()):
        po, k = kappa(pares)
        conc["por_campo"][campo] = {"n": len(pares), "acordo_bruto": round(po, 4),
                                    "kappa": round(k, 4)}
    todos = [p for pares in por_campo.values() for p in pares]
    po, k = kappa(todos)
    conc["global"] = {"n": len(todos), "acordo_bruto": round(po, 4),
                      "kappa": round(k, 4), "divergencias": len(divergentes),
                      "adjudicadas": len(ADJUDICACOES)}
    sem_classe = [p for c, pares in por_campo.items() if c != "_CLASSE" for p in pares]
    po2, k2 = kappa(sem_classe)
    conc["global_sem_classe"] = {"n": len(sem_classe), "acordo_bruto": round(po2, 4),
                                 "kappa": round(k2, 4)}
    (RAIZ / "concordancia_pedidos.json").write_text(
        json.dumps(conc, ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------- gold ---
    COLS = ["ID_PEDIDO", "estrato", "familia_prevista", "estilo", "armadilhas",
            "id_pdm", "campo", "y_gold", "status", "permissivo", "evidencia",
            "justificativa", "anot_A", "anot_B", "origem_decisao", "confianca",
            "motivo_adjudicacao"]
    gold_caixa, gold_classe = [], []
    for k in chaves:
        pid, campo = k
        ra, rb = A.get(k), B.get(k)
        base = ra or rb
        adj = ADJUDICACOES.get(k)
        if adj:
            y, st, perm = adj["y_gold"], adj["status"], adj["permissivo"]
            origem, conf, motivo = "adjudicado", adj["confianca"], adj["motivo"]
        elif k in consequencia:
            c = consequencia[k]
            y, st, perm = c["y_gold"], c["status"], ""
            origem, conf = "consequencia_da_classe", "ALTA"
            motivo = (f"a passada que nao anotou esta caixa deu outra classe ao item; "
                      f"adjudicada a classe {classe_final[pid]}, o rotulo vem com ela")
        else:
            y, st, perm = base["y_gold"], base["status"], ""
            origem, conf, motivo = "acordo", "ALTA", ""
        linha = {
            "ID_PEDIDO": pid, "estrato": estrato[pid],
            "familia_prevista": familia[pid], "estilo": estilo[pid],
            "armadilhas": armadilhas[pid], "id_pdm": base["id_pdm"], "campo": campo,
            "y_gold": y, "status": st, "permissivo": perm,
            "evidencia": base["evidencia"], "justificativa": base["justificativa"],
            "anot_A": rotulo(ra), "anot_B": rotulo(rb),
            "origem_decisao": origem, "confianca": conf, "motivo_adjudicacao": motivo,
        }
        (gold_classe if campo == "_CLASSE" else gold_caixa).append(linha)

    for nome, linhas in [("gold_pedidos.csv", gold_caixa),
                         ("gold_classe_pedidos.csv", gold_classe)]:
        with (RAIZ / nome).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            w.writerows(sorted(linhas, key=lambda r: (r["ID_PEDIDO"], r["campo"])))

    # --------------------------------------------------------- revisao humana ---
    todas = gold_classe + gold_caixa
    marcadas = {(r["ID_PEDIDO"], r["campo"]) for r in todas
                if r["status"] in ("INDEFINIVEL", "AUSENTE")
                or r["origem_decisao"] == "adjudicado"
                or r["confianca"] in ("MEDIA", "BAIXA")}
    resto = [r for r in todas if (r["ID_PEDIDO"], r["campo"]) not in marcadas]
    rnd = random.Random(SEED_REVISAO)
    amostra = rnd.sample(resto, k=max(1, round(len(resto) * FRACAO_REVISAO)))
    revisao = [r for r in todas if (r["ID_PEDIDO"], r["campo"]) in marcadas] + amostra
    texto = dict(zip(cand["ID_PEDIDO"],
                     (cand["TEXTO_SOLICITACAO"].str.strip() + " || "
                      + cand["CONTEUDO_ANEXO"].str.strip()).str.strip(" |")))
    COLS_REV = ["ID_PEDIDO", "texto_do_pedido", "id_pdm", "campo", "y_gold_proposto",
                "status_proposto", "permissivo", "por_que_entrou", "motivo_adjudicacao",
                "confianca", "CONCORDO_S_N", "VALOR_CERTO", "STATUS_CERTO",
                "COMENTARIO"]
    with (RAIZ / "revisao_humana_pedidos.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS_REV, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in sorted(revisao, key=lambda r: (r["ID_PEDIDO"], r["campo"])):
            porque = ("adjudicada" if r["origem_decisao"] == "adjudicado"
                      else r["status"].lower() if r["status"] != "DEFINIDO"
                      else f"amostra de {FRACAO_REVISAO:.0%}")
            w.writerow({
                "ID_PEDIDO": r["ID_PEDIDO"],
                "texto_do_pedido": texto.get(r["ID_PEDIDO"], "")[:300],
                "id_pdm": r["id_pdm"], "campo": r["campo"],
                "y_gold_proposto": r["y_gold"], "status_proposto": r["status"],
                "permissivo": r["permissivo"], "por_que_entrou": porque,
                "motivo_adjudicacao": r["motivo_adjudicacao"],
                "confianca": r["confianca"], "CONCORDO_S_N": "", "VALOR_CERTO": "",
                "STATUS_CERTO": "", "COMENTARIO": ""})

    # ------------------------------------------------------------------ saida ---
    print(f"gold_pedidos.csv:        {len(gold_caixa)} rotulos de caixa")
    print(f"gold_classe_pedidos.csv: {len(gold_classe)} rotulos de classe")
    print(f"revisao_humana_pedidos.csv: {len(revisao)} linhas "
          f"({len(marcadas)} marcadas + {len(amostra)} de amostra)")
    print(f"\ndivergencias: {len(divergentes)} (todas adjudicadas, com motivo escrito)")
    print(f"acordo bruto global: {conc['global']['acordo_bruto']:.1%}  "
          f"kappa {conc['global']['kappa']:.3f}")
    print(f"  sem _CLASSE:       {conc['global_sem_classe']['acordo_bruto']:.1%}  "
          f"kappa {conc['global_sem_classe']['kappa']:.3f}")
    print("\npor campo (so os que divergiram):")
    for campo, v in sorted(conc["por_campo"].items()):
        if v["acordo_bruto"] < 1:
            print(f"  {campo:24s} n={v['n']:3d}  acordo {v['acordo_bruto']:.1%}  "
                  f"kappa {v['kappa']:.3f}")
    perm = sum(1 for r in todas if r["permissivo"])
    print(f"\nrotulos com leitura permissiva: {perm} "
          "(o avaliador reporta invencao estrita e permissiva)")
    st = Counter(r["status"] for r in gold_caixa)
    print("status das caixas:", ", ".join(f"{k}={v}" for k, v in sorted(st.items())))


if __name__ == "__main__":
    main()
