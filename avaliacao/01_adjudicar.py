# -*- coding: utf-8 -*-
"""Adjudica as anotacoes independentes A e B e produz o conjunto-ouro.

Entradas:
  avaliacao/candidatos.csv                universo (item x campo) via campos_alvo
  avaliacao/anotacoes_{A1,A2}.jsonl       persona A (duas metades)
  avaliacao/anotacoes_{B1,B2}.jsonl       persona B (duas metades)

Alinhamento por (CODIGO_MATERIAL, campo). Comparacao sobre o rotulo NORMALIZADO:
  NCM -> so digitos; REFERENCIA_FABRICANTE -> so [A-Z0-9];
  demais -> maiusculo sem acento, espacos colapsados. Status comparado como esta.

Divergencia = valor normalizado diferente OU status diferente. Cada divergencia
exige uma entrada em ADJUDICACOES (decisao pessoal do adjudicador, com
justificativa propria); se faltar, o script ABORTA listando as pendencias —
ele nunca decide sozinho. Resultado da adjudicacao desta rodada: as 456
anotacoes de A e B coincidem em valor e status (0 divergencias); a revisao do
adjudicador foi por amostragem estratificada (plantados, typo, ancora_*,
faltante, abreviacao) contra candidatos.csv e dados/03_padrao_cadastro_PDM.xlsx.

Saidas:
  avaliacao/gold.csv           um rotulo por (item x campo), cobertura 100%
  avaliacao/concordancia.json  acordo bruto e kappa de Cohen por campo e global
"""
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

STATUS_VALIDOS = {"DEFINIDO", "AUSENTE", "INDEFINIVEL"}

# (CODIGO_MATERIAL, campo) -> decisao final do ADJUDICADOR para divergencias.
# Preencher manualmente apos reexaminar a linha crua e o PDM. Vazio nesta
# rodada: A e B nao divergiram em nenhum dos 456 pares.
ADJUDICACOES = {
    # ("12345678", "FABRICANTE"): {
    #     "y_gold": "...", "status": "DEFINIDO",
    #     "evidencia": "...", "justificativa": "decisao do adjudicador: ...",
    # },
}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def norm(campo, v):
    v = sem_acento(str(v or "")).upper().strip()
    if campo == "NCM":
        return re.sub(r"\D", "", v)
    if campo == "REFERENCIA_FABRICANTE":
        return re.sub(r"[^A-Z0-9]", "", v)
    return re.sub(r"\s+", " ", v)


def rotulo_combinado(campo, anot):
    """Categoria unica valor+status usada no acordo bruto e no kappa."""
    return anot["status"] + "|" + norm(campo, anot["y_gold"])


def carrega_anotador(nomes):
    d = {}
    for nome in nomes:
        arq = RAIZ / f"anotacoes_{nome}.jsonl"
        for i, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            linha = linha.strip()
            if not linha:
                continue
            r = json.loads(linha)
            if r["status"] not in STATUS_VALIDOS:
                sys.exit(f"{arq.name}:{i}: status invalido {r['status']!r}")
            k = (str(r["CODIGO_MATERIAL"]).strip(), r["campo"].strip())
            if k in d:
                sys.exit(f"{arq.name}:{i}: par duplicado {k}")
            d[k] = r
    return d


def kappa_cohen(pares):
    """pares: lista de (rotulo_a, rotulo_b). Kappa sobre o rotulo combinado."""
    n = len(pares)
    if n == 0:
        return None
    po = sum(a == b for a, b in pares) / n
    ca = Counter(a for a, _ in pares)
    cb = Counter(b for _, b in pares)
    pe = sum(ca[c] * cb.get(c, 0) for c in ca) / (n * n)
    if pe >= 1.0:  # categoria unica para ambos: kappa degenerado
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def resumo_anot(campo, anot):
    return anot["status"] + ":" + norm(campo, anot["y_gold"])


def main():
    # --- universo esperado -------------------------------------------------
    with open(RAIZ / "candidatos.csv", newline="", encoding="utf-8") as f:
        cand_rows = list(csv.DictReader(f))
    esperados = []   # (codigo, campo) na ordem do candidatos.csv
    estrato = {}
    for r in cand_rows:
        cod = str(r["CODIGO_MATERIAL"]).strip()
        estrato[cod] = r["estrato"]
        for campo in r["campos_alvo"].split("|"):
            campo = campo.strip()
            if campo:
                esperados.append((cod, campo))
    if len(esperados) != len(set(esperados)):
        sys.exit("candidatos.csv tem (codigo,campo) duplicado")

    # --- anotadores --------------------------------------------------------
    A = carrega_anotador(["A1", "A2"])
    B = carrega_anotador(["B1", "B2"])
    univ = set(esperados)
    for nome, d in (("A", A), ("B", B)):
        falta, sobra = univ - set(d), set(d) - univ
        if falta or sobra:
            sys.exit(f"anotador {nome}: faltam {sorted(falta)[:5]}... "
                     f"({len(falta)}) / sobram {sorted(sobra)[:5]}... ({len(sobra)})")

    # --- acordo e kappa por campo -------------------------------------------
    por_campo_pares = {}
    divergencias = []
    for k in esperados:
        cod, campo = k
        a, b = A[k], B[k]
        ra, rb = rotulo_combinado(campo, a), rotulo_combinado(campo, b)
        por_campo_pares.setdefault(campo, []).append((ra, rb))
        if ra != rb:
            divergencias.append(k)

    por_campo = {}
    for campo in sorted(por_campo_pares):
        pares = por_campo_pares[campo]
        acordo = sum(a == b for a, b in pares) / len(pares)
        por_campo[campo] = {"n": len(pares), "acordo": round(acordo, 4),
                            "kappa": round(kappa_cohen(pares), 4)}
    todos = [p for ps in por_campo_pares.values() for p in ps]
    glob = {"n": len(todos),
            "acordo": round(sum(a == b for a, b in todos) / len(todos), 4),
            "kappa": round(kappa_cohen(todos), 4)}

    print("=== acordo A x B por campo (rotulo combinado valor+status) ===")
    for campo, m in por_campo.items():
        print(f"  {campo:<22} n={m['n']:>3}  acordo={m['acordo']:.4f}  kappa={m['kappa']:.4f}")
    print(f"  {'GLOBAL':<22} n={glob['n']:>3}  acordo={glob['acordo']:.4f}  kappa={glob['kappa']:.4f}")
    print(f"\ndivergencias (valor normalizado ou status): {len(divergencias)}")
    for k in divergencias:
        a, b = A[k], B[k]
        print(f"  {k[0]} {k[1]}: A={resumo_anot(k[1], a)}  B={resumo_anot(k[1], b)}")

    # --- toda divergencia precisa de decisao pessoal do adjudicador ----------
    pendentes = [k for k in divergencias if k not in ADJUDICACOES]
    if pendentes:
        sys.exit(f"\n{len(pendentes)} divergencia(s) sem adjudicacao em "
                 f"ADJUDICACOES — reexamine candidatos.csv/PDM e preencha:\n"
                 + "\n".join(f"  {k}" for k in pendentes))
    for k, dec in ADJUDICACOES.items():
        if k not in divergencias:
            sys.exit(f"ADJUDICACOES contem par sem divergencia: {k}")

    # --- gold.csv ------------------------------------------------------------
    linhas = []
    for k in esperados:
        cod, campo = k
        a, b = A[k], B[k]
        base = {"CODIGO_MATERIAL": cod, "estrato": estrato[cod], "campo": campo,
                "anot_A": resumo_anot(campo, a), "anot_B": resumo_anot(campo, b)}
        if k in ADJUDICACOES:
            dec = ADJUDICACOES[k]
            linhas.append({**base, "y_gold": dec["y_gold"], "status": dec["status"],
                           "evidencia": dec["evidencia"],
                           "justificativa": dec["justificativa"],
                           "origem_decisao": "adjudicado", "confianca": "MEDIA"})
        else:
            linhas.append({**base, "y_gold": norm(campo, a["y_gold"]),
                           "status": a["status"], "evidencia": a["evidencia"],
                           "justificativa": a["justificativa"],
                           "origem_decisao": "acordo", "confianca": "ALTA"})

    cols = ["CODIGO_MATERIAL", "estrato", "campo", "y_gold", "status",
            "evidencia", "justificativa", "anot_A", "anot_B",
            "origem_decisao", "confianca"]
    with open(RAIZ / "gold.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(linhas)

    # --- concordancia.json ----------------------------------------------------
    exemplos = []
    for k in divergencias[:10]:
        dec = ADJUDICACOES[k]
        exemplos.append({"codigo": k[0], "campo": k[1],
                         "A": resumo_anot(k[1], A[k]), "B": resumo_anot(k[1], B[k]),
                         "decisao_final": f"{dec['status']}:{norm(k[1], dec['y_gold'])}"})
    conc = {"por_campo": por_campo, "global": glob,
            "divergencias_adjudicadas": len(divergencias),
            "exemplos_divergencia": exemplos}
    (RAIZ / "concordancia.json").write_text(
        json.dumps(conc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- sanidade --------------------------------------------------------------
    chaves = [(l["CODIGO_MATERIAL"], l["campo"]) for l in linhas]
    assert len(chaves) == len(set(chaves)), "gold.csv com (codigo,campo) duplicado"
    assert set(chaves) == univ, "gold.csv nao cobre 100% dos candidatos"
    for l in linhas:
        coerente = (l["status"] == "DEFINIDO") == (norm(l["campo"], l["y_gold"]) != "")
        assert l["status"] == "INDEFINIVEL" or coerente, f"status x y_gold incoerente: {l}"

    print("\n=== distribuicao de status por estrato (gold) ===")
    dist = Counter((l["estrato"], l["status"]) for l in linhas)
    estratos = sorted({e for e, _ in dist})
    for e in estratos:
        tot = sum(n for (ee, _), n in dist.items() if ee == e)
        det = "  ".join(f"{s}={dist[(e, s)]}" for s in
                        ("DEFINIDO", "AUSENTE", "INDEFINIVEL") if dist[(e, s)])
        frac_aus = dist[(e, "AUSENTE")] / tot
        print(f"  {e:<20} n={tot:>3}  {det}  (AUSENTE={frac_aus:.0%})")

    aus_falt = dist[("faltante", "AUSENTE")] / sum(
        n for (e, _), n in dist.items() if e == "faltante")
    if aus_falt < 0.5:
        print("\nALERTA: AUSENTE baixo no estrato 'faltante' "
              f"({aus_falt:.0%}) — investigar antes de usar o gold.")
    print(f"\ngold.csv: {len(linhas)} rotulos "
          f"({sum(1 for l in linhas if l['origem_decisao'] == 'acordo')} acordo, "
          f"{sum(1 for l in linhas if l['origem_decisao'] == 'adjudicado')} adjudicados) "
          "| concordancia.json gravado")


if __name__ == "__main__":
    main()
