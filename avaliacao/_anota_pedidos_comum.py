# -*- coding: utf-8 -*-
"""Mecanica comum das duas passadas de anotacao do gabarito de pedidos.

As passadas A e B gravam so DECISOES (um dict por ID_PEDIDO). Este modulo
expande cada decisao contra a aba ATRIBUTOS do PDM e emite o .jsonl no mesmo
formato das anotacoes que ja existem em avaliacao/:

  {"ID_PEDIDO", "id_pdm", "campo", "y_gold", "status", "evidencia", "justificativa"}

O campo especial _CLASSE leva o ID_PDM do item (ou FORA_DO_PDM).

Por que a expansao e automatica e a decisao nao
-----------------------------------------------
Quem anota decide a classe e o valor de cada caixa. QUAIS caixas existem e
obrigacao do PDM, nao escolha do anotador - e e exatamente onde da para errar
por descuido (esquecer ACABAMENTO num parafuso, ou anotar GRAO num disco de
CORTE, que nao se aplica). Por isso o modulo:

  - monta a lista de obrigatorios da classe anotada, a partir do PDM;
  - resolve os condicionais (QUANDO_SE_APLICA) pelas regras abaixo;
  - ABORTA se a decisao deixou de fora um obrigatorio que se aplica, ou se
    anotou um atributo que nao se aplica, ou um valor fora da lista permitida.

Nenhum artefato do pipeline e lido aqui.

Notacao dos valores na decisao
------------------------------
  "ACO CARBONO"  DEFINIDO: o texto traz esse valor sem ambiguidade
  ""             AUSENTE: o texto nao traz o valor; preencher e invencao
  "?"            INDEFINIVEL: o texto traz algo que nao decide entre dois
                 valores da lista ("aco inox" sem 304/316; "zincado" sem cor)

Para registrar a evidencia e o raciocinio, use uma tupla:
  ("10BAR", "6.000 psi", "6000 PSI / 14,5038 = 413,7 BAR")
       valor   evidencia   justificativa
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def norm(s: str) -> str:
    return sem_acento(s).strip().upper()


# --------------------------------------------------------------------- PDM ---
def _pdm_atributos() -> dict[str, list[dict]]:
    arq = REPO / "dados/03_padrao_cadastro_PDM.xlsx"
    if not arq.exists():
        arq = REPO / "03_padrao_cadastro_PDM.xlsx"
    a = pd.read_excel(arq, sheet_name="ATRIBUTOS", dtype=str).fillna("")
    ob = a[a["OBRIGATORIO"].str.upper() == "S"]
    fora: dict[str, list[dict]] = {}
    for cid, g in ob.groupby("ID_PDM"):
        linhas = []
        for _, r in g.sort_values("ORDEM", key=lambda s: s.astype(float)).iterrows():
            permitidos = [norm(v) for v in r["VALORES_PERMITIDOS"].split("|") if v.strip()]
            linhas.append({
                "atributo": r["ATRIBUTO"].strip(),
                "condicao": r["QUANDO_SE_APLICA"].strip(),
                "formato": r["FORMATO"].strip(),
                "permitidos": permitidos,
            })
        fora[cid] = linhas
    return fora


ATRIBUTOS = _pdm_atributos()
CLASSES = sorted(ATRIBUTOS)


def obrigatorios(id_pdm: str) -> list[dict]:
    if id_pdm not in ATRIBUTOS:
        sys.exit(f"ERRO: classe {id_pdm} nao existe na aba ATRIBUTOS do PDM")
    return ATRIBUTOS[id_pdm]


# ------------------------------------------------------------------ emissao ---
def _desdobra(v):
    """Aceita "VALOR", ("VALOR", evidencia) ou ("VALOR", evidencia, justificativa)."""
    if isinstance(v, tuple):
        v = list(v) + [""] * (3 - len(v))
        return str(v[0]), str(v[1]), str(v[2])
    return str(v), "", ""


def _status(valor: str) -> str:
    if valor == "?":
        return "INDEFINIVEL"
    if valor == "":
        return "AUSENTE"
    return "DEFINIDO"


def expande(decisoes: dict, passada: str, saida: Path) -> dict:
    """Expande DECISOES em rotulos e grava o .jsonl. Aborta em qualquer furo."""
    cand = pd.read_csv(RAIZ / "candidatos_pedidos.csv", dtype=str).fillna("")
    universo = list(cand["ID_PEDIDO"])
    faltando = [p for p in universo if p not in decisoes]
    sobrando = [p for p in decisoes if p not in universo]
    if faltando:
        sys.exit(f"ERRO ({passada}): {len(faltando)} pedido(s) sem decisao: "
                 + ", ".join(faltando[:12]) + ("..." if len(faltando) > 12 else ""))
    if sobrando:
        sys.exit(f"ERRO ({passada}): decisao para pedido fora do sorteio: {sobrando}")

    erros: list[str] = []
    linhas: list[dict] = []
    for pid in universo:
        d = decisoes[pid]
        classe = d["classe"]
        ev_classe = d.get("ev", "")
        just_classe = d.get("just", "")
        linhas.append({"ID_PEDIDO": pid, "id_pdm": classe, "campo": "_CLASSE",
                       "y_gold": classe,
                       "status": "DEFINIDO" if classe != "INDEFINIVEL" else "INDEFINIVEL",
                       "evidencia": ev_classe, "justificativa": just_classe})
        if classe in ("FORA_DO_PDM", "INDEFINIVEL"):
            if d.get("vals"):
                erros.append(f"{pid}: classe {classe} nao deve ter caixas anotadas")
            continue

        vals = dict(d.get("vals", {}))
        nao_aplica = {norm(x) for x in d.get("nao_aplica", [])}
        esperados = obrigatorios(classe)
        nomes = {norm(a["atributo"]) for a in esperados}

        for extra in vals:
            if norm(extra) not in nomes:
                erros.append(f"{pid}: atributo '{extra}' nao e obrigatorio em {classe}")

        for a in esperados:
            nome = a["atributo"]
            chave = next((k for k in vals if norm(k) == norm(nome)), None)
            if chave is None:
                if norm(nome) in nao_aplica:
                    continue
                if a["condicao"] and norm(a["condicao"]) != "SEMPRE":
                    erros.append(f"{pid}: '{nome}' ({classe}) e condicional "
                                 f"[{a['condicao']}] - anote o valor ou declare em "
                                 "nao_aplica")
                else:
                    erros.append(f"{pid}: '{nome}' ({classe}) obrigatorio sem rotulo")
                continue
            if norm(nome) in nao_aplica:
                erros.append(f"{pid}: '{nome}' esta em nao_aplica e tambem em vals")
                continue
            valor, evid, just = _desdobra(vals[chave])
            st = _status(valor)
            if st == "DEFINIDO" and a["permitidos"] and norm(valor) not in a["permitidos"]:
                erros.append(f"{pid}: '{nome}' = '{valor}' fora da lista do PDM "
                             f"({', '.join(a['permitidos'][:6])}...)")
            linhas.append({"ID_PEDIDO": pid, "id_pdm": classe, "campo": nome,
                           "y_gold": "" if st != "DEFINIDO" else valor, "status": st,
                           "evidencia": evid, "justificativa": just})

    if erros:
        print(f"ERRO ({passada}): {len(erros)} problema(s) na anotacao:", file=sys.stderr)
        for e in erros[:40]:
            print("  " + e, file=sys.stderr)
        if len(erros) > 40:
            print(f"  ... e {len(erros) - 40} outro(s)", file=sys.stderr)
        sys.exit(1)

    with saida.open("w", encoding="utf-8") as fh:
        for ln in linhas:
            fh.write(json.dumps(ln, ensure_ascii=False) + "\n")

    st = pd.Series([ln["status"] for ln in linhas]).value_counts().to_dict()
    campos = [ln for ln in linhas if ln["campo"] != "_CLASSE"]
    resumo = {
        "passada": passada, "pedidos": len(universo), "rotulos": len(linhas),
        "rotulos_de_caixa": len(campos), "status": st,
        "fora_do_pdm": sum(1 for ln in linhas
                           if ln["campo"] == "_CLASSE" and ln["y_gold"] == "FORA_DO_PDM"),
    }
    print(f"gravado {saida.name}: {len(linhas)} rotulos "
          f"({len(campos)} de caixa) em {len(universo)} pedidos")
    print("  status:", ", ".join(f"{k}={v}" for k, v in sorted(st.items())))
    print(f"  FORA_DO_PDM: {resumo['fora_do_pdm']}")
    ausentes = sum(1 for ln in campos if ln["status"] in ("AUSENTE", "INDEFINIVEL"))
    print(f"  AUSENTE+INDEFINIVEL em caixas: {ausentes} "
          f"({ausentes / max(len(campos), 1):.1%}) - sem esses nao se mede invencao")
    return resumo
