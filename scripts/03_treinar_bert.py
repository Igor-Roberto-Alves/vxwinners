"""Treina o extrator BERT (classificacao de token BIO) nos rotulos gratuitos.

Roda em CPU. O modelo padrao e multilingue e pequeno de proposito: o texto de
cadastro e muito templado, e um modelo grande nao paga o tempo de treino num
hackathon. Para mais qualidade: --modelo neuralmind/bert-base-portuguese-cased

Uso: python 03_treinar_bert.py [--epocas 3] [--lote 16] [--modelo NOME] [--lr 5e-5]
"""

import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import ExtratorBert, GeradorRotulos, Pdm  # noqa: E402
from saneamento.bert import MODELO_PADRAO  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--modelo", default=MODELO_PADRAO)
p.add_argument("--epocas", type=int, default=3)
p.add_argument("--lote", type=int, default=16)
p.add_argument("--lr", type=float, default=5e-5)
p.add_argument("--max-len", type=int, default=96)
p.add_argument("--semente", type=int, default=42)
p.add_argument("--manter-retomada", action="store_true",
               help="conserva retomada.pt (1 GB) depois do treino terminar")
p.add_argument("--retomar", action="store_true",
               help="continua de onde o checkpoint parou, em vez de recomecar")
p.add_argument("--destino", default=None)
a = p.parse_args()

ART = Path(a.artefatos)
DESTINO = Path(a.destino or ART / "modelo_bert")

pdm = Pdm.carregar(ART / "pdm.json")
treino = GeradorRotulos.ler(ART / "treino.jsonl")
validacao = GeradorRotulos.ler(ART / "validacao.jsonl")

print("=" * 78)
print("TREINO DO EXTRATOR BERT".center(78))
print("=" * 78)
print(f"Modelo base ........................... {a.modelo}")
print(f"Exemplos de treino .................... {len(treino):>7,}")
print(f"Exemplos de validacao ................. {len(validacao):>7,}")
print(f"Rotulos BIO ........................... {1 + 2 * len(pdm.nomes_atributos):>7}")
print(f"Epocas / lote / lr .................... {a.epocas} / {a.lote} / {a.lr}")
print()

ext = ExtratorBert(pdm.nomes_atributos, modelo_base=a.modelo, max_len=a.max_len)
if a.retomar and (DESTINO / "rotulos.json").exists():
    ext.carregar(DESTINO, para_treino=True)
    feitas = ext.epoca_concluida
    if feitas >= a.epocas:
        sys.exit(f"checkpoint ja tem {feitas} epocas concluidas (pedido: {a.epocas}). "
                 f"Use --epocas maior para continuar.")
    print(f"Retomando: {feitas} epoca(s) ja concluida(s)")
elif a.retomar:
    print(f"Nenhum checkpoint em {DESTINO}: comecando do zero")

print(f"Dispositivo: {ext.dispositivo}")
t0 = time.time()
historico = ext.treinar(treino, validacao, epocas=a.epocas, lote=a.lote,
                        lr=a.lr, semente=a.semente, checkpoint=DESTINO)
minutos = (time.time() - t0) / 60

ext.salvar(DESTINO)
final = ext.avaliar(validacao)

print()
print("=" * 78)
print("RESULTADO".center(78))
print("=" * 78)
print(f"Tempo de treino ....................... {minutos:>7.1f} min")
print(f"Acuracia por token .................... {final['acuracia_token']:>7.3f}")
print(f"Precisao (tokens de atributo) ......... {final['precisao']:>7.3f}")
print(f"Recall (tokens de atributo) ........... {final['recall']:>7.3f}")
print(f"F1 .................................... {final['f1']:>7.3f}")
print(f"Sequencia 100% correta ................ {final['exato']:>7.3f}")
# retomada.pt guarda o estado do AdamW: 2 momentos x 135M parametros = ~1 GB,
# o dobro do modelo. Terminado o treino, retomar nao faz sentido e o arquivo so
# triplica o tamanho da transferencia. Para inferencia nao e usado.
retomada = DESTINO / "retomada.pt"
if retomada.exists() and not a.manter_retomada:
    mb = retomada.stat().st_size / 1048576
    retomada.unlink()
    print(f"\nretomada.pt removido ({mb:.0f} MB): treino concluido, nao e preciso retomar")
    print("   (use --manter-retomada para conservar)")

print(f"\nModelo gravado em {DESTINO}")
tamanho = sum(f.stat().st_size for f in DESTINO.iterdir() if f.is_file()) / 1048576
print(f"Tamanho do diretorio .................. {tamanho:>7.0f} MB")

(DESTINO / "metricas.json").write_text(
    json.dumps({"historico": historico, "final": final, "config": vars(a)},
               ensure_ascii=False, indent=1), encoding="utf-8")
