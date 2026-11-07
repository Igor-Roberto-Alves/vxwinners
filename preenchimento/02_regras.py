"""Solucao 'regras': deterministica, custo zero, sem ML.

- FABRICANTE: lexico de nomes do treino casado por palavra inteira no texto.
- REFERENCIA_FABRICANTE: extracao de part number por regex (marcadores REF/PN/COD,
  proximidade de fabricante, candidato mais longo) com exclusao de medidas/bitolas/
  normas/modelos. Regras calibradas inspecionando SOMENTE o split de treino.
- NCM: NCM mais frequente no treino dentro do grupo, priorizando os NCMs validos
  para o grupo segundo o PDM (pdm_classes + pdm_ncm_referencia).
- GRUPO_MERCADORIA: lexico substantivo(+qualificador)->grupo construido do PDM
  (pdm_classes, pdm_subst_sobressalentes->SOB01, pdm_subst_conexoes->TUB01) +
  dicionario de abreviacoes (as dadas + as identificadas no TREINO), casando os
  primeiros tokens da descricao.

Nenhuma chamada de API. O y do teste e usado apenas para gravar y_true.
"""
import re
import sys
import time
from collections import Counter, defaultdict

import pandas as pd

from contrato import (DADOS, caminho_split, norm_ncm, norm_ref, norm_rotulo,
                      norm_texto, salvar_meta, salvar_pred)

SOLUCAO = "regras"
LOG = open("02_regras.log", "a")


def log(msg):
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(linha, flush=True)
    LOG.write(linha + "\n")
    LOG.flush()


def achatar(s):
    """Texto normalizado so com tokens alfanumericos separados por espaco."""
    return " ".join(re.findall(r"[A-Z0-9]+", norm_texto(s)))


def ler(campo, parte):
    return pd.read_csv(caminho_split(campo, parte), dtype=str).fillna("")


# ============================= FABRICANTE =============================

def roda_fabricante():
    t0 = time.time()
    tr, te = ler("FABRICANTE", "treino"), ler("FABRICANTE", "teste")
    freq = Counter(norm_texto(v) for v in tr["y"] if norm_texto(v))
    lex = {}
    for nome in freq:  # casamento por palavra inteira (nomes compostos permitem qualquer separador)
        nome_flat = achatar(nome)
        lex[nome] = re.compile(r"(?<![A-Z0-9])" + re.escape(nome_flat).replace(r"\ ", r"\s") + r"(?![A-Z0-9])")

    linhas = []
    n_abst = 0
    for _, r in te.iterrows():
        t = achatar(str(r["DESCRICAO_CURTA"]) + " " + str(r["DESCRICAO_LONGA"]))
        hits = [nome for nome, rx in lex.items() if rx.search(t)]
        # varios casamentos: nome mais longo primeiro, depois o mais frequente no treino
        hits.sort(key=lambda nm: (-len(nm), -freq[nm]))
        if hits:
            y_pred = norm_rotulo("FABRICANTE", hits[0])
            conf = 0.9 if len(hits) == 1 else 0.7
            top3 = "|".join(norm_rotulo("FABRICANTE", h) for h in hits[:3])
        else:
            y_pred, conf, top3 = "", 0.0, ""
            n_abst += 1
        linhas.append({"CODIGO_MATERIAL": r["CODIGO_MATERIAL"], "y_true": r["y"],
                       "y_pred": y_pred, "conf": conf, "top3": top3})
    df = pd.DataFrame(linhas)
    salvar_pred(SOLUCAO, "FABRICANTE", df)
    seg = time.time() - t0
    obs = (f"lexico de {len(lex)} nomes distintos do treino; casamento por palavra inteira; "
           f"abstencao {n_abst}/{len(te)} ({n_abst/len(te):.1%}) quando nenhum nome aparece no texto")
    salvar_meta(SOLUCAO, "FABRICANTE", segundos=round(seg, 2), chamadas_api=0,
                tokens_entrada=0, tokens_saida=0, modelo="", custo_estimado_usd=0.0,
                observacoes=obs)
    log(f"FABRICANTE ok em {seg:.1f}s | abstencao {n_abst/len(te):.1%}")
    return n_abst / len(te)


# ======================= REFERENCIA_FABRICANTE ========================
# Regras calibradas APENAS no treino (ver 02_regras.log para as taxas).

MARKER_RE = re.compile(
    r"(?<![A-Z0-9])(?:REFERENCIA(?:\s+(?:DO\s+)?FABRICANTE)?|REF\.?(?:\s+FABRICANTE)?|"
    r"PART\s*NUMBER|P\s*/\s*N|PN|COD(?:IGO)?\.?(?:\s+(?:DO\s+)?FAB(?:RICANTE)?\.?)?)"
    r"(?![A-Z0-9])\s*[:=]?\s*([A-Z0-9][A-Z0-9 ./-]*)")
MODEL_KEY = {"MOD", "MODELO", "MODEL", "EQUIP", "EQUIPAMENTO", "APLIC", "APLICACAO", "USO",
             "TIPO", "SERIE", "DE", "DO", "DA"}
MODEL_RE = re.compile(
    r"(?<![A-Z0-9])(?:MOD(?:ELO)?\.?|EQUIP(?:AMENTO)?\.?|APLIC(?:ACAO)?\.?|USO|TIPO|SERIE|"
    r"NORMA|DIN|NBR|ISO|ANSI|ABNT|SAE|AISI|ASTM|API|CLASSE|CL|GRAU|BITOLA|DIM|DIAM(?:ETRO)?\.?|USAR\s+COD)"
    r"(?![A-Z0-9])\s*[:=]?\s*([A-Z0-9][A-Z0-9 ./-]*)")
STOP_WORDS = {"REV", "MARCA", "FAB", "FABR", "FABRICANTE", "MATERIAL", "MAT", "USO", "APLICACAO",
              "APLIC", "MODELO", "MOD", "EQUIP", "EQUIPAMENTO", "ACO", "COR", "TIPO", "DIM", "DIAM",
              "COMPR", "CLASSE", "CL", "GRAU", "PARA", "COM", "USAR", "NAO"}
MEAS = (r"(?:MM|MM2|CM|M|M2|M3|POL|V|KV|KVA|VCC|VCA|A|KA|MA|AH|W|KW|HP|CV|BAR|PSI|MPA|KPA|KG|KGF|"
        r"G|GR|L|ML|LPM|GPM|GRAUS|GRAU|RPM|HZ|C|F|T|TON|AWG|MESH|MIC|MICRA|DENTES|FUROS|LONAS|PC|PCS|UN|LB|NM)")


def is_excluido(t):
    """Padroes de medida/bitola/norma/tag que nao sao part number."""
    if re.fullmatch(r"\d+([.,/X]\d+)*" + MEAS, t): return True            # 20MM 450/750V 3KA
    if re.fullmatch(r"\d+([.,]\d+)?(X\d+([.,]\d+)?){1,3}" + MEAS + r"?", t): return True  # 14X50 4.2X6.8
    if re.fullmatch(r"M\d{1,3}(X\d+([.,]\d+)?)?", t): return True         # bitolas M8 M12X50
    if re.fullmatch(r"(DN|NPT|BSP|UNC|UNF|SAE|GL|CL)\d{1,3}([/.]\d+)?", t): return True  # DN50
    if re.fullmatch(r"[GR]\d([/.]\d+)?", t): return True                   # rosca G1/2 R2
    if re.fullmatch(r"\d+([.,]\d+)?/\d+([.,]\d+)?", t): return True       # fracoes 3/4
    if re.fullmatch(r"\d+\.\d+/\d+", t): return True                       # 1.1/2
    if re.fullmatch(r"A\d(-\d+)?", t): return True                         # classe inox A2-70
    if re.fullmatch(r"A\d{3}", t): return True                             # norma aco A106
    if re.fullmatch(r"[A-Z]{1,3}-\d{1,3}", t): return True                 # tag TC-01
    if re.fullmatch(r"\d{1,3}-\d{1,3}", t): return True                    # modelo 100-315
    if re.fullmatch(r"\d+([.,]\d+)?", t) and len(re.sub(r"\D", "", t)) < 5: return True  # numero puro curto
    return False


def cand_ok(t):
    t = t.strip(".-/")
    if len(t) < 4 or not re.search(r"\d", t): return False
    if is_excluido(t): return False
    if re.search(r"[A-Z]", t): return True                                  # letras E digitos
    if re.search(r"[-./]", t) and re.fullmatch(r"[0-9.\-/]+", t): return True  # digitos com separador
    if re.fullmatch(r"\d{5,}", t): return True                              # digitos puros longos
    return False


def _flag_sep00(raw_last):
    """True quando o trecho termina com sufixo explicito '-00'/'.00'/' 00' (revisao)."""
    return bool(re.search(r"[-. ]00$", raw_last)) or raw_last == "00"


def _marker_caps(t, fabset):
    out = []
    for m in MARKER_RE.finditer(t):
        if t[:m.start()].rstrip().endswith("USAR"):  # 'NAO UTILIZAR - USAR COD 123' = codigo interno
            continue
        keep = []
        for tk in m.group(1).split():
            tkc = tk.strip(".-/")
            if not tkc or tkc in STOP_WORDS or tkc in fabset: break
            if re.fullmatch(r"[A-Z]{4,}", tkc): break
            if re.fullmatch(r"[A-Z]{1,3}", tkc) and any(re.search(r"\d", k) for k in keep): break
            keep.append(tkc)
            if len(keep) >= 6: break
        if not keep: continue
        joined = norm_ref("".join(keep))
        if len(joined) < 4 or not re.search(r"\d", joined): continue
        if len(keep) == 1:
            ok = cand_ok(keep[0]) or bool(re.fullmatch(r"\d{4,}", keep[0].strip(".-/")))
            ok = ok and not is_excluido(keep[0])
        else:
            ok = (all(re.fullmatch(r"\d{2,4}", k) for k in keep) or
                  any(cand_ok(k) for k in keep) or
                  (re.fullmatch(r"[A-Z]{1,3}", keep[0]) and
                   all(re.fullmatch(r"[\d./-]+", k) for k in keep[1:])))
        if ok:
            out.append((joined, _flag_sep00(keep[-1])))
    return out


def _excl_modelos(t):
    excl = set()
    for m in MODEL_RE.finditer(t):
        n_livres = 0
        for tk in m.group(1).split():
            tkc = tk.strip(".-/")
            if not tkc: continue
            if tkc in MODEL_KEY:   # marcadores encadeados: MODELO EQUIPAMENTO ...
                n_livres = 0
                continue
            excl.add(tkc)
            n_livres += 1
            if n_livres >= 2: break
    return excl


def _token_cands(t, fabset):
    """Lista de (perto_de_fab, len, pos, valor_norm, flag_sep00)."""
    excl = _excl_modelos(t)
    flat = re.sub(r"[^A-Z0-9./ -]", " ", t)
    toks = [x for x in flat.split() if x.strip(".-/")]
    fpos = [i for i, tk in enumerate(toks) if tk.strip(".-/") in fabset]
    cands = []
    for i, tk in enumerate(toks):
        tkc = tk.strip(".-/")
        if tkc in excl or tkc in fabset: continue
        if cand_ok(tkc):
            near = any(abs(i - p) <= 3 for p in fpos)
            cands.append((near, len(norm_ref(tkc)), i, norm_ref(tkc), _flag_sep00(tkc)))
            if i > 0:  # prefixo alfabetico curto imediatamente antes (ex: 'LE 4293-00')
                prev = toks[i - 1].strip(".-/")
                if (re.fullmatch(r"[A-Z]{1,3}", prev) and prev not in fabset
                        and prev not in STOP_WORDS and prev not in excl and prev not in MODEL_KEY):
                    v = norm_ref(prev + tkc)
                    cands.append((near, len(v), i, v, _flag_sep00(tkc)))
    # grupos de digitos separados por espaco (ex: '5662 3612 41')
    for m in re.finditer(r"(?<![A-Z0-9.,/-])(\d{2,4}(?: \d{2,4}){1,4})(?![A-Z0-9.,])", t):
        pieces = m.group(1).split()
        joined = "".join(pieces)
        if len(joined) >= 6 and not any(p in excl for p in pieces):
            pos = len(re.sub(r"[^A-Z0-9./ -]", " ", t[:m.start()]).split())
            near = any(abs(pos - p) <= 4 for p in fpos)
            cands.append((near, len(joined), pos, joined, pieces[-1] == "00"))
    return cands


def extrair_referencia(longa, curta, fabset):
    """Candidatos em ordem de prioridade: marcador > perto de fabricante > mais longo."""
    t_l = norm_texto(longa)
    t_c = norm_texto(curta)
    if len(str(curta)) >= 40:  # descricao curta truncada: ultimo token pode estar cortado
        t_c = re.sub(r"[A-Z0-9./-]+$", "", t_c).strip()
    vistos, ordem, origem = set(), [], ""
    for c, f in _marker_caps(t_l, fabset) + _marker_caps(t_c, fabset):
        if c not in vistos:
            vistos.add(c); ordem.append((c, f))
            origem = origem or "marcador"
    tok = _token_cands(t_l, fabset) + _token_cands(t_c, fabset)
    for near, _l, _i, c, f in sorted(tok, key=lambda x: (-x[0], -x[1], x[2])):
        if c not in vistos:
            vistos.add(c); ordem.append((c, f))
            if not origem:
                origem = "perto_fab" if near else "mais_longo"
    return ordem, origem


def roda_referencia():
    t0 = time.time()
    te = ler("REFERENCIA_FABRICANTE", "teste")
    ftr = ler("FABRICANTE", "treino")
    fabset = set()
    for v in ftr["y"]:
        fabset.update(re.findall(r"[A-Z0-9]+", norm_texto(v)))

    conf_por_origem = {"marcador": 0.85, "perto_fab": 0.6, "mais_longo": 0.45}
    linhas = []
    n_abst = 0
    for _, r in te.iterrows():
        ordem, origem = extrair_referencia(r["DESCRICAO_LONGA"], r["DESCRICAO_CURTA"], fabset)
        if not ordem:
            n_abst += 1
            linhas.append({"CODIGO_MATERIAL": r["CODIGO_MATERIAL"], "y_true": r["y"],
                           "y_pred": "", "conf": 0.0, "top3": ""})
            continue
        x, sep00 = ordem[0]
        # convencao de sufixo medida no TREINO: '-00' explicito quase sempre sai do rotulo
        if sep00 and len(x) > 6:
            top3 = [x[:-2], x, x[:-2] + "REVA"]
        else:
            top3 = [x, x + "REVA", x + "00"]
        top3 = [norm_rotulo("REFERENCIA_FABRICANTE", v) for v in top3]
        linhas.append({"CODIGO_MATERIAL": r["CODIGO_MATERIAL"], "y_true": r["y"],
                       "y_pred": top3[0], "conf": conf_por_origem.get(origem, 0.45),
                       "top3": "|".join(top3[:3])})
    df = pd.DataFrame(linhas)
    salvar_pred(SOLUCAO, "REFERENCIA_FABRICANTE", df)
    seg = time.time() - t0
    obs = (f"regex de part number calibrada no treino (acc treino ~0.85): marcadores REF/PN/COD > "
           f"proximidade de fabricante > candidato mais longo; exclusao de medidas/bitolas/normas/modelos; "
           f"sufixo '-00' removido e variantes +REVA/+00 no top3; "
           f"abstencao {n_abst}/{len(te)} ({n_abst/len(te):.1%})")
    salvar_meta(SOLUCAO, "REFERENCIA_FABRICANTE", segundos=round(seg, 2), chamadas_api=0,
                tokens_entrada=0, tokens_saida=0, modelo="", custo_estimado_usd=0.0,
                observacoes=obs)
    log(f"REFERENCIA_FABRICANTE ok em {seg:.1f}s | abstencao {n_abst/len(te):.1%}")
    return n_abst / len(te)


# ================================ NCM =================================

def _ncms_do_texto(s):
    return [norm_ncm(m.group(0)) for m in re.finditer(r"\d{4}\.?\d{2}\.?\d{2}", s) if norm_ncm(m.group(0))]


def roda_ncm():
    t0 = time.time()
    tr, te = ler("NCM", "treino"), ler("NCM", "teste")
    cls = pd.read_csv(DADOS / "pdm_classes.csv", dtype=str).fillna("")
    ncmref = pd.read_csv(DADOS / "pdm_ncm_referencia.csv", dtype=str).fillna("")
    id2grp = dict(zip(cls.ID_PDM, cls.GRUPO_MERCADORIA))

    validos = defaultdict(set)  # grupo -> NCMs validos segundo o PDM
    for _, r in cls.iterrows():
        for v in _ncms_do_texto(r["NCM"]):
            validos[r["GRUPO_MERCADORIA"]].add(v)
    for _, r in ncmref.iterrows():
        g = id2grp.get(r["ID_PDM"])
        if g:
            for v in _ncms_do_texto(r["NCM"]):
                validos[g].add(v)

    cnt = defaultdict(Counter)
    for _, r in tr.iterrows():
        cnt[r["GRUPO_MERCADORIA"]][r["y"]] += 1
    glob = Counter(tr["y"])

    linhas = []
    for _, r in te.iterrows():
        g = r.get("GRUPO_MERCADORIA", "")
        c = cnt.get(g)
        if c:
            vs = validos.get(g, set())
            # mais frequente do treino no grupo que pertenca ao conjunto PDM; senao moda do grupo
            ordem = sorted(c.items(), key=lambda kv: (-(kv[0] in vs), -kv[1]))
            pred = ordem[0][0]
            conf = c[pred] / sum(c.values())
            top3 = [v for v, _ in ordem[:3]]
        else:  # grupo ausente/desconhecido no treino
            pred = glob.most_common(1)[0][0]
            conf = 0.2
            top3 = [v for v, _ in glob.most_common(3)]
        linhas.append({"CODIGO_MATERIAL": r["CODIGO_MATERIAL"], "y_true": r["y"],
                       "y_pred": norm_rotulo("NCM", pred), "conf": round(conf, 4),
                       "top3": "|".join(norm_rotulo("NCM", v) for v in top3)})
    df = pd.DataFrame(linhas)
    salvar_pred(SOLUCAO, "NCM", df)
    seg = time.time() - t0
    obs = ("NCM mais frequente do treino dentro do grupo, priorizando o conjunto de NCMs validos do "
           "PDM (pdm_classes+pdm_ncm_referencia, normalizados p/ 8 digitos); top3 por frequencia "
           "priorizando validos; abstencao 0/2000 (0.0%)")
    salvar_meta(SOLUCAO, "NCM", segundos=round(seg, 2), chamadas_api=0,
                tokens_entrada=0, tokens_saida=0, modelo="", custo_estimado_usd=0.0,
                observacoes=obs)
    log(f"NCM ok em {seg:.1f}s | abstencao 0.0%")
    return 0.0


# ========================= GRUPO_MERCADORIA ===========================

# abreviacoes dadas na tarefa + identificadas inspecionando o TREINO
ABREV = {"PARAF": "PARAFUSO", "SEXT": "SEXTAVADO", "HIDR": "HIDRAULICA", "MANG": "MANGUEIRA",
         "RET": "RETENTOR", "ROL": "ROLAMENTO", "VALV": "VALVULA", "CONEX": "CONEXAO",
         "ELETR": "ELETRICO", "LUBRIF": "LUBRIFICANTE",
         "PCA": "PORCA", "ELET": "ELETRICO", "SEG": "SEGURANCA", "ABRAS": "ABRASIVO",
         "ROSC": "ROSCADA", "COTOV": "COTOVELO", "FLANG": "FLANGE", "FLG": "FLANGE",
         "ORING": "O RING", "PROTECAO": "SEGURANCA", "EPI": "SEGURANCA", "FILT": "FILTRO",
         "ELEMENTO": "FILTRO", "CONDUTOR": "CABO", "COR": "CORREIA", "T": "TE",
         "CURVA": "COTOVELO", "CONT": "CONTATOR", "CONTACTOR": "CONTATOR", "VERGALHAO": "BARRA",
         "TAMPAO": "CAP", "JOELHO": "COTOVELO", "BOTINA": "CALCADO", "JTA": "JUNTA",
         "ARR": "ARRUELA", "DISJ": "DISJUNTOR", "MANOM": "MANOMETRO", "LAMP": "LAMPADA",
         "TERM": "TERMINAL", "NIPPLE": "NIPLE", "FUS": "FUSIVEL"}


def _toks(s):
    return tuple(re.findall(r"[A-Z0-9]+", norm_texto(s)))


def monta_lexico_grupo():
    cls = pd.read_csv(DADOS / "pdm_classes.csv", dtype=str).fillna("")
    sob = pd.read_csv(DADOS / "pdm_subst_sobressalentes.csv", dtype=str).fillna("")
    con = pd.read_csv(DADOS / "pdm_subst_conexoes.csv", dtype=str).fillna("")
    entradas = {}
    head_groups = defaultdict(set)
    for _, r in cls.iterrows():
        s = r["SUBSTANTIVO"]
        if s.startswith("("): continue
        st = _toks(s); g = r["GRUPO_MERCADORIA"]
        head_groups[st].add(g)
        quals = [q.strip() for q in r["QUALIFICADOR"].split("|")] if r["QUALIFICADOR"] else [""]
        for q in quals:
            entradas.setdefault(st + _toks(q), g)
    for _, r in sob.iterrows():
        ent = _toks(r["SUBSTANTIVO_E_QUALIFICADOR"])
        entradas[ent] = "SOB01"; head_groups[ent[:1]].add("SOB01__sub")
    for _, r in con.iterrows():
        ent = _toks(r["SUBSTANTIVO_E_QUALIFICADOR"])
        entradas[ent] = "TUB01"; head_groups[ent[:1]].add("TUB01__con")
    # substantivo sozinho quando o grupo e unico dentro do pdm_classes
    for _, r in cls.iterrows():
        s = r["SUBSTANTIVO"]
        if s.startswith("("): continue
        st = _toks(s)
        gs = {g for g in head_groups[st] if "__" not in g}
        if len(gs) == 1 and st not in entradas:
            entradas[st] = next(iter(gs))
    # cabeca de 1 token das listas de sobressalentes/conexoes quando nao conflita
    for src, gname in ((sob, "SOB01"), (con, "TUB01")):
        for _, r in src.iterrows():
            h = _toks(r["SUBSTANTIVO_E_QUALIFICADOR"])[:1]
            gs = {g.split("__")[0] for g in head_groups[h]}
            if len(gs) == 1 and h not in entradas:
                entradas[h] = gname
    # qualificadores de LUVA de seguranca citados nas regras NCM do PDM (PDM070)
    for q in ("VAQUETA", "RASPA", "NITRILICA", "LATEX", "MALHA"):
        entradas[("LUVA", q)] = "EPI01"
    entradas[("O", "RING")] = "VED01"       # O-RING sem o substantivo ANEL
    entradas[("DESGASTE",)] = "SOB01"       # ANEL DESGASTE sem o substantivo
    entradas[("EXPULSOR",)] = "SOB01"       # ANEL EXPULSOR sem o substantivo
    entradas[("LABIRINTO",)] = "SOB01"      # ANEL LABIRINTO sem o substantivo
    return entradas


def _expandir(ts):
    out = []
    for t in ts:
        out.extend(ABREV.get(t, t).split())
    return out


def _match_grupo(desc, entradas):
    ts = _toks(desc)
    if ts[:2] == ("NAO", "UTILIZAR"):  # boilerplate 'NAO UTILIZAR - USAR COD 123 - ...'
        ts = tuple(t for t in ts[2:] if t not in ("USAR", "COD"))
        while ts and ts[0].isdigit():
            ts = ts[1:]
    ts = _expandir(ts)
    if not ts:
        return "", 0, []
    janela = ts[:8]
    head = ts[0]
    cands = []
    for ent, g in entradas.items():
        if ent[0] != head: continue
        resto = list(ent[1:])
        if not resto:
            cands.append((1, -99, g)); continue
        pos = [janela.index(q) for q in resto if q in janela[1:]]
        if len(pos) == len(resto):  # todos os qualificadores presentes na janela inicial
            cands.append((len(ent), -min(pos), g))
    if not cands:
        return "", 0, []
    cands.sort(reverse=True)  # mais tokens casados > qualificador mais proximo do inicio
    top3 = []
    for _, _, g in cands:
        if g not in top3:
            top3.append(g)
    return cands[0][2], cands[0][0], top3[:3]


def roda_grupo():
    t0 = time.time()
    te = ler("GRUPO_MERCADORIA", "teste")
    entradas = monta_lexico_grupo()
    log(f"GRUPO: lexico com {len(entradas)} entradas do PDM")
    linhas = []
    n_abst = 0
    for _, r in te.iterrows():
        g, n, top3 = _match_grupo(r["DESCRICAO_CURTA"], entradas)
        if not g:  # descricao curta truncada ou com erro: tenta a longa
            g, n, top3 = _match_grupo(r["DESCRICAO_LONGA"], entradas)
        if g:
            conf = 0.9 if n >= 2 else 0.8
            linhas.append({"CODIGO_MATERIAL": r["CODIGO_MATERIAL"], "y_true": r["y"],
                           "y_pred": norm_rotulo("GRUPO_MERCADORIA", g), "conf": conf,
                           "top3": "|".join(norm_rotulo("GRUPO_MERCADORIA", x) for x in top3)})
        else:
            n_abst += 1
            linhas.append({"CODIGO_MATERIAL": r["CODIGO_MATERIAL"], "y_true": r["y"],
                           "y_pred": "", "conf": 0.0, "top3": ""})
    df = pd.DataFrame(linhas)
    salvar_pred(SOLUCAO, "GRUPO_MERCADORIA", df)
    seg = time.time() - t0
    obs = (f"lexico substantivo(+qualificador)->grupo do PDM ({len(entradas)} entradas) + "
           f"{len(ABREV)} abreviacoes (dadas + identificadas no treino); casa primeiros tokens "
           f"da descricao (curta, senao longa); "
           f"abstencao {n_abst}/{len(te)} ({n_abst/len(te):.1%})")
    salvar_meta(SOLUCAO, "GRUPO_MERCADORIA", segundos=round(seg, 2), chamadas_api=0,
                tokens_entrada=0, tokens_saida=0, modelo="", custo_estimado_usd=0.0,
                observacoes=obs)
    log(f"GRUPO_MERCADORIA ok em {seg:.1f}s | abstencao {n_abst/len(te):.1%}")
    return n_abst / len(te)


def main():
    log("== 02_regras.py: inicio ==")
    taxas = {}
    taxas["GRUPO_MERCADORIA"] = roda_grupo()
    taxas["NCM"] = roda_ncm()
    taxas["FABRICANTE"] = roda_fabricante()
    taxas["REFERENCIA_FABRICANTE"] = roda_referencia()
    log("== fim == abstencoes: " + ", ".join(f"{k}={v:.1%}" for k, v in taxas.items()))


if __name__ == "__main__":
    sys.exit(main())
