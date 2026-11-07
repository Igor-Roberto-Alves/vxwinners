"""Compara duas execucoes do 04_extrair, registro a registro.

Serve para medir o efeito de uma mudanca de codigo antes de aceita-la: o
numero agregado (SANEADO, chaves fechadas) esconde troca de sinal - uma melhora
em um lugar e uma piora em outro somam zero. Aqui cada diferenca aparece, com
exemplo, para ser revisada a mao.

Uso (cada diretorio e um --artefatos de 04_extrair.py):
  python 12_comparar_execucoes.py ANTES DEPOIS
  python 12_comparar_execucoes.py ANTES DEPOIS --exemplos 20

O que compara:
  - classe (ID_PDM) de cada registro
  - estado (SANEADO / PENDENTE / REVISAO_HUMANA / FORA_DO_PDM)
  - chave de identidade (abriu, fechou, mudou)
  - valor de cada caixa (preenchida, esvaziada, trocou de valor), so quando a
    classe nao mudou - com classe nova as caixas sao outras
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("antes")
p.add_argument("depois")
p.add_argument("--exemplos", type=int, default=8)
a = p.parse_args()


def ler(d: Path):
    reg = {x["CODIGO_MATERIAL"]: x
           for x in csv.DictReader((d / "saneado_base.csv").open(encoding="utf-8"))}
    dec = {}
    with (d / "decisoes_base.jsonl").open(encoding="utf-8") as fh:
        for linha in fh:
            j = json.loads(linha)
            dec[j["codigo"]] = {x["atributo"]: x["valor"] for x in j.get("decisoes", [])}
    return reg, dec


ra, da = ler(Path(a.antes))
rb, db = ler(Path(a.depois))

conta: Counter = Counter()
por_caixa: Counter = Counter()
exemplos: dict[str, list] = defaultdict(list)

for cod, x in ra.items():
    y = rb.get(cod)
    if y is None:
        conta["registro sumiu"] += 1
        continue
    desc = x["DESCRICAO_ORIGINAL"][:90]

    if x["ID_PDM"] != y["ID_PDM"]:
        t = f"classe {x['ID_PDM'] or '-'} -> {y['ID_PDM'] or '-'}"
        conta[t] += 1
        exemplos[t].append((cod, desc))

    if x["ESTADO"] != y["ESTADO"]:
        t = f"estado {x['ESTADO']} -> {y['ESTADO']}"
        conta[t] += 1
        exemplos[t].append((cod, desc))

    ka, kb = x["CHAVE_IDENTIDADE"], y["CHAVE_IDENTIDADE"]
    if ka != kb:
        t = ("chave fechou" if not ka else "chave abriu" if not kb else "chave mudou")
        conta[t] += 1
        exemplos[t].append((cod, desc))

    if x["ID_PDM"] == y["ID_PDM"]:
        ca, cb = da.get(cod, {}), db.get(cod, {})
        for atr in sorted(set(ca) | set(cb)):
            va, vb = ca.get(atr), cb.get(atr)
            if va == vb:
                continue
            t = ("caixa preenchida" if not va else
                 "caixa esvaziada" if not vb else "caixa trocou valor")
            conta[t] += 1
            por_caixa[(t, atr)] += 1
            exemplos[t].append((cod, atr, va, vb, desc[:70]))

print(f"Registros comparados: {len(ra)}\n")
if not conta:
    print("Nenhuma diferenca.")
for t, n in conta.most_common():
    print(f"{n:7,}  {t}")
if por_caixa:
    print("\nPor caixa:")
    for (t, atr), n in por_caixa.most_common(20):
        print(f"{n:7,}  {t:20} {atr}")
for t, lista in exemplos.items():
    print(f"\n== {t} ({len(lista)})")
    for e in lista[:a.exemplos]:
        print("  ", e)
