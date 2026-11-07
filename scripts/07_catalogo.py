"""Monta o catalogo final: todos os itens cadastrados no padrao do PDM.

Gera um xlsx com:

  RESUMO            indicadores antes/depois
  CATALOGO          um item por linha: descricao no padrao, unidade, NCM, acao de juncao
  PDM001 ... PDM110 uma aba por classe, com as CARACTERISTICAS em colunas,
                    na ordem que a aba ATRIBUTOS do PDM define
  CARACTERISTICAS   formato longo (codigo, atributo, valor, fonte, banda) para auditoria
  PENDENCIAS        o que falta em cada item, atributo por atributo
  JUNCOES           plano de bloqueio: codigo, acao, usar <codigo>

Pre-requisitos: scripts/04_extrair.py e scripts/06_juntar.py ja executados.

Uso: python 07_catalogo.py [--saida artefatos/catalogo_final.xlsx]
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, ler_base  # noqa: E402
from saneamento.caixas import tipo_da_caixa  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--saida", default=None)
a = p.parse_args()

ART = Path(a.artefatos)
SAIDA = Path(a.saida or ART / "catalogo_final.xlsx")

for obrigatorio in ("saneado_base.csv", "decisoes_base.jsonl"):
    if not (ART / obrigatorio).exists():
        sys.exit(f"{ART / obrigatorio} nao existe: rode scripts/04_extrair.py primeiro")

pdm = Pdm.carregar(ART / "pdm.json")

# ------------------------------------------------------------------ carga

print("Lendo artefatos...")
with (ART / "saneado_base.csv").open(encoding="utf-8") as fh:
    san = {r["CODIGO_MATERIAL"]: r for r in csv.DictReader(fh)}

decisoes: dict[str, list[dict]] = {}
with (ART / "decisoes_base.jsonl").open(encoding="utf-8") as fh:
    for linha in fh:
        d = json.loads(linha)
        decisoes[d["codigo"]] = d["decisoes"]

juncao: dict[str, dict] = {}
arq_juncao = ART / "plano_juncao.csv"
if arq_juncao.exists():
    with arq_juncao.open(encoding="utf-8") as fh:
        juncao = {r["CODIGO"]: r for r in csv.DictReader(fh)}

orig = {r["CODIGO_MATERIAL"]: r for r in ler_base(a.base)}
print(f"  {len(san)} registros saneados, {len(juncao)} em plano de juncao")


def num(s):
    try:
        return float(str(s or "0").strip() or 0)
    except ValueError:
        return 0.0


# ------------------------------------------------------------------ planilha

import openpyxl  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

wb = openpyxl.Workbook()
CABECALHO = Font(bold=True, color="FFFFFF")
FUNDO = PatternFill("solid", fgColor="1F4E5F")
FUNDO_PEND = PatternFill("solid", fgColor="FDE9D9")


def formatar(ws, n_colunas, larguras=None):
    for c in range(1, n_colunas + 1):
        cel = ws.cell(row=1, column=c)
        cel.font = CABECALHO
        cel.fill = FUNDO
        cel.alignment = Alignment(vertical="center", wrap_text=False)
        ws.column_dimensions[get_column_letter(c)].width = (
            larguras[c - 1] if larguras and c - 1 < len(larguras) else 18
        )
    ws.freeze_panes = "A2"


# ---------------------------------------------------------------- CATALOGO

print("Aba CATALOGO...")
ws = wb.active
ws.title = "CATALOGO"
cols = ["CODIGO_MATERIAL", "ESTADO", "ACAO", "USAR_CODIGO", "ID_PDM", "SUJEITO",
        "GRUPO_MERCADORIA", "DESCRICAO_PDM", "DESCRICAO_CURTA_PDM",
        "UNIDADE_PDM", "UNIDADE_ORIGINAL", "NCM_PDM", "NCM_ORIGINAL",
        "FABRICANTE", "REFERENCIA_FABRICANTE", "COMPLETUDE", "N_PENDENCIAS",
        "PENDENTES", "CHAVE_IDENTIDADE", "DESCRICAO_ORIGINAL"]
ws.append(cols)
for cod, r in san.items():
    j = juncao.get(cod, {})
    o = orig.get(cod, {})
    sujeito = f"{r.get('SUBSTANTIVO','')} {r.get('QUALIFICADOR','')}".strip()
    pend = r.get("PENDENTES", "")
    ws.append([
        cod, r["ESTADO"], j.get("ACAO", ""), j.get("USAR", ""),
        r["ID_PDM"], sujeito, o.get("GRUPO_MERCADORIA", ""),
        r["DESCRICAO_PDM"], r["DESCRICAO_CURTA_PDM"],
        r["UNIDADE_PDM"], r["UNIDADE_ORIGINAL"], r["NCM_PDM"], r["NCM_ORIGINAL"],
        o.get("FABRICANTE", ""), o.get("REFERENCIA_FABRICANTE", ""),
        num(r["COMPLETUDE"]), len([x for x in pend.split(" | ") if x]), pend,
        r["CHAVE_IDENTIDADE"], r["DESCRICAO_ORIGINAL"],
    ])
formatar(ws, len(cols), [14, 15, 13, 12, 9, 26, 10, 70, 42, 12, 12, 12, 12,
                         16, 20, 11, 12, 34, 50, 60])

# ---------------------------------------------------------------- uma aba por classe

print("Abas por classe (caracteristicas em colunas)...")
por_classe: dict[str, list[str]] = defaultdict(list)
for cod, r in san.items():
    if r["ID_PDM"]:
        por_classe[r["ID_PDM"]].append(cod)

for cid in sorted(por_classe):
    classe = pdm.classes[cid]
    codigos = por_classe[cid]
    atributos = sorted(classe.atributos, key=lambda x: x.ordem)
    nomes = [at.nome for at in atributos]

    ws = wb.create_sheet(cid[:31])
    # cabecalho mostra tambem se o atributo e obrigatorio e de que tipo
    ws.append(["CODIGO", "SUJEITO", "ESTADO", "ACAO"] + nomes + ["UNIDADE", "NCM"])
    ws.append(["", "", "", ""]
              + [("obrigatorio " if at.obrigatorio else "opcional ") + tipo_da_caixa(at)
                 for at in atributos] + ["", ""])
    for cod in sorted(codigos):
        r = san[cod]
        valores = {d["atributo"]: d["valor"] for d in decisoes.get(cod, [])}
        j = juncao.get(cod, {})
        linha = [cod, f"{r.get('SUBSTANTIVO','')} {r.get('QUALIFICADOR','')}".strip(),
                 r["ESTADO"], j.get("ACAO", "")]
        linha += [valores.get(n) or "" for n in nomes]
        linha += [r["UNIDADE_PDM"], r["NCM_PDM"]]
        ws.append(linha)
    formatar(ws, 6 + len(nomes), [13, 24, 15, 13] + [20] * len(nomes) + [10, 12])
    # segunda linha e legenda, nao dado
    ws.freeze_panes = "A3"
    for c in range(5, 5 + len(nomes)):
        ws.cell(row=2, column=c).font = Font(italic=True, size=8, color="666666")

# ---------------------------------------------------------------- longo

print("Aba CARACTERISTICAS (formato longo)...")
ws = wb.create_sheet("CARACTERISTICAS")
cols = ["CODIGO_MATERIAL", "ID_PDM", "ATRIBUTO", "OBRIGATORIO", "TIPO_CAIXA",
        "VALOR", "FONTE", "ESTADO_CAIXA", "CONFIANCA", "MOTIVO"]
ws.append(cols)
n_longo = 0
for cod, ds in decisoes.items():
    cid = san.get(cod, {}).get("ID_PDM", "")
    classe = pdm.classes.get(cid)
    for d in ds:
        at = next((x for x in classe.atributos if x.nome == d["atributo"]), None) if classe else None
        ws.append([cod, cid, d["atributo"],
                   "S" if (at and at.obrigatorio) else "N",
                   tipo_da_caixa(at) if at else "",
                   d["valor"] or "", d["fonte"], d["estado"],
                   d.get("confianca"), (d.get("motivo") or "")[:220]])
        n_longo += 1
formatar(ws, len(cols), [14, 9, 24, 12, 11, 30, 14, 13, 11, 60])

# ---------------------------------------------------------------- pendencias

print("Aba PENDENCIAS...")
ws = wb.create_sheet("PENDENCIAS")
cols = ["CODIGO_MATERIAL", "ID_PDM", "SUJEITO", "ATRIBUTO_FALTANDO", "TIPO_CAIXA",
        "COMO_RESOLVER", "ESTOQUE", "VALOR_ESTOQUE", "DESCRICAO_ORIGINAL"]
ws.append(cols)
COMO = {
    "LIVRE": "recorte do texto (BERT) ou catalogo do fabricante",
    "TEXTUAL": "dicionario/LLM, ou enriquecimento se nao estiver no texto",
    "NUMERICA": "gramatica/LLM, ou ficha tecnica do fabricante",
}
n_pend = 0
for cod, r in san.items():
    classe = pdm.classes.get(r["ID_PDM"])
    o = orig.get(cod, {})
    est, preco = num(o.get("ESTOQUE_ATUAL")), num(o.get("PRECO_MEDIO_UNITARIO"))
    for nome in [x for x in r.get("PENDENTES", "").split(" | ") if x]:
        at = next((x for x in classe.atributos if x.nome == nome), None) if classe else None
        tipo = tipo_da_caixa(at) if at else ""
        ws.append([cod, r["ID_PDM"],
                   f"{r.get('SUBSTANTIVO','')} {r.get('QUALIFICADOR','')}".strip(),
                   nome, tipo, COMO.get(tipo, ""), est, round(est * preco, 2),
                   r["DESCRICAO_ORIGINAL"][:160]])
        n_pend += 1
formatar(ws, len(cols), [14, 9, 24, 24, 11, 48, 10, 14, 60])

# ---------------------------------------------------------------- juncoes

if juncao:
    print("Aba JUNCOES...")
    ws = wb.create_sheet("JUNCOES")
    cols = ["CODIGO", "ACAO", "USAR_CODIGO", "ID_PDM", "DESCRICAO_PDM",
            "ESTOQUE_CONSOLIDADO", "ESTOQUE_PROPRIO", "VALOR_PROPRIO", "CHAVE"]
    ws.append(cols)
    for cod, j in juncao.items():
        o = orig.get(cod, {})
        est, preco = num(o.get("ESTOQUE_ATUAL")), num(o.get("PRECO_MEDIO_UNITARIO"))
        ws.append([cod, j["ACAO"], j["USAR"], j["ID_PDM"], j["DESCRICAO_PDM"],
                   j.get("ESTOQUE_CONSOLIDADO", ""), est, round(est * preco, 2), j["CHAVE"]])
    formatar(ws, len(cols), [13, 14, 13, 9, 70, 20, 16, 16, 60])

# ---------------------------------------------------------------- resumo

print("Aba RESUMO...")
ws = wb.create_sheet("RESUMO", 0)
estados = Counter(r["ESTADO"] for r in san.values())
compl = [num(r["COMPLETUDE"]) for r in san.values() if r["ID_PDM"]]
no_padrao = sum(1 for r in san.values() if ";" in r["DESCRICAO_PDM"] and ":" in r["DESCRICAO_PDM"])
un_ok = sum(1 for r in san.values() if r["UNIDADE_PDM"])
ncm_ok = sum(1 for r in san.values() if r["NCM_PDM"])
bloq = sum(1 for j in juncao.values() if j["ACAO"] == "BLOQUEADO")
fontes = Counter(d["fonte"] for ds in decisoes.values() for d in ds if d["valor"])

ws.append(["CATALOGO DE MATERIAIS NO PADRAO PDM"])
ws["A1"].font = Font(bold=True, size=14)
ws.append([])
ws.append(["INDICADOR", "ANTES", "DEPOIS"])
N = len(san)
antes = {
    "Registros": (N, N),
    "Descricao no formato PDM": (4877, no_padrao),
    "Unidade dentro do padrao da classe": (21085, un_ok),
    "NCM presente e no formato 0000.00.00": (13901, ncm_ok),
    "Atributos obrigatorios preenchidos (media)": (0.0, round(sum(compl) / len(compl), 3) if compl else 0),
    "Codigos redundantes identificados": (0, bloq),
}
for k, (v0, v1) in antes.items():
    ws.append([k, v0, v1])
ws.append([])
ws.append(["ESTADO DOS REGISTROS", "QUANTIDADE", "%"])
for e, q in estados.most_common():
    ws.append([e, q, round(100 * q / N, 1)])
ws.append([])
ws.append(["ORIGEM DOS VALORES PREENCHIDOS", "QUANTIDADE", "%"])
tot_val = sum(fontes.values())
for f, q in fontes.most_common():
    ws.append([f, q, round(100 * q / tot_val, 1)])
ws.append([])
ws.append(["ABAS DESTE ARQUIVO", "CONTEUDO"])
ws.append(["CATALOGO", f"{N} itens, um por linha, com descricao no padrao"])
ws.append([f"PDM001...PDM110 ({len(por_classe)} abas)",
           "caracteristicas em colunas, na ordem da aba ATRIBUTOS do PDM"])
ws.append(["CARACTERISTICAS", f"{n_longo} linhas em formato longo, para auditoria"])
ws.append(["PENDENCIAS", f"{n_pend} atributos faltando, com o caminho de resolucao"])
if juncao:
    ws.append(["JUNCOES", f"{len(juncao)} linhas de plano de bloqueio"])
for c, w in zip("ABC", (46, 16, 16)):
    ws.column_dimensions[c].width = w
for linha in (3, ):
    for c in range(1, 4):
        ws.cell(row=linha, column=c).font = CABECALHO
        ws.cell(row=linha, column=c).fill = FUNDO

# ---------------------------------------------------------------- grava

SAIDA.parent.mkdir(parents=True, exist_ok=True)
wb.save(SAIDA)
wb.close()

print()
print("=" * 78)
print("CATALOGO GERADO".center(78))
print("=" * 78)
print(f"Arquivo ............................... {SAIDA}")
print(f"Itens no catalogo ..................... {N:>9,}")
print(f"Abas por classe ....................... {len(por_classe):>9}")
print(f"Linhas de caracteristica (longo) ...... {n_longo:>9,}")
print(f"Pendencias listadas ................... {n_pend:>9,}")
print(f"Codigos a bloquear por duplicidade .... {bloq:>9,}")
print(f"Completude media dos obrigatorios ..... {sum(compl) / len(compl):>9.3f}")
print(f"Descricao no formato PDM .............. {no_padrao:>9,}  "
      f"({100 * no_padrao / N:.1f}%, era 20,7%)")
