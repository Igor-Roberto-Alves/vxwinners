"""Orquestracao das quatro camadas.

  1 regras lexicas  -> 2 BERT  -> 3 arbitro  -> 4 LLM (so no residuo)  -> validador

O validador fecha o circuito: nenhum valor entra no registro saneado sem passar
pelas invariantes do PDM, independentemente da camada que o propos.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field

from .arbitro import ESTADOS_REVISAO, Arbitro, Decisao, Resultado
from .bert import ExtratorBert
from .llm import DesempateLlm
from .pdm import Pdm
from .regras import Candidato, ClassificadorLexico, ExtratorLexico
from .rotulos import pares
from .texto import juntar, normalizar, normalizar_estrutura
from .validador import Validador

# Rotulo de um par "ATRIBUTO: VALOR": o nome antes dos dois pontos. Mesma forma
# que rotulos.RX_PAR usa para gerar o treino, para treino e inferencia verem o
# mesmo texto.
RX_ROTULO = re.compile(r"(?:^|[;,])\s*[A-Z][A-Z0-9/ ]{0,28}?\s*:")
# Rotulo de part number no comeco do trecho que o BERT recortou
# Caixas que o desempate por LLM pode resolver (o mesmo conjunto que
# scripts/10_desempatar_llm.py manda). PENDENTE puro fica de fora: sem nada no
# texto, nenhum modelo preenche sem inventar.
ESTADOS_ESCALAVEIS = ("CONFLITO", "AMBIGUO", "INVALIDO", "INCERTO")
# Anotado na decisao quando o BERT recortou um trecho que a lista do PDM nao
# tem. scripts/11_canonizar_termos.py procura exatamente este texto.
MOTIVO_FORA_DA_LISTA = "BERT propos {}, fora da lista do PDM"


def carregar_desempates(caminho) -> dict[str, tuple[dict, dict]]:
    """Le artefatos/desempate_llm.jsonl -> {codigo: (valores, evidencias)}.

    So os valores ACEITOS pelo validador quando o script 10 rodou; o pipeline
    ainda os passa de novo pelo validador ao incorporar.
    """
    import json
    from pathlib import Path

    out: dict[str, tuple[dict, dict]] = {}
    caminho = Path(caminho)
    if not caminho.exists():
        return out
    with caminho.open(encoding="utf-8") as fh:
        for linha in fh:
            r = json.loads(linha)
            aceitos = r.get("aceitos") or []
            if aceitos:
                out[str(r["codigo"])] = ({x["atributo"]: x["valor"] for x in aceitos},
                                         {x["atributo"]: x.get("evidencia", "") for x in aceitos})
    return out


def carregar_deteccoes(caminho) -> dict[str, dict[str, tuple[str, str]]]:
    """Le artefatos/deteccao_ausentes.jsonl -> {codigo: {atributo: (veredito, trecho)}}.

    So os vereditos que mudam alguma coisa (PERDIDO, PRESENTE_FORA_DO_PADRAO);
    AUSENTE confirma o que o pipeline ja faz.
    """
    import json
    from pathlib import Path

    out: dict[str, dict[str, tuple[str, str]]] = {}
    caminho = Path(caminho)
    if not caminho.exists():
        return out
    with caminho.open(encoding="utf-8") as fh:
        for linha in fh:
            r = json.loads(linha)
            if r.get("veredito") in ("PERDIDO", "PRESENTE_FORA_DO_PADRAO") and r.get("trecho"):
                out.setdefault(str(r["codigo"]), {})[r["atributo"]] = (r["veredito"], r["trecho"])
    return out


RX_ROTULO_REF = re.compile(
    r"^(?:P/N|PART NUMBER|PN|REFERENCIA FABRICANTE|REF FABRICANTE|REFERENCIA|REF"
    r"|CODIGO FABRICANTE|COD FABRICANTE|CODIGO|COD)(?:\s+(?:DE|DO|DA))?(?:\s+|$)")

# Estados finais do registro.
#
# Sanear nao e completar: e extrair e padronizar CORRETAMENTE tudo o que o texto
# informa. Obrigatorio que o texto nao traz nao torna o registro "nao saneado" -
# torna-o INCOMPLETO, que e outro eixo (campo `completo`), resolvido por
# enriquecimento ou devolucao ao solicitante, nunca por extracao.
SANEADO = "SANEADO"            # tudo o que o texto informa foi extraido e validado, sem duvida
PENDENTE = "PENDENTE"          # o texto traz valor obrigatorio que o PDM nao reconheceu
REVISAO = "REVISAO_HUMANA"     # conflito: duas leituras plausiveis do mesmo dado
FORA_DO_PDM = "FORA_DO_PDM"    # nao existe classe para o item


@dataclass
class RegistroSaneado:
    codigo: str
    estado: str
    id_pdm: str = ""
    substantivo: str = ""
    qualificador: str = ""
    grupo: str = ""
    confianca_sujeito: float = 0.0
    empate_sujeito: tuple[str, ...] = ()
    grupo_corrigido: bool = False
    descricao_original: str = ""
    descricao_pdm: str = ""
    descricao_curta: str = ""
    unidade_original: str = ""
    unidade_pdm: str | None = None
    unidade_motivo: str = ""
    ncm_original: str = ""
    ncm_pdm: str | None = None
    ncm_motivo: str = ""
    chave_identidade: str | None = None
    completude: float = 0.0
    completo: bool = False
    # Proveniencia do LLM: caixa cujo valor saiu de uma conclusao do LLM
    # ("ATRIBUTO=llm" desempate, "=llm_deteccao" valor perdido recuperado,
    # "=dicionario_llm" termo que o LLM canonizou e o dicionario aplicou), e
    # caixa que o LLM julgou generica (o que levou o registro a PENDENTE).
    decidido_por_llm: list[str] = field(default_factory=list)
    pendente_por_llm: list[str] = field(default_factory=list)
    discordancia: float = 0.0
    escalado: bool = False
    motivos_escalada: list[str] = field(default_factory=list)
    pendentes: list[str] = field(default_factory=list)
    conflitos: list[str] = field(default_factory=list)
    decisoes: dict[str, Decisao] = field(default_factory=dict)

    def como_dict(self) -> dict:
        return {
            "CODIGO_MATERIAL": self.codigo,
            "ESTADO": self.estado,
            "ID_PDM": self.id_pdm,
            "GRUPO_CORRIGIDO": int(self.grupo_corrigido),
            "SUBSTANTIVO": self.substantivo,
            "QUALIFICADOR": self.qualificador,
            "DESCRICAO_ORIGINAL": self.descricao_original,
            "DESCRICAO_PDM": self.descricao_pdm,
            "DESCRICAO_CURTA_PDM": self.descricao_curta,
            "UNIDADE_ORIGINAL": self.unidade_original,
            "UNIDADE_PDM": self.unidade_pdm or "",
            "UNIDADE_MOTIVO": self.unidade_motivo,
            "NCM_ORIGINAL": self.ncm_original,
            "NCM_PDM": self.ncm_pdm or "",
            "NCM_MOTIVO": self.ncm_motivo,
            "CHAVE_IDENTIDADE": self.chave_identidade or "",
            "COMPLETUDE": round(self.completude, 3),
            "COMPLETO": int(self.completo),
            "DECIDIDO_POR_LLM": " | ".join(self.decidido_por_llm),
            "PENDENTE_POR_LLM": " | ".join(self.pendente_por_llm),
            "DISCORDANCIA": round(self.discordancia, 3),
            "ESCALADO_LLM": int(self.escalado),
            "MOTIVOS_ESCALADA": " | ".join(self.motivos_escalada),
            "PENDENTES": " | ".join(self.pendentes),
            "CONFLITOS": " | ".join(self.conflitos),
            "FONTES": " | ".join(
                f"{k}={v.fonte}" for k, v in self.decisoes.items() if v.valor
            ),
        }


class Pipeline:
    def __init__(self, pdm: Pdm, bert: ExtratorBert | None = None,
                 llm: DesempateLlm | None = None, arbitro: Arbitro | None = None,
                 aprendizado=None,
                 desempates: dict[str, tuple[dict, dict]] | None = None,
                 deteccoes: dict[str, dict[str, tuple[str, str]]] | None = None):
        self.pdm = pdm
        self.validador = Validador(pdm)
        self.clf = ClassificadorLexico(pdm)
        self.aprendizado = aprendizado
        self.regras = ExtratorLexico(pdm, aprendizado=aprendizado)
        self._palavras_de_rotulo: set[str] | None = None
        self.bert = bert
        self.llm = llm
        self.arbitro = arbitro or Arbitro(self.validador)
        # codigo -> (valores, evidencias) ja decididos pelo LLM em execucao
        # anterior (scripts/10_desempatar_llm.py). Ver carregar_desempates().
        self.desempates = desempates or {}
        # codigo -> {atributo: (veredito, trecho)} de scripts/12_detectar_ausentes.py
        self.deteccoes = deteccoes or {}
        self._bert_fora_da_lista: dict[str, str] = {}
        self.contador = {"total": 0, SANEADO: 0, PENDENTE: 0, REVISAO: 0, FORA_DO_PDM: 0,
                         "escalados": 0, "falhas_llm": 0, "completos": 0,
                         "desempates_aplicados": 0, "genericos_marcados": 0,
                         "perdidos_recuperados": 0, "perdidos_recusados": 0}
        self.ultimo_erro_llm = ""

    # ------------------------------------------------------------- bert

    def _bert(self, texto: str, classe) -> dict[str, Candidato]:
        if self.bert is None:
            return {}
        tokens = self._tokens_para_bert(texto)
        if not tokens:
            return {}
        # Caixa TEXTUAL (lista fechada do PDM): o BERT so entra com valor DA
        # LISTA. Medido na base inteira, ali ele nunca preencheu nada que a regra
        # nao preenchesse (0 caixas exclusivas) e gerou 8.038 propostas fora da
        # lista ('FABRICANTE' como MATERIAL, 'PARA', 'USO') - cada uma virava
        # caixa INVALIDO, sem informacao nenhuma. Mas quando propoe OUTRO valor
        # valido ele aponta erro real da regra: 136 BITOLA em que o gazetteer
        # dizia M10 e o texto dizia M10X1,25 (rosca fina). Por isso a proposta
        # valida continua indo ao arbitro, que a registra como CONFLITO, e a
        # invalida e descartada aqui. Em LIVRE e NUMERICA nada muda.
        por_nome = {a.nome: a for a in classe.atributos}
        saida: dict[str, Candidato] = {}
        # O trecho fora da lista nao entra no arbitro, mas nao some: e o insumo
        # de scripts/11_canonizar_termos.py ('ZINC', 'MANOPLA', 'ACO ESPECIAL'),
        # que o LLM canoniza uma vez por termo. processar() o anota na decisao.
        self._bert_fora_da_lista = {}
        for p in self.bert.prever(tokens):
            atributo = por_nome.get(p.atributo)
            if atributo is None:
                continue                      # mascara pela classe prevista
            if atributo.fechado and not self.validador.valor(atributo, p.valor).ok:
                self._bert_fora_da_lista.setdefault(p.atributo, p.valor)
                continue                      # fora da lista: nao e evidencia de valor
            valor = p.valor
            if p.atributo in ("REFERENCIA FABRICANTE", "REFERENCIA"):
                # Com o texto cru o BERT ve o rotulo telegrafico e as vezes o
                # recorta junto ('PN 12560') ou sozinho ('PN', 'COD'): 53 dos 77
                # conflitos de part number da base eram so isso.
                valor = RX_ROTULO_REF.sub("", valor).strip()
                if not valor or not any(ch.isdigit() for ch in valor):
                    continue
            atual = saida.get(p.atributo)
            if atual is None or p.confianca > atual.confianca:
                saida[p.atributo] = Candidato(
                    atributo=p.atributo, valor=valor, fonte="bert",
                    confianca=p.confianca, evidencia=p.valor,
                )
        return saida

    def _tokens_para_bert(self, texto: str) -> list[str]:
        """Prepara o texto do mesmo jeito que o gerador de rotulos preparou o treino.

        Corrige um train/serve skew real: `rotulos.py` apaga o NOME do atributo
        do texto de treino (sem isso o modelo so aprenderia a copiar o que vem
        depois dos dois pontos e seria inutil nos registros telegraficos). Mas o
        texto de inferencia ainda contem esses nomes, e o modelo - que nunca os
        viu - passa a trata-los como VALOR: 3.141 registros tiveram a palavra
        'FABRICANTE' etiquetada como valor de MATERIAL.

        Remove exatamente o que o treino removeu: o rotulo de um par
        'ATRIBUTO: VALOR'. Texto telegrafico, que nao tem rotulo, passa intacto.
        Filtrar por lista de palavras seria cego - apagaria 'PARAFUSO' (que e o
        sujeito) e manteria 'ACABAMENTO' (que tambem e valor, em SEM ACABAMENTO).

        Sem expandir(): o treino (`rotulos.py`) usa o valor como esta escrito,
        sem expansao de abreviacao. Expandir aqui criava, na inferencia, palavras
        que o modelo nunca viu - FAB -> FABRICANTE e a origem dos 3.141
        'FABRICANTE' recortados como MATERIAL, e P/N -> PART NUMBER moveu mais 47
        registros para o mesmo erro (docs/07-abreviacoes.md, secao 5).
        """
        estruturado = normalizar_estrutura(texto)
        if ":" in estruturado:
            # remove o rotulo, preserva o valor que vem depois
            limpo = RX_ROTULO.sub(" ", estruturado)
        else:
            limpo = estruturado
        return normalizar(limpo).split()

    # ------------------------------------------------------------- registro

    def processar(self, registro: dict) -> RegistroSaneado:
        self.contador["total"] += 1
        codigo = str(registro.get("CODIGO_MATERIAL", ""))
        grupo = str(registro.get("GRUPO_MERCADORIA", "") or "").strip()
        # juntar() evita repetir conteudo: DESCRICAO_CURTA costuma ser truncamento
        # da LONGA, e o texto duplicado quebra a contagem de grandezas
        texto = juntar(*(
            str(registro.get(c, "") or "")
            for c in ("DESCRICAO_LONGA", "DESCRICAO_CURTA", "FABRICANTE", "REFERENCIA_FABRICANTE")
        ))
        original = str(registro.get("DESCRICAO_LONGA", "") or "")
        # '; ' e nao ' ': com espaco, o ultimo par da LONGA continuava dentro da
        # CURTA ('DIAM NOMINAL:1,5POL VALV GAV ACIONAMENTO ...'), o valor era
        # recusado e a camada 0 perdia exatamente o atributo que fecha a linha.
        estruturado = normalizar_estrutura("; ".join(
            str(registro.get(c, "") or "")
            for c in ("DESCRICAO_LONGA", "DESCRICAO_CURTA")))

        sujeito = self.clf.classificar(texto, grupo)
        if sujeito.classe is None:
            self.contador[FORA_DO_PDM] += 1
            return RegistroSaneado(
                codigo=codigo, estado=FORA_DO_PDM, grupo=grupo,
                descricao_original=original,
                motivos_escalada=["nenhuma classe do PDM casa com o substantivo"],
            )

        classe = sujeito.classe
        # texto_estruturado preserva ':' e ';' para a camada 0 ler o rotulo
        cand_regras = self.regras.extrair(texto, classe, sujeito.substantivo,
                                          texto_estruturado=estruturado)
        # A coluna REFERENCIA_FABRICANTE do ERP e o campo proprio do cadastro e
        # vale mais que o rotulo telegrafico lido no texto: quando ela existe, a
        # regra telegrafica cede e _preencher_das_colunas usa a coluna. Sem isso
        # a regra trocava '1728 9860 67' (coluna) por um codigo lido do texto, e
        # a chave de identidade mudava em 308 registros.
        ref = cand_regras.get("REFERENCIA FABRICANTE")
        if (ref is not None and ref.fonte == "rotulo_telegrafico"
                and str(registro.get("REFERENCIA_FABRICANTE", "") or "").strip()):
            cand_regras["REFERENCIA FABRICANTE"] = Candidato(
                ref.atributo, None, "rotulo_telegrafico", 0.0,
                motivo="coluna REFERENCIA_FABRICANTE do ERP tem precedencia")
        cand_bert = self._bert(texto, classe)
        # Mesma precedencia para o BERT: com a coluna do ERP preenchida, o
        # part number recortado do texto nao a substitui.
        if str(registro.get("REFERENCIA_FABRICANTE", "") or "").strip():
            cand_bert.pop("REFERENCIA FABRICANTE", None)
        res: Resultado = self.arbitro.arbitrar(classe, cand_regras, cand_bert,
                                               sujeito.confianca, sujeito.substantivo)
        for nome, trecho in self._bert_fora_da_lista.items():
            d = res.decisoes.get(nome)
            if d is not None and not d.valor and d.candidato_bert is None:
                d.candidato_bert = trecho
                d.motivo = f"{d.motivo}; {MOTIVO_FORA_DA_LISTA.format(trecho)}"
        self._bert_fora_da_lista = {}

        escalado = False
        # Desempate ja feito por scripts/10_desempatar_llm.py: aplica sem chamar
        # o LLM de novo. So nas caixas que AINDA estao em duvida - a resposta foi
        # dada para uma extracao anterior, e caixa que a extracao atual ja
        # resolveu nao pode ser sobrescrita por ela.
        if self.desempates and codigo in self.desempates:
            valores, evidencias = self.desempates[codigo]
            em_duvida = {d.atributo for d in res.em_estado(*ESTADOS_ESCALAVEIS)}
            valores = {k: v for k, v in valores.items() if k in em_duvida}
            if valores:
                res = self.arbitro.incorporar_llm(
                    classe, res, valores, evidencias=evidencias,
                    aprendizado=self.aprendizado, codigo=codigo)
                escalado = True
                self.contador["desempates_aplicados"] += 1
        # Deteccao de ausente x perdido (scripts/12_detectar_ausentes.py). So
        # atua em caixa que continua VAZIA na extracao atual.
        #   PERDIDO: o LLM apontou um trecho que existe no texto e e valor valido
        #            do PDM -> entra como valor, pelo validador, como o desempate.
        #   GENERICO: o texto informa o atributo de forma que nao decide um valor
        #            da lista ('ZINCADO' sem a cor, 'INOX' sem o grau). A caixa
        #            continua vazia, mas o registro nao esta saneado: o dado
        #            existe e nao foi padronizado. Vai para PENDENTE, com o trecho.
        if self.deteccoes and codigo in self.deteccoes:
            perdidos = {}
            for nome, (veredito, trecho) in self.deteccoes[codigo].items():
                d = res.decisoes.get(nome)
                if d is None or d.valor or not trecho:
                    continue
                if veredito == "PERDIDO":
                    # Caixa de formato livre (part number) aceita qualquer texto,
                    # entao o validador nao pega a atribuicao errada do LLM: em
                    # 10410458 ele chamou de part number o MODELO 'AHLSTAR A22 80',
                    # que ja estava na caixa MODELO EQUIPAMENTO, e a chave fechou
                    # com um codigo inventado. Trecho que e o valor de OUTRA caixa
                    # do mesmo registro nao entra.
                    k = re.sub(r"[^A-Z0-9]", "", trecho.upper())
                    outros = {re.sub(r"[^A-Z0-9]", "", (o.valor or "").upper())
                              for n2, o in res.decisoes.items() if n2 != nome and o.valor}
                    # ... ou que o proprio cadastro escreveu como valor de OUTRO
                    # rotulo ('MODELO:AHLSTAR A22 80'), mesmo com a caixa vazia
                    outros |= {re.sub(r"[^A-Z0-9]", "", v.upper())
                               for rot, v in pares(estruturado) if rot != nome}
                    if k and any(k in o or o in k for o in outros if len(o) >= 4):
                        self.contador["perdidos_recusados"] += 1
                        d.motivo = (f"{d.motivo}; a deteccao apontou {trecho!r}, que e o "
                                    f"valor de outra caixa do registro: recusado")
                        continue
                    perdidos[nome] = trecho
                elif veredito == "PRESENTE_FORA_DO_PADRAO":
                    d.estado = "GENERICO"
                    d.fonte = "llm_deteccao"          # quem julgou que o dado existe
                    d.evidencia = trecho
                    d.motivo = (f"{d.motivo}; o texto informa {trecho!r}, que nao decide "
                                f"um valor da lista do PDM")
                    self.contador["genericos_marcados"] += 1
            if perdidos:
                res = self.arbitro.incorporar_llm(
                    classe, res, perdidos, evidencias=dict(perdidos), aprendizado=None)
                for nome in perdidos:
                    d = res.decisoes.get(nome)
                    if d is not None and d.fonte == "llm":
                        d.fonte = "llm_deteccao"      # proveniencia: veio da deteccao
                self.contador["perdidos_recuperados"] += len(perdidos)
        if not escalado and res.escalar and self.llm is not None:
            foco = [d.atributo for d in res.em_estado("CONFLITO", "AMBIGUO", "INCERTO", "INVALIDO")]
            resposta = self.llm.desempatar(classe, texto, foco, res.motivos_escalada)
            if resposta.valores:
                res = self.arbitro.incorporar_llm(
                    classe, res, resposta.valores,
                    evidencias=resposta.evidencias, aprendizado=self.aprendizado,
                    codigo=codigo)
                escalado = True
                self.contador["escalados"] += 1
            elif resposta.erro:
                # Falha do LLM nao pode passar por "rodou e nao achou nada": com o
                # modelo errado configurado, 100% das chamadas falham e o relatorio
                # mostraria resultado normal. Conta e registra no motivo do registro.
                self.contador["falhas_llm"] += 1
                self.ultimo_erro_llm = resposta.erro
                res.motivos_escalada.append(f"LLM indisponivel: {resposta.erro[:120]}")

        return self._montar(registro, classe, sujeito, res, escalado, texto, original, codigo, grupo)

    # Colunas proprias do ERP que alimentam caixas de atributo homonimas.
    # Sao fonte legitima e, nas classes de referencia do fabricante, costumam ser
    # a UNICA fonte: REFERENCIA FABRICANTE e caixa de formato livre, que a regra
    # nao consegue recortar do texto.
    COLUNA_PARA_CAIXA = {
        "FABRICANTE": "FABRICANTE",
        "REFERENCIA_FABRICANTE": "REFERENCIA FABRICANTE",
    }

    def _preencher_das_colunas(self, registro, classe, res) -> None:
        """Completa caixa vazia com o valor da coluna do ERP, se houver.

        Sem isso a chave de identidade fecha pela coluna enquanto a descricao
        imprime <PENDENTE> para o mesmo atributo - duas verdades diferentes para
        o mesmo registro. O valor passa pelo validador como qualquer outro.
        """
        for coluna, nome in self.COLUNA_PARA_CAIXA.items():
            bruto = str(registro.get(coluna, "") or "").strip()
            d = res.decisoes.get(nome)
            if not bruto or d is None or d.valor:
                continue
            atributo = next((a for a in classe.atributos if a.nome == nome), None)
            if atributo is None:
                continue
            v = self.validador.valor(atributo, bruto)
            if not v.ok:
                d.motivo = f"{d.motivo}; coluna {coluna}={bruto!r} recusada: {v.motivo}"
                continue
            d.valor, d.fonte, d.estado = v.valor, "coluna_erp", "ACEITO"
            d.confianca = 0.95
            d.evidencia = f"coluna {coluna}"
            d.motivo = f"preenchido pela coluna {coluna} do cadastro"

    def _aprender_do_bert(self, classe, res, codigo: str = "") -> None:
        """Guarda o que o BERT recortou e o validador aprovou.

        So caixa TEXTUAL (vocabulario fechado): em caixa NUMERICA o par
        termo->valor nao generaliza, porque a atribuicao e posicional.
        """
        if self.aprendizado is None:
            return
        por_nome = {a.nome: a for a in classe.atributos}
        for d in res.decisoes.values():
            if d.fonte not in ("bert", "bert_desempata") or not d.valor or not d.evidencia:
                continue
            atributo = por_nome.get(d.atributo)
            if atributo is not None and atributo.fechado:
                self.aprendizado.aprender(atributo, d.evidencia, d.valor,
                                          "bert", classe.id_pdm, codigos=codigo)

    def _montar(self, registro, classe, sujeito, res, escalado, texto, original, codigo, grupo):
        self._aprender_do_bert(classe, res, codigo)
        self._preencher_das_colunas(registro, classe, res)
        # Recontar e necessario porque _preencher_das_colunas acabou de encher
        # caixa (FABRICANTE, REFERENCIA FABRICANTE) depois de o arbitro medir.
        # Mas o denominador tem de ser o do arbitro, nao classe.obrigatorios:
        # aquele filtra quando=='sempre' e devolvia 100% de completude a um
        # disjuntor que estava sem CORRENTE NOMINAL, CURVA e CAPACIDADE
        # INTERRUPCAO - as tres obrigatorias, as tres vazias, e a chave de
        # identidade (que ja contava os condicionais) sem fechar. A completude
        # dizia 'completo' e o estado dizia PENDENTE, para o mesmo registro.
        obrigatorios = [n for n in res.obrigatorios if n in res.decisoes]
        if obrigatorios:
            res.completude = sum(1 for n in obrigatorios if res.decisoes[n].valor) / len(obrigatorios)

        valores = res.valores
        fabricante = valores.get("FABRICANTE") or str(registro.get("FABRICANTE", "") or "")
        referencia = valores.get("REFERENCIA FABRICANTE") or str(
            registro.get("REFERENCIA_FABRICANTE", "") or "")

        descricao = self.validador.descricao(classe, sujeito.substantivo, valores,
                                             fabricante, referencia)
        un = self.validador.unidade(str(registro.get("UNIDADE_MEDIDA", "") or ""), classe)
        ncm = self.validador.ncm(registro.get("NCM", ""), classe)
        chave = self.validador.chave_identidade(classe, sujeito.substantivo, valores,
                                                fabricante, referencia)

        pendentes = [d.atributo for d in res.em_estado("PENDENTE")]
        conflitos = [d.atributo for d in res.em_estado(*ESTADOS_REVISAO)]
        # INVALIDO vira pendencia, nao revisao: a caixa esta vazia de todo jeito.
        # Mas so pesa quando o atributo e OBRIGATORIO para este registro. Caixa
        # opcional vazia e normal (PDM110 MATERIAL e 'quando informado pelo
        # fabricante'); contar o INVALIDO dela prendia em PENDENTE 3.180
        # registros com a chave fechada e todos os obrigatorios cheios, quase
        # todos por um 'FABRICANTE' que o BERT recortou como MATERIAL.
        exigidos = set(res.obrigatorios)
        invalidos = [d.atributo for d in res.em_estado("INVALIDO") if d.atributo in exigidos]
        # GENERICO conta como INVALIDO para o estado: o dado esta no texto e nao
        # foi padronizado (ver o bloco de deteccoes em processar)
        invalidos += [d.atributo for d in res.em_estado("GENERICO") if d.atributo in exigidos]

        if conflitos:
            estado = REVISAO
        elif invalidos:
            estado = PENDENTE          # ha dado no texto, mas fora do padrao do PDM
        else:
            estado = SANEADO           # mesmo com obrigatorio ausente do texto
        # Segundo eixo: todo obrigatorio cheio e a identidade provada pela chave
        completo = not pendentes and not invalidos and chave is not None
        decidido_por_llm = []
        for d in res.decisoes.values():
            if not d.valor:
                continue
            if d.fonte in ("llm", "llm_deteccao"):
                decidido_por_llm.append(f"{d.atributo}={d.fonte}")
            elif d.fonte == "aprendido" and self.aprendizado is not None:
                origem = self.aprendizado.origem(d.atributo, d.valor, texto)
                if origem and origem.startswith("llm"):
                    decidido_por_llm.append(f"{d.atributo}=dicionario_llm")
        pendente_por_llm = [d.atributo for d in res.em_estado("GENERICO")]
        self.contador[estado] += 1
        self.contador["completos"] += int(completo)

        return RegistroSaneado(
            codigo=codigo, estado=estado, id_pdm=classe.id_pdm,
            substantivo=sujeito.substantivo, qualificador=sujeito.qualificador, grupo=grupo,
            confianca_sujeito=sujeito.confianca, empate_sujeito=sujeito.empate,
            grupo_corrigido=sujeito.grupo_corrigido,
            descricao_original=original, descricao_pdm=descricao,
            descricao_curta=self.validador.descricao_curta(descricao),
            unidade_original=str(registro.get("UNIDADE_MEDIDA", "") or ""),
            unidade_pdm=un.valor, unidade_motivo=un.motivo,
            ncm_original=str(registro.get("NCM", "") or ""),
            ncm_pdm=ncm.valor, ncm_motivo=ncm.motivo,
            chave_identidade=chave, completude=res.completude, completo=completo,
            decidido_por_llm=decidido_por_llm, pendente_por_llm=pendente_por_llm,
            discordancia=res.discordancia,
            escalado=escalado, motivos_escalada=res.motivos_escalada,
            pendentes=sorted(set(pendentes) | set(invalidos)),
            conflitos=conflitos, decisoes=res.decisoes,
        )

    # ------------------------------------------------------------- lote

    def processar_lote(self, registros: list[dict], log_cada: int = 2000) -> list[RegistroSaneado]:
        out = []
        for i, r in enumerate(registros, 1):
            out.append(self.processar(r))
            if log_cada and i % log_cada == 0:
                c = self.contador
                print(f"  {i}/{len(registros)}  saneado={c[SANEADO]} pendente={c[PENDENTE]} "
                      f"revisao={c[REVISAO]} fora={c[FORA_DO_PDM]} escalados={c['escalados']}",
                      flush=True)
        return out
