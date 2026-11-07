"""Roda a camada de enriquecimento sobre o resultado saneado.

Entrada:  artefatos/saneado_base.csv   (o que o pipeline produziu)
Saida:    artefatos/enriquecimento.csv (uma linha por dado novo, com procedencia)
          artefatos/enriquecimento.json (trilha completa + fontes + estatisticas)

Script proprio de proposito: o `pipeline.py` esta sendo mexido por outras
camadas, e enriquecimento nao precisa entrar no caminho quente para render
valor. Ele le a grade de caixas de volta da DESCRICAO_PDM, propoe para o que
ficou vazio e grava um artefato separado, que a plataforma junta na hora de
exibir. A integracao no pipeline fica para depois.

Uso:
    python scripts/09_enriquecer.py
    python scripts/09_enriquecer.py --baixar-ncm      # (re)baixa a tabela oficial
    python scripts/09_enriquecer.py --validar-15      # so os 15 produtos reais
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm  # noqa: E402
from saneamento.enriquecimento import (  # noqa: E402
    ARQUIVO_NCM, CATALOGO_TENTADO, Enriquecedor, TabelaNcm,
)

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--referencia", default=str(RAIZ / "dados" / "referencia"))
p.add_argument("--saneado", default=None)
p.add_argument("--baixar-ncm", action="store_true",
               help="baixa a tabela oficial da NCM do Portal Unico Siscomex")
p.add_argument("--validar-15", action="store_true",
               help="roda so nos 15 ultimos registros (os produtos reais)")
p.add_argument("--limite", type=int, default=0)
a = p.parse_args()

ARTEFATOS = Path(a.artefatos)
REFERENCIA = Path(a.referencia)
SANEADO = Path(a.saneado) if a.saneado else ARTEFATOS / "saneado_base.csv"

# ------------------------------------------------------------------ fonte (a)

if a.baixar_ncm:
    print(f"baixando a tabela oficial da NCM para {REFERENCIA / ARQUIVO_NCM} ...")
    try:
        t = TabelaNcm.baixar(REFERENCIA / ARQUIVO_NCM)
        print(f"  ok: {t.meta['codigos_8_digitos']} codigos de 8 digitos | "
              f"{t.meta['vigencia_declarada']} | {t.meta['ato']}")
    except Exception as e:                                  # noqa: BLE001
        print(f"  FALHOU: {type(e).__name__}: {e}")
        print("  o pipeline segue sem a validacao de existencia/vigencia.")

tabela = TabelaNcm.local(REFERENCIA)
if tabela is None:
    print("AVISO: tabela oficial da NCM ausente em dados/referencia/.")
    print("       existencia e vigencia NAO serao verificadas (rode --baixar-ncm).")
else:
    print(f"tabela oficial da NCM: {tabela.meta['codigos_8_digitos']} codigos | "
          f"{tabela.meta['vigencia_declarada']} | baixada em "
          f"{tabela.meta['data_download']}")

pdm = Pdm.carregar(ARTEFATOS / "pdm.json")
enr = Enriquecedor(pdm, tabela_ncm=tabela)

# ------------------------------------------------------ ler a grade de volta

# A DESCRICAO_PDM e 'SUBSTANTIVO QUALIFICADOR; ATRIBUTO: VALOR; ...' (regra 2).
# Ler a grade de volta dali, em vez de pedir um artefato novo ao pipeline, deixa
# esta camada acoplada so ao formato do PDM - que e contrato - e nao ao formato
# interno de nenhuma outra camada.
RX_PAR = re.compile(r"([A-Z][A-Z0-9 /]*?)\s*:\s*(.*)")


def grade(descricao_pdm: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for parte in str(descricao_pdm or "").split(";"):
        m = RX_PAR.match(parte.strip())
        if not m:
            continue
        nome, valor = m.group(1).strip(), m.group(2).strip()
        out[nome] = None if valor == "<PENDENTE>" else valor
    return out


linhas = list(csv.DictReader(SANEADO.open(encoding="utf-8")))
if a.validar_15:
    linhas = linhas[-15:]
elif a.limite:
    linhas = linhas[: a.limite]
print(f"lendo {len(linhas)} registros de {SANEADO.name}\n")

# as caixas obrigatorias que ficaram vazias, para medir cobertura
vazias_obrigatorias: Counter = Counter()
preenchidas_obrigatorias: Counter = Counter()
saida: list[dict] = []

for r in linhas:
    valores = grade(r["DESCRICAO_PDM"])
    # PENDENTES e a lista de obrigatorias vazias que o pipeline apurou
    pendentes = {x.strip() for x in (r.get("PENDENTES") or "").split("|") if x.strip()}
    for nome in pendentes:
        valores.setdefault(nome, None)
        vazias_obrigatorias[nome] += 1

    # caixas que existem na classe e nao apareceram na descricao (as opcionais)
    classe = pdm.classes.get(r["ID_PDM"])
    if classe:
        for at in classe.atributos:
            valores.setdefault(at.nome, None)

    e = enr.enriquecer(
        codigo=r["CODIGO_MATERIAL"], id_pdm=r["ID_PDM"], valores=valores,
        texto=r.get("DESCRICAO_ORIGINAL", ""), ncm_atual=r.get("NCM_PDM", ""),
    )

    for s in e.sugestoes:
        if s.atributo in pendentes:
            preenchidas_obrigatorias[s.atributo] += 1
        d = s.como_dict()
        d["CODIGO_MATERIAL"] = e.codigo
        d["ID_PDM"] = e.id_pdm
        d["OBRIGATORIA_VAZIA"] = int(s.atributo in pendentes)
        saida.append(d)
    if e.ncm:
        d = e.ncm.como_dict()
        d["CODIGO_MATERIAL"] = e.codigo
        d["ID_PDM"] = e.id_pdm
        d["OBRIGATORIA_VAZIA"] = 0
        saida.append(d)

# ------------------------------------------------------------------ gravar

COLUNAS = ["CODIGO_MATERIAL", "ID_PDM", "ATRIBUTO", "VALOR", "TIPO", "FONTE",
           "URL_OU_REFERENCIA", "DATA_CONSULTA", "CONFIANCA", "DERIVADO_DE",
           "METODO", "OBRIGATORIA_VAZIA", "REVISAR", "MOTIVO"]

destino_csv = ARTEFATOS / "enriquecimento.csv"
with destino_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLUNAS, extrasaction="ignore")
    w.writeheader()
    w.writerows(saida)

destino_json = ARTEFATOS / "enriquecimento.json"
n_reg = enr.salvar(destino_json)

# ------------------------------------------------------------------ relatorio

est = enr.estatisticas()
print("=" * 92)
print("ENRIQUECIMENTO")
print("=" * 92)
print(f"registros lidos .................. {est['registros']}")
print(f"dados novos com procedencia ...... {est['sugestoes']}")
print(f"registros tocados ................ {n_reg}")
print(f"caixas ja ocupadas preservadas ... {est['caixas_ocupadas_preservadas']}"
      "   (invariante 3: nunca sobrescreve extracao)")
print(f"recusadas pelo validador do PDM .. {est['recusadas_pelo_validador']}"
      "   (invariante 2: enum manda, venha de onde vier)")
print(f"recusadas sem procedencia ........ {est['recusadas_sem_procedencia']}"
      "   (invariante 1: dado sem rastro nao entra)")

print("\npor fonte:")
for k, v in est["por_fonte"].items():
    print(f"  {v:7d}  {k}")

print("\npor atributo:")
for k, v in est["por_atributo"].items():
    print(f"  {v:7d}  {k}")

obrig_total = sum(vazias_obrigatorias.values())
obrig_cheias = sum(preenchidas_obrigatorias.values())
print(f"\ncaixas OBRIGATORIAS vazias nos registros lidos: {obrig_total}")
print(f"  preenchidas por esta camada ................. {obrig_cheias}"
      f"  ({(100 * obrig_cheias / obrig_total if obrig_total else 0):.1f}%)")
for k, v in preenchidas_obrigatorias.most_common():
    print(f"    {v:6d}  {k}  (de {vazias_obrigatorias[k]} vazias)")

print("\nNCM contra a tabela oficial do Portal Unico Siscomex:")
print(f"  vigente ........ {est['ncm_vigente']}")
print(f"  NAO vigente .... {est['ncm_nao_vigente']}   <- passa pelo formato e pela classe,"
      " mas nao existe na tabela")
print(f"  ausente ........ {est['ncm_ausente']}")
print(f"  preenchido ..... {est['ncm_preenchido']}")
print(f"  sem tabela ..... {est['ncm_sem_tabela']}")

nao_vigentes = [e for e in enr.trilha if e.ncm_veredito == "NAO_VIGENTE"]
if nao_vigentes:
    print("\n  codigos nao vigentes encontrados:")
    vistos: Counter = Counter()
    for e in nao_vigentes:
        vistos[e.ncm_motivo[:110]] += 1
    for motivo, n in vistos.most_common(10):
        print(f"    {n:5d}x  {motivo}")

print("\nfonte (c) catalogo de fabricante - tentado e NAO funcionou:")
for t in CATALOGO_TENTADO:
    print(f"  {t['fabricante']}: {t['resultado']}")
    print(f"     robots.txt: {t['robots_txt']}")

print(f"\ngravado:\n  {destino_csv}\n  {destino_json}")

# ------------------------------------------------------ validacao nos 15 reais

if a.validar_15:
    # Gabarito publico, conferido fora deste codigo. As dimensoes do 6205 e do
    # 6310 estao no catalogo de qualquer fabricante e no enunciado do desafio. A
    # vedacao e a folga saem do sufixo, lido no sistema de designacao do
    # fabricante que escreveu aquele item (2RSH=SKF, 2HRS=FAG, DDU=NSK,
    # 2Z=SKF/FAG, ZZ=NTN; /C3 = folga C3). O fabricante dos dois filtros sai do
    # registro gemeo da propria base (LF9009 = FLEETGUARD em 16031971) e do
    # prefixo DBL, que e a linha Donaldson Blue.
    GABARITO_DIM = {
        "DIAMETRO INTERNO": {"6205": "25MM", "6310": "50MM"},
        "DIAMETRO EXTERNO": {"6205": "52MM", "6310": "110MM"},
        "LARGURA": {"6205": "15MM", "6310": "27MM"},
    }
    GABARITO_CODIGO = {
        "20866024": {"VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"},
        "27026717": {"VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"},
        "28490077": {"VEDACAO": "BORRACHA AMBOS LADOS", "FOLGA": "C3"},
        "29364361": {"VEDACAO": "METALICA AMBOS LADOS", "FOLGA": "C3"},
        "14840397": {"VEDACAO": "METALICA AMBOS LADOS", "FOLGA": "C3"},
        "16303905": {"VEDACAO": "METALICA AMBOS LADOS", "FOLGA": "C3"},
        "27841570": {"FABRICANTE": "FLEETGUARD"},
        "18308575": {"FABRICANTE": "DONALDSON"},
    }
    print("\n" + "=" * 92)
    print("VALIDACAO NOS 15 PRODUTOS REAIS")
    print("=" * 92)
    acerto = erro = sem_gabarito = 0
    for e in enr.trilha:
        linha = next(r for r in linhas if r["CODIGO_MATERIAL"] == e.codigo)
        desc = linha["DESCRICAO_ORIGINAL"]
        base = "6205" if "6205" in desc else ("6310" if "6310" in desc else "")
        print(f"\n{e.codigo}  {e.id_pdm}  {desc[:58]}")
        if not e.sugestoes and not e.ncm:
            print("   (nada a enriquecer)")
        for s in e.sugestoes:
            gab = (GABARITO_DIM.get(s.atributo, {}).get(base)
                   or GABARITO_CODIGO.get(e.codigo, {}).get(s.atributo))
            if gab is None:
                marca, sem_gabarito = "   ?", sem_gabarito + 1
            elif gab == s.valor:
                marca, acerto = "  OK", acerto + 1
            else:
                marca, erro = " ERRO", erro + 1
            print(f"  {marca}  {s.atributo}: {s.valor}"
                  f"{'' if gab is None else f'  (catalogo: {gab})'}"
                  f"   [{s.procedencia.fonte} conf={s.procedencia.confianca}]")
        if e.ncm:
            print(f"     +  NCM: {e.ncm.valor}   [{e.ncm.procedencia.fonte}"
                  f" conf={e.ncm.procedencia.confianca}]  {e.ncm.motivo[:60]}")
    print(f"\nconferido contra catalogo publico: {acerto} acerto, {erro} erro")
    print(f"sugestoes sem gabarito publico para conferir: {sem_gabarito}")
    print(json.dumps({"acerto": acerto, "erro": erro, "sem_gabarito": sem_gabarito}))
