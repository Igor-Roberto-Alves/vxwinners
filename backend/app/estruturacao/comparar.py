"""Compara este backend com o pipeline de `src/saneamento` sobre a mesma base.

São dois caminhos independentes: quando um une dois códigos e o outro, com as duas chaves em mãos,
não une, um deles está errado. Foi assim que apareceram junções falsas nos dois lados. Rode depois de
`scripts/04_extrair.py` e de `estruturar`, e leia a amostra de cada divergência.
"""
from __future__ import annotations

import csv
import random
from collections import Counter, defaultdict
from itertools import combinations

from sqlalchemy import text

from ..config import RAIZ_REPO
from ..db import engine

ARQUIVO = RAIZ_REPO / "artefatos" / "saneado_base.csv"


def _pares(chaves: dict[str, str | None]) -> set[tuple[str, str]]:
    g: dict[str, list[str]] = defaultdict(list)
    for cod, ch in chaves.items():
        if ch:
            g[ch].append(cod)
    out: set[tuple[str, str]] = set()
    for v in g.values():
        if len(v) > 1:
            out.update(combinations(sorted(v), 2))
    return out


def compara() -> dict:
    csv.field_size_limit(10**7)
    with open(ARQUIVO, encoding="utf-8") as f:
        ex = {r["CODIGO_MATERIAL"]: r for r in csv.DictReader(f)}
    with engine().connect() as c:
        linhas = c.execute(text("""select k.codigo, k.id_pdm, case when i.completa then i.chave end
            from material_classificacao k left join material_identidade i using (codigo)""")).all()
        desc = {r[0]: r[1] for r in c.execute(text("select codigo, descricao_longa from material"))}
    meu_cl = {r[0]: r[1] for r in linhas}
    meu_ch = {r[0]: r[2] for r in linhas}
    ex_ch = {c: (r["CHAVE_IDENTIDADE"] or None) for c, r in ex.items()}
    ambos = [c for c in ex if ex[c]["ID_PDM"] and meu_cl.get(c)]
    iguais = sum(1 for c in ambos if ex[c]["ID_PDM"] == meu_cl[c])
    pe, pm = _pares(ex_ch), _pares(meu_ch)
    so_e, so_m = pe - pm, pm - pe
    disc_e = [(a, b) for a, b in so_e if meu_ch.get(a) and meu_ch.get(b)]
    disc_m = [(a, b) for a, b in so_m if ex_ch.get(a) and ex_ch.get(b)]
    return {
        "classe": {"ambos": len(ambos), "iguais": iguais, "pct": round(100 * iguais / len(ambos), 2) if ambos else 0,
                   "divergencias": Counter((ex[c]["ID_PDM"], meu_cl[c]) for c in ambos if ex[c]["ID_PDM"] != meu_cl[c]).most_common(8)},
        "pares": {"saneamento": len(pe), "backend": len(pm), "comum": len(pe & pm), "so_saneamento": len(so_e), "so_backend": len(so_m)},
        "discordam": {"saneamento_une": disc_e, "backend_une": disc_m},
        "chaves": {"saneamento": ex_ch, "backend": meu_ch}, "descricoes": desc,
    }


def imprime(amostra: int = 5) -> None:
    r = compara()
    k, p, d = r["classe"], r["pares"], r["discordam"]
    print(f"classe: {k['iguais']} de {k['ambos']} iguais ({k['pct']}%) | maiores divergencias (saneamento, backend): {k['divergencias'][:5]}")
    print(f"pares de duplicidade: saneamento {p['saneamento']} | backend {p['backend']} | em comum {p['comum']}")
    print(f"so saneamento: {p['so_saneamento']} (com as 2 chaves no backend e discordando: {len(d['saneamento_une'])})")
    print(f"so backend: {p['so_backend']} (com as 2 chaves no saneamento e discordando: {len(d['backend_une'])})")
    random.seed(1)
    for titulo, lista in (("SANEAMENTO UNE, BACKEND NAO", d["saneamento_une"]), ("BACKEND UNE, SANEAMENTO NAO", d["backend_une"])):
        print(f"\n--- {titulo}")
        for a, b in random.sample(lista, min(amostra, len(lista))):
            print(f"  {a}: {r['descricoes'][a][:100]}\n  {b}: {r['descricoes'][b][:100]}")
            print(f"    saneamento: {(r['chaves']['saneamento'].get(a) or '')[-70:]} | {(r['chaves']['saneamento'].get(b) or '')[-70:]}")
            print(f"    backend:    {(r['chaves']['backend'].get(a) or '')[-70:]} | {(r['chaves']['backend'].get(b) or '')[-70:]}")
