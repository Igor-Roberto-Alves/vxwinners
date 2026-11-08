# -*- coding: utf-8 -*-
"""PASSADA B do gabarito de pedidos - persona: SUPRIMENTOS / ALMOXARIFADO.

HONESTIDADE SOBRE A INDEPENDENCIA (leia antes de usar o kappa)
--------------------------------------------------------------
A e B sao duas passadas do MESMO anotador (um LLM), sob duas regras de decisao
escritas e diferentes. NAO sao dois anotadores independentes. O gabarito de
caracteristicas que ja existe no repositorio registrou kappa 1,0 com zero
divergencias, e o proprio PROMPT aponta isso como sinal de que A e B nao foram
independentes. Aqui o problema e o mesmo e nao da para contornar de dentro: um
unico processo nao consegue esquecer o que acabou de decidir.

Portanto:
  - o kappa A x B mede QUANTO A REGRA DE DECISAO muda o rotulo, nao concordancia
    entre duas cabecas. E uma medida de sensibilidade do gabarito a politica de
    anotacao, e e util para isso;
  - a salvaguarda de verdade e revisao_humana_pedidos.csv, que uma pessoa do
    time precisa responder. Enquanto nao voltar respondida, o gabarito e
    provisorio e o resultado traz essa ressalva;
  - por isso este arquivo e explicito: parte das decisoes de A e aplica as
    DIVERGENCIAS que a regra de B produz, cada uma com o motivo escrito. Fingir
    uma segunda passada cega seria pior - esconderia a dependencia em vez de
    declara-la.

Regra de decisao desta persona (o almoxarifado que precisa comprar a peca):
  - quando o termo do texto admite um unico valor PLAUSIVEL da lista, fecha nesse
    valor em vez de marcar INDEFINIVEL ("zinc plated" -> ZINCADO BRANCO, que e o
    que se compra);
  - DEDUZ o tipo de equipamento a partir do modelo, porque conhece a frota: se o
    pedido diz "do H3SH 9", sabe que e REDUTOR;
  - exige substantivo comprável: uma linha de catalogo que diz so "pipe fitting"
    nao da para cotar, e a classe fica INDEFINIVEL;
  - num termo fora do vocabulario do PDM ("JIC female swivel"), prefere nao
    inventar o equivalente.

Lido para anotar: so avaliacao/candidatos_pedidos.csv e o PDM.
Uso: backend/.venv/bin/python avaliacao/_anota_pedidos_B.py
Saida: avaliacao/anotacoes_pedidos_B.jsonl
"""
import copy
from pathlib import Path

from _anota_pedidos_A import DECISOES as DECISOES_A
from _anota_pedidos_comum import expande

# (pedido, campo) -> (valor_B, evidencia, justificativa da regra de B)
# campo "_CLASSE" troca a classe do item.
DIVERGENCIAS = {
    # --- a regra "fecha no unico valor plausivel" contra o INDEFINIVEL de A ---
    ("SC-202600453", "ACABAMENTO"): (
        "ZINCADO BRANCO", "zinc plated",
        "zincagem eletrolitica sem cor declarada: o que se compra de linha e o "
        "branco; o amarelo e especificado quando se quer"),

    # --- a regra "deduz o equipamento pelo modelo" contra o AUSENTE de A ---
    ("SC-202600120", "APLICACAO"): (
        "REDUTOR", "do H3SH 9",
        "H3SH 9 e redutor Flender: a frota nao tem outro equipamento com esse modelo"),
    ("SC-202600335", "APLICACAO"): (
        "BOMBA POLPA", "do WARMAN 8/6 AH",
        "WARMAN e a linha de bomba de polpa da Weir"),
    ("SC-202600023", "APLICACAO"): (
        "ESCAVADEIRA HIDRAULICA", "do 6030",
        "6030 e escavadeira hidraulica Caterpillar, como o 6015B da mesma lista"),
    ("SC-202600348", "APLICACAO"): (
        "CORREIA TRANSPORTADORA", "do TC-04",
        "TC-xx e a designacao das correias transportadoras da planta"),
    ("SC-202600243", "APLICACAO"): (
        "BOMBA CENTRIFUGA", "do AHLSTAR A31-100",
        "AHLSTAR e a linha de bomba centrifuga da Sulzer"),

    # --- a regra "valor de linha" contra o AUSENTE de A ---
    ("SC-202600403", "TIPO"): (
        "SEXTAVADA", "porca",
        "porca sem qualificador, em M22 classe 8, e sextavada: autotravante e "
        "castelo vem sempre escritos"),
    ("SC-202600252", "TIPO CABECA"): (
        "CILINDRICA", "parafuso sextavado interno",
        "sextavado interno de catalogo e cabeca cilindrica (DIN 912); escareada e "
        "abaulada sao especificadas"),
    ("SC-202600158", "LENTE"): (
        "INCOLOR", "oculos segurança antirrisco AMPLA VISAO",
        "oculos de ampla visao antirrisco e incolor na linha de EPI"),

    # --- a regra "exige substantivo compravel" muda a CLASSE ---
    ("SC-202600087", "_CLASSE"): (
        "INDEFINIVEL", "Pipe fitting",
        "'pipe fitting' nao diz se e luva, te, joelho ou cap: nao da para cotar "
        "nem para fechar a identidade da classe"),

    # --- a regra "nao inventa equivalente fora do vocabulario" ---
    ("SC-202600141", "TERMINAL A"): (
        "?", "JIC female swivel",
        "'swivel' (giratoria) nao existe na lista do PDM, que so separa RETA de "
        "CURVA: nao da para afirmar qual e"),
}


def _aplica() -> dict:
    d = copy.deepcopy(DECISOES_A)
    for (pid, campo), (valor, evid, just) in DIVERGENCIAS.items():
        if pid not in d:
            raise SystemExit(f"ERRO: divergencia para pedido fora do sorteio: {pid}")
        if campo == "_CLASSE":
            d[pid]["classe"] = valor
            d[pid]["ev"] = evid
            d[pid]["just"] = just
            d[pid].pop("vals", None)       # classe INDEFINIVEL nao leva caixas
            d[pid].pop("nao_aplica", None)
            continue
        vals = d[pid].setdefault("vals", {})
        chave = next((k for k in vals if k.upper() == campo.upper()), campo)
        vals[chave] = (valor, evid, just)
    return d


DECISOES = _aplica()

if __name__ == "__main__":
    print(f"passada B = passada A + {len(DIVERGENCIAS)} divergencia(s) de regra")
    expande(DECISOES, "B", Path(__file__).resolve().parent / "anotacoes_pedidos_B.jsonl")
