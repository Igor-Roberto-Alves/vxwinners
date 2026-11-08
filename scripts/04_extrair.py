"""Roda o pipeline completo: regras -> BERT -> arbitro -> LLM no residuo.

Uso:
  # so as camadas baratas, sem BERT nem LLM (baseline deterministico)
  python 04_extrair.py --sem-bert --sem-llm

  # com BERT, LLM desligado: mostra quanto seria escalado e por que
  python 04_extrair.py --sem-llm

  # completo, com desempate no Bedrock
  python 04_extrair.py --limite 300

  # os 520 pedidos de cadastro em vez da base
  python 04_extrair.py --pedidos
"""

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import (  # noqa: E402
    FORA_DO_PDM, PENDENTE, REVISAO, SANEADO,
    Arbitro, DesempateLlm, ExtratorBert, Pdm, Pipeline, Validador,
    ler_base, ler_pedidos,
)
from saneamento.llm import MODELO_PADRAO  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--pedidos-arquivo", default=str(RAIZ / "dados/02_pedidos_cadastro.xlsx"))
p.add_argument("--pedidos", action="store_true", help="processa os 520 pedidos de cadastro")
p.add_argument("--sem-bert", action="store_true")
p.add_argument("--sem-llm", action="store_true")
p.add_argument("--modelo-llm", default=MODELO_PADRAO)
p.add_argument("--limiar", type=float, default=0.30, help="indice de discordancia que escala para o LLM")
p.add_argument("--limiar-bert", type=float, default=0.60)
p.add_argument("--escalar-pendentes", action="store_true", help="manda tambem os obrigatorios vazios ao LLM")
p.add_argument("--limite", type=int, default=0, help="processa so os N primeiros registros")
p.add_argument("--congelar-aprendizado", action="store_true",
               help="consulta o dicionario aprendido sem aprender nem gravar "
                    "(execucao reprodutivel)")
p.add_argument("--sem-aprendizado", action="store_true",
               help="nao le nem alimenta artefatos/aprendizado.json")
p.add_argument("--saida", default=None)
p.add_argument("--sem-classe-aprendida", action="store_true",
               help="ignora artefatos/sujeito_aprendido.json (regras de classe do LLM)")
p.add_argument("--aplicar-desempates", nargs="?", const="", default=None, metavar="JSONL",
               help="aplica as respostas que scripts/10_desempatar_llm.py gravou "
                    "(padrao: artefatos/desempate_llm.jsonl), sem chamar o LLM")
p.add_argument("--aplicar-deteccao", nargs="?", const="", default=None, metavar="JSONL",
               help="aplica scripts/12_detectar_ausentes.py (padrao: "
                    "artefatos/deteccao_ausentes.jsonl): dado GENERICO vira PENDENTE, "
                    "PERDIDO volta como valor")
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")

# Regras de classe aprendidas pelo LLM (24_aprender_classes_llm.py). Sem o
# arquivo, nada muda.
from saneamento.sinonimos import carregar_sujeitos_aprendidos  # noqa: E402

n_sujeitos = 0 if a.sem_classe_aprendida else carregar_sujeitos_aprendidos(ART / "sujeito_aprendido.json")

bert = None
if not a.sem_bert:
    dir_modelo = ART / "modelo_bert"
    if not dir_modelo.exists():
        sys.exit(f"modelo nao encontrado em {dir_modelo}: rode 03_treinar_bert.py ou use --sem-bert")
    bert = ExtratorBert(pdm.nomes_atributos).carregar(dir_modelo)

llm = None if a.sem_llm else DesempateLlm(modelo=a.modelo_llm, cache=ART / "cache_llm")

aprendizado = None
if not a.sem_aprendizado:
    from saneamento.aprendizado import Aprendizado

    # pdm= ativa a trava de substantivo na ESCRITA: sem ele, o termo
    # 'PARAFUSO' (que e o sujeito da classe) volta a ser aprendido
    # como valor de MATERIAL a cada execucao.
    aprendizado = Aprendizado(ART / "aprendizado.json", pdm=pdm,
                              congelado=a.congelar_aprendizado)

arbitro = Arbitro(Validador(pdm), limiar_discordancia=a.limiar,
                  limiar_bert=a.limiar_bert, escalar_pendentes=a.escalar_pendentes)
desempates = {}
if a.aplicar_desempates is not None:
    from saneamento.pipeline import carregar_desempates
    arq = Path(a.aplicar_desempates or ART / "desempate_llm.jsonl")
    desempates = carregar_desempates(arq)
    print(f"Desempates do LLM a aplicar ........... {len(desempates):,} registros ({arq})")
deteccoes = {}
if a.aplicar_deteccao is not None:
    from saneamento.pipeline import carregar_deteccoes
    arq = Path(a.aplicar_deteccao or ART / "deteccao_ausentes.jsonl")
    deteccoes = carregar_deteccoes(arq)
    print(f"Deteccoes a aplicar ................... {len(deteccoes):,} registros ({arq})")
pipe = Pipeline(pdm, bert=bert, llm=llm, arbitro=arbitro, aprendizado=aprendizado,
                desempates=desempates, deteccoes=deteccoes)

if a.pedidos:
    registros = ler_pedidos(a.pedidos_arquivo)
    rotulo_fonte = "pedidos de cadastro"
else:
    registros = ler_base(a.base)
    rotulo_fonte = "base de materiais"
if a.limite:
    registros = registros[: a.limite]

print("=" * 78)
print("PIPELINE DE SANEAMENTO".center(78))
print("=" * 78)
print(f"Fonte ................................. {rotulo_fonte} ({len(registros):,} registros)")
print(f"Camada 1 regras lexicas ............... ativa")
print(f"Camada 2 BERT ......................... {'ativa' if bert else 'DESLIGADA'}")
print(f"Camada 3 arbitro ...................... limiar de discordancia {a.limiar}")
print(f"Camada 4 LLM .......................... {a.modelo_llm if llm else 'DESLIGADA'}")
print(f"Classes aprendidas pelo LLM ........... {n_sujeitos} regras")
if aprendizado is not None:
    e = aprendizado.estatisticas()
    print(f"Dicionario aprendido .................. {e['entradas']} termos "
          f"({e['confiaveis']} confiaveis, {e['a_revisar']} a revisar)")
print()

t0 = time.time()
resultados = pipe.processar_lote(registros)
segundos = time.time() - t0

# ------------------------------------------------------------------ relatorio

n = len(resultados)
estados = Counter(r.estado for r in resultados)
escalados = [r for r in resultados if r.escalado]
candidatos_escalada = [r for r in resultados if r.motivos_escalada and r.estado != FORA_DO_PDM]
fontes = Counter(d.fonte for r in resultados for d in r.decisoes.values() if d.valor)
motivos = Counter(m.split(":")[0].split(" >=")[0] for r in candidatos_escalada for m in r.motivos_escalada)

print()
print("=" * 78)
print("ESTADO DOS REGISTROS".center(78))
print("=" * 78)
for e in (SANEADO, PENDENTE, REVISAO, FORA_DO_PDM):
    print(f"{e:22s} {estados[e]:>8,}  {100 * estados[e] / n:>5.1f}%")
# Segundo eixo: SANEADO diz que o que o texto informa esta certo; COMPLETO diz
# que nao falta obrigatorio nenhum (o que falta vai para enriquecimento).
completos = sum(1 for r in resultados if r.estado == SANEADO and r.completo)
saneados_incompletos = sum(1 for r in resultados if r.estado == SANEADO and not r.completo)
print(f"{'  saneado completo':22s} {completos:>8,}  {100 * completos / n:>5.1f}%   (todo obrigatorio cheio e chave fechada)")
print(f"{'  saneado incompleto':22s} {saneados_incompletos:>8,}  {100 * saneados_incompletos / n:>5.1f}%   "
      "(falta dado que o texto nao traz -> enriquecimento)")
print(f"{'tempo total':22s} {segundos:>8.1f}s  ({n / max(segundos, 0.001):.0f} registros/s)")

print()
print("=" * 78)
print("DISCORDANCIA ENTRE AS CAMADAS".center(78))
print("=" * 78)
print(f"Registros que o arbitro escalaria ..... {len(candidatos_escalada):>8,}"
      f"  {100 * len(candidatos_escalada) / n:>5.1f}%")
print(f"Efetivamente enviados ao LLM .......... {len(escalados):>8,}")
disc = sorted(r.discordancia for r in resultados if r.estado != FORA_DO_PDM)
if disc:
    print(f"Indice de discordancia  mediana ....... {disc[len(disc) // 2]:>8.3f}")
    print(f"                        p90 ........... {disc[int(len(disc) * 0.9)]:>8.3f}")
print("\nMotivos de escalada:")
for m, q in motivos.most_common(8):
    print(f"   {m:52s} {q:>7,}")

print()
print("=" * 78)
print("DE ONDE VEIO CADA VALOR ACEITO".center(78))
print("=" * 78)
total_valores = sum(fontes.values())
for f, q in fontes.most_common():
    print(f"   {f:22s} {q:>8,}  {100 * q / total_valores:>5.1f}%")

completude = [r.completude for r in resultados if r.estado != FORA_DO_PDM]
if completude:
    print()
    print(f"Completude media dos obrigatorios ..... {sum(completude) / len(completude):>8.3f}")

chaves = Counter(r.chave_identidade for r in resultados if r.chave_identidade)
dups = {k: v for k, v in chaves.items() if v > 1}
print()
print("=" * 78)
print("IDENTIDADE (REGRA 10)".center(78))
print("=" * 78)
print(f"Registros com chave fechada ........... {sum(chaves.values()):>8,}")
print(f"Chaves distintas ...................... {len(chaves):>8,}")
print(f"Chaves com mais de um codigo .......... {len(dups):>8,}")
print(f"Codigos redundantes (duplicidade) ..... {sum(v - 1 for v in dups.values()):>8,}")

if deteccoes:
    print(f"Dados GENERICOS marcados (-> PENDENTE)  {pipe.contador['genericos_marcados']:>8,}")
    print(f"Dados PERDIDOS recuperados ............ {pipe.contador['perdidos_recuperados']:>8,}")
if desempates:
    print(f"Desempates do LLM aplicados ........... {pipe.contador['desempates_aplicados']:>8,}"
          f"  de {len(desempates):,} gravados (o resto ja nao estava em duvida)")

if llm:
    print()
    print(llm.resumo())
    falhas = pipe.contador.get("falhas_llm", 0)
    if falhas:
        print(f"FALHAS DE CHAMADA AO LLM: {falhas:,}")
        print(f"  ultimo erro: {pipe.ultimo_erro_llm[:200]}")
    if llm.erro_cliente:
        print(f"LLM indisponivel: {llm.erro_cliente}")
        print("O residuo ficou marcado como REVISAO_HUMANA, que e o comportamento correto.")
    if falhas and not llm.contador["chamadas"]:
        print("\nNenhuma chamada teve sucesso: verifique MODELO_LLM e as credenciais")
        print("antes de confiar neste resultado.")

# ------------------------------------------------------------------ saida

# Com --limite o resultado e PARCIAL e nao pode sobrescrever o artefato da base
# inteira: foi assim que uma medicao de 6.000 registros quase apagou o
# decisoes_base.jsonl de onde sairam o catalogo e os numeros reportados.
sufixo = "pedidos" if a.pedidos else "base"
if a.limite:
    sufixo += f"_{a.limite}"
saida = Path(a.saida or ART / f"saneado_{sufixo}.csv")
with saida.open("w", encoding="utf-8", newline="") as fh:
    campos = list(resultados[0].como_dict().keys())
    w = csv.DictWriter(fh, fieldnames=campos)
    w.writeheader()
    for r in resultados:
        w.writerow(r.como_dict())

detalhe = ART / f"decisoes_{sufixo}.jsonl"
with detalhe.open("w", encoding="utf-8") as fh:
    for r in resultados:
        fh.write(json.dumps({
            "codigo": r.codigo, "id_pdm": r.id_pdm, "estado": r.estado,
            "discordancia": round(r.discordancia, 3), "escalado": r.escalado,
            "decisoes": [
                # 'evidencia' e o trecho do texto original que gerou o valor.
                # Sem ela na trilha, nao da para mostrar O QUE virou O QUE -
                # que e a pergunta que qualquer auditor faz primeiro.
                {"atributo": d.atributo, "valor": d.valor, "fonte": d.fonte,
                 "estado": d.estado, "confianca": round(d.confianca, 3),
                 "evidencia": d.evidencia,
                 "motivo": d.motivo, "regra": d.candidato_regra, "bert": d.candidato_bert}
                for d in r.decisoes.values()
            ],
        }, ensure_ascii=False) + "\n")

if aprendizado is not None:
    # reaplica as travas ao dicionario inteiro: elas sao de escrita, e o arquivo
    # sobrevive ao codigo. Termo aprendido antes de a trava existir seguiria
    # respondendo para sempre.
    removidos = aprendizado.revalidar(pdm)
    if removidos:
        print(f"\nrevalidacao do dicionario removeu {removidos} entrada(s) insegura(s)")
    aprendizado.salvar()
    e = aprendizado.estatisticas()
    print()
    print("=" * 78)
    print("DICIONARIO APRENDIDO".center(78))
    print("=" * 78)
    print(f"Termos no dicionario .................. {e['entradas']:>8,}  "
          f"({e['confiaveis']} confiaveis)")
    print(f"  aprendidos nesta execucao ........... {e['aprendidos']:>8,}")
    print(f"  confirmados (vistos de novo) ........ {e['confirmados']:>8,}")
    print(f"  rejeitados (termo ruim/conflito) .... {e['rejeitados']:>8,}")
    print(f"Caixas resolvidas pelo aprendido ...... {e['acertos']:>8,}  "
          f"<- chamadas de LLM evitadas")
    print(f"  recusados pelo enum da classe ....... {e['recusados_pelo_enum']:>8,}  "
          f"(protecao contra vazamento entre classes)")
    print(f"Arquivo ............................... {ART / 'aprendizado.json'}")

print(f"\nGravado: {saida}")
print(f"Gravado: {detalhe}  (trilha de auditoria por atributo)")
