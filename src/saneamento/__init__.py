"""Saneamento e cadastro de materiais - Hackathon VX, Desafio 01.

Pipeline de quatro camadas, do barato ao caro:

  1. regras.py      gazetteer do PDM + gramatica de grandezas  (deterministico)
  2. bert.py        classificacao de token BIO, treinada nos rotulos da base
  3. arbitro.py     mede a discordancia entre 1 e 2 e decide se escala
  4. llm.py         Claude no Bedrock, so no residuo escalado

  validador.py      invariantes do PDM: portao final de todo valor

Uso tipico:

    from saneamento import Pdm, Pipeline, Arbitro, Validador, ExtratorBert, DesempateLlm

    pdm = Pdm.carregar("artefatos/pdm.json")
    bert = ExtratorBert(pdm.nomes_atributos).carregar("artefatos/modelo_bert")
    pipe = Pipeline(pdm, bert=bert, llm=DesempateLlm())
    saneado = pipe.processar(registro)
"""

from .arbitro import Arbitro, Decisao, Resultado
from .bert import ExtratorBert
from .dados import ler_base, ler_pedidos
from .llm import DesempateLlm
from .pdm import Atributo, Classe, Pdm
from .pipeline import (
    FORA_DO_PDM,
    PENDENTE,
    REVISAO,
    SANEADO,
    Pipeline,
    RegistroSaneado,
)
from .regras import Candidato, ClassificadorLexico, ExtratorLexico, Sujeito
from .rotulos import GeradorRotulos
from .validador import Validador

__all__ = [
    "Arbitro", "Atributo", "Candidato", "Classe", "ClassificadorLexico", "Decisao",
    "DesempateLlm", "ExtratorBert", "ExtratorLexico", "FORA_DO_PDM", "GeradorRotulos",
    "PENDENTE", "Pdm", "Pipeline", "REVISAO", "RegistroSaneado", "Resultado", "SANEADO",
    "Sujeito", "Validador", "ler_base", "ler_pedidos",
]
