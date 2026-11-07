"""Camada 3 - arbitro: mede a discordancia entre regra e BERT e decide quem desempata.

O LLM e caro e nao e reproduzivel, entao ele nao roda na base inteira: roda so
onde as duas camadas baratas nao fecham. Este modulo e quem define "nao fecham".

Decisao por atributo:

  regra      BERT       situacao                              estado
  ---------  ---------  ------------------------------------  --------------------
  valor      valor      iguais                                ACEITO (acordo)
  valor      valor      diferentes                            CONFLITO  -> LLM
  valor      vazio      valor veio de lista de valores        ACEITO (regra manda)
  valor      vazio      valor veio de heuristica de ordem     ACEITO (confianca media)
  vazio      valor      valor passa no validador              ACEITO
  vazio      valor      valor recusado pelo validador         INVALIDO  -> LLM
  vazio      vazio      atributo obrigatorio                  PENDENTE (sem LLM)
  ambiguo    qualquer   gazetteer achou 2+ valores            AMBIGUO   -> LLM

PENDENTE nao vai para o LLM de proposito: quando a informacao nao esta no texto,
nenhum modelo pode preencher sem inventar. Esse caso e enriquecimento (fonte
externa) ou devolucao ao solicitante, nao extracao.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .pdm import Classe, aplica_atributo
from .regras import Candidato
from .validador import Validador

# Peso de cada tipo de desacordo no indice de discordancia do registro.
PESO = {
    "CONFLITO": 1.00,   # as duas camadas afirmam valores diferentes
    "AMBIGUO": 0.70,    # dicionario casou mais de um valor permitido
    "INVALIDO": 0.60,   # BERT recortou um trecho que o PDM nao aceita
    "INCERTO": 0.40,    # so o BERT preencheu, e abaixo do limiar
    "ACEITO": 0.00,
    "PENDENTE": 0.00,   # ausencia de dado nao e discordancia
}

# Estados que exigem decisao humana (caixa com DUAS respostas plausiveis).
# INVALIDO fica fora de proposito: ali a caixa esta vazia nas duas camadas, o
# BERT so recortou um trecho que o enum do PDM nao aceita. Isso e pendencia com
# uma pista para o LLM, nao divergencia que uma pessoa precise arbitrar - e
# tratar como tal jogava 49,5% da base para revisao humana sem motivo.
ESTADOS_REVISAO = ("CONFLITO", "AMBIGUO")

LIMIAR_DISCORDANCIA = 0.30
LIMIAR_BERT = 0.60
LIMIAR_SUJEITO = 0.60


@dataclass
class Decisao:
    atributo: str
    valor: str | None
    fonte: str
    confianca: float
    estado: str
    motivo: str = ""
    evidencia: str = ""
    candidato_regra: str | None = None
    candidato_bert: str | None = None


@dataclass
class Resultado:
    decisoes: dict[str, Decisao] = field(default_factory=dict)
    discordancia: float = 0.0
    escalar: bool = False
    motivos_escalada: list[str] = field(default_factory=list)
    completude: float = 0.0

    @property
    def valores(self) -> dict[str, str | None]:
        return {k: d.valor for k, d in self.decisoes.items()}

    def em_estado(self, *estados: str) -> list[Decisao]:
        return [d for d in self.decisoes.values() if d.estado in estados]


class Arbitro:
    def __init__(self, validador: Validador,
                 limiar_discordancia: float = LIMIAR_DISCORDANCIA,
                 limiar_bert: float = LIMIAR_BERT,
                 limiar_sujeito: float = LIMIAR_SUJEITO,
                 escalar_pendentes: bool = False):
        self.val = validador
        self.limiar = limiar_discordancia
        self.limiar_bert = limiar_bert
        self.limiar_sujeito = limiar_sujeito
        self.escalar_pendentes = escalar_pendentes

    # ------------------------------------------------------------- por atributo

    def _decidir(self, classe: Classe, nome: str,
                 regra: Candidato | None, bert: Candidato | None) -> Decisao:
        atributo = next((a for a in classe.atributos if a.nome == nome), None)
        if atributo is None:
            return Decisao(nome, None, "-", 0.0, "PENDENTE", "atributo nao pertence a classe")

        v_regra = self._validar(atributo, regra)
        v_bert = self._validar(atributo, bert)
        obrig = atributo.obrigatorio and atributo.sempre

        base = dict(
            atributo=nome,
            candidato_regra=v_regra.valor if v_regra else None,
            candidato_bert=v_bert.valor if v_bert else None,
        )

        # dicionario casou mais de um valor permitido: o texto e que e ambiguo
        if regra is not None and regra.ambiguo and regra.alternativas:
            if v_bert and v_bert.valor in regra.alternativas:
                return Decisao(**base, valor=v_bert.valor, fonte="bert_desempata",
                               confianca=min(0.88, v_bert.confianca), estado="ACEITO",
                               motivo=f"gazetteer ambiguo entre {list(regra.alternativas)}, BERT escolheu",
                               evidencia=v_bert.evidencia)
            return Decisao(**base, valor=None, fonte="gazetteer", confianca=0.0,
                           estado="AMBIGUO",
                           motivo=f"valores permitidos em conflito: {list(regra.alternativas)}")

        if v_regra and v_bert:
            if v_regra.valor == v_bert.valor:
                return Decisao(**base, valor=v_regra.valor, fonte="acordo",
                               confianca=min(0.99, 0.5 * (v_regra.confianca + v_bert.confianca) + 0.3),
                               estado="ACEITO", motivo="regra e BERT concordam",
                               evidencia=v_regra.evidencia)
            # atributo de lista: a regra e restricao dura, o BERT nao sobrepoe
            if atributo.fechado:
                return Decisao(**base, valor=v_regra.valor, fonte="gazetteer",
                               confianca=0.75, estado="CONFLITO",
                               motivo=f"BERT propos {v_bert.valor}, fora do casamento exato do dicionario",
                               evidencia=v_regra.evidencia)
            # Conflito em grandeza: mantem o valor da REGRA e escala para
            # desempate. Esvaziar os dois descartava a restricao de dominio
            # (alojamento > eixo > largura), que e a informacao mais confiavel
            # que temos para esse caso.
            return Decisao(**base, valor=v_regra.valor, fonte=v_regra.fonte,
                           confianca=0.50, estado="CONFLITO", evidencia=v_regra.evidencia,
                           motivo=f"regra diz {v_regra.valor}, BERT diz {v_bert.valor}")

        if v_regra and not v_bert:
            dura = atributo.fechado or v_regra.fonte in ("regra_pdm_2", "dominio")
            return Decisao(**base, valor=v_regra.valor,
                           fonte=v_regra.fonte, confianca=v_regra.confianca,
                           estado="ACEITO",
                           motivo="restricao do PDM" if dura else "heuristica de ordem, sem contraste",
                           evidencia=v_regra.evidencia)

        if v_bert and not v_regra:
            if v_bert.confianca >= self.limiar_bert:
                return Decisao(**base, valor=v_bert.valor, fonte="bert",
                               confianca=v_bert.confianca, estado="ACEITO",
                               motivo="regra nao achou, BERT confiante",
                               evidencia=v_bert.evidencia)
            return Decisao(**base, valor=None, fonte="bert", confianca=v_bert.confianca,
                           estado="INCERTO",
                           motivo=f"BERT propos {v_bert.valor} com confianca {v_bert.confianca:.2f}")

        # nenhuma camada preencheu
        if bert is not None and bert.valor and not v_bert:
            # O trecho recusado e dado valioso, nao lixo: o BERT afirmou que
            # aquele pedaco do texto pertence a esta caixa, e o enum do PDM nao
            # reconheceu o termo. Isso e exatamente um candidato a entrada de
            # dicionario. Gravar so dentro da mensagem de motivo perdia a
            # informacao para qualquer analise posterior.
            base["candidato_bert"] = bert.valor
            return Decisao(**base, valor=None, fonte="bert", confianca=0.0, estado="INVALIDO",
                           motivo=f"BERT propos {bert.valor}, recusado pelo validador")
        return Decisao(**base, valor=None, fonte="-", confianca=0.0,
                       estado="PENDENTE" if obrig else "ACEITO",
                       motivo="nao informado no texto")

    def _validar(self, atributo, cand: Candidato | None) -> Candidato | None:
        """Passa o candidato pelo validador do PDM. Recusado vira None."""
        if cand is None or cand.valor is None:
            return None
        v = self.val.valor(atributo, cand.valor)
        if not v.ok:
            return None
        return Candidato(cand.atributo, v.valor, cand.fonte, cand.confianca,
                         cand.evidencia, cand.alternativas, cand.ambiguo)

    # ------------------------------------------------------------- por registro

    def arbitrar(self, classe: Classe, regras: dict[str, Candidato],
                 bert: dict[str, Candidato] | None = None,
                 confianca_sujeito: float = 1.0,
                 substantivo: str = "") -> Resultado:
        bert = bert or {}
        res = Resultado()
        aplicaveis = [a for a in classe.atributos if aplica_atributo(a, substantivo)]
        for a in aplicaveis:
            res.decisoes[a.nome] = self._decidir(classe, a.nome, regras.get(a.nome), bert.get(a.nome))

        # Segunda passada: so agora da para saber se um obrigatorio CONDICIONAL se
        # aplica, porque a condicao depende de valores que acabaram de ser
        # decididos (COR vale "somente cabos de 1 condutor"). Filtrar por
        # a.sempre aqui era um bug: os 19 obrigatorios condicionais do PDM ficavam
        # fora da completude e nunca viravam PENDENTE, embora bloqueassem a chave
        # de identidade. A classe PDM062 (disjuntor) ficava em 0% de SANEADO
        # relatando PENDENTES vazio.
        valores_ate_agora = {n: d.valor for n, d in res.decisoes.items()}
        obrigatorios = [a.nome for a in aplicaveis
                        if a.obrigatorio
                        and aplica_atributo(a, substantivo, valores_ate_agora)]
        for nome in obrigatorios:
            d = res.decisoes[nome]
            if not d.valor and d.estado == "ACEITO":
                d.estado = "PENDENTE"
                d.motivo = d.motivo or "obrigatorio condicional aplicavel, nao informado"
        if obrigatorios:
            pesos = sum(PESO.get(res.decisoes[n].estado, 0.0) for n in obrigatorios)
            res.discordancia = pesos / len(obrigatorios)
            preenchidos = sum(1 for n in obrigatorios if res.decisoes[n].valor)
            res.completude = preenchidos / len(obrigatorios)
        else:
            res.completude = 1.0

        motivos = []
        if res.discordancia >= self.limiar:
            motivos.append(f"indice de discordancia {res.discordancia:.2f} >= {self.limiar:.2f}")
        conflitos = [d.atributo for d in res.em_estado("CONFLITO") if d.atributo in obrigatorios]
        if conflitos:
            motivos.append(f"conflito em atributo obrigatorio: {', '.join(conflitos)}")
        ambiguos = [d.atributo for d in res.em_estado("AMBIGUO")]
        if ambiguos:
            motivos.append(f"ambiguidade de dicionario: {', '.join(ambiguos)}")
        if confianca_sujeito < self.limiar_sujeito:
            motivos.append(f"sujeito incerto (confianca {confianca_sujeito:.2f})")
        if self.escalar_pendentes and res.em_estado("PENDENTE"):
            motivos.append("pendentes com segunda leitura habilitada")

        res.motivos_escalada = motivos
        res.escalar = bool(motivos)
        return res

    # ------------------------------------------------------------- pos-LLM

    def incorporar_llm(self, classe: Classe, res: Resultado,
                       proposto: dict[str, str | None],
                       evidencias: dict[str, str] | None = None,
                       aprendizado=None) -> Resultado:
        """Aplica a resposta do LLM, sempre sujeita ao validador.

        O LLM nao tem passe livre: valor fora da lista de valores permitidos e
        recusado do mesmo jeito que seria o do BERT.
        """
        for nome, valor in (proposto or {}).items():
            d = res.decisoes.get(nome)
            if d is None or valor is None:
                continue
            if d.estado == "ACEITO" and d.fonte == "acordo":
                continue                                  # acordo das duas camadas prevalece
            atributo = next((a for a in classe.atributos if a.nome == nome), None)
            if atributo is None:
                continue
            v = self.val.valor(atributo, valor)
            if not v.ok:
                d.motivo = f"{d.motivo}; LLM propos {valor}, recusado: {v.motivo}"
                continue
            d.valor, d.fonte, d.estado = v.valor, "llm", "ACEITO"
            d.confianca = 0.80
            d.evidencia = (evidencias or {}).get(nome, "") or d.evidencia
            d.motivo = f"desempate por LLM ({d.motivo})"
            # alimenta o dicionario: a mesma duvida nao deve custar outra chamada
            if aprendizado is not None and d.evidencia:
                atributo_alvo = next((x for x in classe.atributos if x.nome == nome), None)
                if atributo_alvo is not None:
                    aprendizado.aprender(atributo_alvo, d.evidencia, v.valor,
                                         "llm", classe.id_pdm)

        obrigatorios = [a.nome for a in classe.obrigatorios if a.nome in res.decisoes]
        if obrigatorios:
            res.completude = sum(1 for n in obrigatorios if res.decisoes[n].valor) / len(obrigatorios)
            res.discordancia = sum(
                PESO.get(res.decisoes[n].estado, 0.0) for n in obrigatorios
            ) / len(obrigatorios)
        return res
